"""
FMailSender — License identity cache (offline mode).
Используется core/app_identity.py для offline-проверки.

БЕЗОПАСНОСТЬ:
  - Кеш зашифрован через cryptography.fernet (тот же ключ, что и storage.py)
  - TTL: 24 часа с момента последней успешной online-проверки
  - Нельзя продлить кеш без онлайн-проверки
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional, Any

logger = logging.getLogger("fmail.identity_cache")

_CACHE_TTL_SECS = 24 * 3600  # 24 часа


def _get_cache_path() -> Path:
    if getattr(sys, "frozen", False):
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        return Path(appdata) / "FMailSender" / "identity_cache.enc"
    return Path(__file__).parent.parent / "data" / "identity_cache.enc"


def _get_fernet():
    """Получаем Fernet из storage.py (общий ключ)."""
    try:
        from core.storage import _get_fernet as sf
        return sf()
    except Exception:
        pass
    try:
        from cryptography.fernet import Fernet
        # Deterministic key derived from MachineGuid (не меняется при переустановке)
        from core.app_identity import get_hwid
        hwid = get_hwid()
        key_raw = hashlib.sha256(f"fmail_cache_{hwid}".encode()).digest()
        import base64
        return Fernet(base64.urlsafe_b64encode(key_raw))
    except Exception as exc:
        logger.error("Cannot create Fernet for cache: %s", exc)
        return None


def save_to_cache(license_key: str, data: dict[str, Any]) -> None:
    """Сохраняет результат успешной online-проверки в зашифрованный кеш."""
    try:
        fernet = _get_fernet()
        if not fernet:
            return
        payload = {
            "license_key": license_key,
            "cached_at":   time.time(),
            "data":        data,
        }
        encrypted = fernet.encrypt(json.dumps(payload).encode())
        path = _get_cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(encrypted)
    except Exception as exc:
        logger.warning("Cache save failed: %s", exc)


def load_from_cache(license_key: str) -> Optional[dict[str, Any]]:
    """
    Загружает и проверяет кешированный результат.

    Возвращает данные только если:
      1. Кеш расшифровывается без ошибок
      2. Ключ совпадает
      3. cached_at + 24h > now (кеш не просрочен)

    Возвращает None если кеш невалиден или просрочен.
    """
    try:
        fernet = _get_fernet()
        if not fernet:
            return None

        path = _get_cache_path()
        if not path.exists():
            return None

        encrypted = path.read_bytes()
        decrypted = fernet.decrypt(encrypted)
        payload = json.loads(decrypted.decode())

        # Проверяем ключ
        if payload.get("license_key", "").upper() != license_key.upper():
            logger.warning("Cache key mismatch — ignoring cache")
            return None

        # Проверяем TTL
        cached_at = float(payload.get("cached_at", 0))
        age_secs   = time.time() - cached_at
        if age_secs > _CACHE_TTL_SECS:
            logger.warning("Cache expired (age %.0fh > 24h) — online check required", age_secs / 3600)
            return None

        return payload.get("data")

    except Exception as exc:
        logger.warning("Cache load failed: %s", exc)
        return None
