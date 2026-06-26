"""
FMailSender auto-updater v2.0.0.
- Проверяет GitHub Releases на наличие новой версии
- Поддерживает PATCH-обновления (только изменённые файлы — без полной загрузки EXE)
- Fallback на полную загрузку EXE если патч недоступен
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import sys
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import requests

from core._version import APP_VERSION

logger = logging.getLogger("updater")

GITHUB_API_URL = "https://api.github.com/repos/FTPLabs/FMailSender/releases/latest"
VERSION_CHECK_URL = "https://fmail.shop/version.json"  # публичный эндпоинт (не зависит от приватности репо)
CHECK_INTERVAL_SEC = 3600  # раз в час

# Каталог патчей рядом с EXE (или рядом с main.py в dev-режиме)
_EXE_DIR = (
    Path(sys.executable).parent
    if getattr(sys, "frozen", False)
    else Path(__file__).parent.parent
)
PATCH_DIR = _EXE_DIR / "_patches"


@dataclass
class UpdateInfo:
    """Информация о доступном обновлении."""
    version: str
    tag_name: str
    release_name: str
    body: str
    html_url: str
    download_url: str           # Полный EXE
    download_size: int = 0      # Размер EXE в байтах
    patch_manifest_url: str = ""  # URL patch_manifest_v*.json
    patch_size: int = 0         # Суммарный размер патча в байтах
    is_patch_available: bool = False
    patch_files: list[dict] = field(default_factory=list)  # [{path, sha256, url, size}]
    published_at: str = ""


def _parse_version(tag: str) -> tuple[int, ...]:
    """Конвертирует 'v2.9.0' или '2.9.0' в (2, 9, 0) для сравнения."""
    clean = tag.lstrip("v").strip()
    try:
        return tuple(int(x) for x in clean.split("."))
    except ValueError:
        return (0,)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _check_fmail_shop(timeout: float) -> Optional[UpdateInfo]:
    """
    Первичный эндпоинт: https://fmail.shop/version.json
    Не зависит от того, публичный репо или приватный.
    Формат: {"version":"5.2.3","tag":"v5.2.3","release_name":"...","body":"...",
              "html_url":"...","exe_url":"...","exe_size":0,"patch_manifest_url":"..."}
    """
    try:
        resp = requests.get(
            VERSION_CHECK_URL,
            timeout=timeout,
            headers={"User-Agent": f"FMailSender/{APP_VERSION}"},
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        ver = data.get("version", "")
        if not ver:
            return None
        if _parse_version(ver) <= _parse_version(APP_VERSION):
            return None
        tag = data.get("tag", f"v{ver}")
        return UpdateInfo(
            version=ver,
            tag_name=tag,
            release_name=data.get("release_name", f"FMail Sender {ver}"),
            body=data.get("body", ""),
            html_url=data.get("html_url", ""),
            download_url=data.get("exe_url", ""),
            download_size=int(data.get("exe_size", 0)),
            patch_manifest_url=data.get("patch_manifest_url", ""),
            published_at=data.get("published_at", ""),
        )
    except Exception as e:
        logger.debug("fmail.shop version check failed: %s", e)
        return None


def _check_github_api(timeout: float) -> Optional[UpdateInfo]:
    """
    Резервный эндпоинт: GitHub Releases API.
    Работает только если репо публичный или установлен GITHUB_TOKEN.
    """
    try:
        _gh_token = os.environ.get("GITHUB_TOKEN", "")
        _headers = {"User-Agent": f"FMailSender/{APP_VERSION}"}
        if _gh_token:
            _headers["Authorization"] = f"Bearer {_gh_token}"

        resp = requests.get(GITHUB_API_URL, timeout=timeout, headers=_headers)
        if resp.status_code != 200:
            return None

        data = resp.json()
        tag = data.get("tag_name", "")
        if not tag:
            return None

        latest = _parse_version(tag)
        current = _parse_version(APP_VERSION)
        if latest <= current:
            return None

        assets = data.get("assets", [])
        exe_asset = next(
            (a for a in assets if a["name"].endswith(".exe") and "patch" not in a["name"].lower()),
            None,
        )
        exe_url = exe_asset["browser_download_url"] if exe_asset else data.get("html_url", "")
        exe_size = exe_asset["size"] if exe_asset else 0
        manifest_asset = next(
            (a for a in assets if "patch_manifest" in a["name"] and a["name"].endswith(".json")),
            None,
        )
        info = UpdateInfo(
            version=tag.lstrip("v"),
            tag_name=tag,
            release_name=data.get("name", tag),
            body=data.get("body", ""),
            html_url=data.get("html_url", ""),
            download_url=exe_url,
            download_size=exe_size,
            published_at=data.get("published_at", ""),
        )
        if manifest_asset:
            info.patch_manifest_url = manifest_asset["browser_download_url"]
        return info
    except Exception as e:
        logger.debug("GitHub API update check failed: %s", e)
        return None


def check_for_update(timeout: float = 10.0) -> Optional[UpdateInfo]:
    """
    Проверяет наличие новой версии.
    Сначала — fmail.shop/version.json (работает всегда, репо может быть приватным).
    Если не ответил — GitHub Releases API (резерв).
    """
    info = _check_fmail_shop(timeout)
    if info is not None:
        return info
    return _check_github_api(timeout)


def fetch_patch_manifest(info: UpdateInfo, timeout: float = 10.0) -> bool:
    """
    Загружает patch manifest и заполняет info.patch_files.
    Возвращает True если патч доступен и содержит файлы.
    """
    if not info.patch_manifest_url:
        return False
    try:
        resp = requests.get(info.patch_manifest_url, timeout=timeout)
        if resp.status_code != 200:
            return False
        manifest = resp.json()
        files = manifest.get("files", [])
        if not files:
            return False
        info.patch_files = files
        info.patch_size = sum(f.get("size", 0) for f in files)
        info.is_patch_available = True
        logger.info(
            "Patch manifest loaded: %d files, %d bytes", len(files), info.patch_size
        )
        return True
    except Exception as e:
        logger.debug("Failed to fetch patch manifest: %s", e)
        return False


def apply_patch(
    patch_files: list[dict],
    on_progress: Optional[Callable[[int, int, str], None]] = None,
    timeout: float = 30.0,
) -> tuple[bool, str]:
    """
    Скачивает изменённые .py файлы и кладёт их в PATCH_DIR.
    Возвращает (success, error_message).
    """
    if not patch_files:
        return False, "Нет файлов в патче"

    PATCH_DIR.mkdir(parents=True, exist_ok=True)
    total = len(patch_files)

    for i, file_info in enumerate(patch_files):
        rel_path = file_info.get("path", "")
        sha256 = file_info.get("sha256", "")
        url = file_info.get("url", "")

        if not rel_path or not url:
            continue

        if on_progress:
            on_progress(i, total, rel_path)

        try:
            resp = requests.get(url, timeout=timeout)
            if resp.status_code != 200:
                return False, f"HTTP {resp.status_code} при загрузке {rel_path}"

            data = resp.content

            if sha256 and _sha256_bytes(data) != sha256:
                return False, f"Контрольная сумма не совпала: {rel_path}"

            # Защита от path traversal: rel_path с '..' или абсолютный путь
            # не должен выводить запись за пределы PATCH_DIR.
            _base = PATCH_DIR.resolve()
            dest = (PATCH_DIR / rel_path).resolve()
            if _base != dest and _base not in dest.parents:
                return False, f"Небезопасный путь в патче: {rel_path}"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            logger.info("Patch applied: %s", rel_path)

        except Exception as e:
            return False, f"Ошибка загрузки {rel_path}: {e}"

    if on_progress:
        on_progress(total, total, "Готово")

    return True, ""


def clear_patches() -> None:
    """Удаляет все патчи (сброс к состоянию EXE)."""
    if PATCH_DIR.exists():
        shutil.rmtree(PATCH_DIR, ignore_errors=True)
        logger.info("Patches cleared: %s", PATCH_DIR)


class Downloader(threading.Thread):
    """Скачивает файл в фоновом потоке с колбэками прогресса."""

    def __init__(
        self,
        url: str,
        dest: Path,
        on_progress: Optional[Callable[[int, int], None]] = None,
        on_done: Optional[Callable[[bool, str], None]] = None,
        chunk_size: int = 65536,
    ):
        super().__init__(daemon=True, name="downloader")
        self.url = url
        self.dest = dest
        self.on_progress = on_progress
        self.on_done = on_done
        self.chunk_size = chunk_size
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            resp = requests.get(self.url, stream=True, timeout=30)
            resp.raise_for_status()
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            self.dest.parent.mkdir(parents=True, exist_ok=True)

            with open(self.dest, "wb") as f:
                for chunk in resp.iter_content(self.chunk_size):
                    if self._cancelled:
                        if self.on_done:
                            self.on_done(False, "Отменено")
                        return
                    f.write(chunk)
                    downloaded += len(chunk)
                    if self.on_progress:
                        self.on_progress(downloaded, total)

            if self.on_done:
                self.on_done(True, "")

        except Exception as e:
            if self.on_done:
                self.on_done(False, str(e))


def apply_update_windows(new_exe_path: Path) -> None:
    """
    Заменяет запущенный EXE на новый через PowerShell без окна.
    (Windows only) — silent: никаких CMD-окон, только прогресс-бар в диалоге приложения.
    """
    import subprocess
    current_exe = Path(sys.executable)

    # PowerShell скрипт: ждём 2с → копируем → запускаем → удаляем скрипт
    ps_script = current_exe.parent / "_update_apply.ps1"
    ps_content = (
        "Start-Sleep -Seconds 2\r\n"
        f'Copy-Item -Path "{new_exe_path}" -Destination "{current_exe}" -Force\r\n'
        f'Remove-Item -Path "{new_exe_path}" -Force -ErrorAction SilentlyContinue\r\n'
        f'Start-Process -FilePath "{current_exe}"\r\n'
        f'Remove-Item -Path "$PSCommandPath" -Force -ErrorAction SilentlyContinue\r\n'
    )
    ps_script.write_text(ps_content, encoding="utf-8")

    # Запускаем PowerShell полностью скрыто: нет CMD окна, нет мерцания
    CREATE_NO_WINDOW = 0x08000000
    subprocess.Popen(
        [
            "powershell.exe",
            "-NonInteractive",
            "-WindowStyle", "Hidden",
            "-ExecutionPolicy", "Bypass",
            "-File", str(ps_script),
        ],
        creationflags=CREATE_NO_WINDOW,
        close_fds=True,
    )
    sys.exit(0)


def open_download_folder(path: Path) -> None:
    """Открывает Проводник с выбранным файлом."""
    import subprocess
    subprocess.Popen(["explorer", "/select,", str(path)])


def start_background_check(
    on_update_found: Callable[[UpdateInfo], None],
    delay_sec: float = 30.0,
) -> threading.Event:
    """
    Запускает фоновый поток проверки обновлений.
    Возвращает stop_event — установи его для остановки.
    """
    stop_event = threading.Event()

    def _worker() -> None:
        import time
        if stop_event.wait(timeout=delay_sec):
            return
        notified_tag: str = ""
        while not stop_event.is_set():
            info = check_for_update()
            if info and info.tag_name != notified_tag:
                notified_tag = info.tag_name
                logger.info("New version available: %s", notified_tag)
                try:
                    on_update_found(info)
                except Exception as e:
                    logger.debug("on_update_found callback failed: %s", e)
            if stop_event.wait(timeout=CHECK_INTERVAL_SEC):
                break

    t = threading.Thread(target=_worker, daemon=True, name="updater-bg")
    t.start()
    return stop_event
