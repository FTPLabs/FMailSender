// FMailSender Tauri shell v6.1.0
// Security: fmail-core is embedded inside this binary via include_bytes!().
// It is extracted to %TEMP%\fmailsender-{session}\ at startup and deleted on exit.
// There is no separate fmail-core.exe file next to the app.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::io::Write;
use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use tauri::Manager;

const CORE_PORT:            u16 = 7531;
const CORE_HOST:            &str = "127.0.0.1";
const STARTUP_TIMEOUT_SECS: u64 = 60;

/// fmail-core embedded at compile time.
/// The CI workflow builds fmail-core.exe via PyInstaller before `tauri build`,
/// so this path is always valid in the release pipeline.
#[cfg(target_os = "windows")]
static CORE_BYTES: &[u8] = include_bytes!(
    "../binaries/fmail-core-x86_64-pc-windows-msvc.exe"
);

// ── helpers ────────────────────────────────────────────────────────────────

fn session_hex() -> String {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .subsec_nanos();
    let pid = std::process::id();
    format!("{:08x}{:08x}", pid, nanos)
}

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

/// Kill by exe name — used at startup and on exit.
fn kill_core_by_name() {
    #[cfg(target_os = "windows")]
    for name in &["fmail-core-x86_64-pc-windows-msvc.exe", "fmail-core.exe"] {
        let _ = Command::new("taskkill")
            .args(["/F", "/IM", name])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
    }
}

/// Full startup kill: port-based + name-based, then wait until port is free.
fn kill_existing_core() {
    #[cfg(target_os = "windows")]
    {
        // Stage 1 — kill by port
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
            .stdout(Stdio::null()).stderr(Stdio::null()).status();

        // Stage 2 — kill by name
        kill_core_by_name();

        // Remove any leftover fmail-core*.exe from the %LOCALAPPDATA% install dir
        // (previous versions placed the sidecar next to FMailSender.exe).
        if let Ok(local) = std::env::var("LOCALAPPDATA") {
            let app_dir = PathBuf::from(local).join("FMailSender");
            for name in &["fmail-core-x86_64-pc-windows-msvc.exe", "fmail-core.exe"] {
                let p = app_dir.join(name);
                if p.exists() {
                    let _ = std::fs::remove_file(&p);
                }
            }
        }

        // Wait until port is confirmed free (up to 5 s), then 300 ms extra.
        let deadline = Instant::now() + Duration::from_secs(5);
        loop {
            thread::sleep(Duration::from_millis(200));
            if TcpStream::connect((CORE_HOST, CORE_PORT)).is_err() {
                thread::sleep(Duration::from_millis(300));
                break;
            }
            if Instant::now() >= deadline {
                break;
            }
        }
    }
}

// ── core extraction & spawn ────────────────────────────────────────────────

/// Extract the embedded fmail-core binary to a session-specific temp directory.
/// Returns the path of the extracted exe, or None on error.
#[cfg(target_os = "windows")]
fn extract_core() -> Option<PathBuf> {
    let tmp = std::env::temp_dir().join(format!("fmailsender-{}", session_hex()));
    std::fs::create_dir_all(&tmp).ok()?;

    let exe_path = tmp.join("fmail-core.exe");
    let mut f = std::fs::File::create(&exe_path).ok()?;
    f.write_all(CORE_BYTES).ok()?;
    drop(f);

    Some(exe_path)
}

#[cfg(not(target_os = "windows"))]
fn extract_core() -> Option<PathBuf> {
    None // only Windows is supported
}

fn spawn_core_from(path: &PathBuf) -> Option<Child> {
    Command::new(path)
        .env("FMAIL_PORT", CORE_PORT.to_string())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .ok()
}

// ── cleanup ────────────────────────────────────────────────────────────────

fn delete_temp_core(path: &PathBuf) {
    let _ = std::fs::remove_file(path);
    if let Some(dir) = path.parent() {
        let _ = std::fs::remove_dir(dir);
    }
}

// ── Tauri command ──────────────────────────────────────────────────────────

#[tauri::command]
fn get_core_url() -> String {
    format!("http://{}:{}", CORE_HOST, CORE_PORT)
}

// ── main ───────────────────────────────────────────────────────────────────

fn main() {
    let core_handle:   Arc<Mutex<Option<Child>>>   = Arc::new(Mutex::new(None));
    let temp_exe_path: Arc<Mutex<Option<PathBuf>>> = Arc::new(Mutex::new(None));

    let core_for_event = Arc::clone(&core_handle);
    let temp_for_event = Arc::clone(&temp_exe_path);

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(move |_app| {
            // 1. Kill any leftover core (port + name + port-free wait).
            kill_existing_core();

            // 2. Extract embedded binary to temp.
            let core_path = match extract_core() {
                Some(p) => p,
                None => {
                    eprintln!("[FMailSender] Failed to extract fmail-core to temp dir");
                    return Ok(());
                }
            };

            // 3. Store temp path so we can delete it on exit.
            *temp_exe_path.lock().unwrap() = Some(core_path.clone());

            // 4. Spawn core from temp location.
            let child = spawn_core_from(&core_path);
            *core_handle.lock().unwrap() = child;

            // 5. Background thread waits for core to become ready.
            //    The UI (StartupOverlay) polls /api/health independently.
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
                // Kill tracked child (current session).
                if let Ok(mut guard) = core_for_event.lock() {
                    if let Some(mut child) = guard.take() {
                        let _ = child.kill();
                    }
                }
                // Belt-and-suspenders: kill any orphaned core by name.
                kill_core_by_name();

                // Delete the temp exe and its directory.
                if let Ok(mut guard) = temp_for_event.lock() {
                    if let Some(path) = guard.take() {
                        delete_temp_core(&path);
                    }
                }
            }
        })
        .invoke_handler(tauri::generate_handler![get_core_url])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
