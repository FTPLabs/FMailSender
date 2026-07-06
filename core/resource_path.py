"""
FMailSender — Resource path helper v7.1.0
==========================================
Поддерживает три режима запуска:

1. Dev (python main.py из корня репо):
   Файлы ищутся относительно корня репозитория.

2. Embedded CPython v7.1.0 (основной production режим):
   python.exe запускается из app/ в LOCALAPPDATA\\FMailSender\\
   Структура: LOCALAPPDATA\\FMailSender\\app\\main.py
                                           core\\
                                           templates\\
   Ресурсы ищутся относительно __file__ (app/).
   sys.frozen НЕ установлен — используем путь __file__.

3. PyInstaller (legacy, для совместимости):
   Использует sys._MEIPASS как base.
"""
import os
import sys
from pathlib import Path


def _get_base_dir() -> Path:
    """
    Определяет корневую директорию приложения (где лежат core/, templates/).
    """
    # PyInstaller onefile/onedir: ресурсы в _MEIPASS
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]

    # Embedded CPython и Dev: base = директория main.py
    # В Embedded CPython это app/ внутри LOCALAPPDATA\FMailSender\
    # В Dev это корень репозитория
    return Path(__file__).parent.parent


def get_resource_path(relative_path: str) -> Path:
    """
    Возвращает абсолютный путь к ресурсу.

    Args:
        relative_path: путь относительно корня приложения
                       (напр. "templates", "i18n/ru.json", "data/spam_words.json")

    Returns:
        Path к ресурсу
    """
    return _get_base_dir() / relative_path


def _is_embedded_production() -> bool:
    """
    Определяет, запущены ли мы в production Embedded CPython режиме.
    Признак: main.py находится внутри LOCALAPPDATA\\FMailSender\\app\\
    """
    try:
        main_path = Path(__file__).parent.parent  # app/
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        if not local_appdata:
            return False
        fmailsender_dir = Path(local_appdata) / "FMailSender"
        return str(main_path).startswith(str(fmailsender_dir))
    except Exception:
        return False


def get_data_dir() -> Path:
    """
    Возвращает директорию для пользовательских данных (сохраняется между запусками).
    Всегда записываемая директория вне зависимости от режима запуска.

    Embedded CPython / PyInstaller:  %APPDATA%\\FMailSender\\
    Dev:                              ./data/
    """
    if getattr(sys, "frozen", False) or _is_embedded_production():
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        return Path(appdata) / "FMailSender"
    # Dev: ./data/
    return Path(__file__).parent.parent / "data"
