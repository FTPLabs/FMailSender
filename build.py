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

  # FIX: APP_NAME aligned with setup.iss (was "EmailSenderPro", setup.iss expects "FMailSender")
  APP_NAME = "FMailSender"
  sys.path.insert(0, str(Path(__file__).parent))
  from core._version import APP_VERSION, APP_AUTHOR  # noqa: E402
  ICON_PATH = ROOT / "assets" / "icons" / "app.ico"
  MAIN_PY = ROOT / "main.py"


  def run(cmd: list, cwd: Path = None) -> int:
      print("\n-> " + " ".join(str(c) for c in cmd))
      result = subprocess.run(cmd, cwd=cwd or ROOT)
      return result.returncode


  def clean():
      for d in [DIST, BUILD]:
          if d.exists():
              shutil.rmtree(d)
              print(f"Removed: {d}")


  def generate_version_info():
      # FIX: use APP_VERSION instead of hardcoded "1.0.0"
      ver_tuple = APP_VERSION.replace("-", ".").split(".")
      while len(ver_tuple) < 4:
          ver_tuple.append("0")
      ver_csv = ", ".join(ver_tuple[:4])
      content = (
          "# UTF-8\n"
          "VSVersionInfo(\n"
          "  ffi=FixedFileInfo(\n"
          f"    filevers=({ver_csv}),\n"
          f"    prodvers=({ver_csv}),\n"
          "    mask=0x3f, flags=0x0, OS=0x40004,\n"
          "    fileType=0x1, subtype=0x0, date=(0, 0)\n"
          "  ),\n"
          "  kids=[\n"
          "    StringFileInfo([\n"
          "      StringTable(u'040904B0', [\n"
          f"        StringStruct(u'CompanyName', u'{APP_AUTHOR}'),\n"
          "        StringStruct(u'FileDescription', u'FMail Sender'),\n"
          f"        StringStruct(u'FileVersion', u'{APP_VERSION}'),\n"
          "        StringStruct(u'InternalName', u'FMailSender'),\n"
          f"        StringStruct(u'LegalCopyright', u'Copyright 2025 {APP_AUTHOR}'),\n"
          "        StringStruct(u'OriginalFilename', u'FMailSender.exe'),\n"
          "        StringStruct(u'ProductName', u'FMail Sender'),\n"
          f"        StringStruct(u'ProductVersion', u'{APP_VERSION}')])"
          "\n"
          "    ]),\n"
          "    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])\n"
          "  ]\n"
          ")\n"
      )
      path = ROOT / "version_info.txt"
      with open(path, "w") as fh:
          fh.write(content)
      print("version_info.txt created")
      return path


  def ensure_data_dirs():
      dirs = [
          ROOT / "assets" / "icons",
          ROOT / "assets" / "fonts",
          ROOT / "i18n",
          ROOT / "data",
      ]
      for d in dirs:
          d.mkdir(parents=True, exist_ok=True)

      spam_json = ROOT / "data" / "spam_words.json"
      if not spam_json.exists():
          spam_json.write_text('["free", "win", "prize", "click here", "buy now"]')
          print("Created placeholder data/spam_words.json")

      print("Data directories ready")


  def check_requirements():
      try:
          import PyInstaller
          print(f"PyInstaller {PyInstaller.__version__} OK")
      except ImportError:
          run([sys.executable, "-m", "pip", "install", "pyinstaller>=6.0"])


  def build(onefile: bool = False):
      print("=" * 60)
      print(f"  FMail Sender v{APP_VERSION}")
      print(f"  Mode: {'Single EXE' if onefile else 'Folder (for installer)'}")
      print("=" * 60)

      check_requirements()
      ensure_data_dirs()
      ver_file = generate_version_info()

      data_dirs = [
          (ROOT / "assets", "assets"),
          (ROOT / "i18n",   "i18n"),
          (ROOT / "data",   "data"),
      ]

      cmd = [
          sys.executable, "-m", "PyInstaller",
          "--name", APP_NAME,
          "--windowed",
          "--noconfirm",
          "--clean",
          "--distpath", str(DIST),
          "--workpath", str(BUILD),
      ]

      for src_dir, dest_name in data_dirs:
          if src_dir.exists():
              cmd += ["--add-data", f"{src_dir}{os.pathsep}{dest_name}"]
          else:
              print(f"WARNING: skipping missing dir {src_dir}")

      cmd += ["--paths", str(ROOT)]
      cmd += ["--collect-all", "PyQt6"]
      cmd += ["--collect-all", "core"]
      cmd += ["--collect-all", "gui"]

      cmd += [
          "--hidden-import", "core._version",
          "--hidden-import", "core.license",
          "--hidden-import", "core.sender",
          "--hidden-import", "core.bounce",
          "--hidden-import", "core.spam_checker",
          "--hidden-import", "core.updater",
          "--hidden-import", "core.warmup",
          "--hidden-import", "PyQt6.QtWebEngineWidgets",
          "--hidden-import", "PyQt6.QtWebEngineCore",
          "--hidden-import", "PyQt6.QtWebChannel",
          "--hidden-import", "PyQt6.QtSvgWidgets",
          "--hidden-import", "PyQt6.QtPrintSupport",
          "--hidden-import", "PyQt6.sip",
          "--hidden-import", "aiosmtplib",
          "--hidden-import", "cryptography",
          "--hidden-import", "cryptography.fernet",
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
          "--hidden-import", "requests",
          "--hidden-import", "wmi",
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
          print(f"WARNING: icon not found at {ICON_PATH}")

      if onefile:
          cmd.append("--onefile")

      cmd.append(str(MAIN_PY))

      print("\nRunning PyInstaller...")
      code = run(cmd)

      if code != 0:
          print(f"\nBuild FAILED (exit {code})")
          sys.exit(code)

      exe = DIST / f"{APP_NAME}.exe" if onefile else DIST / APP_NAME / f"{APP_NAME}.exe"

      if exe.exists():
          size_mb = exe.stat().st_size / 1024 / 1024
          print("=" * 60)
          print("Build SUCCESS!")
          print(f"Output: {exe}")
          print(f"Size:   {size_mb:.1f} MB")
          print("=" * 60)
      else:
          print(f"\nEXE not found at: {exe}")
          sys.exit(1)


  if __name__ == "__main__":
      parser = argparse.ArgumentParser(description="FMail Sender Builder")
      parser.add_argument("--onefile", action="store_true")
      parser.add_argument("--clean", action="store_true")
      args = parser.parse_args()
      if args.clean:
          clean()
      build(onefile=args.onefile)
  