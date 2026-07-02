// FMailSender Tauri shell v6.8.0
//
// Key change (v6.8.0): fmail-core is cached in %LOCALAPPDATA%\FMailSender\core\
// under a version-stamped filename (e.g. fmail-core-6.8.0.exe).
// Windows Defender scans it ONCE on first run of each version; all subsequent
// launches reuse the cached file — no write, no AV delay, no temp-dir churn.
// Old version files are cleaned up automatically when a new version is installed.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::io::Write;
use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};
use tauri::Manager;

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;
#[cfg(target_os = "windows")]
const CREATE_NO_WINDOW: u32 = 0x08000000;

const CORE_PORT:            u16  = 7531;
const CORE_HOST:            &str = "127.0.0.1";
// Warm start (cached exe, fast lifespan): ~5-8 s.
// Cold start (first-ever run, AV scan): up to 30 s.
// License validation now happens in the background — does NOT block startup.
const STARTUP_TIMEOUT_SECS: u64  = 30;

/// fmail-core embedded at compile time.
#[cfg(target_os = "windows")]
static CORE_BYTES: &[u8] = include_bytes!(
    "../binaries/fmail-core-x86_64-pc-windows-msvc.exe"
);

// ── helpers ────────────────────────────────────────────────────────────────

fn wait_for_core(timeout: Duration) -> bool {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if TcpStream::connect((CORE_HOST, CORE_PORT)).is_ok() {
            return true;
        }
        thread::sleep(Duration::from_millis(200));
    }
    false
}

// ── kill helpers ───────────────────────────────────────────────────────────

/// Kill all fmail-core* processes by wildcard — handles version-stamped names.
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
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .creation_flags(CREATE_NO_WINDOW)
            .status();
    }
}

/// Full startup cleanup: kill by port, then by name, then wait for port free.
fn kill_existing_core() {
    #[cfg(target_os = "windows")]
    {
        // Kill any process listening on our port.
        let _ = Command::new("powershell")
            .args([
                "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
                "-Command",
                &format!(
                    "$pids = (Get-NetTCPConnection -LocalPort {port} -State Listen \
                     -ErrorAction SilentlyContinue | Select-Object -ExpandProperty \
                     OwningProcess -ErrorAction SilentlyContinue); \
                     if ($pids) {{ foreach ($p in @($pids)) {{ \
                       Stop-Process -Id $p -Force -ErrorAction SilentlyContinue }} }}",
                    port = CORE_PORT
                ),
            ])
            .stdout(Stdio::null()).stderr(Stdio::null())
            .creation_flags(CREATE_NO_WINDOW)
            .status();

        kill_core_by_name();

        // Remove any legacy sidecar left by old versions next to FMailSender.exe.
        if let Ok(local) = std::env::var("LOCALAPPDATA") {
            let app_dir = PathBuf::from(local).join("FMailSender");
            for name in &["fmail-core-x86_64-pc-windows-msvc.exe", "fmail-core.exe"] {
                let p = app_dir.join(name);
                if p.exists() { let _ = std::fs::remove_file(&p); }
            }
        }

        // Wait until port is confirmed free (up to 5 s).
        let deadline = Instant::now() + Duration::from_secs(5);
        loop {
            thread::sleep(Duration::from_millis(200));
            if TcpStream::connect((CORE_HOST, CORE_PORT)).is_err() {
                thread::sleep(Duration::from_millis(300));
                break;
            }
            if Instant::now() >= deadline { break; }
        }
    }
}

// ── core extraction & spawn ────────────────────────────────────────────────

/// Return path to the cached fmail-core binary, extracting it only when needed.
///
/// Cache location: %LOCALAPPDATA%\FMailSender\core\fmail-core-{VERSION}.exe
///
/// Behaviour:
///   - If the file already exists with the correct size → return immediately (0 ms).
///   - If missing or size mismatch → write once, clean up old-version files.
///
/// This means Windows Defender scans the file exactly once per app version,
/// not on every launch.
#[cfg(target_os = "windows")]
fn extract_core() -> Option<PathBuf> {
    let local = std::env::var("LOCALAPPDATA").ok()?;
    let cache_dir = PathBuf::from(&local).join("FMailSender").join("core");
    std::fs::create_dir_all(&cache_dir).ok()?;

    let version   = env!("CARGO_PKG_VERSION");
    let exe_name  = format!("fmail-core-{}.exe", version);
    let exe_path  = cache_dir.join(&exe_name);

    let expected_size = CORE_BYTES.len() as u64;
    let needs_write   = std::fs::metadata(&exe_path)
        .map(|m| m.len() != expected_size)
        .unwrap_or(true);

    if needs_write {
        // Clean up old-version cached binaries before writing.
        if let Ok(entries) = std::fs::read_dir(&cache_dir) {
            for entry in entries.flatten() {
                let n = entry.file_name();
                let s = n.to_string_lossy();
                if s.starts_with("fmail-core-") && s.ends_with(".exe")
                    && s.as_ref() != exe_name.as_str()
                {
                    let _ = std::fs::remove_file(entry.path());
                }
            }
        }
        let mut f = std::fs::File::create(&exe_path).ok()?;
        f.write_all(CORE_BYTES).ok()?;
        drop(f);
    }

    Some(exe_path)
}

#[cfg(not(target_os = "windows"))]
fn extract_core() -> Option<PathBuf> {
    None
}

fn spawn_core_from(path: &PathBuf) -> Option<Child> {
    let mut cmd = Command::new(path);
    cmd.env("FMAIL_PORT", CORE_PORT.to_string())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    #[cfg(target_os = "windows")]
    cmd.creation_flags(CREATE_NO_WINDOW);
    cmd.spawn().ok()
}

// ── Tauri command ──────────────────────────────────────────────────────────

#[tauri::command]
fn get_core_url() -> String {
    format!("http://{}:{}", CORE_HOST, CORE_PORT)
}

// ── main ───────────────────────────────────────────────────────────────────

fn main() {
    let core_handle:   Arc<Mutex<Option<Child>>> = Arc::new(Mutex::new(None));
    let core_for_event = Arc::clone(&core_handle);

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(move |_app| {
            // 1. Kill any leftover core (port + name + port-free wait).
            kill_existing_core();

            // 2. Get cached binary path (extract only if missing / changed).
            let core_path = match extract_core() {
                Some(p) => p,
                None => {
                    eprintln!("[FMailSender] Failed to locate fmail-core binary");
                    return Ok(());
                }
            };

            // 3. Spawn core.
            let child = spawn_core_from(&core_path);
            *core_handle.lock().unwrap() = child;

            // 4. Background thread: wait for port to open (informational only;
            //    the UI polls /api/health independently).
            thread::spawn(move || {
                if !wait_for_core(Duration::from_secs(STARTUP_TIMEOUT_SECS)) {
                    eprintln!(
                        "[FMailSender] fmail-core did not start within {}s",
                        STARTUP_TIMEOUT_SECS
                    );
                }
            });

            Ok(())
        })
        .on_window_event(move |_window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                // Kill the tracked child process.
                if let Ok(mut guard) = core_for_event.lock() {
                    if let Some(mut child) = guard.take() {
                        let _ = child.kill();
                    }
                }
                // Belt-and-suspenders: kill any orphaned core by name.
                kill_core_by_name();
                // Note: the cached binary (%LOCALAPPDATA%\FMailSender\core\) is
                // intentionally preserved — reused on the next launch with 0 write cost.
            }
        })
        .invoke_handler(tauri::generate_handler![get_core_url])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
