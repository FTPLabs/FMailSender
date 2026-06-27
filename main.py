"""
FMailSender v6.0 — Entry point.
Starts the FastAPI server (core/server.py) on localhost:7531.
Tauri main.rs spawns this as a sidecar subprocess.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("FMAIL_PORT", "7531"))
    uvicorn.run(
        "core.server:app",
        host="127.0.0.1",
        port=port,
        log_level="warning",
        reload=False,
    )
