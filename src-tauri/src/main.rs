// FMailSender Tauri shell v6.9.2
//
// Fixes in v6.9.2:
//   - PORT_WAIT_SECS increased 90s → 200s (Nuitka first-run extracts to cache)
//   - SPAWN_MAX_RETRIES reduced 25 → 8 (avoid long pointless retry loops)
//   - "av_wait" event emitted while waiting for port (helps frontend show better message)
//   - av_wait_secs tracking added for UI progress calculation
//
// Events emitted to the frontend (via AppHandle::emit):
//   core://status  →  { stage: str, message: str, attempt: u32 }
//     stages: extracting | av_wait | spawning | killed | running | ready | failed
//
// Tauri commands:
//   restart_core  —  kill current core + re-extract + re-spawn (UI "Retry" button)
//   get_core_url  —  returns "http://127.0.0.1:7531"
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Serialize;
use std::io::Write;
use std::net::TcpStream;
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

const CORE_PORT:            u16 = 7531;
const CORE_HOST_PRIMARY:    &str = "127.0.0.1";
const CORE_HOST_FALLBACK:   &str = "localhost";

// v6.9.2: Increased from 90s → 200s.
// Nuitka onefile extracts to %LOCALAPPDATA%\FMailSender\core\ on first run (~5-30s).
// Windows Defender may scan extracted files (up to 60s on slow machines).
// Python uvicorn startup: ~2-5s after extraction.
// Total worst-case first run: ~120s. We give 200s for safety.
const PORT_WAIT_SECS:       u64 = 200;

// v6.9.2: Reduced from 25 → 8.
// Each retry cycle = SPAWN_ALIVE_CHECK_S + SPAWN_RETRY_DELAY_S = 6s.
// 8 retries × 6s = 48s max retry window. Prevents very long pointless loops.
const SPAWN_MAX_RETRIES:    u32 = 8;
const SPAWN_ALIVE_CHECK_S:  u64 = 3;
const SPAWN_RETRY_DELAY_S:  u64 = 3;

/// fmail-core embedded at compile time.
/// Build will FAIL with a clear error if this file is missing — that is intentional.
/// CI must run Nuitka BEFORE `tauri build`.
#[cfg(target_os = "windows")]
static CORE_BYTES: &[u8] = include_bytes!(
    "../binaries/fmail-core-x86_64-pc-windows-msvc.exe"
);

// ── Event payload ──────────────────────────────────────────────────────────

#[derive(Clone, Serialize)]
struct CoreStatus {
    stage:   &'static str,
    message: String,
    attempt: u32,
}

fn emit(handle: &AppHandle, stage: &'static str, message: impl Into<String>, attempt: u32) {
    let _ = handle.emit("core://status", CoreStatus {
        stage,
        message: message.into(),
        attempt,
    });
}

// ── Helpers ─────────────────────────────────────────────────────────────────

fn try_connect(host: &str, port: u16) -> bool {
    let addr = format!("{}:{}", host, port);
    TcpStream::connect_timeout(
        &addr.parse().unwrap_or_else(|_| format!("127.0.0.1:{}", port).parse().unwrap()),
        Duration::from_millis(500),
    ).is_ok()
}

fn port_open() -> bool {
    try_connect(CORE_HOST_PRIMARY, CORE_PORT) || try_connect(CORE_HOST_FALLBACK, CORE_PORT)
}

/// Wait until the Python core is reachable or timeout elapses.
/// Emits "av_wait" events every 10s so the UI can update progress.
fn wait_for_port(timeout: Duration, handle: &AppHandle) -> bool {
    let deadline = Instant::now() + timeout;
    let mut last_event = Instant::now();
    let mut elapsed_s: u64 = 0;

    while Instant::now() < deadline {
        if port_open() { return true; }
        thread::sleep(Duration::from_millis(300));

        elapsed_s = Instant::now().duration_since(last_event).as_secs();
        // Emit progress event every 8 seconds so UI can show "still starting..."
        if elapsed_s >= 8 {
            last_event = Instant::now();
            let total_elapsed = timeout.as_secs().saturating_sub(
                deadline.duration_since(Instant::now()).as_secs()
            );
            emit(handle, "av_wait",
                format!("Запуск Python ядра... ({} сек)", total_elapsed), 0);
        }
    }
    false
}

// ── Kill helpers ────────────────────────────────────────────────────────────

