// FMailSender Tauri shell v6.0
  // Spawns Python core (localhost:7531), then shows the WebView UI.
  #![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

  use std::net::TcpStream;
  use std::process::{Child, Command, Stdio};
  use std::sync::Mutex;
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
  fn spawn_python_core(app: &tauri::App) -> Option<Child> {
      let resource_path = app.path().resource_dir().ok()?;
      
      // In production: look for bundled fmail-core.exe sidecar
      let sidecar = resource_path.join("fmail-core.exe");
      if sidecar.exists() {
          return Command::new(&sidecar)
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
      tauri::Builder::default()
          .plugin(tauri_plugin_shell::init())
          .plugin(tauri_plugin_dialog::init())
          .plugin(tauri_plugin_fs::init())
          .manage(PythonCore(Mutex::new(None)))
          .setup(|app| {
              // Spawn Python core
              let child = spawn_python_core(app);
              *app.state::<PythonCore>().0.lock().unwrap() = child;

              // Wait for core to start
              let timeout = Duration::from_secs(STARTUP_TIMEOUT_SECS);
              if !wait_for_core(timeout) {
                  eprintln!("[FMailSender] WARNING: Python core did not start in time");
              }

              Ok(())
          })
          .on_window_event(|window, event| {
              if let tauri::WindowEvent::CloseRequested { .. } = event {
                  // Kill Python core when window closes
                  if let Some(state) = window.try_state::<PythonCore>() {
                      if let Ok(mut guard) = state.0.lock() {
                          if let Some(mut child) = guard.take() {
                              let _ = child.kill();
                          }
                      }
                  }
              }
          })
          .invoke_handler(tauri::generate_handler![get_core_url])
          .run(tauri::generate_context!())
          .expect("error while running tauri application");
  }
  