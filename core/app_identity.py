"""
FMailSender — App Identity & Security Module v1.0
==================================================
Модуль безопасности: единая точка для всех проверок идентичности.

Функции:
  get_hwid()               — стабильный HWID, привязан к железу
  get_app_fingerprint()    — SHA-256 хеш запущенного EXE (защита от подмены)
  verify_on_startup()      — проверка ключа + HWID на сервере при каждом запуске
  bind_hwid()              — первичная привязка HWID к ключу (+ Telegram sync)

Правила безопасности:
  - HWID вычисляется из hardware-only источников (не hostname, не MAC по умолчанию)
  - Fingerprint сверяется с сервером: если изменился — значит подмена бинаря
  - Все обращения к серверу идут с тремя обязательными заголовками:
      X-FMail-HWID, X-FMail-Version, X-FMail-AppKey
  - Offline grace: если сервер недоступен, используется кеш (max 24h)
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import subprocess
import sys
import time
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Optional, Any

import requests

logger = logging.getLogger("fmail.identity")

# ── Конфигурация ───────────────────────────────────────────────────────────────
LICENSE_SERVER_BASE = os.environ.get("LICENSE_SERVER_URL", "https://fmail.shop")
VERIFY_URL          = LICENSE_SERVER_BASE + "/api/v2/verify"
BIND_HWID_URL       = LICENSE_SERVER_BASE + "/api/v2/bind_hwid"
STARTUP_TIMEOUT     = 10   # секунд на запрос к серверу при старте
_CREATE_NO_WINDOW   = 0x08000000  # Windows: не показывать консоль subprocess

# ── HWID ───────────────────────────────────────────────────────────────────────

_hwid_cache: Optional[str] = None


def get_hwid() -> str:
    """
    Генерирует стабильный аппаратный идентификатор.

    Порядок приоритетов (от самого стабильного):
      1. Windows MachineGuid (реестр, <1 мс, всегда стабилен)
      2. Win32_ComputerSystemProduct.UUID (WMI)
      3. Win32_Processor.ProcessorId (WMI)
      4. PowerShell Get-WmiObject (если wmi-пакет недоступен)
      5. MAC-адрес + hostname (только fallback, non-Windows)

    Использует ОДИН источник (первый успешный) — не смешивает.
    Результат кешируется на время процесса.

    Returns:
        64-символьная hex строка SHA-256.
    """
    global _hwid_cache
    if _hwid_cache is not None:
        return _hwid_cache

    raw: Optional[str] = None

    # 1. Windows MachineGuid
    if raw is None:
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
            )
            guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            winreg.CloseKey(key)
            if guid and len(str(guid)) > 8:
                raw = f"mg:{guid}"
        except Exception:
            pass

    # 2. WMI — motherboard UUID
    if raw is None:
        try:
            import wmi
            c = wmi.WMI(find_classes=False)
            for item in c.Win32_ComputerSystemProduct():
                val = (getattr(item, "UUID", "") or "").strip()
                if val and "FFFFFFFF" not in val.upper() and len(val) > 8:
                    raw = f"mb:{val}"
                    break
        except Exception:
            pass

    # 3. WMI — Processor ID
    if raw is None:
        try:
            import wmi
            c = wmi.WMI(find_classes=False)
            for item in c.Win32_Processor():
                val = (getattr(item, "ProcessorId", "") or "").strip()
                if val:
                    raw = f"cpu:{val}"
                    break
        except Exception:
            pass

    # 4. PowerShell fallback (wmi-пакет недоступен)
    if raw is None and sys.platform == "win32":
        try:
            result = subprocess.run(
                [
                    "powershell", "-NoProfile", "-NonInteractive", "-Command",
                    "(Get-WmiObject Win32_ComputerSystemProduct).UUID",
                ],
                capture_output=True, text=True, timeout=8,
                creationflags=_CREATE_NO_WINDOW,
            )
            val = (result.stdout or "").strip()
            if val and "FFFFFFFF" not in val.upper() and len(val) > 8:
                raw = f"ps_mb:{val}"
        except Exception:
            pass

    # 5. Fallback (non-Windows или всё выше не сработало)
    if raw is None:
        try:
            node = uuid.getnode()
            raw = f"mac:{node}:{platform.machine()}:{platform.node() or 'x'}"
        except Exception:
            raw = "fallback"

    _hwid_cache = hashlib.sha256(raw.encode()).hexdigest()
    return _hwid_cache


def get_app_fingerprint() -> str:
    """
    Вычисляет SHA-256 запущенного EXE.
    Используется для защиты от подмены бинаря.

    В dev-режиме (не frozen): возвращает хеш main.py.

    Returns:
        64-символьная hex строка или "dev-mode".
    """
    try:
        if getattr(sys, "frozen", False):
            exe_path = Path(sys.executable)
        else:
            # Dev режим — хешируем главный скрипт
            exe_path = Path(__file__).parent.parent / "main.py"

        h = hashlib.sha256()
        with exe_path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception as exc:
        logger.warning("app_fingerprint failed: %s", exc)
        return "unknown"


# ── Startup verification ───────────────────────────────────────────────────────

class VerifyResult:
    """Результат проверки лицензии при запуске."""

    __slots__ = ("ok", "reason", "plan", "expires_at",
                 "hwid_bound", "hwid_match", "offline")

    def __init__(
        self,
        ok: bool,
        reason: str = "",
        plan: str = "",
        expires_at: str = "",
        hwid_bound: bool = False,
        hwid_match: bool = True,
        offline: bool = False,
    ) -> None:
        self.ok         = ok
        self.reason     = reason
        self.plan       = plan
        self.expires_at = expires_at
        self.hwid_bound = hwid_bound
        self.hwid_match = hwid_match
        self.offline    = offline

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok":         self.ok,
            "reason":     self.reason,
            "plan":       self.plan,
            "expires_at": self.expires_at,
            "hwid_bound": self.hwid_bound,
            "hwid_match": self.hwid_match,
            "offline":    self.offline,
        }


def verify_on_startup(license_key: str) -> VerifyResult:
    """
    Проверяет лицензионный ключ при каждом запуске приложения.

    Отправляет на сервер:
      - license_key
      - hwid (аппаратный ID)
      - fingerprint (хеш EXE)
      - action: "startup_verify"

    Сервер:
      - При первом запуске с ключом: привязывает HWID
      - При последующих: сверяет HWID
      - Проверяет fingerprint (опционально, если настроено)
      - Возвращает статус лицензии

    Offline grace: если сервер недоступен, возвращает ok=True с offline=True.
    Вызывающий код решает, принять ли offline-результат.
    """
    from core._version import __version__

    hwid        = get_hwid()
    fingerprint = get_app_fingerprint()

    headers = {
        "X-FMail-HWID":    hwid,
        "X-FMail-Version": __version__,
        "X-FMail-AppKey":  license_key,
        "Content-Type":    "application/json",
        "User-Agent":      f"FMailSender/{__version__}",
    }

    payload = {
        "key":         license_key,
        "hwid":        hwid,
        "fingerprint": fingerprint,
        "action":      "startup_verify",
    }

    try:
        resp = requests.post(
            VERIFY_URL,
            json=payload,
            headers=headers,
            timeout=STARTUP_TIMEOUT,
        )
        data: dict = resp.json()

        if resp.status_code == 200 and data.get("ok"):
            result = VerifyResult(
                ok         = True,
                plan       = data.get("plan", ""),
                expires_at = data.get("expires_at", ""),
                hwid_bound = data.get("hwid_bound", False),
                hwid_match = data.get("hwid_match", True),
            )
            # Сохраняем в кеш для offline-режима (TTL=24ч)
            try:
                from core.identity_cache import save_to_cache
                save_to_cache(license_key, result.to_dict())
            except Exception:
                pass
            return result

        reason = data.get("reason") or data.get("detail") or f"HTTP {resp.status_code}"

        # HWID mismatch — ключ уже используется на другом устройстве
        if resp.status_code == 403 or "hwid" in reason.lower():
            return VerifyResult(ok=False, reason="hwid_mismatch", hwid_match=False)

        return VerifyResult(ok=False, reason=reason)

    except requests.exceptions.ConnectionError:
        # SECURITY: не разрешаем безусловный offline bypass.
        # Проверяем зашифрованный локальный кеш (TTL=24ч).
        # Блокировка сети не даёт обойти лицензионную проверку.
        logger.warning("License server unreachable — checking local cache")
        return _verify_from_cache(license_key)

    except requests.exceptions.Timeout:
        logger.warning("License server timed out — checking local cache")
        return _verify_from_cache(license_key)

    except Exception as exc:
        logger.error("startup verify error: %s", exc)
        return VerifyResult(ok=False, reason=str(exc))


def bind_hwid(license_key: str) -> bool:
    """
    Привязывает HWID к лицензионному ключу.
    Вызывается после первой успешной активации.
    Сервер уведомляет Telegram-бота о привязке.

    Returns:
        True если сервер подтвердил привязку.
    """
    from core._version import __version__

    hwid = get_hwid()
    payload = {
        "key":  license_key,
        "hwid": hwid,
    }
    headers = {
        "X-FMail-HWID":    hwid,
        "X-FMail-Version": __version__,
        "X-FMail-AppKey":  license_key,
        "Content-Type":    "application/json",
    }

    try:
        resp = requests.post(
            BIND_HWID_URL,
            json=payload,
            headers=headers,
            timeout=8,
        )
        result = resp.json()
        ok = resp.status_code == 200 and result.get("ok", False)
        if ok:
            logger.info("HWID bound to key %s...", license_key[:12])
        else:
            logger.warning("HWID bind failed: %s", result.get("reason", "unknown"))
        return ok
    except Exception as exc:
        logger.warning("HWID bind request failed: %s", exc)
        return False

def _verify_from_cache(license_key: str) -> VerifyResult:
    """
    Offline-проверка через зашифрованный локальный кеш.
    
    Разрешает запуск только если:
      1. Кеш существует и расшифровывается
      2. Ключ совпадает
      3. cached_at + 24ч > сейчас (кеш свежий)
    
    Это предотвращает байпас лицензии блокировкой сети.
    """
    try:
        from core.identity_cache import load_from_cache
        cached = load_from_cache(license_key)
        if cached and cached.get("ok"):
            logger.info("Offline: using cached license (age < 24h)")
            return VerifyResult(
                ok         = True,
                reason     = "offline_cache",
                plan       = cached.get("plan", ""),
                expires_at = cached.get("expires_at", ""),
                hwid_bound = cached.get("hwid_bound", False),
                offline    = True,
            )
        else:
            logger.error("Offline: no valid cache — license check failed")
            return VerifyResult(
                ok     = False,
                reason = "offline_no_cache",
                offline = True,
            )
    except Exception as exc:
        logger.error("Cache check error: %s", exc)
        return VerifyResult(ok=False, reason="cache_error", offline=True)
