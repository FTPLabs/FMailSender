"""
Persistent update preferences: skip-version and remind-later timestamp.
Stored in a JSON file next to the EXE (or next to main.py in dev mode).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_EXE_DIR = (
    Path(sys.executable).parent
    if getattr(sys, "frozen", False)
    else Path(__file__).parent.parent
)
_SETTINGS_FILE = _EXE_DIR / "_update_prefs.json"

_REMIND_LATER_SEC = 24 * 3600   # не показываем повторно раньше 24 часов


def _load() -> dict:
    try:
        if _SETTINGS_FILE.exists():
            return json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save(data: dict) -> None:
    try:
        _SETTINGS_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass


def is_version_skipped(version: str) -> bool:
    """True if user chose 'Пропустить эту версию' для данной версии."""
    return _load().get("skipped_version") == version


def skip_version(version: str) -> None:
    d = _load()
    d["skipped_version"] = version
    d.pop("remind_after", None)
    _save(d)


def is_remind_later_active() -> bool:
    """True если пользователь выбрал 'Напомнить позже' и 24 часа ещё не прошли."""
    remind_after = _load().get("remind_after", 0)
    return time.time() < remind_after


def set_remind_later() -> None:
    d = _load()
    d["remind_after"] = time.time() + _REMIND_LATER_SEC
    _save(d)


def clear_remind_later() -> None:
    d = _load()
    d.pop("remind_after", None)
    _save(d)
