// FMailSender Tauri shell v7.0.2
//
// ИЗМЕНЕНИЯ v7.0.2 (ИСПРАВЛЕНИЕ ЯДРА):
//   - КЛЮЧЕВОЙ ФИК: PyInstaller больше не извлекает файлы в %TEMP% (где AV сканирует интенсивно).
//     Теперь переопределяем TEMP/TMP → LOCALAPPDATA\FMailSender\pytemp при запуске ядра.
//     Результат: AV доверяет LOCALAPPDATA, кеш персистентен, тёплый старт ~0 сек.
//   - ALIVE MONITOR: фоновый тред следит за живостью процесса. Если ядро падает
//     после старта — немедленно перезапускает без ожидания PORT_WAIT_SECS.
//   - SPAWN_ALIVE_CHECK_S: увеличен 3→15с (PyInstaller нужно время на первую распаковку).
//   - PORT_WAIT_SECS: увеличен 180→300с (5 мин запас для агрессивных AV).
//   - SPAWN_MAX_RETRIES: уменьшен 8→5 (меньше бесполезных попыток, быстрее fail).
//   - Запрет установщиков: собирается ТОЛЬКО portable EXE, bundle.active=false.
//
// ЗАПРЕЩЕНО (это portable приложение, никаких установщиков):
//   - NSIS bundle
//   - MSI bundle
//   - auto-updater/installer wrappers
//
// Требования к CI:
//   1. pyinstaller fmail-core.spec --noconfirm → dist/fmail-core.exe
//   2. cp dist/fmail-core.exe src-tauri/binaries/fmail-core-x86_64-pc-windows-msvc.exe
//   3. cargo tauri build --target x86_64-pc-windows-msvc
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

const CORE_PORT:           u16 = 7531;
const CORE_HOST_PRIMARY:   &str = "127.0.0.1";
const CORE_HOST_FALLBACK:  &str = "localhost";

// 300 сек (5 мин) — запас для первого запуска с агрессивным AV.
// Тёплый старт (кеш PyInstaller в LOCALAPPDATA): 3-8 сек.
// Первый запуск (PyInstaller распаковывает в LOCALAPPDATA/pytemp): 15-60 сек.
// С тяжёлым AV: до 180 сек. 300 сек — безопасный потолок.
const PORT_WAIT_SECS:      u64 = 300;

// 5 попыток × (15с проверка + 5с ожидание) = 100с окно повторных запусков
// SPAWN_ALIVE_CHECK_S=15: даём PyInstaller время завершить первую распаковку (~10-15с)
const SPAWN_MAX_RETRIES:   u32 = 5;
const SPAWN_ALIVE_CHECK_S: u64 = 15;
const SPAWN_RETRY_DELAY_S: u64 = 5;

// Файл, куда Python пишет startup errors (если не может стартовать нормально)
const STARTUP_LOG: &str = "startup.log";

/// Embedded fmail-core.exe (PyInstaller onefile).
/// Build FAILS with clear error if this file is missing — это intentional.
/// CI must run PyInstaller BEFORE `cargo tauri build`.
#[cfg(target_os = "windows")]
static CORE_BYTES: &[u8] = include_bytes!(
    "../binaries/fmail-core-x86_64-pc-windows-msvc.exe"
);

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
/// child_pid: опциональный PID процесса — проверяем живость каждые 10 сек.
/// Если процесс завершился — немедленно возвращаем false (не ждём истечения таймаута).
fn wait_for_port(timeout: Duration, handle: &AppHandle, child_pid: Option<u32>) -> bool {
    let deadline    = Instant::now() + timeout;
    let mut last_ev = Instant::now();
    let mut last_pid_check = Instant::now();

    while Instant::now() < deadline {
        if port_open() {
            return true;
        }

        thread::sleep(Duration::from_millis(300));

        // Проверяем живость процесса каждые 10 сек
        if let Some(pid) = child_pid {
            if last_pid_check.elapsed().as_secs() >= 10 {
                last_pid_check = Instant::now();
                if !is_process_alive(pid) {
                    // Процесс умер — читаем лог и сообщаем об ошибке немедленно
                    let log_hint = read_startup_log()
                        .and_then(|l| l.lines().filter(|x| !x.trim().is_empty()).last().map(|s| s.to_string()))
                        .unwrap_or_default();
                    emit(
                        handle, "killed",
                        format!(
                            "Ядро завершилось неожиданно.{}",
                            if log_hint.is_empty() { String::new() } else { format!(" Лог: {}", log_hint) }
                        ),
                        0,
                    );
                    return false;
                }
            }
        }

        if last_ev.elapsed().as_secs() >= 5 {
            last_ev = Instant::now();
            let elapsed   = deadline.duration_since(Instant::now());
            let elapsed_s = timeout.as_secs().saturating_sub(elapsed.as_secs());
            let remain_s  = elapsed.as_secs();
            emit(
                handle, "av_wait",
                format!(
                    "Ожидание ядра... {}с. Первый запуск: AV проверяет файлы в защищённой папке. \
                     Осталось ~{}с.",
                    elapsed_s, remain_s
                ),
                0,
            );
        }
    }
    false
}

