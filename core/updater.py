"""
Auto-updater: checks GitHub Releases for a newer version, downloads the ZIP,
and replaces the running .exe via a self-elevating BAT script on Windows.
"""
import os
import re
import sys
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
    return _parse_version(remote) > _parse_version(local)


def check_for_updates(current_version: str = APP_VERSION, timeout: int = 8) -> Optional[UpdateInfo]:
    try:
        resp = requests.get(
            GITHUB_API_LATEST, timeout=timeout,
            headers={"Accept": "application/vnd.github.v3+json",
                     "User-Agent": f"EmailSenderPro/{current_version}"},
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.debug(f"Update check failed: {e}")
        return None
    tag = data.get("tag_name", "")
    remote_ver = tag.lstrip("v")
    if not is_newer(remote_ver, current_version):
        return None
    assets = data.get("assets", [])
    zip_asset = next((a for a in assets if a.get("name","").endswith(".zip") and "windows" in a.get("name","").lower()), None)
    if not zip_asset and assets:
        zip_asset = assets[0]
    if not zip_asset:
        return None
    return UpdateInfo(
        tag=tag, version=remote_ver,
        release_name=data.get("name", f"Version {remote_ver}"),
        body=data.get("body", ""),
        download_url=zip_asset["browser_download_url"],
        download_size=zip_asset.get("size", 0),
        published_at=data.get("published_at", ""),
    )


class Downloader(threading.Thread):
    def __init__(self, url, dest_dir, progress_callback=None, finished_callback=None):
        super().__init__(daemon=True, name="esp-downloader")
        self.url = url
        self.dest_dir = dest_dir
        self._progress_cb = progress_callback
        self._finished_cb = finished_callback
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        dest_path = None
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


def verify_zip_integrity(zip_path: Path) -> bool:
    """Проверяет структурную целостность скачанного ZIP перед применением."""
    import zipfile, hashlib
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            bad = z.testzip()
            if bad:
                logger.error(f"ZIP повреждён, первый плохой файл: {bad}")
                return False
        return True
    except Exception as e:
        logger.error(f"Ошибка проверки ZIP: {e}")
        return False


def apply_update_windows(zip_path: Path) -> bool:
    if platform.system() != "Windows":
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
    if not verify_zip_integrity(zip_path):
        logger.error("Обновление отменено: ZIP не прошёл проверку целостности")
        return False
    new_exes = list(extract_dir.rglob("EmailSenderPro.exe"))
    if not new_exes:
        logger.error("No EmailSenderPro.exe found in downloaded ZIP")
        return False
    new_dir = new_exes[0].parent
    bat_path = zip_path.parent / "esp_update.bat"
    pid = os.getpid()
    nd = str(new_dir)
    ad = str(app_dir)
    ne = str(app_dir / "EmailSenderPro.exe")
    bat = [
        "@echo off",
        "echo Waiting for EmailSenderPro to exit...",
        "set WAIT_COUNT=0",
        ":wait",
        f'tasklist /FI "PID eq {pid}" 2>NUL | find /I "{pid}" >NUL',
        "if not errorlevel 1 (",
        "    timeout /t 1 /nobreak >NUL",
        "    goto wait",
        "    if %WAIT_COUNT% GEQ 60 goto apply",
        "    set /A WAIT_COUNT+=1",
        ")",
        ":apply",
        "echo Applying update...",
        f'xcopy /E /Y /I "{nd}" "{ad}"',
        "echo Starting...",
        f'start "" "{ne}"',
        'del "%~f0"',
    ]
    bat_path.write_text("\n".join(bat) + "\n", encoding="utf-8")
    subprocess.Popen(
        ["cmd.exe", "/C", str(bat_path)],
        creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.DETACHED_PROCESS,
        close_fds=True,
    )
    return True


def open_download_folder(zip_path: Path) -> None:
    if platform.system() == "Windows":
        subprocess.Popen(["explorer", "/select,", str(zip_path)])
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", "-R", str(zip_path)])
    else:
        subprocess.Popen(["xdg-open", str(zip_path.parent)])
