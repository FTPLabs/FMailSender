# Changelog

  All notable changes are documented here.

  ---

  ## [2.0.0] — 2025-06-11 — Premium Visual Overhaul

  ### Visual
  - New **Aether Dark** premium color palette: deep violet #8B5CF6 + hot-rose #EC4899 gradient
  - Updated entire QSS stylesheet across all screens, modals, dialogs, toasts
  - Progress bars, buttons, tabs now use violet→rose gradient
  - Activation screen: gradient CTA button with glow border

  ### Assets
  - Phase 2: SVG logo (envelope + gradient fill) embedded in activation screen
  - Custom in-app icon set (20 icons) as inline SVG in `gui/app.py`
  - Sidebar nav icons updated to new stroke colors

  ### Fixes
  - **build.py**: `APP_VERSION` was hardcoded as "1.0.0"; now imported from `core._version`
  - **core/license.py**: activation payload now sends real `APP_VERSION` (was "1.0.0")
  - **core/license.py**: `_load_license_data` now logs on decrypt error instead of silently returning `None`
  - **core/license.py**: `ESP_HWID_SALT` missing env now raises `WARNING` (was `DEBUG`)
  - **core/sender.py**: fixed regex `<brs*/?> ` (stray space) in `_html_to_text` — `<br>` tags now correctly become newlines
  - **core/sender.py**: `SMTP_CONFIGS` dict moved from inside function to module level — eliminates per-call allocation
  - **gui/screens/screen_sending.py**: `_speed_timer.start()` was never called — speed KPI now updates every 5 s
  - **core/spam_checker.py**: all `dns.resolver.resolve()` calls now have `lifetime=5` timeout — no more hangs on slow DNS
  - **requirements.txt**: removed unused `PyQt6-WebEngine` (~150 MB); moved `pyinstaller` to `requirements-dev.txt`

  ### Performance
  - SMTP config lookup is O(1) dict lookup (was O(n) re-allocation)
  - DNS checks time-bounded to 5 s maximum per call

  ---

  ## [1.0.1] — 2025-06-10

  - Initial public release
  