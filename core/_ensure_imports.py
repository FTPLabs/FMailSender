"""
FMailSender — Explicit import guard.

Originally written for PyInstaller, which required explicit imports
to include lazily-loaded modules in the bundle.

With Nuitka (v6.9.2+), static analysis is more thorough and usually
finds lazy imports automatically. We keep this file for:
  1. Dev-mode compatibility (importing this is harmless)
  2. Fallback if Nuitka misses any import
  3. Documentation of all runtime dependencies

DO NOT remove imports from this file without verifying the frozen exe works.

ROOT CAUSE NOTE (v6.7.7):
  core.license and requests were both lazy-imported inside try blocks,
  making them INVISIBLE to PyInstaller static analysis. Missing requests
  caused _validate_online() to always raise ImportError -> "offline: True"
  -> 7-day grace period -> license bypass. Missing core.license caused
  ImportError in lifespan -> _set_license_ok(True) -> all users admitted.
"""

# ── License module ────────────────────────────────────────────────────────────
import core.license                         # noqa: F401

# ── requests ──────────────────────────────────────────────────────────────────
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

# ── email.mime (required by smtplib / aiosmtplib) ─────────────────────────────
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

# ── FastAPI / Starlette internals ─────────────────────────────────────────────
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
