"""
Скрипт сборки EmailSenderPro в .exe через PyInstaller.
Использование: python build.py [--onefile] [--clean]
"""
import os
import sys
import shutil
import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
DIST = ROOT / "dist"
BUILD = ROOT / "build"

APP_NAME = "EmailSenderPro"
APP_VERSION = "1.0.0"
ICON_PATH = ROOT / "assets" / "icons" / "app.ico"
MAIN_PY = ROOT / "main.py"


def run(cmd: list, cwd: Path = None) -> int:
    print(f"\n→ {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, cwd=cwd or ROOT)
    return result.returncode


def clean():
    for d in [DIST, BUILD]:
        if d.exists():
            shutil.rmtree(d)
            print(f"✓ Удалена директория: {d}")


def generate_version_info():
    content = (
        "# UTF-8\n"
        "VSVersionInfo(\n"
        "  ffi=FixedFileInfo(\n"
        "    filevers=(1, 0, 0, 0),\n"
        "    prodvers=(1, 0, 0, 0),\n"
        "    mask=0x3f, flags=0x0, OS=0x40004,\n"
        "    fileType=0x1, subtype=0x0, date=(0, 0)\n"
        "  ),\n"
        "  kids=[\n"
        "    StringFileInfo([\n"
        "      StringTable(u'040904B0', [\n"
        "        StringStruct(u'CompanyName', u'EmailSenderPro'),\n"
        "        StringStruct(u'FileDescription', u'Email Sender Pro'),\n"
        "        StringStruct(u'FileVersion', u'1.0.0'),\n"
        "        StringStruct(u'InternalName', u'EmailSenderPro'),\n"
        "        StringStruct(u'LegalCopyright', u'Copyright 2024'),\n"
        "        StringStruct(u'OriginalFilename', u'EmailSenderPro.exe'),\n"
        "        StringStruct(u'ProductName', u'Email Sender Pro'),\n"
        "        StringStruct(u'ProductVersion', u'1.0.0')])\n"
        "    ]),\n"
        "    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])\n"
        "  ]\n"
        ")\n"
    )
    path = ROOT / "version_info.txt"
    with open(path, "w") as f:
        f.write(content)
    print("✓ version_info.txt создан")
    return path


def check_requirements():
    try:
        import PyInstaller
        print(f"✓ PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("Устанавливаю PyInstaller...")
        run([sys.executable, "-m", "pip", "install", "pyinstaller>=6.0"])


def build(onefile: bool = False):
    print(f"\n{'='*60}")
    print(f"  Email Sender Pro v{APP_VERSION}")
    print(f"  Режим: {'Single EXE' if onefile else 'Folder'}")
    print(f"{'='*60}\n")

    check_requirements()

    # Версионная информация
    ver_file = generate_version_info()

    # Аргументы PyInstaller
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--windowed",                # Без консоли
        "--noconfirm",
        "--clean",
        "--distpath", str(DIST),
        "--workpath", str(BUILD),
        # Данные приложения
        "--add-data", f"{ROOT / 'assets'}{os.pathsep}assets",
        "--add-data", f"{ROOT / 'i18n'}{os.pathsep}i18n",
        "--add-data", f"{ROOT / 'data'}{os.pathsep}data",
        # Hidden imports
        "--hidden-import", "PyQt6.QtWebEngineWidgets",
        "--hidden-import", "PyQt6.QtWebEngineCore",
        "--hidden-import", "PyQt6.QtSvgWidgets",
        "--hidden-import", "PyQt6.QtPrintSupport",
        "--hidden-import", "PyQt6.sip",
        "--hidden-import", "aiosmtplib",
        "--hidden-import", "cryptography",
        "--hidden-import", "cryptography.hazmat.primitives",
        "--hidden-import", "cryptography.hazmat.backends",
        "--hidden-import", "cryptography.hazmat.backends.openssl",
        "--hidden-import", "jwt",
        "--hidden-import", "dns.resolver",
        "--hidden-import", "dns.rdatatype",
        "--hidden-import", "dns.rdataclass",
        "--hidden-import", "openpyxl",
        "--hidden-import", "reportlab",
        "--hidden-import", "reportlab.platypus",
        "--hidden-import", "reportlab.lib.pagesizes",
        "--hidden-import", "reportlab.lib.styles",
        "--hidden-import", "reportlab.lib.units",
        "--hidden-import", "chardet",
        "--hidden-import", "certifi",
        "--hidden-import", "psutil",
        # Исключения (уменьшает размер)
        "--exclude-module", "tkinter",
        "--exclude-module", "matplotlib",
        "--exclude-module", "numpy",
        "--exclude-module", "pandas",
        "--exclude-module", "scipy",
        "--exclude-module", "PIL",
        "--exclude-module", "cv2",
        # Версия
        "--version-file", str(ver_file),
    ]

    # Иконка (только если файл существует)
    if ICON_PATH.exists():
        cmd += ["--icon", str(ICON_PATH)]
    else:
        print(f"⚠ Иконка не найдена: {ICON_PATH} — собираем без иконки")

    # Single EXE или папка
    if onefile:
        cmd.append("--onefile")

    # UPX (если доступен — сжимает exe)
    cmd.append("--upx-dir")
    cmd.append(".")  # PyInstaller сам найдёт или пропустит

    # Главный файл
    cmd.append(str(MAIN_PY))

    print("\nЗапуск PyInstaller...")
    code = run(cmd)

    if code != 0:
        print(f"\n✗ Сборка завершилась с ошибкой (код {code})")
        sys.exit(code)

    # Проверяем результат
    if onefile:
        exe = DIST / f"{APP_NAME}.exe"
    else:
        exe = DIST / APP_NAME / f"{APP_NAME}.exe"

    if exe.exists():
        size_mb = exe.stat().st_size / 1024 / 1024
        print(f"\n{'='*60}")
        print(f"✓ Сборка успешна!")
        print(f"✓ Файл: {exe}")
        print(f"✓ Размер: {size_mb:.1f} MB")
        print(f"{'='*60}\n")
    else:
        print(f"\n✗ EXE не найден: {exe}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Email Sender Pro Builder")
    parser.add_argument("--onefile", action="store_true",
                        help="Собрать в один .exe файл")
    parser.add_argument("--clean", action="store_true",
                        help="Очистить папки сборки перед компиляцией")
    args = parser.parse_args()

    if args.clean:
        clean()

    build(onefile=args.onefile)
