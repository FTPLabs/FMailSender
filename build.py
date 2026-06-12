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

    return (
        "# -*- mode: python ; coding: utf-8 -*-\n"
        "from PyInstaller.utils.hooks import collect_submodules\n"
        "\n"
        "block_cipher = None\n"
        "\n"
        "extra_hidden = collect_submodules('PyQt6') + collect_submodules('cryptography')\n"
        "\n"
        "a = Analysis(\n"
        f"    [r'{ROOT / 'main.py'}'],\n"
        f"    pathex=[r'{ROOT}'],\n"
        "    binaries=[],\n"
        "    datas=[\n"
        f"        {datas_str},\n"
        "    ],\n"
        "    hiddenimports=[\n"
        "        'core', 'core.license', 'core.sender', 'core.bounce',\n"
        "        'core.warmup', 'core.spam_checker', 'core.updater', 'core._version',\n"
        "        'gui', 'gui.app', 'gui.theme',\n"
        "        'gui.screens', 'gui.screens.screen_dashboard', 'gui.screens.screen_accounts',\n"
        "        'gui.screens.screen_compose', 'gui.screens.screen_recipients',\n"
        "        'gui.screens.screen_sending', 'gui.screens.screen_analytics',\n"
        "        'gui.screens.screen_activation',\n"
        "        'aiosmtplib', 'cryptography', 'cryptography.fernet',\n"
        "        'cryptography.hazmat.primitives', 'cryptography.hazmat.backends',\n"
        "        'jwt', 'requests', 'urllib3', 'dns', 'dns.resolver', 'dns.exception',\n"
        "        'email.mime.multipart', 'email.mime.text', 'email.mime.base',\n"
        "        'PyQt6', 'PyQt6.QtWidgets', 'PyQt6.QtCore', 'PyQt6.QtGui',\n"
        "        'PyQt6.QtSvg', 'PyQt6.QtSvgWidgets', 'PyQt6.QtNetwork',\n"
        "        'psutil', 'wmi',\n"
        "    ] + extra_hidden,\n"
        "    hookspath=[],\n"
        "    hooksconfig={},\n"
        "    runtime_hooks=[],\n"
        "    excludes=[],\n"
        "    cipher=block_cipher,\n"
        "    noarchive=False,\n"
        ")\n"
        "\n"
        "pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)\n"
        "\n"
        "exe = EXE(\n"
        "    pyz,\n"
        "    a.scripts,\n"
        "    a.binaries,\n"
        "    a.zipfiles,\n"
        "    a.datas,\n"
        "    [],\n"
        "    name='FMailSender',\n"
        "    debug=False,\n"
        "    bootloader_ignore_signals=False,\n"
        "    strip=False,\n"
        "    upx=False,\n"
        "    runtime_tmpdir=None,\n"
        "    console=False,\n"
        "    disable_windowed_traceback=False,\n"
        "    argv_emulation=False,\n"
        "    target_arch=None,\n"
        "    codesign_identity=None,\n"
        "    entitlements_file=None,\n"
        f"    {icon_line}\n"
        ")\n"
    );


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

    print("\n✅ Сборка завершена успешно!")


if __name__ == "__main__":
    main()