fn kill_core_by_name() {
    #[cfg(target_os = "windows")]
    {
        let _ = Command::new("powershell")
            .args([
                "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
                "-Command",
                "Get-Process | Where-Object { $_.Name -like 'fmail-core*' } \
                 | Stop-Process -Force -ErrorAction SilentlyContinue",
            ])
            .stdout(Stdio::null()).stderr(Stdio::null())
            .creation_flags(CREATE_NO_WINDOW)
            .status();
    }
}

fn kill_existing_core() {
    #[cfg(target_os = "windows")]
    {
        let _ = Command::new("powershell")
            .args([
                "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
                "-Command",
                &format!(
                    "$p = (Get-NetTCPConnection -LocalPort {port} -State Listen \
                     -ErrorAction SilentlyContinue | Select-Object -ExpandProperty \
                     OwningProcess -ErrorAction SilentlyContinue); \
                     if ($p) {{ $p | ForEach-Object {{ Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }} }}",
                    port = CORE_PORT
                ),
            ])
            .stdout(Stdio::null()).stderr(Stdio::null())
            .creation_flags(CREATE_NO_WINDOW)
            .status();

        kill_core_by_name();

        // Wait until port is free (up to 5s).
        let deadline = Instant::now() + Duration::from_secs(5);
        loop {
            thread::sleep(Duration::from_millis(200));
            if !port_open() { thread::sleep(Duration::from_millis(300)); break; }
            if Instant::now() >= deadline { break; }
        }
    }
}

// ── Core extraction ─────────────────────────────────────────────────────────

/// Extract fmail-core to %LOCALAPPDATA%\FMailSender\core\fmail-core-{VERSION}.exe
/// Returns (path, was_freshly_written).
#[cfg(target_os = "windows")]
fn extract_core(handle: &AppHandle) -> Option<(PathBuf, bool)> {
    let local    = std::env::var("LOCALAPPDATA").ok()?;
    let dir      = PathBuf::from(&local).join("FMailSender").join("core");
    std::fs::create_dir_all(&dir).ok()?;

    let version  = env!("CARGO_PKG_VERSION");
    let name     = format!("fmail-core-{}.exe", version);
    let path     = dir.join(&name);

    let expected = CORE_BYTES.len() as u64;
    let needs_write = std::fs::metadata(&path)
        .map(|m| m.len() != expected)
        .unwrap_or(true);

    if needs_write {
        emit(handle, "extracting",
            format!("Извлечение Python ядра ({:.0} МБ)...", expected as f64 / 1_048_576.0), 0);

        // Remove stale versions.
        if let Ok(entries) = std::fs::read_dir(&dir) {
            for e in entries.flatten() {
                let n = e.file_name();
                let s = n.to_string_lossy();
                if s.starts_with("fmail-core-") && s.ends_with(".exe") && s.as_ref() != name {
                    let _ = std::fs::remove_file(e.path());
                }
            }
        }

        let mut f = std::fs::File::create(&path).ok()?;
        f.write_all(CORE_BYTES).ok()?;
        drop(f);

        // Verify write integrity.
        let written = std::fs::metadata(&path).map(|m| m.len()).unwrap_or(0);
        if written != expected {
            eprintln!("[core] write failed: expected {} bytes, got {}", expected, written);
            return None;
        }
    }

    Some((path, needs_write))
}

#[cfg(not(target_os = "windows"))]
fn extract_core(_handle: &AppHandle) -> Option<(PathBuf, bool)> { None }

// ── Spawn helpers ───────────────────────────────────────────────────────────

fn spawn_core_from(path: &PathBuf) -> Option<Child> {
    let mut cmd = Command::new(path);
    cmd.env("FMAIL_PORT", CORE_PORT.to_string())
        .env("FMAIL_HOST", "127.0.0.1")
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    #[cfg(target_os = "windows")]
    cmd.creation_flags(CREATE_NO_WINDOW);
    cmd.spawn().ok()
}