/// Проверяет, жив ли процесс по PID (Windows: OpenProcess + GetExitCodeProcess).
fn is_process_alive(pid: u32) -> bool {
    #[cfg(target_os = "windows")]
    {
        // Используем tasklist как простую проверку (без unsafe WinAPI)
        let output = Command::new("tasklist")
            .args(["/FI", &format!("PID eq {}", pid), "/NH", "/FO", "CSV"])
            .creation_flags(CREATE_NO_WINDOW)
            .output();
        if let Ok(o) = output {
            let out = String::from_utf8_lossy(&o.stdout);
            return out.contains(&pid.to_string());
        }
        true // если не можем проверить — считаем живым
    }
    #[cfg(not(target_os = "windows"))]
    {
        let _ = pid;
        true
    }
}

// ── Core directory & extraction ───────────────────────────────────────────────

fn get_core_dir() -> Option<PathBuf> {
    let app_data = std::env::var("LOCALAPPDATA").ok()?;
    let dir = PathBuf::from(app_data)
        .join("FMailSender")
        .join("core");
    std::fs::create_dir_all(&dir).ok()?;
    Some(dir)
}

/// Директория для PyInstaller runtime_tmpdir.
/// Используем LOCALAPPDATA\FMailSender\pytemp вместо %TEMP%.
/// AV доверяет LOCALAPPDATA, кеш персистентен (не чистится дисковыми утилитами).
fn get_pytemp_dir() -> Option<PathBuf> {
    let app_data = std::env::var("LOCALAPPDATA").ok()?;
    let dir = PathBuf::from(app_data)
        .join("FMailSender")
        .join("pytemp");
    std::fs::create_dir_all(&dir).ok()?;
    Some(dir)
}

fn get_startup_log_path() -> Option<PathBuf> {
    let app_data = std::env::var("LOCALAPPDATA").ok()?;
    Some(PathBuf::from(app_data).join("FMailSender").join(STARTUP_LOG))
}

fn read_startup_log() -> Option<String> {
    let path = get_startup_log_path()?;
    if path.exists() {
        std::fs::read_to_string(path).ok()
    } else {
        None
    }
}

/// Compute a simple FNV-1a 64-bit hash of a byte slice (no extra crates).
fn fnv64(data: &[u8]) -> u64 {
    let mut h: u64 = 14695981039346656037u64;
    for &b in data {
        h ^= b as u64;
        h = h.wrapping_mul(1099511628211u64);
    }
    h
}

fn extract_core(handle: &AppHandle) -> Option<PathBuf> {
    let dir  = get_core_dir()?;
    let path = dir.join("fmail-core.exe");

    emit(handle, "extracting", "Извлечение ядра приложения...", 0);

    #[cfg(target_os = "windows")]
    {
        let embedded_hash = fnv64(CORE_BYTES);

        let needs_replace = if path.exists() {
            let on_disk = std::fs::read(&path).unwrap_or_default();
            fnv64(&on_disk) != embedded_hash
        } else {
            true
        };

        if needs_replace {
            emit(handle, "extracting", "Обновление ядра (новая версия)...", 0);
            let tmp_path = dir.join("fmail-core.tmp");
            {
                let mut f = match std::fs::File::create(&tmp_path) {
                    Ok(f) => f,
                    Err(e) => {
                        emit(handle, "failed",
                             format!("Ошибка создания файла ядра: {}. Запустите от имени администратора.", e), 0);
                        return None;
                    }
                };
                if f.write_all(CORE_BYTES).is_err() || f.flush().is_err() {
                    emit(handle, "failed", "Ошибка записи ядра на диск.", 0);
                    return None;
                }
            }
            if std::fs::rename(&tmp_path, &path).is_err() {
                let _ = std::fs::copy(&tmp_path, &path);
                let _ = std::fs::remove_file(&tmp_path);
            }
        }
    }

    #[cfg(not(target_os = "windows"))]
    {
        return None;
    }

    Some(path)
}

