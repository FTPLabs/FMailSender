// FMailSender Tauri shell v6.0.5
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::TcpStream;
use std::path::PathBuf;
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

/// Kill any leftover fmail-core process so the new sidecar can bind port 7531.
///
/// Problem this solves: after installing a new version, the old fmail-core.exe
/// from a previous session may still be running and holding port 7531.
/// Tauri's wait_for_core() then sees the port open and considers the core
/// "started" — but the UI is talking to the OLD server with stale state and
/// old code (including any bugs that were already fixed in the new build).
/// Killing first guarantees the new binary is the one that answers on 7531.
fn kill_existing_core() {
    #[cfg(target_os = "windows")]
    {
        for name in &["fmail-core-x86_64-pc-windows-msvc.exe", "fmail-core.exe"] {
            let _ = Command::new("taskkill")
                .args(["/F", "/IM", name])
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status();
        }
        // Give the OS a moment to free the socket before spawning the new process
        thread::sleep(Duration::from_millis(800));
    }
}

/// Returns candidate directories to search for the sidecar binary.
/// Order: (1) Tauri resource_dir — correct for NSIS-installed bundles,
///        (2) current exe's own directory — correct for portable / no-bundle builds.
fn sidecar_search_dirs(app: &tauri::App) -> Vec<PathBuf> {
    let mut dirs: Vec<PathBuf> = Vec::new();

    // 1. Tauri resource directory (NSIS install dir / bundle resources)
    if let Ok(p) = app.path().resource_dir() {
        dirs.push(p);
    }

    // 2. Directory that contains the running executable (portable mode)
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
        // Tauri sidecar naming convention: <name>-<target-triple>.exe
        let msvc = dir.join("fmail-core-x86_64-pc-windows-msvc.exe");
        if msvc.exists() {
            return Command::new(&msvc)
                .env("FMAIL_PORT", CORE_PORT.to_string())
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .spawn()
                .ok();
        }
        // Bare name fallback (portable / extracted builds)
        let bare = dir.join("fmail-core.exe");
        if bare.exists() {
            return Command::new(&bare)
                .env("FMAIL_PORT", CORE_PORT.to_string())
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .spawn()
                .ok();
        }
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
            // Kill any leftover core process from a previous session or version
            // BEFORE spawning the new sidecar. Fixes the upgrade scenario where
            // the old fmail-core.exe is still bound to port 7531, causing Tauri
            // to connect to the old server instead of the freshly-built one.
            kill_existing_core();

            let child = spawn_python_core(app);
            *core_handle.lock().unwrap() = child;

            let timeout = Duration::from_secs(STARTUP_TIMEOUT_SECS);
            if !wait_for_core(timeout) {
                eprintln!(
                    "[FMailSender] Python core did not start within {}s",
                    STARTUP_TIMEOUT_SECS
                );
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
