"""
Build script — создаёт чистый .exe без установщика.
Запуск: python build.py
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"
SPEC = ROOT / "FMailSenderPro.spec"

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
    "--hidden-import", "PyQt6.QtSvgWidgets",
    "--hidden-import", "aiosmtplib",
    "--hidden-import", "cryptography",
    "--hidden-import", "jwt",
    "--hidden-import", "requests",
    "--hidden-import", "dns.resolver",
    "--hidden-import", "dns.exception",
    "--collect-all", "PyQt6",
    "--add-data", f"{ROOT / 'assets'}:assets",
    "--add-data", f"{ROOT / 'data'}:data",
    "--add-data", f"{ROOT / 'templates'}:templates",
    "--add-data", f"{ROOT / 'i18n'}:i18n",
]

if ICON_ARG:
    PYINSTALLER_CMD.append(ICON_ARG)

# Версионная информация для Windows
VERSION_INFO = """
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(2, 2, 0, 0),
    prodvers=(2, 2, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'FTPLabs'),
         StringStruct(u'FileDescription', u'FMail Sender Pro'),
         StringStruct(u'FileVersion', u'2.2.0.0'),
         StringStruct(u'InternalName', u'FMailSenderPro'),
         StringStruct(u'LegalCopyright', u'Copyright (C) 2026 FTPLabs'),
         StringStruct(u'OriginalFilename', u'FMailSenderPro.exe'),
         StringStruct(u'ProductName', u'FMail Sender Pro'),
         StringStruct(u'ProductVersion', u'2.2.0.0')])
    ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""

VERSION_FILE = BUILD / "version_info.txt"


def main():
    print("=" * 60)
    print("FMail Sender Pro — Build System")
    print("=" * 60)

    for d in [DIST, BUILD]:
        d.mkdir(parents=True, exist_ok=True)

    BUILD.mkdir(parents=True, exist_ok=True)
    VERSION_FILE.write_text(VERSION_INFO, encoding="utf-8")

    cmd = list(PYINSTALLER_CMD)
    cmd += ["--version-file", str(VERSION_FILE)]
    cmd.append(str(ROOT / "main.py"))

    print(f"\n📦 Запуск PyInstaller...")
    result = subprocess.run(cmd, cwd=str(ROOT), capture_output=False)

    if result.returncode != 0:
        print("\n❌ Сборка завершилась с ошибкой")
        sys.exit(result.returncode)

    exe = DIST / "FMailSenderPro.exe"
    if exe.exists():
        size_mb = exe.stat().st_size / 1024 / 1024
        print(f"\n✅ Сборка завершена!")
        print(f"   Файл: {exe}")
        print(f"   Размер: {size_mb:.1f} MB")
    else:
        print("\n❌ EXE файл не найден")
        sys.exit(1)


if __name__ == "__main__":
    main()
