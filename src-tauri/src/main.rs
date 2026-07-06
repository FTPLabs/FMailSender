// FMailSender Tauri shell v7.1.0
//
// АРХИТЕКТУРА v7.1.0: Embedded CPython (официальный python.exe от PSF)
// ======================================================================
//
// ПОЧЕМУ PyInstaller не работает с AV:
//   PyInstaller bootloader (~50KB C/Rust) намеренно занесён в базы AV-вендоров,
//   потому что ~80% Python-малвари распространяется через PyInstaller.
//   Смена режима (onefile→onedir) не помогает: AV ловит сам bootloader, а не файлы.
//
// РЕШЕНИЕ v7.1.0 — Embedded CPython:
//   Используем официальный python-3.12.10-embed-amd64.zip от Python Software Foundation.
//   python.exe ЦИФРОВО ПОДПИСАН Microsoft/PSF — AV физически не может его заблокировать.
//   PyInstaller bootloader полностью исключён из дистрибутива.
//
// Структура после первого запуска:
//   %LOCALAPPDATA%\FMailSender\
//     pyenv\                   ← Embedded CPython (python.exe + stdlib)
//       python.exe             ← ПОДПИСАННЫЙ PSF, AV не трогает
//       python312.dll          ← ПОДПИСАННЫЙ Microsoft
//       Lib\site-packages\     ← fastapi, uvicorn, aiosmtplib, ...
//     app\                     ← Python-код приложения
//       main.py                ← точка входа
//       core\                  ← FastAPI логика
//       templates\             ← HTML шаблоны
//     .env_hash                ← FNV64 хеш ZIP для инкрементных обновлений
//
// CI (release.yml):
//   1. Скачивает python-3.12.10-embed-amd64.zip (официальный, подписанный)
//   2. pip install -r requirements.txt --target pyenv/Lib/site-packages/
//   3. Копирует core/, main.py, templates/, data/ → app/
//   4. Zip pyenv/ + app/ → src-tauri/binaries/fmail-core.zip
//   5. cargo tauri build (include_bytes! встраивает ZIP)
//
// ЗАПРЕЩЕНО: PyInstaller, Nuitka, cx_Freeze, любые Python-упаковщики с bootloader.
// ЗАПРЕЩЕНО: NSIS, MSI, установщики. Только portable EXE.
//
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Serialize;
use std::io::Write;
use std::net::{TcpStream, ToSocketAddrs};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};
use tauri::{AppHandle, Emitter, Manager};

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;
#[cfg(target_os = "windows")]
const CREATE_NO_WINDOW: u32 = 0x08000000;

const CORE_PORT:          u16  = 7531;
const CORE_HOST_PRIMARY:  &str = "127.0.0.1";
const CORE_HOST_FALLBACK: &str = "localhost";

// Embedded CPython запускает uvicorn за 3-8 сек (нет никакой распаковки при старте)
const PORT_WAIT_SECS:      u64 = 90;
const SPAWN_MAX_RETRIES:   u32 = 3;
const SPAWN_ALIVE_CHECK_S: u64 = 6;
const SPAWN_RETRY_DELAY_S: u64 = 2;

const STARTUP_LOG: &str = "startup.log";

/// Встроенный ZIP содержит:
///   pyenv/  — официальный Embedded CPython 3.12.10 + зависимости
///   app/    — Python-код (core/, main.py, templates/)
///
/// python.exe в pyenv/ цифрово подписан Python Software Foundation.
/// AV не может заблокировать подписанный системный бинарь.
/// ZIP распаковывается ОДИН РАЗ при первом запуске.
/// При повторных запусках: FNV64 хеш совпадает → немедленный старт.
#[cfg(target_os = "windows")]
static CORE_ZIP: &[u8] = include_bytes!("../binaries/fmail-core.zip");

// ── Event payload ─────────────────────────────────────────────────────────────

#[derive(Clone, Serialize)]
struct CoreStatus {
    stage:   &'static str,
    message: String,
    attempt: u32,
}

fn emit(handle: &AppHandle, stage: &'static str, msg: impl Into<String>, attempt: u32) {
    let _ = handle.emit("core://status", CoreStatus {
        stage,
        message: msg.into(),
        attempt,
    });
}

// ── Network helpers ───────────────────────────────────────────────────────────

