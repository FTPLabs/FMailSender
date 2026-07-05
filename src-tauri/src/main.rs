// FMailSender Tauri shell v7.0.3
//
// АРХИТЕКТУРА v7.0.3: PyInstaller ONEDIR — полное устранение AV-проблем
// ======================================================================
//
// ПРОБЛЕМА v7.0.1-7.0.2 (onefile):
//   PyInstaller onefile при КАЖДОМ запуске распаковывает Python-среду в temp.
//   AV перехватывает запись исполняемых файлов в temp → блокирует / убивает процесс.
//   Даже redirect TEMP→LOCALAPPDATA не помогает: AV ловит сам момент записи.
//
// РЕШЕНИЕ v7.0.3 (onedir):
//   CI собирает fmail-core/ (директория с DLL/pyd/exe), зипует → fmail-core.zip.
//   Tauri встраивает ZIP через include_bytes! (один раз при сборке EXE).
//   При ПЕРВОМ запуске: Tauri распаковывает ZIP в LOCALAPPDATA\FMailSender\
//   через PowerShell Expand-Archive (занимает 5-30 сек, только один раз).
//   При ПОСЛЕДУЮЩИХ запусках: хеш ZIP совпадает → распаковка пропускается,
//   fmail-core.exe стартует немедленно из уже существующих файлов.
//   НИКАКОЙ РАСПАКОВКИ ПРИ СТАРТЕ → AV не мешает.
//
// Расположение файлов после установки:
//   %LOCALAPPDATA%\FMailSender\fmail-core\fmail-core.exe  ← запускаем это
//   %LOCALAPPDATA%\FMailSender\fmail-core\_internal\      ← DLLs, .pyd
//   %LOCALAPPDATA%\FMailSender\.core_hash                 ← хеш ZIP для кеша
//
// Требования к CI (release.yml):
//   1. pyinstaller fmail-core.spec --noconfirm → dist/fmail-core/ (ONEDIR)
//   2. Compress-Archive dist/fmail-core → src-tauri/binaries/fmail-core.zip
//   3. cargo tauri build (встраивает fmail-core.zip через include_bytes!)
//
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

const CORE_PORT:         u16  = 7531;
const CORE_HOST_PRIMARY: &str = "127.0.0.1";
const CORE_HOST_FALLBACK: &str = "localhost";

// 120 сек: достаточно для uvicorn startup без распаковки.
// onedir не извлекает ничего при старте → порт открывается за 3-15 сек.
const PORT_WAIT_SECS:      u64 = 120;
const SPAWN_MAX_RETRIES:   u32 = 3;
const SPAWN_ALIVE_CHECK_S: u64 = 8;   // Время на старт uvicorn
const SPAWN_RETRY_DELAY_S: u64 = 3;

const STARTUP_LOG: &str = "startup.log";

/// Встроенный ZIP архив Python onedir дистрибутива.
/// Содержимое: папка fmail-core/ с fmail-core.exe + _internal/ (DLLs, .pyd).
/// Распаковывается один раз при первом запуске в LOCALAPPDATA\FMailSender\.
/// AV не мешает: файлы не пишутся при каждом старте — только один раз.
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

