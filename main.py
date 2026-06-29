"""
FMailSender v6.0 — Entry point.
Starts the FastAPI server (core/server.py) on localhost:7531.
Tauri main.rs spawns this as a sidecar subprocess.

Environment variables:
  FMAIL_PORT  — TCP port to listen on (default: 7531)
  FMAIL_HOST  — bind host (default: 127.0.0.1)
               Override to 'localhost' on systems where VPN blocks 127.0.0.1 loopback.
               Do NOT set to 0.0.0.0 — the API has no authentication.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Must be imported before uvicorn — ensures PyInstaller bundles all lazy deps.
import core._ensure_imports  # noqa: F401, E402

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("FMAIL_PORT", "7531"))
    host = os.environ.get("FMAIL_HOST", "127.0.0.1")
    # Safety: never bind to a non-loopback address (no auth on this server)
    if not host.startswith("127.") and host not in ("localhost", "::1"):
        host = "127.0.0.1"
    uvicorn.run(
        "core.server:app",
        host=host,
        port=port,
        log_level="warning",
        reload=False,
    )
