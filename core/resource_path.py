"""
FMailSender — Resource path helper for PyInstaller onefile.
===========================================================
PyInstaller onefile распаковывает ресурсы в %TEMP%/_MEIxxxxxx/
При запуске sys._MEIPASS указывает на эту директорию.

В dev-режиме используем корень репозитория.

Использование:
    from core.resource_path import get_resource_path
    templates_dir = get_resource_path("templates")
"""
import os
import sys
from pathlib import Path


def get_resource_path(relative_path: str) -> Path:
    """
    Возвращает абсолютный путь к ресурсу, совместимый с PyInstaller onefile.

    Args:
        relative_path: путь относительно корня приложения
                       (напр. "templates", "i18n/ru.json")

    Returns:
        Path к ресурсу (существующий или нет — вызывающий код проверяет)
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # PyInstaller onefile: ресурсы в %TEMP%/_MEIxxxxxx/
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        # Dev: ищем корень репозитория (директория, содержащая main.py)
        base = Path(__file__).parent.parent

    return base / relative_path


def get_data_dir() -> Path:
    """
    Возвращает директорию для пользовательских данных (сохраняется между запусками).
    В отличие от get_resource_path(), эта директория доступна для записи.
    """
    if getattr(sys, "frozen", False):
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        return Path(appdata) / "FMailSender"
    # Dev: ./data/
    return Path(__file__).parent.parent / "data"
