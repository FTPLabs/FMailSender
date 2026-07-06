## FMailSender — Agent Memory v7.1.5

- [Build: Embedded CPython arch](build-decision.md) — v7.1+ uses Embedded CPython (official PSF python.exe, digitally signed). PyInstaller/Nuitka removed.
- [Core startup timeouts](core-startup.md) — PORT_WAIT_SECS=300, SPAWN_ALIVE_CHECK_S=10. Version mismatch causes infinite reload.
- [Version sync rule](version-sync.md) — ALL 5 files must match: core/_version.py, ui/src/version.ts, tauri.conf.json, Cargo.toml, ui/package.json. Mismatch = infinite reload.
- [HWID binding architecture](hwid-binding.md) — get_hwid() returns first stable source (MachineGuid > WMI UUID > CPU > PowerShell > MAC). Never mix sources.
- [Startup log](startup-log.md) — fmail-core writes %LOCALAPPDATA%\FMailSender\startup.log. Tauri reads it on failure.
- [Lazy sender import](lazy-sender-import.md) — core.sender loaded via _get_sender() to avoid 5-15s startup cost; _engine type is Optional[Any] at import time.
- [VPS deploy: pip install required](deploy-pip.md) — release.yml deploy step must run pip3 install after git reset --hard; without it VPS misses new dependencies.
- [SSH action version](ssh-action.md) — use appleboy/ssh-action@v1.2.5 (v1.0.3 had signal/timeout issues in CI deploy).
