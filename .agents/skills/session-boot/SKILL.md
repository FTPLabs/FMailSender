# Session Boot — FMailSender v6

  ## Architecture

  ```
  core/server.py    FastAPI REST API → localhost:7531 (all endpoints here)
  core/models.py    SmtpAccount, Recipient, CampaignConfig, CampaignStatus
  core/storage.py   Encrypted disk persistence (data/*.json + Fernet)
  core/proxy.py     ProxyManager: parse/rotate/check SOCKS5+HTTP
  core/validator.py validate_account (wraps sender.py test_smtp_connection)
  core/sender.py    SMTP engine — DO NOT RESTRUCTURE, duck-compat with models.py
  main.py           uvicorn entry on :7531
  src-tauri/        Rust shell → spawns main.py, shows WebView2
  ui/src/           React + Vite + Tailwind
    api.ts          All HTTP calls to :7531 go here
    pages/          Dashboard Accounts Recipients Compose Sending Inbox
  ARCHITECTURE.md   AI-readable map of every file
  ```

  ## Duck-compatibility (models.py ↔ sender.py)

  sender.py SmtpAccount fields = models.py SmtpAccount fields.
  Pass models.py instances directly to test_smtp_connection() and SendingEngine.
  Fields: email, password, host, port, use_ssl, use_tls, display_name,
  daily_limit, hourly_limit, is_active, proxy, access_token, refresh_token,
  token_expires_at, imap_host, imap_port, imap_ssl

  ## SendingEngine API

  ```python
  engine = SendingEngine(accounts=active, config=SenderConfig(...),
      recipients=sender_recipients, template=EmailTemplate(...), stop_event=threading.Event())
  engine.on_progress = lambda sent, total, result: ...
  engine.on_finished = lambda results: ...
  engine._paused = True/False   # pause/resume
  engine.stop_event.set()       # stop
  threading.Thread(target=engine.run, daemon=True).start()  # run() is SYNC
  ```

  ## Agent rules

  - Add endpoint → core/server.py only
  - Change model → core/models.py only
  - Change SMTP → core/sender.py only (careful)
  - Change proxy → core/proxy.py only
  - Change UI color → ui/src/theme.ts only
  - Push to GitHub → always use Git Tree API (see github-push skill)
  