"""
FMailSender — License validation module v1.0.0
Validates license against fmail.shop license server.
Caches valid license locally for offline startup.

License key format: FM-XXXXXXXX-XXXXXXXX-XXXXXXXX
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger("fmailsender.license")

LICENSE_SERVER_URL = "https://fmail.shop/api/license"
CACHE_TTL_SECS = 24 * 3600   # Re-validate every 24 hours
OFFLINE_GRACE_DAYS = 7        # Allow offline use for up to 7 days


def _get_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        return Path(appdata) / "FMailSender"
    return Path(__file__).parent.parent / "data"


DATA_DIR = _get_data_dir()
DATA_DIR.mkdir(parents=True, exist_ok=True)
LICENSE_FILE = DATA_DIR / "license.json"


def _get_hardware_id() -> str:
    """
    Stable hardware ID (HWID) — survives reboots and minor config changes.
    Источники (по убыванию стабильности):
      1. Windows MachineGuid (HKLM\\SOFTWARE\\Microsoft\\Cryptography) — сохраняется
         между перезагрузками, меняется только при переустановке Windows.
      2. UUID материнской платы (WMIC csproduct) — меняется только при замене платы.
      3. CPU ProcessorId (WMIC cpu) — меняется только при замене процессора.
      4. Fallback: MAC + OS-info (для не-Windows / если WMIC недоступен).
    Итоговый HWID меняется только при физической замене компонентов.
    """
    import subprocess as _sp
    _CF = 0x08000000  # CREATE_NO_WINDOW — скрыть консоль wmic на Windows
    components: list = []

    # 1. Windows MachineGuid
    try:
        import winreg as _wr
        _key = _wr.OpenKey(_wr.HKEY_LOCAL_MACHINE,
                           r"SOFTWARE\Microsoft\Cryptography")
        _guid, _ = _wr.QueryValueEx(_key, "MachineGuid")
        _wr.CloseKey(_key)
        if _guid:
            components.append(f"mg:{_guid}")
    except Exception:
        pass

    # 2. Motherboard UUID
    try:
        _r = _sp.run(
            ["wmic", "csproduct", "get", "UUID", "/value"],
            capture_output=True, text=True, timeout=5, creationflags=_CF,
        )
        for _line in _r.stdout.splitlines():
            if "UUID=" in _line:
                _val = _line.split("=", 1)[-1].strip()
                if _val and "FFFFFFFF" not in _val.upper() and len(_val) > 8:
                    components.append(f"mb:{_val}")
                break
    except Exception:
        pass

    # 3. CPU ProcessorId
    try:
        _r = _sp.run(
            ["wmic", "cpu", "get", "ProcessorId", "/value"],
            capture_output=True, text=True, timeout=5, creationflags=_CF,
        )
        for _line in _r.stdout.splitlines():
            if "ProcessorId=" in _line:
                _val = _line.split("=", 1)[-1].strip()
                if _val:
                    components.append(f"cpu:{_val}")
                break
    except Exception:
        pass

    # 4. Fallback (non-Windows / WMIC unavailable)
    if not components:
        try:
            _node = uuid.getnode()
            components.append(
                f"mac:{_node}:{platform.machine()}:{platform.node() or 'x'}"
            )
        except Exception:
            components.append("fallback")

    _raw = "|".join(components)
    return hashlib.sha256(_raw.encode()).hexdigest()[:32]


def _load_cached() -> Optional[dict]:
    if not LICENSE_FILE.exists():
        return None
    try:
        return json.loads(LICENSE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_cache(data: dict) -> None:
    try:
        tmp = LICENSE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(LICENSE_FILE)
    except Exception as exc:
        logger.warning("license cache write failed: %s", exc)


def _validate_online(key: str, hwid: str, timeout: float = 10.0) -> dict:
    try:
        import requests
        resp = requests.post(
            LICENSE_SERVER_URL + "/validate",
            json={"key": key, "hwid": hwid},
            timeout=timeout,
        )
        if resp.status_code == 200:
            return resp.json()
        return {"valid": False, "error": f"HTTP {resp.status_code}"}
    except ImportError:
        return {"valid": False, "error": "requests not installed", "offline": True}
    except Exception as exc:
        return {"valid": False, "error": str(exc), "offline": True}


def get_license_status() -> dict:
    """Returns current license status. Checks cache, re-validates online if stale."""
    hwid = _get_hardware_id()
    cached = _load_cached()

    if not cached or not cached.get("key"):
        return {
            "valid": False,
            "plan": None,
            "hwid": hwid,
            "message": "Лицензия не активирована",
            "requires_activation": True,
        }

    key = cached["key"]

    # Fresh cache — skip network
    if (time.time() - cached.get("validated_at", 0)) < CACHE_TTL_SECS:
        return {
            "valid": cached.get("valid", False),
            "plan": cached.get("plan"),
            "expires_at": cached.get("expires_at"),
            "hwid": hwid,
            "key": key[:12] + "****",
            "message": cached.get("message", ""),
            "from_cache": True,
        }

    # Online re-validation
    result = _validate_online(key, hwid)
    if result.get("offline"):
        if (time.time() - cached.get("validated_at", 0)) < (OFFLINE_GRACE_DAYS * 86400):
            return {
                "valid": cached.get("valid", False),
                "plan": cached.get("plan"),
                "expires_at": cached.get("expires_at"),
                "hwid": hwid,
                "key": key[:12] + "****",
                "message": "Оффлайн-режим (нет связи с сервером лицензий)",
                "offline": True,
                "from_cache": True,
            }
        return {"valid": False, "hwid": hwid, "message": "Лицензия не подтверждена: нет связи с сервером"}

    cached.update({
        "valid": result.get("valid", False),
        "plan": result.get("plan", cached.get("plan")),
        "expires_at": result.get("expires_at"),
        "message": result.get("message", ""),
        "validated_at": time.time(),
    })
    _save_cache(cached)
    return {
        "valid": result.get("valid", False),
        "plan": result.get("plan"),
        "expires_at": result.get("expires_at"),
        "hwid": hwid,
        "key": key[:12] + "****",
        "message": result.get("message", ""),
    }


def activate_license_key(key: str) -> dict:
    """Activate a license key on this machine."""
    if not key or not key.upper().startswith("FM-"):
        raise ValueError("Неверный формат ключа. Ожидается: FM-XXXXXXXX-XXXXXXXX-XXXXXXXX")

    hwid = _get_hardware_id()
    logger.info("Activating license key %s... hwid=%s...", key[:12], hwid[:8])

    try:
        import requests
        resp = requests.post(
            LICENSE_SERVER_URL + "/activate",
            json={"key": key, "hwid": hwid},
            timeout=15.0,
        )
        result = resp.json()
        if not result.get("valid") and resp.status_code != 200:
            raise RuntimeError(result.get("error") or result.get("message") or "Ключ недействителен")
    except ImportError:
        # requests unavailable — accept key offline
        result = {"valid": True, "plan": "offline", "message": "Ключ сохранён (оффлайн)"}
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Не удалось связаться с сервером лицензий: {exc}") from exc

    cache_data = {
        "key": key,
        "valid": True,
        "plan": result.get("plan", "unknown"),
        "expires_at": result.get("expires_at"),
        "hwid": hwid,
        "message": result.get("message", "Активировано"),
        "activated_at": time.time(),
        "validated_at": time.time(),
    }
    _save_cache(cache_data)
    logger.info("License activated: plan=%s", cache_data["plan"])

    return {
        "success": True,
        "plan": cache_data["plan"],
        "expires_at": cache_data.get("expires_at"),
        "message": result.get("message", "Лицензия успешно активирована"),
    }
