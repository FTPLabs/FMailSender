## FMailSender — Agent Memory v7.0.0

- [Build: PyInstaller vs Nuitka](build-decision.md) — v7 switched back to PyInstaller 6.21 (2-4 min) from Nuitka (60+ min). Nuitka = C compilation = slow CI.
- [Core startup failure causes](core-startup.md) — ModuleNotFoundError (missing hiddenimports), AV blocking exe, port 7531 conflict, license crash before uvicorn binds.
- [HWID binding architecture](hwid-binding.md) — get_hwid() returns first stable source (MachineGuid > WMI UUID > CPU > PowerShell > MAC). Never mix sources.
- [Security: /api/v2/verify](security-endpoints.md) — new v2 endpoints in server/bot.py. Verify HWID + fingerprint on every startup. Bind HWID on first run.
- [Startup log](startup-log.md) — fmail-core writes %LOCALAPPDATA%\FMailSender\startup.log. Tauri reads it on failure for diagnostics.