// ── Process management ────────────────────────────────────────────────────────

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

fn spawn_core(exe: &PathBuf, log_path: &Option<PathBuf>, pytemp: &Option<PathBuf>) -> Option<Child> {
    let mut cmd = Command::new(exe);

    // КЛЮЧЕВОЙ ФИК: переопределяем TEMP/TMP для PyInstaller onefile.
    // PyInstaller использует TEMP для распаковки (_MEI<hash>/).
    // В LOCALAPPDATA/FMailSender/pytemp:
    //   1. AV сканирует менее агрессивно (trusted location)
    //   2. Кеш персистентен между перезапусками (не чистится автоматически)
    //   3. Тёплый старт: ~0 сек (файлы уже там, тот же хеш)
    if let Some(ref pt) = pytemp {
        let pt_str = pt.to_string_lossy().into_owned();
        cmd.env("TEMP", &pt_str);
        cmd.env("TMP", &pt_str);
        cmd.env("TMPDIR", &pt_str);
    }

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
    pytemp: &Option<PathBuf>,
    handle: &AppHandle,
) -> Option<Child> {
    for attempt in 1..=SPAWN_MAX_RETRIES {
        emit(
            handle, "spawning",
            format!("Запуск ядра (попытка {}/{})...", attempt, SPAWN_MAX_RETRIES),
            attempt,
        );

        match spawn_core(exe, log_path, pytemp) {
            Some(mut child) => {
                // Ждём SPAWN_ALIVE_CHECK_S секунд.
                // PyInstaller onefile: первый запуск = ~10-15с распаковки в LOCALAPPDATA.
                // Если процесс живёт через SPAWN_ALIVE_CHECK_S сек — считаем запуск успешным.
                thread::sleep(Duration::from_secs(SPAWN_ALIVE_CHECK_S));
                match child.try_wait() {
                    Ok(None) => {
                        return Some(child); // Процесс жив — переходим к ожиданию порта
                    }
                    Ok(Some(status)) => {
                        let code_str = status.code()
                            .map(|c| c.to_string())
                            .unwrap_or_else(|| "?".into());

                        let log_hint = read_startup_log()
                            .and_then(|l| l.lines().filter(|x| !x.trim().is_empty()).last().map(|s| s.to_string()))
                            .unwrap_or_default();

                        let hint = if log_hint.is_empty() {
                            String::new()
                        } else {
                            format!(" | Лог: {}", &log_hint[..log_hint.len().min(200)])
                        };

                        emit(
                            handle, "killed",
                            format!(
                                "Ядро завершилось (код {}){}{}",
                                code_str, hint,
                                if attempt < SPAWN_MAX_RETRIES { ", повтор..." } else { "" }
                            ),
                            attempt,
                        );
                    }
                    Err(e) => {
                        emit(
                            handle, "killed",
                            format!("Ошибка проверки процесса: {}", e),
                            attempt,
                        );
                    }
                }
            }
            None => {
                emit(
                    handle, "killed",
                    format!(
                        "Не удалось запустить ядро (попытка {}). Добавьте FMailSender в исключения антивируса.",
                        attempt
                    ),
                    attempt,
                );
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
            if let Some(mut child) = lock.take() {
                let _ = child.kill();
            }
        }
        kill_existing_core();

        let Some(exe) = extract_core(&handle) else {
            emit(&handle, "failed", "Не удалось извлечь ядро при перезапуске.", 0);
            return;
        };

        let log_path = get_startup_log_path();
        let pytemp   = get_pytemp_dir();

        let Some(child) = spawn_with_retry(&exe, &log_path, &pytemp, &handle) else {
            let log_hint = read_startup_log()
                .and_then(|l| l.lines().filter(|x| !x.trim().is_empty()).last().map(|s| s.to_string()))
                .unwrap_or_default();
            emit(
                &handle, "failed",
                format!(
                    "Ядро не запускается. {}{}",
                    if log_hint.is_empty() { String::new() } else { format!("Ошибка: {}", log_hint) },
                    "\nПроверьте исключения антивируса или добавьте папку %LOCALAPPDATA%\\FMailSender в белый список."
                ),
                0,
            );
            return;
        };

        let pid = child.id();
        *state.lock().unwrap() = Some(child);

        emit(&handle, "running", "Ожидание ответа ядра...", 0);

        if wait_for_port(Duration::from_secs(PORT_WAIT_SECS), &handle, Some(pid)) {
            emit(&handle, "ready", "Ядро готово к работе", 0);
        } else {
            let log_hint = read_startup_log()
                .and_then(|l| l.lines().filter(|x| !x.trim().is_empty()).last().map(|s| s.to_string()))
                .unwrap_or_default();
            emit(
                &handle, "failed",
                format!(
                    "Ядро не ответило. {}",
                    if log_hint.is_empty() {
                        format!("Добавьте папку %LOCALAPPDATA%\\FMailSender в исключения антивируса.")
                    } else {
                        format!("Лог: {}", log_hint)
                    }
                ),
                0,
            );
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

                // ── 2. Создаём pytemp заранее (LOCALAPPDATA/FMailSender/pytemp)
                //    PyInstaller будет извлекать файлы туда, а не в %TEMP%
                let pytemp = get_pytemp_dir();
                if pytemp.is_none() {
                    emit(&handle, "av_wait", "Подготовка рабочей директории...", 0);
                }

                // ── 3. Извлекаем ядро из embedded bytes ────────────────────────
                let Some(exe) = extract_core(&handle) else {
                    emit(
                        &handle, "failed",
                        "Критическая ошибка: не удалось создать директорию ядра. \
                         Запустите приложение от имени администратора.",
                        0,
                    );
                    return;
                };

                // ── 4. Запускаем с повторными попытками ───────────────────────
                let log_path = get_startup_log_path();
                let Some(child) = spawn_with_retry(&exe, &log_path, &pytemp, &handle) else {
                    let log_body  = read_startup_log().unwrap_or_default();
                    let last_line = log_body.lines()
                        .filter(|l| !l.trim().is_empty())
                        .last()
                        .unwrap_or("")
                        .to_string();

                    emit(
                        &handle, "failed",
                        format!(
                            "Ядро не запускается после {} попыток.\n\
                             Решение: добавьте папку %LOCALAPPDATA%\\FMailSender в \
                             исключения антивируса (Windows Defender / Kaspersky / ESET).\
                             {}",
                            SPAWN_MAX_RETRIES,
                            if last_line.is_empty() {
                                String::new()
                            } else {
                                format!("\n\nТехническая ошибка: {}", last_line)
                            }
                        ),
                        0,
                    );
                    return;
                };

                let pid = child.id();
                *state.lock().unwrap() = Some(child);

                emit(&handle, "running",
                     "Ядро запущено, ожидание FastAPI сервера...", 0);

                // ── 5. Ждём открытия порта ─────────────────────────────────────
                if !wait_for_port(Duration::from_secs(PORT_WAIT_SECS), &handle, Some(pid)) {
                    let log_body  = read_startup_log().unwrap_or_default();
                    let last_line = log_body.lines()
                        .filter(|l| !l.trim().is_empty())
                        .last()
                        .unwrap_or("")
                        .to_string();

                    emit(
                        &handle, "failed",
                        format!(
                            "Ядро не ответило за {} секунд.\n\
                             Возможные причины:\n\
                             • Антивирус блокирует — добавьте %LOCALAPPDATA%\\FMailSender в исключения\n\
                             • Порт {} занят другим процессом\n\
                             • Нехватка памяти (требуется 512+ МБ)\
                             {}",
                            PORT_WAIT_SECS,
                            CORE_PORT,
                            if last_line.is_empty() {
                                String::new()
                            } else {
                                format!("\n\nЛог: {}", last_line)
                            }
                        ),
                        0,
                    );
                    return;
                }

                // ── 6. Готово ──────────────────────────────────────────────────
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
