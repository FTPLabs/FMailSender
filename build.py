"""
Build script — генерирует PyInstaller spec и собирает EXE.
Перед сборкой автоматически конвертирует fmail_logo.png → fmail_logo.ico через Pillow.
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

ROOT = Path(__file__).parent.resolve()
DIST = ROOT / "dist"
BUILD = ROOT / "build"
SPEC_FILE = ROOT / "FMailSender.spec"
ICON_ICO = ROOT / "assets" / "images" / "fmail_logo.ico"
ICON_PNG = ROOT / "assets" / "images" / "fmail_logo.png"


def ensure_icon() -> None:
    """Конвертирует PNG-логотип в ICO для EXE. Требует Pillow."""
    if ICON_ICO.exists():
        print(f"[icon] Используем существующий: {ICON_ICO.name}")
        return
    if not ICON_PNG.exists():
        print("[icon] fmail_logo.png не найден — иконка не будет установлена")
        return
    try:
        from PIL import Image
        img = Image.open(ICON_PNG).convert("RGBA")
        sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        ICON_ICO.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(ICON_ICO), format="ICO", sizes=sizes)
        print(f"[icon] Создан {ICON_ICO.name} из {ICON_PNG.name}")
    except ImportError:
        print("[icon] Pillow не установлен — запустите: pip install Pillow")
    except Exception as e:
        print(f"[icon] Ошибка конвертации: {e}")


def build_spec() -> str:
    icon_line = f"icon=r'{ICON_ICO}'," if ICON_ICO.exists() else "icon=None,"

    datas_parts = [
        f"(r'{ROOT / 'core'}', 'core')",
        f"(r'{ROOT / 'gui'}', 'gui')",
    ]
    for extra in ("assets", "data", "templates", "i18n"):
        p = ROOT / extra
        if p.exists():
            datas_parts.append(f"(r'{p}', '{extra}')")

    datas_str = ",\n        ".join(datas_parts)

    lines = [
        "# -*- mode: python ; coding: utf-8 -*-",
        "from PyInstaller.utils.hooks import collect_submodules, collect_binaries",
        "_ssl_bins = collect_binaries('ssl') + collect_binaries('_ssl') + collect_binaries('cryptography')",
        "",
        "block_cipher = None",
        "",
        "extra_hidden = collect_submodules('PyQt6') + collect_submodules('cryptography')",
        "",
        "a = Analysis(",
        f"    [r'{ROOT / 'main.py'}'],",
        f"    pathex=[r'{ROOT}'],",
        "    binaries=[*_ssl_bins],",
        "    datas=[",
        f"        {datas_str},",
        "    ],",
        "    hiddenimports=[",
        "        'core', 'core.license', 'core.sender', 'core.bounce',",
        "        'core.warmup', 'core.spam_checker', 'core.updater', 'core._version',",
        "        'gui', 'gui.app', 'gui.theme',",
        "        'gui.screens', 'gui.screens.screen_dashboard', 'gui.screens.screen_accounts',",
        "        'gui.screens.screen_compose', 'gui.screens.screen_recipients',",
        "        'gui.screens.screen_sending', 'gui.screens.screen_analytics',",
        "        'gui.screens.screen_activation',",
        "        'ssl', '_ssl', 'hashlib', '_hashlib',",
        "        'aiosmtplib', 'cryptography', 'cryptography.fernet',",
        "        'cryptography.hazmat.primitives', 'cryptography.hazmat.backends',",
        "        'jwt', 'requests', 'urllib3', 'dns', 'dns.resolver', 'dns.exception',",
        "        'email.mime.multipart', 'email.mime.text', 'email.mime.base',",
        "        'PyQt6', 'PyQt6.QtWidgets', 'PyQt6.QtCore', 'PyQt6.QtGui',",
        "        'PyQt6.QtSvg', 'PyQt6.QtSvgWidgets', 'PyQt6.QtNetwork',",
        "        'psutil', 'wmi',",
        "    ] + extra_hidden,",
        "    hookspath=[],",
        "    hooksconfig={},",
        "    runtime_hooks=[],",
        "    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas', 'PIL', 'cv2', 'flask', 'django', 'tornado', 'IPython', 'notebook', 'pytest', 'setuptools', 'pkg_resources', 'multiprocessing', 'lib2to3', 'pydoc', 'doctest', 'unittest', 'xmlrpc', 'ftplib', 'telnetlib', 'imghdr', 'sndhdr', 'aifc', 'sunau'],",
        "    cipher=block_cipher,",
        "    noarchive=False,",
        ")",
        "",
        "pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)",
        "",
        "exe = EXE(",
        "    pyz,",
        "    a.scripts,",
        "    a.binaries,",
        "    a.zipfiles,",
        "    a.datas,",
        "    [],",
        "    name='FMailSender',",
        "    debug=False,",
        "    bootloader_ignore_signals=False,",
        "    strip=False,",
        "    upx=True,",
        "    runtime_tmpdir=None,",
        "    console=False,",
        "    disable_windowed_traceback=False,",
        "    argv_emulation=False,",
        "    target_arch=None,",
        "    codesign_identity=None,",
        "    entitlements_file=None,",
        f"    {icon_line}",
        ")",
    ]
    return "\n".join(lines) + "\n"


def main():
    print("=" * 60)
    print("  FMail Sender — Build Script")
    print("=" * 60)

    for d in (DIST, BUILD):
        if d.exists():
            shutil.rmtree(d)
    if SPEC_FILE.exists():
        SPEC_FILE.unlink()
    print("[1/5] Очистка предыдущих артефактов")

    ensure_icon()
    print("[2/5] Иконка готова")

    spec_content = build_spec()
    SPEC_FILE.write_text(spec_content, encoding="utf-8")
    print(f"[3/5] Spec-файл: {SPEC_FILE.name}")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
        "--distpath", str(DIST),
        "--workpath", str(BUILD),
        str(SPEC_FILE),
    ]
    print("[4/5] Запуск PyInstaller...")
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        print("PyInstaller завершился с ошибкой!")
        sys.exit(1)

    exe = DIST / "FMailSender.exe"
    if not exe.exists():
        print(".exe не найден после сборки!")
        sys.exit(1)

    size_mb = exe.stat().st_size / 1024 / 1024
    print(f"[5/5] Готово: {exe.name} ({size_mb:.1f} MB)")

    if SPEC_FILE.exists():
        SPEC_FILE.unlink()

    print("\n Сборка завершена успешно!")


if __name__ == "__main__":
    main()