fn try_connect(host: &str, port: u16) -> bool {
    let addr_str = format!("{}:{}", host, port);
    let mut addrs = match addr_str.to_socket_addrs() {
        Ok(a) => a,
        Err(_) => return false,
    };
    let addr = match addrs.next() {
        Some(a) => a,
        None => return false,
    };
    TcpStream::connect_timeout(&addr, Duration::from_millis(500)).is_ok()
}

fn port_open() -> bool {
    try_connect(CORE_HOST_PRIMARY, CORE_PORT)
        || try_connect(CORE_HOST_FALLBACK, CORE_PORT)
}

fn wait_for_port(timeout: Duration, handle: &AppHandle, child_pid: Option<u32>) -> bool {
    let deadline       = Instant::now() + timeout;
    let mut last_ev    = Instant::now();
    let mut last_pid_c = Instant::now();

    while Instant::now() < deadline {
        if port_open() {
            return true;
        }
        thread::sleep(Duration::from_millis(300));

        if let Some(pid) = child_pid {
            if last_pid_c.elapsed().as_secs() >= 10 {
                last_pid_c = Instant::now();
                if !is_process_alive(pid) {
                    let log_hint = read_startup_log()
                        .and_then(|l| l.lines().filter(|x| !x.trim().is_empty())
                                       .last().map(|s| s.to_string()))
                        .unwrap_or_default();
                    emit(handle, "killed",
                        format!("Python процесс упал неожиданно.{}",
                            if log_hint.is_empty() { String::new() }
                            else { format!(" Лог: {}", log_hint) }
                        ), 0);
                    return false;
                }
            }
        }

        if last_ev.elapsed().as_secs() >= 4 {
            last_ev = Instant::now();
            let rem = deadline.saturating_duration_since(Instant::now()).as_secs();
            let ela = timeout.as_secs().saturating_sub(rem);
            emit(handle, "av_wait",
                format!("Запуск FastAPI сервера... {}с (осталось ~{}с)", ela, rem),
                0);
        }
    }
    false
}

fn is_process_alive(pid: u32) -> bool {
    #[cfg(target_os = "windows")]
    {
        let out = Command::new("tasklist")
            .args(["/FI", &format!("PID eq {}", pid), "/NH", "/FO", "CSV"])
            .creation_flags(CREATE_NO_WINDOW)
            .output();
        if let Ok(o) = out {
            return String::from_utf8_lossy(&o.stdout).contains(&pid.to_string());
        }
        true
    }
    #[cfg(not(target_os = "windows"))]
    { let _ = pid; true }
}

// ── Директории ────────────────────────────────────────────────────────────────

fn get_fmailsender_dir() -> Option<PathBuf> {
    let app_data = std::env::var("LOCALAPPDATA").ok()?;
    let dir = PathBuf::from(app_data).join("FMailSender");
    std::fs::create_dir_all(&dir).ok()?;
    Some(dir)
}

fn get_python_exe() -> Option<PathBuf> {
    let base = get_fmailsender_dir()?;
    Some(base.join("pyenv").join("python.exe"))
}

fn get_main_py() -> Option<PathBuf> {
    let base = get_fmailsender_dir()?;
    Some(base.join("app").join("main.py"))
}

fn get_hash_file_path() -> Option<PathBuf> {
    let base = get_fmailsender_dir()?;
    Some(base.join(".env_hash"))
}

fn get_startup_log_path() -> Option<PathBuf> {
    let base = get_fmailsender_dir()?;
    Some(base.join(STARTUP_LOG))
}

fn read_startup_log() -> Option<String> {
    let path = get_startup_log_path()?;
    if path.exists() { std::fs::read_to_string(path).ok() } else { None }
}

fn fnv64(data: &[u8]) -> u64 {
    let mut h: u64 = 14695981039346656037u64;
    for &b in data {
        h ^= b as u64;
        h = h.wrapping_mul(1099511628211u64);
    }
    h
}

// ── Извлечение Embedded CPython ───────────────────────────────────────────────

