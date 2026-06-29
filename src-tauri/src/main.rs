// FMailSender Tauri shell v6.0.6
// Fixes: port-based process kill (handles renamed/relocated binary), tighter socket wait.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};
use tauri::Manager;

const CORE_PORT:           u16 = 7531;
const CORE_HOST:           &str = "127.0.0.1";
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

/// Kill any process that is listening on CORE_PORT, then also kill by exe name.
///
/// Why two-stage kill?
/// ─ Port-based kill (PowerShell Get-NetTCPConnection): handles the upgrade
///   scenario where the old process is renamed or lives in a different path.
///   It finds whichever PID holds port 7531 and terminates it.
/// ─ Name-based kill (taskkill /IM): belt-and-suspenders fallback for cases
///   where Get-NetTCPConnection fails or the binary isn't yet listening (rare).
///
/// A 1 second sleep after kills gives Windows time to release the TCP socket
/// and free file handles on the old exe before we try to write the new one.
fn kill_existing_core() {
    #[cfg(target_os = "windows")]
    {
        // Stage 1 — kill by port (most reliable; works regardless of exe name/path)
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

        // Stage 2 — kill by exe name (belt-and-suspenders)
        for name in &["fmail-core-x86_64-pc-windows-msvc.exe", "fmail-core.exe"] {
            let _ = Command::new("taskkill")
                .args(["/F", "/IM", name])
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status();
        }

        // Give the OS time to release the socket and flush file handles
        thread::sleep(Duration::from_millis(1000));
    }
}

/// Returns candidate directories to search for the sidecar binary.
/// Order: (1) Tauri resource_dir — correct for NSIS-installed bundles,
///        (2) current exe's own directory — correct for portable / no-bundle builds.
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
        // Tauri sidecar naming convention: <name>-<target-triple>.exe
        let msvc = dir.join("fmail-core-x86_64-pc-windows-msvc.exe");
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
            // Kill any leftover core process before spawning the new sidecar.
            // Uses port-based kill first (reliable on upgrade), then name-based.
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
