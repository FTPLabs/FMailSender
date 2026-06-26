# Tauri + FastAPI Architecture — FMailSender v6

  ## How it works

  ```
  [Windows user] opens FMailSender.exe
    → Tauri main.rs runs
    → Looks for fmail-core.exe in resource_dir() → spawns it (port 7531)
    → Falls back to: python main.py (dev mode)
    → Waits up to 30s for :7531 to accept connections
    → WebView2 loads embedded ui/dist/ (prod) or http://localhost:5173 (dev)
  ```

  ## Adding a new feature

  1. Add endpoint to core/server.py
  2. Add type to core/models.py if needed
  3. Add API call to ui/src/api.ts
  4. Add/update page in ui/src/pages/

  ## Dev workflow

  ```bash
  python main.py       # FastAPI on :7531
  cd ui && npm run dev # Vite on :5173 → open browser
  ```

  ## CORS

  allow_origins=["*"] — works in dev and prod (Tauri WebView).
  