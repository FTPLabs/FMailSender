"""
EmailSenderPro build script — compiles to .exe via PyInstaller.
Usage: python build.py [--onefile] [--clean]
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
    print(f"\n-> {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, cwd=cwd or ROOT)
    return result.returncode


def clean():
    for d in [DIST, BUILD]:
        if d.exists():
            shutil.rmtree(d)
            print(f"Removed: {d}")


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
    print("version_info.txt created")
    return path


def check_requirements():
    try:
        import PyInstaller
        print(f"PyInstaller {PyInstaller.__version__} OK")
    except ImportError:
        print("Installing PyInstaller...")
        run([sys.executable, "-m", "pip", "install", "pyinstaller>=6.0"])


def build(onefile: bool = False):
    print("=" * 60)
    print(f"  Email Sender Pro v{APP_VERSION}")
    print(f"  Mode: {'Single EXE' if onefile else 'Folder'}")
    print("=" * 60)

    check_requirements()
    ver_file = generate_version_info()

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--windowed",
        "--noconfirm",
        "--clean",
        "--distpath", str(DIST),
        "--workpath", str(BUILD),
        "--add-data", f"{ROOT / 'assets'}{os.pathsep}assets",
        "--add-data", f"{ROOT / 'i18n'}{os.pathsep}i18n",
        "--add-data", f"{ROOT / 'data'}{os.pathsep}data",
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
        "--exclude-module", "tkinter",
        "--exclude-module", "matplotlib",
        "--exclude-module", "numpy",
        "--exclude-module", "pandas",
        "--exclude-module", "scipy",
        "--exclude-module", "PIL",
        "--exclude-module", "cv2",
        "--version-file", str(ver_file),
    ]

    if ICON_PATH.exists():
        cmd += ["--icon", str(ICON_PATH)]
    else:
        print(f"WARNING: icon not found at {ICON_PATH} — building without icon")

    if onefile:
        cmd.append("--onefile")

    cmd.append(str(MAIN_PY))

    print("\nRunning PyInstaller...")
    code = run(cmd)

    if code != 0:
        print(f"\nBuild FAILED with exit code {code}")
        sys.exit(code)

    if onefile:
        exe = DIST / f"{APP_NAME}.exe"
    else:
        exe = DIST / APP_NAME / f"{APP_NAME}.exe"

    if exe.exists():
        size_mb = exe.stat().st_size / 1024 / 1024
        print("=" * 60)
        print(f"Build SUCCESS!")
        print(f"Output: {exe}")
        print(f"Size:   {size_mb:.1f} MB")
        print("=" * 60)
    else:
        print(f"\nEXE not found at: {exe}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Email Sender Pro Builder")
    parser.add_argument("--onefile", action="store_true",
                        help="Build a single .exe file")
    parser.add_argument("--clean", action="store_true",
                        help="Clean build directories before build")
    args = parser.parse_args()

    if args.clean:
        clean()

    build(onefile=args.onefile)
