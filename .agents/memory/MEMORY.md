## FMailSender — Agent Memory v7.1.3

    - [Build: Embedded CPython arch](build-decision.md) — v7.1+ uses Embedded CPython (official PSF python.exe, digitally signed). PyInstaller/Nuitka removed.
    - [Core startup failure causes](core-startup.md) — PORT_WAIT_SECS=150 (90 was too short). SPAWN_ALIVE_CHECK_S=10. Version mismatch causes infinite reload.
    - [Version sync rule](version-sync.md) — ALL 4 files must match: core/_version.py, ui/src/version.ts, tauri.conf.json, Cargo.toml. Mismatch = infinite reload.
    - [HWID binding architecture](hwid-binding.md) — get_hwid() returns first stable source (MachineGuid > WMI UUID > CPU > PowerShell > MAC). Never mix sources.
    - [Startup log](startup-log.md) — fmail-core writes %LOCALAPPDATA%\FMailSender\startup.log. Tauri reads it on failure.
    