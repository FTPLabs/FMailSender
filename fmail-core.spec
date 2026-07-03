# -*- mode: python ; coding: utf-8 -*-
"""
FMailSender — PyInstaller 6.21 spec  (FAST BUILD: 2-4 min)
============================================================
ПЕРЕХОД С NUITKA → PYINSTALLER 6.21

Проблема:  Nuitka 2.6.x компилирует Python → C → EXE,  60+ мин на GitHub Actions.
Решение:   PyInstaller 6.21 только упаковывает байткод — 2-4 мин.
           PyInstaller 6.x «Parallel Metadata Scanning» — ещё быстрее.

Запуск (из корня репо):
  pyinstaller fmail-core.spec --noconfirm --distpath src-tauri/binaries

После сборки Tauri ожидает sidecar по имени:
  src-tauri/binaries/fmail-core-x86_64-pc-windows-msvc.exe
CI-шаг «Rename sidecar» делает это автоматически.
"""
import sys
from pathlib import Path

ROOT = Path(SPECPATH)

# ── Hidden imports ────────────────────────────────────────────────────────────
# PyInstaller не находит динамические импорты uvicorn / anyio / fastapi.
# Без них сервер крашится с ModuleNotFoundError — главная причина
# «ядро не запускается» при Nuitka/PyInstaller без явных хинтов.

UVICORN_HIDDEN = [
    "uvicorn",
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
    "uvicorn.config",
    "uvicorn.main",
]

FASTAPI_HIDDEN = [
    "fastapi",
    "fastapi.middleware",
    "fastapi.middleware.cors",
    "fastapi.responses",
    "fastapi.routing",
    "fastapi.security",
    "fastapi.staticfiles",
    "fastapi.templating",
    "pydantic",
    "pydantic.v1",
    "pydantic_core",
    "anyio",
    "anyio._backends",
    "anyio._backends._asyncio",
    "anyio._backends._trio",
    "anyio.streams",
    "anyio.streams.memory",
    "starlette",
    "starlette.middleware",
    "starlette.middleware.cors",
    "starlette.routing",
    "starlette.responses",
    "starlette.staticfiles",
    "email_validator",
    "h11",
    "h11._readers",
    "h11._writers",
    "httptools",
]

CRYPTO_HIDDEN = [
    "cryptography",
    "cryptography.fernet",
    "cryptography.hazmat",
    "cryptography.hazmat.primitives",
    "cryptography.hazmat.primitives.ciphers",
    "cryptography.hazmat.primitives.kdf",
    "cryptography.hazmat.primitives.kdf.pbkdf2",
    "cryptography.hazmat.primitives.hashes",
    "cryptography.hazmat.primitives.padding",
    "cryptography.hazmat.backends",
    "cryptography.hazmat.backends.openssl",
    "cryptography.hazmat.backends.openssl.backend",
]

EMAIL_HIDDEN = [
    "email",
    "email.mime",
    "email.mime.application",
    "email.mime.audio",
    "email.mime.base",
    "email.mime.image",
    "email.mime.message",
    "email.mime.multipart",
    "email.mime.nonmultipart",
    "email.mime.text",
    "email.generator",
    "email.parser",
    "email.policy",
    "email.headerregistry",
    "email.contentmanager",
    "email.encoders",
    "email.charset",
    "email.header",
    "email.utils",
    "email.message",
    "email.errors",
    "email.feedparser",
    "email.iterators",
    "email.quoprimime",
    "email.base64mime",
    "email._parseaddr",
]

AIOSMTPLIB_HIDDEN = [
    "aiosmtplib",
    "aiosmtplib.connection",
    "aiosmtplib.errors",
    "aiosmtplib.response",
    "aiosmtplib.smtp",
    "aiosmtplib.status",
    "aiosmtplib.protocol",
    "aiosmtplib.compat",
]

SOCKS_HIDDEN = [
    "socks",
    "sockshandler",
    "PySocks",
]

DKIM_HIDDEN = [
    "dkim",
    "authheaders",
    "dns",
    "dns.resolver",
    "dns.rdatatype",
]

REQUESTS_HIDDEN = [
    "requests",
    "requests.adapters",
    "requests.auth",
    "requests.models",
    "requests.sessions",
    "urllib3",
    "urllib3.util",
    "urllib3.util.retry",
    "urllib3.util.ssl_",
    "urllib3.poolmanager",
    "certifi",
    "charset_normalizer",
    "idna",
]

JWT_HIDDEN = [
    "jwt",
    "jwt.algorithms",
    "jwt.exceptions",
]

