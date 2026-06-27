// FMailSender Tauri shell v6.0
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::TcpStream;
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};
use tauri::Manager;

const CORE_PORT: u16 = 7531;
const CORE_HOST: &str = "127.0.0.1";
const STARTUP_TIMEOUT_SECS: u64 = 30;

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

fn spawn_python_core(app: &tauri::App) -> Option<Child> {
    let resource_path = app.path().resource_dir().ok()?;

    // Production: bundled PyInstaller binary (Tauri v2 sidecar naming)
    let sidecar = resource_path.join("fmail-core-x86_64-pc-windows-msvc.exe");
    if sidecar.exists() {
        return Command::new(&sidecar)
            .env("FMAIL_PORT", CORE_PORT.to_string())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .ok();
    }

    // Fallback: bare name
    let bare = resource_path.join("fmail-core.exe");
    if bare.exists() {
        return Command::new(&bare)
            .env("FMAIL_PORT", CORE_PORT.to_string())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .ok();
    }

    // Dev mode: python main.py from project root
    let python = if cfg!(target_os = "windows") { "python" } else { "python3" };
    Command::new(python)
        .arg("main.py")
        .current_dir(std::env::current_dir().unwrap_or_default())
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
    let core_handle: Arc<Mutex<Option<Child>>> = Arc::new(Mutex::new(None));
    let core_for_event = Arc::clone(&core_handle);

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(move |app| {
            let child = spawn_python_core(app);
            *core_handle.lock().unwrap() = child;

            let timeout = Duration::from_secs(STARTUP_TIMEOUT_SECS);
            if !wait_for_core(timeout) {
                eprintln!("[FMailSender] Python core did not start within {}s", STARTUP_TIMEOUT_SECS);
            }
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
