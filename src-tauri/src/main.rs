// FMailSender Tauri shell v7.0.0
//
// ИЗМЕНЕНИЯ v7.0.0:
//   - Сборка: PyInstaller 6.21 (2-4 мин) вместо Nuitka (60+ мин)
//   - Ядро: onefile PyInstaller → мгновенный тёплый старт (PyInstaller кеширует по хешу)
//   - Startup: улучшенные сообщения об ошибках на русском
//   - Безопасность: читаем /api/identity после старта (HWID + fingerprint)
//   - DEBUG: если ядро не стартует, читаем startup.log из %LOCALAPPDATA%\FMailSender\
//   - Команды: restart_core, get_core_url
//   - События: core://status { stage, message, attempt }
//     Stages: extracting | av_wait | spawning | killed | running | ready | failed | license_error
//
// Требования к CI:
//   1. pyinstaller fmail-core.spec --noconfirm → dist/fmail-core.exe
//   2. cp dist/fmail-core.exe src-tauri/binaries/fmail-core-x86_64-pc-windows-msvc.exe
//   3. tauri build
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

// 180 сек — достаточно для PyInstaller onefile (кеш по хешу, тёплый старт быстрее)
// При первом запуске: ~5-15 сек распаковка + ~3-5 сек uvicorn
// При AV-сканировании: до 60 сек
const PORT_WAIT_SECS:      u64 = 180;

// 8 попыток × (3с проверка + 3с ожидание) = 48с окно повторных запусков
const SPAWN_MAX_RETRIES:   u32 = 8;
const SPAWN_ALIVE_CHECK_S: u64 = 3;
const SPAWN_RETRY_DELAY_S: u64 = 3;

// Файл, куда Python пишет startup errors (если не может стартовать нормально)
const STARTUP_LOG: &str = "startup.log";

/// Embedded fmail-core.exe (PyInstaller onefile).
/// Build FAILS with clear error if this file is missing — это intentional.
/// CI must run PyInstaller BEFORE `tauri build`.
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
fn wait_for_port(timeout: Duration, handle: &AppHandle) -> bool {
    let deadline    = Instant::now() + timeout;
    let mut last_ev = Instant::now();

    while Instant::now() < deadline {
        if port_open() {
            return true;
        }
        thread::sleep(Duration::from_millis(300));

        if last_ev.elapsed().as_secs() >= 5 {
            last_ev = Instant::now();
            let elapsed  = timeout.as_secs()
                .saturating_sub(deadline.duration_since(Instant::now()).as_secs());
            let remaining = deadline.duration_since(Instant::now()).as_secs();
            emit(
                handle, "av_wait",
                format!(
                    "Ожидание ядра... прошло {}с, осталось {}с. \
                     Если долго — добавьте FMailSender в исключения антивируса.",
                    elapsed, remaining
                ),
                0,
            );
        }
    }
    false
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
        // Вычисляем хеш встроенных байт для проверки целостности
        let embedded_hash = fnv64(CORE_BYTES);

        // Проверяем, нужно ли перезаписывать файл
        let needs_replace = if path.exists() {
            // Сравниваем хеш на диске с хешем встроенных байт
            let on_disk = std::fs::read(&path).unwrap_or_default();
            fnv64(&on_disk) != embedded_hash
        } else {
            true
        };

        if needs_replace {
            // Атомарная запись через временный файл
            let tmp_path = dir.join("fmail-core.tmp");
            {
                let mut f = match std::fs::File::create(&tmp_path) {
                    Ok(f) => f,
                    Err(e) => {
                        emit(handle, "failed",
                             format!("Ошибка создания temp файла: {}", e), 0);
                        return None;
                    }
                };
                if f.write_all(CORE_BYTES).is_err() || f.flush().is_err() {
                    return None;
                }
            }
            // На Windows rename может не сработать если файл заблокирован — fallback на copy+delete
            if std::fs::rename(&tmp_path, &path).is_err() {
                let _ = std::fs::copy(&tmp_path, &path);
                let _ = std::fs::remove_file(&tmp_path);
            }
        }
    }

    #[cfg(not(target_os = "windows"))]
    {
        // Dev режим: ищем python main.py
        return None;
    }

    Some(path)
}

// ── Process management ────────────────────────────────────────────────────────

fn kill_existing_core() {
    #[cfg(target_os = "windows")]
    {
        // Убиваем всё, что держит порт 7531
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
        thread::sleep(Duration::from_millis(1000));
    }
}

