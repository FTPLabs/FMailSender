---
name: Lazy sender import
description: core.sender is loaded lazily via _get_sender() to avoid 5-15s AV scan at startup; _engine type is Optional[Any].
---

## Rule

`core.sender` must NOT be imported at module-level in `core/server.py`.
Use the `_get_sender()` function to access it; `_engine` is typed `Optional[Any]` at import time.

**Why:** `core.sender` is 2000+ lines and transitively imports `aiosmtplib`, `dnspython`, `dkim`,
and `oauth2` libraries. Loading at FastAPI startup adds 5-15 s of import time AND increases
the AV scanner surface on first run (AV scans each new .py/.pyc file). Lazy-loading defers
this cost until the first SMTP test or campaign start, when the user has already
interacted with the UI.

**How to apply:**
- Any code in `server.py` that needs a type from `core.sender` (e.g. `SendingEngine`,
  `Recipient`, `CampaignConfig`, `EmailTemplate`, `get_smtp_config_for_domain`,
  `test_smtp_connection`) must access it as `_get_sender().TypeName` at runtime.
- Do NOT write `from core.sender import ...` at the top of `server.py`.
- The `_get_sender()` function caches the module in `_sender_module` (module-level variable).
  Thread-safe: Python's import lock prevents double-import; worst case is benign redundant
  assignment to the same object.
- `_engine: Optional[Any]` — add a comment `# type at runtime: core.sender.SendingEngine`
  for documentation purposes.
