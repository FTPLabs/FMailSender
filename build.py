"""
Build script -- creates clean .exe without installer.
Run: python build.py
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"

ICON_PATH = ROOT / "assets" / "images" / "fmail_logo.ico"
ICON_ARG = f"--icon={ICON_PATH}" if ICON_PATH.exists() else ""

PYINSTALLER_CMD = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--windowed",
    "--name", "FMailSenderPro",
    "--clean",
    "--noconfirm",
    "--distpath", str(DIST),
    "--workpath", str(BUILD),
    "--paths", str(ROOT),
    "--hidden-import", "PyQt6",
    "--hidden-import", "PyQt6.QtWidgets",
    "--hidden-import", "PyQt6.QtCore",
    "--hidden-import", "PyQt6.QtGui",
    "--hidden-import", "PyQt6.QtSvg",
    "--hidden-import", "PyQt6.QtSvgWidgets",
    "--hidden-import", "PyQt6.QtNetwork",
    "--hidden-import", "aiosmtplib",
    "--hidden-import", "cryptography",
    "--hidden-import", "cryptography.fernet",
    "--hidden-import", "cryptography.hazmat.primitives",
    "--hidden-import", "jwt",
    "--hidden-import", "requests",
    "--hidden-import", "dns",
    "--hidden-import", "dns.resolver",
    "--hidden-import", "dns.exception",
    "--hidden-import", "email.mime.multipart",
    "--hidden-import", "email.mime.text",
    "--hidden-import", "email.mime.base",
    "--collect-all", "PyQt6",
    "--collect-all", "cryptography",
    "--add-data", str(ROOT / "assets") + os.pathsep + "assets",
    "--add-data", str(ROOT / "data") + os.pathsep + "data",
    "--add-data", str(ROOT / "templates") + os.pathsep + "templates",
    "--add-data", str(ROOT / "i18n") + os.pathsep + "i18n",
]

# Entry point — must be last positional argument
PYINSTALLER_CMD.append(str(ROOT / "main.py"))

if ICON_ARG:
    PYINSTALLER_CMD.append(ICON_ARG)

VERSION_INFO_CONTENT = """
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(2, 3, 0, 0),
    prodvers=(2, 3, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'FTPLabs'),
         StringStruct(u'FileDescription', u'FMail Sender Pro'),
         StringStruct(u'FileVersion', u'2.3.0.0'),
         StringStruct(u'InternalName', u'FMailSenderPro'),
         StringStruct(u'LegalCopyright', u'Copyright (C) 2026 FTPLabs'),
         StringStruct(u'OriginalFilename', u'FMailSenderPro.exe'),
         StringStruct(u'ProductName', u'FMail Sender Pro'),
         StringStruct(u'ProductVersion', u'2.3.0.0')]
      )]
    ),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""

VERSION_FILE = ROOT / "version_info.txt"


def main():
    print("=" * 60)
    print("  FMail Sender Pro — Build Script")
    print("=" * 60)

    # Clean previous build
    if DIST.exists():
        shutil.rmtree(DIST)
    if BUILD.exists():
        shutil.rmtree(BUILD)
    print("[1/4] Cleaned previous build artifacts")

    # Write version info
    VERSION_FILE.write_text(VERSION_INFO_CONTENT, encoding="utf-8")
    cmd = PYINSTALLER_CMD + [f"--version-file={VERSION_FILE}"]
    print("[2/4] Running PyInstaller...")

    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        print("❌ PyInstaller failed!")
        sys.exit(1)

    exe = DIST / "FMailSenderPro.exe"
    if exe.exists():
        size_mb = exe.stat().st_size / 1024 / 1024
        print(f"[3/4] Build successful: {exe}")
        print(f"      Size: {size_mb:.1f} MB")
    else:
        print("❌ .exe not found after build!")
        sys.exit(1)

    # Clean temp files
    if VERSION_FILE.exists():
        VERSION_FILE.unlink()
    spec = ROOT / "FMailSenderPro.spec"
    if spec.exists():
        spec.unlink()
    print("[4/4] Cleaned temporary files")

    print("\n✅ Build complete!")
    print(f"   Output: {exe}")


if __name__ == "__main__":
    main()