/// Распаковывает fmail-core.zip → LOCALAPPDATA\FMailSender\
/// ZIP содержит pyenv/ (Embedded CPython + deps) и app/ (Python-код).
/// Пропускает если хеш ZIP не изменился — инкрементные обновления бесплатны.
fn extract_core(handle: &AppHandle) -> Option<()> {
    let base       = get_fmailsender_dir()?;
    let python_exe = get_python_exe()?;
    let hash_file  = get_hash_file_path()?;

    #[cfg(target_os = "windows")]
    {
        let zip_hash  = fnv64(CORE_ZIP);
        let hash_str  = format!("{:016x}", zip_hash);

        // Быстрый путь: уже установлено с тем же хешом
        let already_ok = python_exe.exists() && {
            std::fs::read_to_string(&hash_file)
                .map(|s| s.trim() == hash_str)
                .unwrap_or(false)
        };

        if already_ok {
            emit(handle, "extracting", "Python среда готова", 0);
            return Some(());
        }

        // Первый запуск или обновление
        emit(handle, "extracting",
             "Первый запуск: установка Python среды в %LOCALAPPDATA%\\FMailSender\\ \
              (30–60 сек, только один раз)...", 0);

        // Записываем ZIP на диск
        let zip_path = base.join("fmail-core-install.zip");
        match std::fs::File::create(&zip_path) {
            Ok(mut f) => {
                if f.write_all(CORE_ZIP).is_err() || f.flush().is_err() {
                    emit(handle, "failed", "Ошибка записи установочного файла.", 0);
                    return None;
                }
            }
            Err(e) => {
                emit(handle, "failed",
                     format!("Нет доступа к %LOCALAPPDATA%\\FMailSender\\: {}.", e), 0);
                return None;
            }
        }

        // Удаляем старые версии pyenv и app
        for dir_name in &["pyenv", "app"] {
            let d = base.join(dir_name);
            if d.exists() { let _ = std::fs::remove_dir_all(&d); }
        }

        emit(handle, "extracting", "Распаковка Python среды (~30 сек)...", 0);

        let base_str = base.to_string_lossy();
        let zip_str  = zip_path.to_string_lossy();
        let ps_cmd   = format!(
            "Expand-Archive -LiteralPath '{zip}' -DestinationPath '{dest}' -Force; \
             Remove-Item -LiteralPath '{zip}' -Force -ErrorAction SilentlyContinue",
            zip  = zip_str.replace("'", "''"),
            dest = base_str.replace("'", "''"),
        );

        let status = Command::new("powershell")
            .args(["-NoProfile", "-NonInteractive", "-Command", &ps_cmd])
            .creation_flags(CREATE_NO_WINDOW)
            .status();

        let _ = std::fs::remove_file(&zip_path);

        match status {
            Ok(s) if s.success() => {}
            Ok(s) => {
                emit(handle, "failed",
                     format!("Ошибка распаковки (код {}). \
                              Проверьте свободное место (~200 МБ).",
                              s.code().unwrap_or(-1)), 0);
                return None;
            }
            Err(e) => {
                emit(handle, "failed",
                     format!("PowerShell недоступен: {}.", e), 0);
                return None;
            }
        }

        if !python_exe.exists() {
            emit(handle, "failed",
                 "python.exe не найден после распаковки. \
                  Возможно, ZIP повреждён или диск заполнен.", 0);
            return None;
        }

        // Настраиваем pth-файл для site-packages в embedded Python
        // Embedded CPython по умолчанию не загружает site-packages из Lib/
        let pth_path = base.join("pyenv").join("python312._pth");
        if pth_path.exists() {
            // Добавляем Lib/site-packages в путь поиска
            let existing = std::fs::read_to_string(&pth_path).unwrap_or_default();
            if !existing.contains("Lib\\site-packages") {
                let updated = format!("{}\nLib\\site-packages\nimport site\n", existing.trim_end());
                let _ = std::fs::write(&pth_path, updated);
            }
        }

        let _ = std::fs::write(&hash_file, &hash_str);
        emit(handle, "extracting", "Python среда установлена. Запуск...", 0);
    }

    #[cfg(not(target_os = "windows"))]
    { return None; }

    Some(())
}

// ── Управление процессом ──────────────────────────────────────────────────────

