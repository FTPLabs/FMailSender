// FMailSender Tauri shell v6.0
// Spawns Python core (localhost:7531), then shows the WebView UI.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::TcpStream;
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};
use tauri::{Manager, State};

const CORE_PORT: u16 = 7531;
const CORE_HOST: &str = "127.0.0.1";
const STARTUP_TIMEOUT_SECS: u64 = 30;

struct PythonCore(Mutex<Option<Child>>);

/// Wait until the Python FastAPI server is accepting connections.
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

/// Find the Python / core executable to launch.
/// BUG FIX: Tauri v2 bundles sidecar with platform suffix.
/// We try both the suffixed name (production) and bare python (dev).
fn spawn_python_core(app: &tauri::App) -> Option<Child> {
    let resource_path = app.path().resource_dir().ok()?;

    // In production: look for bundled fmail-core sidecar (with platform suffix)
    let suffixed = resource_path.join("fmail-core-x86_64-pc-windows-msvc.exe");
    if suffixed.exists() {
        return Command::new(&suffixed)
            .env("FMAIL_PORT", CORE_PORT.to_string())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .ok();
    }

    // Fallback: bare name without suffix (edge case)
    let bare = resource_path.join("fmail-core.exe");
    if bare.exists() {
        return Command::new(&bare)
            .env("FMAIL_PORT", CORE_PORT.to_string())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .ok();
    }

    // In development: run "python main.py" from project root
    let project_root = std::env::current_dir().unwrap_or_default();
    let python_bin = if cfg!(target_os = "windows") { "python" } else { "python3" };
    Command::new(python_bin)
        .arg("main.py")
        .current_dir(&project_root)
        .env("FMAIL_PORT", CORE_PORT.to_string())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .ok()
}

#[tauri::command]
fn get_core_url() -> String {
    format!("http://{}:{}", CORE_HOST, CORE_PORT)
}

fn main() {
    // Shared state — Arc so the on_window_event closure can own a reference
    let python_core = Arc::new(Mutex::new(None::<Child>));
    let python_core_for_event = Arc::clone(&python_core);

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .manage(PythonCore(Mutex::new(None)))
        .setup(move |app| {
            // Spawn Python core and store handle
            let child = spawn_python_core(app);
            *python_core.lock().unwrap() = child;

            // Wait for core to start (non-blocking — runs in background thread)
            let timeout = Duration::from_secs(STARTUP_TIMEOUT_SECS);
            if !wait_for_core(timeout) {
                eprintln!("[FMailSender] WARNING: Python core did not start within {}s", STARTUP_TIMEOUT_SECS);
            }

            Ok(())
        })
        .on_window_event(move |window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                // BUG FIX: use Arc-shared handle instead of try_state (unreliable in v2)
                if let Ok(mut guard) = python_core_for_event.lock() {
                    if let Some(mut child) = guard.take() {
                        let _ = child.kill();
                    }
                }
                window.destroy().ok();
            }
        })
        .invoke_handler(tauri::generate_handler![get_core_url])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
