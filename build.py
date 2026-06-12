"""
  Build script — generates a PyInstaller spec file and runs it.
  Using a .spec file guarantees local packages (core/, gui/) are bundled.
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
  SPEC_FILE = ROOT / "FMailSenderPro.spec"

  ICON_PATH = ROOT / "assets" / "images" / "fmail_logo.ico"

  SEP = os.pathsep  # ';' on Windows, ':' on Linux

  def make_add_data(src: Path, dst: str) -> str:
      return f"(r'{src}', '{dst}')"

  def build_spec() -> str:
      icon_line = f"icon=r'{ICON_PATH}'," if ICON_PATH.exists() else "icon=None,"

      hidden = [
          # local packages
          "core", "core.license", "core.sender", "core.bounce",
          "core.warmup", "core.spam_checker", "core.updater", "core._version",
          "gui", "gui.app", "gui.theme",
          "gui.screens", "gui.screens.screen_dashboard", "gui.screens.screen_accounts",
          "gui.screens.screen_compose", "gui.screens.screen_recipients",
          "gui.screens.screen_sending", "gui.screens.screen_analytics",
          "gui.screens.screen_activation",
          # stdlib/third-party
          "aiosmtplib", "cryptography", "cryptography.fernet",
          "cryptography.hazmat.primitives", "cryptography.hazmat.primitives.kdf",
          "cryptography.hazmat.primitives.kdf.pbkdf2",
          "cryptography.hazmat.backends",
          "jwt", "requests", "dns", "dns.resolver", "dns.exception",
          "email.mime.multipart", "email.mime.text", "email.mime.base",
          "PyQt6", "PyQt6.QtWidgets", "PyQt6.QtCore", "PyQt6.QtGui",
          "PyQt6.QtSvg", "PyQt6.QtSvgWidgets", "PyQt6.QtNetwork",
          "wmi", "psutil",
      ]
      hidden_str = ",\n        ".join(f'"{h}"' for h in hidden)

      datas = [
          (ROOT / "core", "core"),
          (ROOT / "gui", "gui"),
      ]
      for extra in ("assets", "data", "templates", "i18n"):
          p = ROOT / extra
          if p.exists():
              datas.append((p, extra))

      datas_str = ",\n        ".join(
          f"(r'{src}', '{dst}')" for src, dst in datas
      )

      return f'''# -*- mode: python ; coding: utf-8 -*-
  import sys
  from PyInstaller.utils.hooks import collect_submodules, collect_data_files

  block_cipher = None

  extra_hidden = collect_submodules("PyQt6") + collect_submodules("cryptography")

  a = Analysis(
      [r'{ROOT / "main.py"}'],
      pathex=[r'{ROOT}'],
      binaries=[],
      datas=[
          {datas_str},
      ],
      hiddenimports=[
          {hidden_str},
      ] + extra_hidden,
      hookspath=[],
      hooksconfig={{}},
      runtime_hooks=[],
      excludes=[],
      win_no_prefer_redirects=False,
      win_private_assemblies=False,
      cipher=block_cipher,
      noarchive=False,
  )

  pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

  exe = EXE(
      pyz,
      a.scripts,
      a.binaries,
      a.zipfiles,
      a.datas,
      [],
      name="FMailSenderPro",
      debug=False,
      bootloader_ignore_signals=False,
      strip=False,
      upx=True,
      upx_exclude=[],
      runtime_tmpdir=None,
      console=False,
      disable_windowed_traceback=False,
      argv_emulation=False,
      target_arch=None,
      codesign_identity=None,
      entitlements_file=None,
      {icon_line}
      version_file=None,
  )
  '''


  def main():
      print("=" * 60)
      print("  FMail Sender Pro — Build Script")
      print("=" * 60)

      # Clean
      for d in (DIST, BUILD):
          if d.exists():
              shutil.rmtree(d)
      if SPEC_FILE.exists():
          SPEC_FILE.unlink()
      print("[1/4] Cleaned previous artifacts")

      # Write .spec
      spec_content = build_spec()
      SPEC_FILE.write_text(spec_content, encoding="utf-8")
      print(f"[2/4] Generated spec: {SPEC_FILE.name}")

      # Run PyInstaller with the spec file
      cmd = [
          sys.executable, "-m", "PyInstaller",
          "--clean",
          "--noconfirm",
          "--distpath", str(DIST),
          "--workpath", str(BUILD),
          str(SPEC_FILE),
      ]
      print("[3/4] Running PyInstaller...")
      result = subprocess.run(cmd, cwd=str(ROOT))
      if result.returncode != 0:
          print("❌ PyInstaller failed!")
          sys.exit(1)

      exe = DIST / "FMailSenderPro.exe"
      if not exe.exists():
          print("❌ .exe not found after build!")
          sys.exit(1)

      size_mb = exe.stat().st_size / 1024 / 1024
      print(f"[4/4] Build complete: {exe.name} ({size_mb:.1f} MB)")
      print("\n✅ Success!")

      # Cleanup spec
      if SPEC_FILE.exists():
          SPEC_FILE.unlink()


  if __name__ == "__main__":
      main()
  