fn kill_existing_core() {
    #[cfg(target_os = "windows")]
    {
        let _ = Command::new("powershell")
            .args([
                "-NoProfile", "-NonInteractive", "-Command",
                &format!(
                    "Get-NetTCPConnection -LocalPort {port} -State Listen \
                     -ErrorAction SilentlyContinue | \
                     ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force \
                     -ErrorAction SilentlyContinue }}",
                    port = CORE_PORT
                ),
            ])
            .creation_flags(CREATE_NO_WINDOW)
            .output();
        thread::sleep(Duration::from_millis(600));
    }
}

fn spawn_core(log_path: &Option<PathBuf>) -> Option<Child> {
    let python_exe = get_python_exe()?;
    let main_py    = get_main_py()?;

    if !python_exe.exists() || !main_py.exists() {
        return None;
    }

    // Рабочая директория = app/ (где лежат core/, templates/)
    let app_dir = main_py.parent()?;

    let mut cmd = Command::new(&python_exe);
    cmd.arg(&main_py);
    cmd.current_dir(app_dir);

    // Embedded CPython: убеждаемся что site-packages загружается
    // PYTHONPATH указывает на Lib/site-packages относительно pyenv/
    if let Some(pyenv_dir) = python_exe.parent() {
        let site_packages = pyenv_dir.join("Lib").join("site-packages");
        if site_packages.exists() {
            cmd.env("PYTHONPATH", site_packages.to_string_lossy().as_ref());
        }
    }

    // Лог файл для диагностики
    if let Some(ref lp) = log_path {
        if let Ok(log_file) = std::fs::File::create(lp) {
            let log_file2 = log_file.try_clone().ok();
            cmd.stdout(log_file);
            if let Some(lf2) = log_file2 {
                cmd.stderr(lf2);
            } else {
                cmd.stderr(Stdio::null());
            }
        } else {
            cmd.stdout(Stdio::null()).stderr(Stdio::null());
        }
    } else {
        cmd.stdout(Stdio::null()).stderr(Stdio::null());
    }

    #[cfg(target_os = "windows")]
    cmd.creation_flags(CREATE_NO_WINDOW);

    cmd.spawn().ok()
}

fn spawn_with_retry(log_path: &Option<PathBuf>, handle: &AppHandle) -> Option<Child> {
    for attempt in 1..=SPAWN_MAX_RETRIES {
        emit(handle, "spawning",
             format!("Запуск Python сервера (попытка {}/{})...", attempt, SPAWN_MAX_RETRIES),
             attempt);

        match spawn_core(log_path) {
            Some(mut child) => {
                thread::sleep(Duration::from_secs(SPAWN_ALIVE_CHECK_S));
                match child.try_wait() {
                    Ok(None) => return Some(child),
                    Ok(Some(status)) => {
                        let code = status.code().map(|c| c.to_string()).unwrap_or("?".into());
                        let log_hint = read_startup_log()
                            .and_then(|l| l.lines().filter(|x| !x.trim().is_empty())
                                           .last().map(|s| s.to_string()))
                            .unwrap_or_default();
                        let hint = if log_hint.is_empty() { String::new() }
                                   else { format!(" | {}", &log_hint[..log_hint.len().min(200)]) };
                        emit(handle, "killed",
                             format!("Python завершился (код {}){}{}",
                                 code, hint,
                                 if attempt < SPAWN_MAX_RETRIES { ", повтор..." } else { "" }),
                             attempt);
                    }
                    Err(e) => emit(handle, "killed", format!("Ошибка проверки: {}", e), attempt),
                }
            }
            None => {
                emit(handle, "killed",
                     format!("Не удалось запустить python.exe (попытка {})", attempt),
                     attempt);
            }
        }
        if attempt < SPAWN_MAX_RETRIES {
            thread::sleep(Duration::from_secs(SPAWN_RETRY_DELAY_S));
        }
    }
    None
}

// ── Tauri state ───────────────────────────────────────────────────────────────

type CoreHandle = Arc<Mutex<Option<Child>>>;

// ── Tauri commands ────────────────────────────────────────────────────────────

#[tauri::command]
fn get_core_url() -> String {
    format!("http://{}:{}", CORE_HOST_PRIMARY, CORE_PORT)
}