/// Ждёт открытия порта. Обновляет UI каждые 5 сек.
/// Проверяет живость процесса каждые 10 сек — если умер, немедленно возвращает false.
fn wait_for_port(timeout: Duration, handle: &AppHandle, child_pid: Option<u32>) -> bool {
    let deadline       = Instant::now() + timeout;
    let mut last_ev    = Instant::now();
    let mut last_pid_c = Instant::now();

    while Instant::now() < deadline {
        if port_open() {
            return true;
        }
        thread::sleep(Duration::from_millis(300));

        // Проверяем живость процесса каждые 10 сек
        if let Some(pid) = child_pid {
            if last_pid_c.elapsed().as_secs() >= 10 {
                last_pid_c = Instant::now();
                if !is_process_alive(pid) {
                    let log_hint = read_startup_log()
                        .and_then(|l| l.lines().filter(|x| !x.trim().is_empty())
                                       .last().map(|s| s.to_string()))
                        .unwrap_or_default();
                    emit(handle, "killed",
                        format!("Ядро упало неожиданно.{}",
                            if log_hint.is_empty() { String::new() }
                            else { format!(" Лог: {}", log_hint) }
                        ), 0);
                    return false;
                }
            }
        }

        if last_ev.elapsed().as_secs() >= 5 {
            last_ev = Instant::now();
            let rem = deadline.saturating_duration_since(Instant::now()).as_secs();
            let ela = timeout.as_secs().saturating_sub(rem);
            emit(handle, "av_wait",
                format!("Ожидание FastAPI сервера... {}с (осталось ~{}с)", ela, rem),
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

fn get_core_exe_path() -> Option<PathBuf> {
    let base = get_fmailsender_dir()?;
    Some(base.join("fmail-core").join("fmail-core.exe"))
}

fn get_hash_file_path() -> Option<PathBuf> {
    let base = get_fmailsender_dir()?;
    Some(base.join(".core_hash"))
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

// ── Извлечение и проверка ядра ────────────────────────────────────────────────

/// Распаковывает fmail-core.zip → LOCALAPPDATA\FMailSender\fmail-core\
/// Только если хеш изменился (или первый запуск).
/// Использует PowerShell Expand-Archive — не требует внешних зависимостей.
fn extract_core(handle: &AppHandle) -> Option<PathBuf> {
    let base     = get_fmailsender_dir()?;
    let core_exe = get_core_exe_path()?;
    let hash_file = get_hash_file_path()?;

    #[cfg(target_os = "windows")]
    {
        let zip_hash  = fnv64(CORE_ZIP);
        let hash_str  = format!("{:016x}", zip_hash);

        // Проверяем: уже распакован с тем же хешом?
        let already_ok = core_exe.exists() && {
            std::fs::read_to_string(&hash_file)
                .map(|s| s.trim() == hash_str)
                .unwrap_or(false)
        };

        if already_ok {
            // Быстрый путь — всё уже на месте
            emit(handle, "extracting", "Ядро готово", 0);
            return Some(core_exe);
        }

        // Первый запуск или обновление версии
        emit(handle, "extracting",
             "Первый запуск: установка Python ядра в %LOCALAPPDATA%\\FMailSender\\ \
              (30–60 сек, только один раз)...", 0);

        // Записываем ZIP во временный файл
        let zip_path = base.join("fmail-core-install.zip");
        {
            match std::fs::File::create(&zip_path) {
                Ok(mut f) => {
                    if f.write_all(CORE_ZIP).is_err() || f.flush().is_err() {
                        emit(handle, "failed", "Ошибка записи установочного файла.", 0);
                        return None;
                    }
                }
                Err(e) => {
                    emit(handle, "failed",
                         format!("Нет доступа к %LOCALAPPDATA%\\FMailSender\\: {}. \
                                  Запустите от имени администратора.", e), 0);
                    return None;
                }
            }
        }

        // Удаляем старую версию ядра (если есть)
        let core_dir = base.join("fmail-core");
        if core_dir.exists() {
            emit(handle, "extracting", "Обновление ядра до новой версии...", 0);
            if std::fs::remove_dir_all(&core_dir).is_err() {
                // Если не удалось удалить (заблокирован процесс) — пробуем переименовать
                let _ = std::fs::rename(&core_dir, base.join("fmail-core-old"));
            }
        }

        emit(handle, "extracting", "Распаковка Python ядра (это займёт ~30 сек)...", 0);

        // Expand-Archive через PowerShell
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

        // Очищаем временный zip в любом случае
        let _ = std::fs::remove_file(&zip_path);

        match status {
            Ok(s) if s.success() => {}
            Ok(s) => {
                emit(handle, "failed",
                     format!("Ошибка распаковки (код {}). \
                              Проверьте свободное место на диске (нужно ~150 МБ).",
                              s.code().unwrap_or(-1)), 0);
                return None;
            }
            Err(e) => {
                emit(handle, "failed",
                     format!("PowerShell недоступен: {}. \
                              Убедитесь, что PowerShell не заблокирован.", e), 0);
                return None;
            }
        }

        if !core_exe.exists() {
            emit(handle, "failed",
                 "Распаковка завершена, но fmail-core\\fmail-core.exe не найден. \
                  Возможно, антивирус удалил файл — добавьте папку \
                  %LOCALAPPDATA%\\FMailSender в исключения.", 0);
            return None;
        }

        // Сохраняем хеш — следующий запуск пропустит распаковку
        let _ = std::fs::write(&hash_file, &hash_str);
        emit(handle, "extracting", "Python ядро установлено. Запуск...", 0);
    }

    #[cfg(not(target_os = "windows"))]
    { return None; }

    Some(core_exe)
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
        thread::sleep(Duration::from_millis(800));
    }
}

fn spawn_core(exe: &PathBuf, log_path: &Option<PathBuf>) -> Option<Child> {
    let mut cmd = Command::new(exe);

    // onedir НЕ требует TEMP/TMP override — нет runtime extraction.
    // fmail-core.exe просто запускает Python из файлов рядом с собой.

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

fn spawn_with_retry(
    exe: &PathBuf,
    log_path: &Option<PathBuf>,
    handle: &AppHandle,
) -> Option<Child> {
    for attempt in 1..=SPAWN_MAX_RETRIES {
        emit(handle, "spawning",
             format!("Запуск FastAPI сервера (попытка {}/{})...", attempt, SPAWN_MAX_RETRIES),
             attempt);

        match spawn_core(exe, log_path) {
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
                                   else { format!(" | {}", &log_hint[..log_hint.len().min(300)]) };
                        emit(handle, "killed",
                             format!("Ядро завершилось (код {}){}{}",
                                 code, hint,
                                 if attempt < SPAWN_MAX_RETRIES { ", повтор..." } else { "" }),
                             attempt);
                    }
                    Err(e) => emit(handle, "killed", format!("Ошибка проверки: {}", e), attempt),
                }
            }
            None => {
                emit(handle, "killed",
                     format!("Не удалось запустить fmail-core.exe (попытка {})", attempt),
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

        let Some(exe) = extract_core(&handle) else {
            emit(&handle, "failed", "Не удалось найти ядро при перезапуске.", 0);
            return;
        };

        let log_path = get_startup_log_path();
        let Some(child) = spawn_with_retry(&exe, &log_path, &handle) else {
            let log_hint = read_startup_log()
                .and_then(|l| l.lines().filter(|x| !x.trim().is_empty()).last().map(|s| s.to_string()))
                .unwrap_or_default();
            emit(&handle, "failed",
                 format!("Ядро не запускается при перезапуске.{}",
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
                 format!("Ядро не ответило.{}",
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

                // ── 2. Извлекаем/проверяем ядро ────────────────────────────────
                // При первом запуске: распаковывает ZIP → LOCALAPPDATA\FMailSender\
                // При повторных: хеш совпадает → пропускает распаковку (instant)
                let Some(exe) = extract_core(&handle) else {
                    // extract_core уже отправил emit("failed", ...)
                    return;
                };

                // ── 3. Запускаем с повторными попытками ───────────────────────
                let log_path = get_startup_log_path();
                let Some(child) = spawn_with_retry(&exe, &log_path, &handle) else {
                    let log_body  = read_startup_log().unwrap_or_default();
                    let last_line = log_body.lines()
                        .filter(|l| !l.trim().is_empty())
                        .last().unwrap_or("").to_string();

                    emit(&handle, "failed",
                         format!(
                             "Ядро не запускается после {} попыток.\n\
                              Путь ядра: %LOCALAPPDATA%\\FMailSender\\fmail-core\\fmail-core.exe\n\
                              Если антивирус удалил файлы — добавьте папку \
                              %LOCALAPPDATA%\\FMailSender в исключения и нажмите «Перезапустить».{}",
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
                              Возможные причины:\n\
                              • Порт {} занят другим приложением\n\
                              • Антивирус удалил файлы ядра (добавьте %LOCALAPPDATA%\\FMailSender в исключения)\n\
                              • Нехватка памяти (требуется 256+ МБ){}",
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
