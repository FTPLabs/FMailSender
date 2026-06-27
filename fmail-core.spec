# -*- mode: python ; coding: utf-8 -*-
"""
FMailSender — PyInstaller spec for the Python core (FastAPI server).
Output: fmail-core.exe  (run by Tauri as a sidecar on localhost:7531)

Build command (from repo root):
  pyinstaller fmail-core.spec --distpath src-tauri/binaries --noconfirm
"""
import sys
from pathlib import Path

ROOT = Path(SPECPATH)

# ── Hidden imports required by FastAPI / uvicorn ─────────────────────────────
UVICORN_HIDDEN = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
]

FASTAPI_HIDDEN = [
    "fastapi",
    "fastapi.middleware.cors",
    "pydantic",
    "pydantic.v1",
    "anyio",
    "anyio._backends._asyncio",
    "anyio._backends._trio",
    "starlette",
    "starlette.middleware",
    "starlette.middleware.cors",
    "email_validator",
    "h11",
]

CRYPTO_HIDDEN = [
    "cryptography",
    "cryptography.fernet",
    "cryptography.hazmat.primitives.ciphers",
    "cryptography.hazmat.backends.openssl",
]

SMTP_HIDDEN = [
    "aiosmtplib",
    "dns",
    "dns.resolver",
    "socks",
    "sockshandler",
]

WINDOWS_HIDDEN = [
    "win32com",
    "win32com.client",
    "wmi",
    "win32api",
    "win32con",
]

ALL_HIDDEN = (
    UVICORN_HIDDEN + FASTAPI_HIDDEN + CRYPTO_HIDDEN + SMTP_HIDDEN + WINDOWS_HIDDEN + [
        "asyncio",
        "threading",
        "smtplib",
        "imaplib",
        "ssl",
        "socket",
    ]
)

# Build datas list — only include directories that exist
datas = [(str(ROOT / "core"), "core")]
if (ROOT / "data").exists():
    datas.append((str(ROOT / "data"), "data"))
if (ROOT / "i18n").exists():
    datas.append((str(ROOT / "i18n"), "i18n"))

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=ALL_HIDDEN,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PyQt6", "PyQt6.QtWidgets", "PyQt6.QtCore", "PyQt6.QtGui",
        "tkinter", "matplotlib", "numpy", "pandas", "scipy",
        "PIL", "Pillow", "openpyxl", "reportlab",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

# PyInstaller >= 6.0: no cipher= argument
pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="fmail-core",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