#[tauri::command]
fn restart_core(handle: AppHandle, state: tauri::State<'_, CoreHandle>) {
    let state = Arc::clone(&state);
    thread::spawn(move || {
        {
            let mut lock = state.lock().unwrap();
            if let Some(mut child) = lock.take() { let _ = child.kill(); }
        }
        kill_existing_core();

        if extract_core(&handle).is_none() {
            return; // extract_core уже отправил emit("failed", ...)
        }

        let log_path = get_startup_log_path();
        let Some(child) = spawn_with_retry(&log_path, &handle) else {
            let log_hint = read_startup_log()
                .and_then(|l| l.lines().filter(|x| !x.trim().is_empty()).last().map(|s| s.to_string()))
                .unwrap_or_default();
            emit(&handle, "failed",
                 format!("Python сервер не запускается.{}",
                     if log_hint.is_empty() { String::new() } else { format!(" Лог: {}", log_hint) }),
                 0);
            return;
        };

        let pid = child.id();
        *state.lock().unwrap() = Some(child);

        if wait_for_port(Duration::from_secs(PORT_WAIT_SECS), &handle, Some(pid)) {
            emit(&handle, "ready", "Ядро готово к работе", 0);
        } else {
            let log_hint = read_startup_log()
                .and_then(|l| l.lines().filter(|x| !x.trim().is_empty()).last().map(|s| s.to_string()))
                .unwrap_or_default();
            emit(&handle, "failed",
                 format!("Python сервер не ответил.{}",
                     if log_hint.is_empty() { String::new() } else { format!(" Лог: {}", log_hint) }),
                 0);
        }
    });
}

// ── Entry point ───────────────────────────────────────────────────────────────

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let core_handle: CoreHandle = Arc::new(Mutex::new(None));

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .manage(Arc::clone(&core_handle))
        .setup(move |app| {
            let handle = app.handle().clone();
            let state  = Arc::clone(&core_handle);

            thread::spawn(move || {
                // ── 1. Убиваем старые процессы ─────────────────────────────────
                kill_existing_core();

                // ── 2. Извлекаем/проверяем среду ───────────────────────────────
                // Первый запуск: распаковывает ZIP (pyenv/ + app/) в LOCALAPPDATA
                // Повторные: хеш совпадает → пропускает, стартует мгновенно
                if extract_core(&handle).is_none() {
                    return;
                }

                // ── 3. Запускаем python.exe main.py ───────────────────────────
                let log_path = get_startup_log_path();
                let Some(child) = spawn_with_retry(&log_path, &handle) else {
                    let log_body  = read_startup_log().unwrap_or_default();
                    let last_line = log_body.lines()
                        .filter(|l| !l.trim().is_empty())
                        .last().unwrap_or("").to_string();

                    emit(&handle, "failed",
                         format!(
                             "Python сервер не запускается после {} попыток.\n\
                              Путь: %LOCALAPPDATA%\\FMailSender\\pyenv\\python.exe\n\
                              Лог:  %LOCALAPPDATA%\\FMailSender\\startup.log{}",
                             SPAWN_MAX_RETRIES,
                             if last_line.is_empty() { String::new() }
                             else { format!("\n\nОшибка: {}", last_line) }
                         ), 0);
                    return;
                };

                let pid = child.id();
                *state.lock().unwrap() = Some(child);

                emit(&handle, "running", "FastAPI сервер запускается...", 0);

                // ── 4. Ждём открытия порта ─────────────────────────────────────
                if !wait_for_port(Duration::from_secs(PORT_WAIT_SECS), &handle, Some(pid)) {
                    let log_body  = read_startup_log().unwrap_or_default();
                    let last_line = log_body.lines()
                        .filter(|l| !l.trim().is_empty())
                        .last().unwrap_or("").to_string();

                    emit(&handle, "failed",
                         format!(
                             "Сервер не ответил за {} сек.\n\
                              • Порт {} занят другим приложением\n\
                              • Нехватка памяти (требуется 256+ МБ)\n\
                              • Проверьте лог: %LOCALAPPDATA%\\FMailSender\\startup.log{}",
                             PORT_WAIT_SECS, CORE_PORT,
                             if last_line.is_empty() { String::new() }
                             else { format!("\n\nЛог: {}", last_line) }
                         ), 0);
                    return;
                }

                // ── 5. Готово ──────────────────────────────────────────────────
                emit(&handle, "ready", "FMailSender готов к работе", 0);
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![restart_core, get_core_url])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

fn main() {
    run()
}