/// Spawn fmail-core, retrying if AV kills the process immediately.
fn spawn_with_retry(path: &PathBuf, handle: &AppHandle) -> Option<Child> {
    for attempt in 1..=SPAWN_MAX_RETRIES {
        emit(handle, "spawning",
            format!("Запуск Python ядра... (попытка {})", attempt), attempt);

        let child = spawn_core_from(path);
        let Some(mut child) = child else {
            eprintln!("[core] spawn() failed on attempt {}", attempt);
            emit(handle, "killed",
                format!("Не удалось запустить процесс (попытка {}), повтор через {}с...",
                    attempt, SPAWN_RETRY_DELAY_S), attempt);
            thread::sleep(Duration::from_secs(SPAWN_RETRY_DELAY_S));
            continue;
        };

        // Wait a few seconds and check whether the process survived.
        thread::sleep(Duration::from_secs(SPAWN_ALIVE_CHECK_S));

        match child.try_wait() {
            Ok(None) => {
                // Process is still running — AV allowed it.
                emit(handle, "running",
                    "Python ядро запущено, ожидание порта...", attempt);
                return Some(child);
            }
            Ok(Some(status)) => {
                // Process exited immediately — likely AV kill or crash.
                eprintln!("[core] process terminated immediately on attempt {} ({})",
                    attempt, status);
                emit(handle, "killed",
                    format!("Инициализация ядра... (попытка {})", attempt), attempt);
                thread::sleep(Duration::from_secs(SPAWN_RETRY_DELAY_S));
            }
            Err(_) => {
                // Cannot query process status — assume it is alive.
                return Some(child);
            }
        }
    }

    emit(handle, "failed",
        "Не удалось запустить Python ядро. Попробуйте перезапустить приложение.".to_string(),
        SPAWN_MAX_RETRIES);
    None
}

// ── Full startup sequence ───────────────────────────────────────────────────

fn run_startup(core_handle: Arc<Mutex<Option<Child>>>, app_handle: AppHandle) {
    // 1. Kill any leftover instance.
    kill_existing_core();

    // 2. Extract binary (no-op on warm start).
    let (core_path, fresh) = match extract_core(&app_handle) {
        Some(x) => x,
        None => {
            emit(&app_handle, "failed",
                "Не удалось извлечь Python ядро. Попробуйте переустановить приложение.", 0);
            return;
        }
    };

    // If binary was freshly written, re-verify size.
    if fresh {
        let on_disk = std::fs::metadata(&core_path).map(|m| m.len()).unwrap_or(0);
        #[cfg(target_os = "windows")]
        let expected = CORE_BYTES.len() as u64;
        #[cfg(not(target_os = "windows"))]
        let expected = 0u64;

        if on_disk != expected {
            emit(&app_handle, "failed",
                "Файл ядра повреждён при записи. Попробуйте перезапустить приложение.", 0);
            return;
        }
    }

    // 3. Spawn with retry (handles AV killing the process immediately).
    let child = spawn_with_retry(&core_path, &app_handle);
    *core_handle.lock().unwrap() = child;

    // 4. Wait for the TCP port to open.
    if wait_for_port(Duration::from_secs(PORT_WAIT_SECS), &app_handle) {
        emit(&app_handle, "ready", "Python ядро готово", 0);
        eprintln!("[FMailSender] fmail-core is ready on port {}", CORE_PORT);
    } else {
        emit(&app_handle, "failed",
            format!("Python ядро не ответило на порт {} за {} сек. Нажмите «Перезапустить ядро».", CORE_PORT, PORT_WAIT_SECS), 0);
        eprintln!("[FMailSender] fmail-core failed to open port {} within {}s",
            CORE_PORT, PORT_WAIT_SECS);
    }
}

// ── Tauri commands ──────────────────────────────────────────────────────────

/// UI "Retry" button — kills the running core and restarts the full sequence.
#[tauri::command]
fn restart_core(
    core_handle: tauri::State<Arc<Mutex<Option<Child>>>>,
    app_handle: AppHandle,
) {
    if let Ok(mut guard) = core_handle.lock() {
        if let Some(mut child) = guard.take() {
            let _ = child.kill();
        }
    }
    kill_core_by_name();

    let handle_clone   = Arc::clone(&core_handle);
    let app_clone      = app_handle.clone();
    thread::spawn(move || run_startup(handle_clone, app_clone));
}

#[tauri::command]
fn get_core_url() -> String {
    format!("http://{}:{}", CORE_HOST_PRIMARY, CORE_PORT)
}

// ── main ────────────────────────────────────────────────────────────────────

fn main() {
    let core_handle: Arc<Mutex<Option<Child>>> = Arc::new(Mutex::new(None));
    let core_for_event = Arc::clone(&core_handle);
    let core_for_cmd   = Arc::clone(&core_handle);

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(core_for_cmd)
        .setup(move |app| {
            let app_handle = app.handle().clone();
            let ch         = Arc::clone(&core_handle);
            thread::spawn(move || run_startup(ch, app_handle));
            Ok(())
        })
        .on_window_event(move |_win, event| {
            if let tauri::WindowEvent::Destroyed = event {
                if let Ok(mut g) = core_for_event.lock() {
                    if let Some(mut c) = g.take() { let _ = c.kill(); }
                }
                kill_core_by_name();
            }
        })
        .invoke_handler(tauri::generate_handler![get_core_url, restart_core])
        .run(tauri::generate_context!())
        .expect("tauri runtime error");
}
