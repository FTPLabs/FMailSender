"""
  Auto-updater: checks GitHub Releases for a newer version, downloads the ZIP,
  and replaces the running .exe via a self-elevating BAT script on Windows.
  """
  import os
  import re
  import sys
  import json
  import shutil
  import logging
  import platform
  import threading
  import subprocess
  from dataclasses import dataclass
  from pathlib import Path
  from typing import Callable, Optional

  import requests

  from core._version import APP_VERSION

  logger = logging.getLogger("updater")

  GITHUB_API_LATEST = "https://api.github.com/repos/FTPLabs/EmailSenderPro/releases/latest"


  @dataclass
  class UpdateInfo:
      tag: str
      version: str
      release_name: str
      body: str
      download_url: str
      download_size: int
      published_at: str


  class VersionError(Exception):
      pass


  def _parse_version(v: str) -> tuple:
      """Parse version string like 1.2.3 or v1.2.3 into a tuple of ints."""
      v = v.lstrip("v").strip()
      parts = re.split(r"[.\-]", v)
      result = []
      for p in parts[:3]:
          try:
              result.append(int(p))
          except ValueError:
              break
      while len(result) < 3:
          result.append(0)
      return tuple(result)


  def is_newer(remote: str, local: str) -> bool:
      """Return True if remote version is strictly newer than local."""
      return _parse_version(remote) > _parse_version(local)


  def check_for_updates(
      current_version: str = APP_VERSION,
      timeout: int = 8,
  ) -> Optional[UpdateInfo]:
      """
      Query GitHub Releases for the latest release.
      Returns UpdateInfo if a newer version is available, else None.
      """
      try:
          resp = requests.get(
              GITHUB_API_LATEST,
              timeout=timeout,
              headers={
                  "Accept": "application/vnd.github.v3+json",
                  "User-Agent": f"EmailSenderPro/{current_version}",
              },
          )
          if resp.status_code == 404:
              logger.debug("No releases found on GitHub")
              return None
          resp.raise_for_status()
          data = resp.json()
      except requests.RequestException as e:
          logger.debug(f"Update check failed: {e}")
          return None

      tag = data.get("tag_name", "")
      remote_ver = tag.lstrip("v")

      if not is_newer(remote_ver, current_version):
          logger.debug(f"Already up to date: {current_version}")
          return None

      assets = data.get("assets", [])
      zip_asset = None
      for asset in assets:
          name: str = asset.get("name", "")
          if name.endswith(".zip") and "windows" in name.lower():
              zip_asset = asset
              break
      if not zip_asset and assets:
          zip_asset = assets[0]

      if not zip_asset:
          logger.debug("No downloadable asset found in release")
          return None

      return UpdateInfo(
          tag=tag,
          version=remote_ver,
          release_name=data.get("name", f"Version {remote_ver}"),
          body=data.get("body", ""),
          download_url=zip_asset["browser_download_url"],
          download_size=zip_asset.get("size", 0),
          published_at=data.get("published_at", ""),
      )


  class Downloader(threading.Thread):
      """
      Background thread: downloads a file and reports progress via callbacks.
      progress_callback(downloaded_bytes, total_bytes)
      finished_callback(local_path: Path | None, error: str | None)
      """

      def __init__(
          self,
          url: str,
          dest_dir: Path,
          progress_callback: Optional[Callable[[int, int], None]] = None,
          finished_callback: Optional[Callable[[Optional[Path], Optional[str]], None]] = None,
      ):
          super().__init__(daemon=True, name="esp-downloader")
          self.url = url
          self.dest_dir = dest_dir
          self._progress_cb = progress_callback
          self._finished_cb = finished_callback
          self._cancelled = False

      def cancel(self) -> None:
          self._cancelled = True

      def run(self) -> None:
          dest_path: Optional[Path] = None
          try:
              self.dest_dir.mkdir(parents=True, exist_ok=True)
              filename = self.url.split("/")[-1].split("?")[0] or "update.zip"
              dest_path = self.dest_dir / filename

              resp = requests.get(self.url, stream=True, timeout=60,
                                  headers={"User-Agent": f"EmailSenderPro/{APP_VERSION}"})
              resp.raise_for_status()

              total = int(resp.headers.get("Content-Length", 0))
              downloaded = 0

              with open(dest_path, "wb") as f:
                  for chunk in resp.iter_content(chunk_size=65536):
                      if self._cancelled:
                          raise InterruptedError("Download cancelled")
                      if chunk:
                          f.write(chunk)
                          downloaded += len(chunk)
                          if self._progress_cb:
                              self._progress_cb(downloaded, total)

              if self._finished_cb:
                  self._finished_cb(dest_path, None)

          except Exception as e:
              if dest_path and dest_path.exists():
                  dest_path.unlink(missing_ok=True)
              if self._finished_cb:
                  self._finished_cb(None, str(e))


  def apply_update_windows(zip_path: Path) -> bool:
      """
      Extracts the downloaded ZIP next to the current .exe and launches a BAT
      script that replaces the exe after the current process exits.
      Returns True if the BAT was launched (the app should then quit).
      """
      if platform.system() != "Windows":
          logger.warning("apply_update_windows called on non-Windows platform")
          return False

      exe_path = Path(sys.executable)
      app_dir = exe_path.parent

      extract_dir = zip_path.parent / "esp_update_extracted"
      if extract_dir.exists():
          shutil.rmtree(extract_dir, ignore_errors=True)
      extract_dir.mkdir(parents=True, exist_ok=True)

      import zipfile
      with zipfile.ZipFile(zip_path, "r") as z:
          z.extractall(extract_dir)

      new_exes = list(extract_dir.rglob("EmailSenderPro.exe"))
      if not new_exes:
          logger.error("No EmailSenderPro.exe found in downloaded ZIP")
          return False

      new_exe = new_exes[0]
      new_dir = new_exe.parent

      bat_path = zip_path.parent / "esp_update.bat"
      pid = os.getpid()
      # Пути в кавычках — защита от пробелов в пути (например C:\Users\John Doe\...)
      new_dir_q = str(new_dir)
      app_dir_q = str(app_dir)
      new_exe_q = str(app_dir / "EmailSenderPro.exe")
      bat_content = (
          "@echo off\n"
          "echo Waiting for EmailSenderPro to exit...\n"
          ":wait\n"
          f'tasklist /FI "PID eq {pid}" 2>NUL | find /I "{pid}" >NUL\n'
          "if not errorlevel 1 (\n"
          "    timeout /t 1 /nobreak >NUL\n"
          "    goto wait\n"
          ")\n"
          "echo Applying update...\n"
          f'xcopy /E /Y /I "{new_dir_q}" "{app_dir_q}"\n'
          "echo Starting new version...\n"
          f'start "" "{new_exe_q}"\n'
          'del "%~f0"\n'
      )
      bat_path.write_text(bat_content, encoding="utf-8")

      subprocess.Popen(
          ["cmd.exe", "/C", str(bat_path)],
          creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.DETACHED_PROCESS,
          close_fds=True,
      )
      return True


  def open_download_folder(zip_path: Path) -> None:
      """Opens the folder containing the downloaded ZIP in Explorer."""
      if platform.system() == "Windows":
          subprocess.Popen(["explorer", "/select,", str(zip_path)])
      elif platform.system() == "Darwin":
          subprocess.Popen(["open", "-R", str(zip_path)])
      else:
          subprocess.Popen(["xdg-open", str(zip_path.parent)])
  