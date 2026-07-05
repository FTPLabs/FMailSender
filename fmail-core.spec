# -*- mode: python ; coding: utf-8 -*-
"""
FMailSender — PyInstaller 6.21 spec  (ONEDIR mode — без AV-проблем)
====================================================================

v7.0.3: ПЕРЕХОД НА ONEDIR (папка вместо одного файла)

ПРОБЛЕМА onefile: при каждом запуске PyInstaller распаковывает Python-среду
в %TEMP%\PYINSTALLER_<hash>\ — AV сканирует temp и блокирует/замедляет процесс.
Даже кеш по хешу не помогает: AV пересчитывает по расписанию.

РЕШЕНИЕ onedir: Python-среда распаковывается ОДИН РАЗ при первом запуске
в %LOCALAPPDATA%\FMailSender\fmail-core\ через Tauri. После этого fmail-core.exe
запускается НАПРЯМУЮ из уже существующих файлов — никакой распаковки при старте.
AV сканирует файлы один раз, затем доверяет им как обычным приложениям.

Структура dist/fmail-core/:
  fmail-core.exe        ← запускаемый файл
  _internal/            ← Python dll, .pyd, данные (PyInstaller 6.x)
    python312.dll
    *.pyd
    ...

CI зипует папку dist/fmail-core/ → src-tauri/binaries/fmail-core.zip
Tauri встраивает ZIP через include_bytes! и распаковывает при первом запуске.
"""
import sys
from pathlib import Path

ROOT = Path(SPECPATH)

# ── Hidden imports ────────────────────────────────────────────────────────────
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

MULTIPART_HIDDEN = [
    "multipart",
    "multipart.multipart",
    "python_multipart",
    "starlette.formparsers",
    "starlette.datastructures",
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
    AIOSMTPLIB_HIDDEN + MULTIPART_HIDDEN + SOCKS_HIDDEN + DKIM_HIDDEN +
    REQUESTS_HIDDEN + JWT_HIDDEN + WIN32_HIDDEN + ASYNCIO_HIDDEN + [
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


# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    ["main.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "templates"), "templates"),
        *(([(str(ROOT / "i18n"), "i18n")] if (ROOT / "i18n").exists() else [])),
    ],
    hiddenimports=ALL_HIDDEN,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "tkinter.ttk", "_tkinter",
        "PyQt5", "PyQt6", "PySide2", "PySide6",
        "wx", "gi", "GTK",
        "matplotlib", "numpy", "pandas", "scipy", "sklearn",
        "tensorflow", "torch", "keras",
        "PIL", "Pillow",
        "IPython", "jupyter", "notebook", "nbformat",
        "ipykernel", "ipywidgets",
        "boto3", "botocore", "s3transfer",
        "google.cloud", "google.api_core",
        "azure", "azure.core",
        "pytest", "unittest", "_pytest",
        "setuptools._vendor", "pkg_resources._vendor",
        "docutils", "sphinx",
        "sqlalchemy", "alembic", "django", "flask",
        "lxml", "openpyxl", "xlrd", "xlwt",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
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

pyz = PYZ(a.pure, a.zipped_data)

# ── EXE (onedir — НЕТ runtime_tmpdir, НЕТ self-extracting) ───────────────────
# КЛЮЧЕВОЕ ОТЛИЧИЕ от onefile:
#   - exclude_binaries=True → binaries/datas идут в COLLECT, не в EXE
#   - Нет runtime_tmpdir — файлы не распаковываются при запуске
#   - fmail-core.exe просто запускает Python из уже существующих файлов рядом
exe = EXE(
    pyz,
    a.scripts,
    [],                   # ONEDIR: binaries/datas НЕ встраиваются в EXE
    exclude_binaries=True,  # ONEDIR маркер — обязательно для COLLECT
    name="fmail-core",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=None,
    uac_admin=False,
    uac_uiaccess=False,
)

# ── COLLECT (onedir — создаёт папку dist/fmail-core/) ─────────────────────────
# Собирает всё вместе: EXE + DLLs + .pyd + данные → dist/fmail-core/
# CI зипует эту папку → embed в Tauri EXE через include_bytes!
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="fmail-core",
)