WIN32_HIDDEN = [
    "win32api",
    "win32con",
    "win32com",
    "win32com.client",
    "winreg",
    "wmi",
    "pythoncom",
    "pywintypes",
    "win32security",
    "win32net",
]

ASYNCIO_HIDDEN = [
    "asyncio",
    "asyncio.selector_events",
    "asyncio.proactor_events",
    "asyncio.windows_events",
    "asyncio.windows_utils",
    "concurrent.futures",
    "concurrent.futures.thread",
    "concurrent.futures.process",
    "multiprocessing",
    "multiprocessing.pool",
]

ALL_HIDDEN = (
    UVICORN_HIDDEN + FASTAPI_HIDDEN + CRYPTO_HIDDEN + EMAIL_HIDDEN +
    AIOSMTPLIB_HIDDEN + SOCKS_HIDDEN + DKIM_HIDDEN + REQUESTS_HIDDEN +
    JWT_HIDDEN + WIN32_HIDDEN + ASYNCIO_HIDDEN + [
        "logging.handlers",
        "xml.etree.ElementTree",
        "zipimport",
        "pkgutil",
        "importlib.metadata",
        "importlib.resources",
        "importlib.resources._adapters",
        "importlib.resources._compat",
        "importlib.resources.readers",
        "importlib.resources.simple",
        "platform",
        "socket",
        "ssl",
        "queue",
        "threading",
        "subprocess",
        "hashlib",
        "hmac",
        "base64",
        "json",
        "time",
        "uuid",
        "re",
        "os",
        "sys",
        "pathlib",
        "typing",
        "typing_extensions",
        "dataclasses",
        "enum",
        "abc",
        "copy",
        "io",
        "collections",
        "functools",
        "itertools",
        "contextlib",
        "weakref",
        "inspect",
        "ast",
        "textwrap",
        "struct",
        "array",
    ]
)

block_cipher = None

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    ["main.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # HTML email шаблоны
        (str(ROOT / "templates"), "templates"),
        # i18n строки (если есть)
        *(([(str(ROOT / "i18n"), "i18n")] if (ROOT / "i18n").exists() else [])),
    ],
    hiddenimports=ALL_HIDDEN,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # КРИТИЧНО: исключить тяжёлые пакеты, которых нет в требованиях
    # Это главная причина долгих сборок — PyInstaller сканирует всё подряд
    excludes=[
        # GUI фреймворки
        "tkinter", "tkinter.ttk", "_tkinter",
        "PyQt5", "PyQt6", "PySide2", "PySide6",
        "wx", "gi", "GTK",
        # Data Science (не используется в mailer)
        "matplotlib", "numpy", "pandas", "scipy", "sklearn",
        "tensorflow", "torch", "keras",
        "PIL", "Pillow",
        # Jupyter / IPython
        "IPython", "jupyter", "notebook", "nbformat",
        "ipykernel", "ipywidgets",
        # Cloud SDKs
        "boto3", "botocore", "s3transfer",
        "google.cloud", "google.api_core",
        "azure", "azure.core",
        # Test infrastructure
        "pytest", "unittest",
        "_pytest",
        # Build tools
        "setuptools._vendor", "pkg_resources._vendor",
        "distutils",
        "docutils", "sphinx",
        # Unused DB
        "sqlalchemy", "alembic", "django", "flask",
        # Unused heavy deps
        "lxml",
        "openpyxl",
        "xlrd", "xlwt",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    # PyInstaller 6.x: оптимизация байткода
    optimize=2,
)

# Удалить ненужные data entries
a.datas = [
    (dst, src, t) for (dst, src, t) in a.datas
    if not any(x in dst.lower() for x in [
        "node_modules", ".venv", "venv", "__pycache__",
        ".git", "/test/", "/tests/", "docs/", "doc/",
        "example/", "examples/", "sample/",
        "matplotlib", "numpy", "pandas",
    ])
]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── EXE (onefile) ─────────────────────────────────────────────────────────────
# onefile: Tauri встраивает один .exe через include_bytes!
# PyInstaller onefile при запуске распаковывается в %TEMP%\..._MEIXXXXX
# Но только при первом запуске с данным хешом. Warm start — мгновенный.
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
    upx=False,          # UPX выключен: -40% времени сборки, меньше AV ложных срабатываний
    upx_exclude=[],
    runtime_tmpdir=None,  # Стандартный %TEMP% — PyInstaller кеширует по хешу автоматически
    console=True,          # console=True: stderr/stdout видны в логах Tauri
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # version info
    version=None,
    uac_admin=False,
    uac_uiaccess=False,
)
