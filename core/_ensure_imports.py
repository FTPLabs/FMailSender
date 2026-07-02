"""
FMailSender — Explicit import guard for PyInstaller.

PyInstaller performs static analysis to discover modules. Any module that is
loaded lazily at runtime (via importlib, __import__, or plugin mechanisms)
is invisible to the analyser and gets excluded from the bundle — causing
ModuleNotFoundError when the frozen exe runs.

Importing this module from main.py guarantees that every lazy dependency is
present in the bundle, because PyInstaller follows explicit import statements.

DO NOT remove imports from this file without verifying the frozen exe works.
Add new imports here whenever a new RuntimeError / ModuleNotFoundError appears.

ROOT CAUSE NOTE (v6.7.7):
  core.license and requests were both lazy-imported inside try blocks,
  making them INVISIBLE to PyInstaller static analysis. Missing requests
  caused _validate_online() to always raise ImportError -> "offline: True"
  -> 7-day grace period -> license bypass. Missing core.license caused
  ImportError in lifespan -> _set_license_ok(True) -> all users admitted.
"""

# ── License module (imported lazily inside try blocks in server.py) ───────────
# Without this, PyInstaller misses core.license entirely, causing lifespan
# ImportError → _set_license_ok(True) → all users bypassed without a key.
import core.license                         # noqa: F401

# ── requests (imported lazily inside _validate_online() in core/license.py) ───
# Without this, import requests raises ImportError at runtime → treated as
# "offline" → 7-day grace period fires → license check bypassed completely!
import requests                             # noqa: F401
import requests.adapters                    # noqa: F401
import requests.auth                        # noqa: F401
import requests.certs                       # noqa: F401
import requests.cookies                     # noqa: F401
import requests.exceptions                  # noqa: F401
import requests.models                      # noqa: F401
import requests.sessions                    # noqa: F401
import requests.structures                  # noqa: F401
import requests.utils                       # noqa: F401
import urllib3                              # noqa: F401
import urllib3.util.retry                   # noqa: F401
import urllib3.util.timeout                 # noqa: F401
import certifi                              # noqa: F401
import charset_normalizer                   # noqa: F401
import idna                                 # noqa: F401

# ── python-multipart (required by FastAPI for file/form uploads) ──────────────
import multipart                            # noqa: F401
import multipart.multipart                  # noqa: F401

# ── email.mime (required by smtplib / aiosmtplib for composing emails) ────────
import email.mime                           # noqa: F401
import email.mime.application               # noqa: F401
import email.mime.audio                     # noqa: F401
import email.mime.base                      # noqa: F401
import email.mime.image                     # noqa: F401
import email.mime.message                   # noqa: F401
import email.mime.multipart                 # noqa: F401
import email.mime.nonmultipart              # noqa: F401
import email.mime.text                      # noqa: F401
import email.encoders                       # noqa: F401
import email.header                         # noqa: F401
import email.utils                          # noqa: F401

# ── FastAPI / Starlette internals loaded lazily ───────────────────────────────
import fastapi.middleware.cors              # noqa: F401
import starlette.middleware.cors            # noqa: F401
import starlette.responses                  # noqa: F401
import starlette.routing                    # noqa: F401
import starlette.staticfiles                # noqa: F401

# ── uvicorn protocols (loaded by string name at startup) ──────────────────────
import uvicorn.protocols.http.h11_impl      # noqa: F401
import uvicorn.protocols.http.httptools_impl  # noqa: F401
import uvicorn.lifespan.on                  # noqa: F401
import uvicorn.lifespan.off                 # noqa: F401
import uvicorn.loops.asyncio                # noqa: F401

# ── Crypto ────────────────────────────────────────────────────────────────────
import cryptography.fernet                  # noqa: F401
import cryptography.hazmat.backends.openssl  # noqa: F401
import cryptography.hazmat.primitives.ciphers  # noqa: F401
