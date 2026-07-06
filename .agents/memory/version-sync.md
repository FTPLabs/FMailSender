---
    name: version-sync
    description: Правило синхронизации версий — все 4 файла должны совпадать
    ---

    # Version Sync Rule

    ALL 4 files MUST have the same version string:
    1. core/_version.py → APP_VERSION = "X.Y.Z"
    2. ui/src/version.ts → FRONTEND_VERSION = "X.Y.Z"  
    3. src-tauri/tauri.conf.json → "version": "X.Y.Z"
    4. src-tauri/Cargo.toml → version = "X.Y.Z"

    **Why:** StartupOverlay compares FRONTEND_VERSION with APP_VERSION from /api/health.
    Mismatch → window.location.reload() → infinite reload loop.

    **How:** CI "Sync version" step updates all automatically. For manual changes — update all 4 at once.
    