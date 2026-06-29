// FMailSender Tauri shell v6.0.7
// Fix: window now appears immediately; core startup wait moved to background thread.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};
use tauri::Manager;

const CORE_PORT:            u16 = 7531;
const CORE_HOST:            &str = "127.0.0.1";
const STARTUP_TIMEOUT_SECS: u64 = 60;

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

/// Kill any process listening on CORE_PORT, then also kill by exe name.
///
/// Two-stage kill:
///   1. Port-based (PowerShell Get-NetTCPConnection) — handles upgrade scenario
///      where the old process lives at a different path.
///   2. Name-based (taskkill /IM) — belt-and-suspenders fallback.
///
/// The 300 ms sleep gives Windows time to release the TCP socket and
/// flush file handles. 300 ms is sufficient in practice; 1000 ms was
/// overly conservative and added visible startup latency.
fn kill_existing_core() {
    #[cfg(target_os = "windows")]
    {
        // Stage 1 — kill by port
        let _ = Command::new("powershell")
            .args([
                "-NoProfile",
                "-NonInteractive",
                "-WindowStyle",
                "Hidden",
                "-Command",
                &format!(
                    "$pids = (Get-NetTCPConnection -LocalPort {port} -State Listen \
                     -ErrorAction SilentlyContinue | \
                     Select-Object -ExpandProperty OwningProcess -ErrorAction SilentlyContinue); \
                     if ($pids) {{ foreach ($p in @($pids)) {{ \
                       Stop-Process -Id $p -Force -ErrorAction SilentlyContinue }} }}",
                    port = CORE_PORT
                ),
            ])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();

        // Stage 2 — kill by exe name
        for name in &["fmail-core-x86_64-pc-windows-msvc.exe", "fmail-core.exe"] {
            let _ = Command::new("taskkill")
                .args(["/F", "/IM", name])
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status();
        }

        // 300 ms is enough for Windows to release the listening socket and
        // close file handles on the old exe (was 1000 ms — unnecessarily long).
        thread::sleep(Duration::from_millis(300));
    }
}

/// Returns candidate directories to search for the sidecar binary.
fn sidecar_search_dirs(app: &tauri::App) -> Vec<PathBuf> {
    let mut dirs: Vec<PathBuf> = Vec::new();

    if let Ok(p) = app.path().resource_dir() {
        dirs.push(p);
    }

    if let Ok(exe) = std::env::current_exe() {
        if let Some(parent) = exe.parent() {
            let parent_buf = parent.to_path_buf();
            if !dirs.contains(&parent_buf) {
                dirs.push(parent_buf);
            }
        }
    }

    dirs
}

fn spawn_python_core(app: &tauri::App) -> Option<Child> {
    for dir in sidecar_search_dirs(app) {
        let msvc  = dir.join("fmail-core-x86_64-pc-windows-msvc.exe");
        let plain = dir.join("fmail-core.exe");

        let bin = if msvc.exists() {
            msvc
        } else if plain.exists() {
            plain
        } else {
            continue;
        };

        if let Some(child) = Command::new(&bin)
            .env("FMAIL_PORT", CORE_PORT.to_string())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .ok()
        {
            return Some(child);
        }
    }
    None
}

#[tauri::command]
fn get_core_url() -> String {
    format!("http://{}:{}", CORE_HOST, CORE_PORT)
}

fn main() {
    let core_handle: Arc<Mutex<Option<Child>>> = Arc::new(Mutex::new(None));
    let core_for_event = Arc::clone(&core_handle);

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(move |app| {
            // Kill leftover core before spawning the new sidecar.
            // This runs synchronously so we don't race with the new spawn.
            kill_existing_core();

            let child = spawn_python_core(app);
            *core_handle.lock().unwrap() = child;

            // KEY FIX: do NOT block setup() waiting for the Python core.
            //
            // Previously wait_for_core() was called here, which blocked the
            // Tauri main thread for up to 30 s — the OS reported the window as
            // "Not Responding" because no window was created yet.
            //
            // Now we return from setup() immediately so the window opens at once.
            // The UI (StartupOverlay + StatusContext) already handles the
            // "backend not ready yet" state with a loading screen and 500 ms
            // polling on /api/health until online=true.
            thread::spawn(move || {
                if !wait_for_core(Duration::from_secs(STARTUP_TIMEOUT_SECS)) {
                    eprintln!(
                        "[FMailSender] Python core did not start within {}s",
                        STARTUP_TIMEOUT_SECS
                    );
                }
                // Startup is logged; StatusContext polling handles the UI transition.
            });

            Ok(())
        })
        .on_window_event(move |_window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                if let Ok(mut guard) = core_for_event.lock() {
                    if let Some(mut child) = guard.take() {
                        let _ = child.kill();
                    }
                }
            }
        })
        .invoke_handler(tauri::generate_handler![get_core_url])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