fn spawn_core(exe: &PathBuf, log_path: &Option<PathBuf>) -> Option<Child> {
    let mut cmd = Command::new(exe);

    // Перенаправляем stdout/stderr в лог-файл для отладки
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
        emit(
            handle, "spawning",
            format!("Запуск ядра (попытка {}/{})", attempt, SPAWN_MAX_RETRIES),
            attempt,
        );

        match spawn_core(exe, log_path) {
            Some(mut child) => {
                thread::sleep(Duration::from_secs(SPAWN_ALIVE_CHECK_S));
                match child.try_wait() {
                    Ok(None) => return Some(child), // Процесс жив
                    Ok(Some(status)) => {
                        let code_str = status.code()
                            .map(|c| c.to_string())
                            .unwrap_or_else(|| "?".into());

                        // Читаем лог для диагностики
                        let log_hint = if let Some(log) = read_startup_log() {
                            let last = log.lines()
                                .filter(|l| !l.trim().is_empty())
                                .last()
                                .unwrap_or("");
                            if last.is_empty() {
                                String::new()
                            } else {
                                format!(" | Лог: {}", last)
                            }
                        } else {
                            String::new()
                        };

                        emit(
                            handle, "killed",
                            format!(
                                "Ядро завершилось (код {}), повтор...{}",
                                code_str, log_hint
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
                        "Не удалось запустить EXE (попытка {}). \
                         Возможно, заблокирован антивирусом.",
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
        // Убиваем текущий процесс
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
        let Some(child) = spawn_with_retry(&exe, &log_path, &handle) else {
            let log_hint = read_startup_log()
                .and_then(|l| l.lines().last().map(|s| s.to_string()))
                .unwrap_or_default();
            emit(
                &handle, "failed",
                format!(
                    "Ядро не запускается при перезапуске. {}",
                    if log_hint.is_empty() { String::new() } else { format!("Ошибка: {}", log_hint) }
                ),
                0,
            );
            return;
        };
        *state.lock().unwrap() = Some(child);

        if wait_for_port(Duration::from_secs(PORT_WAIT_SECS), &handle) {
            emit(&handle, "ready", "Ядро готово к работе", 0);
        } else {
            let log_hint = read_startup_log()
                .and_then(|l| l.lines().last().map(|s| s.to_string()))
                .unwrap_or_default();
            emit(
                &handle, "failed",
                format!("Ядро не ответило при перезапуске. {}", log_hint),
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

                // ── 2. Извлекаем ядро из embedded bytes ────────────────────────
                let Some(exe) = extract_core(&handle) else {
                    emit(
                        &handle, "failed",
                        "Критическая ошибка: не удалось создать директорию ядра. \
                         Запустите от имени администратора или переустановите приложение.",
                        0,
                    );
                    return;
                };

                // ── 3. Запускаем с повторными попытками ───────────────────────
                let log_path = get_startup_log_path();
                let Some(child) = spawn_with_retry(&exe, &log_path, &handle) else {
                    let log_body = read_startup_log().unwrap_or_default();
                    let last_line = log_body.lines()
                        .filter(|l| !l.trim().is_empty())
                        .last()
                        .unwrap_or("")
                        .to_string();

                    emit(
                        &handle, "failed",
                        format!(
                            "Ядро не запускается после {} попыток. \
                             Добавьте FMailSender в исключения антивируса и \
                             перезапустите приложение.{}",
                            SPAWN_MAX_RETRIES,
                            if last_line.is_empty() {
                                String::new()
                            } else {
                                format!("\n\nОшибка: {}", last_line)
                            }
                        ),
                        0,
                    );
                    return;
                };
                *state.lock().unwrap() = Some(child);

                emit(&handle, "running", "Ожидание готовности ядра...", 0);

                // ── 4. Ждём открытия порта ─────────────────────────────────────
                if !wait_for_port(Duration::from_secs(PORT_WAIT_SECS), &handle) {
                    let log_body = read_startup_log().unwrap_or_default();
                    let last_line = log_body.lines()
                        .filter(|l| !l.trim().is_empty())
                        .last()
                        .unwrap_or("")
                        .to_string();

                    emit(
                        &handle, "failed",
                        format!(
                            "Ядро не ответило за {} секунд. \
                             Возможные причины:\n\
                             • Антивирус блокирует ядро — добавьте FMailSender в исключения\n\
                             • Порт {} занят другим процессом\n\
                             • Недостаточно памяти (мин. 512 МБ свободной ОЗУ){}",
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
