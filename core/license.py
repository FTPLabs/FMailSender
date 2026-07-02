"""
FMailSender — License validation module v1.2.0
Validates license against fmail.shop license server.
Caches valid license locally for offline startup.

License key format: FMSND-XXXXXX-XXXXXX-XXXXXX-XXXXXX
(Legacy format FM-XXXXXXXX-XXXXXXXX-XXXXXXXX also accepted)

Remote API:
  POST https://fmail.shop/v1/verify   — validate existing key + hwid
  POST https://fmail.shop/v1/activate — bind key to hwid
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

LICENSE_SERVER_BASE = "https://fmail.shop"
LICENSE_VALIDATE_URL = LICENSE_SERVER_BASE + "/v1/verify"
LICENSE_ACTIVATE_URL = LICENSE_SERVER_BASE + "/v1/activate"

# Backward-compat alias used by code that still reads LICENSE_SERVER_URL
LICENSE_SERVER_URL = LICENSE_SERVER_BASE

CACHE_TTL_SECS = 24 * 3600   # Re-validate every 24 hours
OFFLINE_GRACE_DAYS = 0        # No offline grace — server must confirm validity

# Valid key prefixes — must match KEY_PREFIX in server/config.py
_VALID_PREFIXES = ("FMSND-", "FM-")

# HWID is stable for the lifetime of the process — cache after first call
# to avoid repeated WMIC subprocess calls (each takes up to 5 seconds).
_hwid_cache: Optional[str] = None


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
    Sources (by stability):
      1. Windows MachineGuid (HKLM\\SOFTWARE\\Microsoft\\Cryptography)
      2. UUID материнской платы (WMIC csproduct)
      3. CPU ProcessorId (WMIC cpu)
      4. Fallback: MAC + OS-info (для не-Windows / если WMIC недоступен).

    Result is cached for the lifetime of the process — WMIC can take up to
    5 seconds per call and we must not re-run it on every license check.
    """
    global _hwid_cache
    if _hwid_cache is not None:
        return _hwid_cache

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
    _hwid_cache = hashlib.sha256(_raw.encode()).hexdigest()[:32]
    return _hwid_cache


def _is_valid_key_format(key: str) -> bool:
    """Return True if the key matches any known valid prefix."""
    key_upper = key.upper().strip()
    return any(key_upper.startswith(p) for p in _VALID_PREFIXES)


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
    """Call /v1/verify on fmail.shop to validate a key."""
    try:
        import requests
        resp = requests.post(
            LICENSE_VALIDATE_URL,
            json={"key": key, "hwid": hwid},
            timeout=timeout,
        )
        if resp.status_code == 200:
            data = resp.json()
            # Normalise: server returns {"valid":bool, "plan":..., "expires_at":...}
            return data
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
        # Server unreachable — no grace period.
        return {
            "valid": False,
            "hwid": hwid,
            "message": "Нет связи с сервером лицензий. Проверьте подключение к интернету.",
            "offline": True,
        }

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
    """Activate a license key on this machine via /v1/activate."""
    if not key or not _is_valid_key_format(key):
        raise ValueError(
            "Неверный формат ключа. Ожидается: FMSND-XXXXXX-XXXXXX-XXXXXX-XXXXXX"
        )

    hwid = _get_hardware_id()
    logger.info("Activating license key %s... hwid=%s...", key[:12], hwid[:8])

    try:
        import requests
        resp = requests.post(
            LICENSE_ACTIVATE_URL,
            json={"key": key, "hwid": hwid},
            timeout=15.0,
        )
        result = resp.json()
        # Server returns HTTP 200 with {"valid":true,...} on success
        # or HTTP 4xx with {"detail":"..."} on failure
        if resp.status_code != 200:
            detail = result.get("detail") or result.get("error") or result.get("message") or "Ключ недействителен"
            raise RuntimeError(detail)
        # Reject activation if server explicitly returns valid=false (HTTP 200)
        if result.get("valid") is False:
            detail = result.get("detail") or result.get("error") or result.get("message") or "Ключ недействителен или уже использован"
            raise RuntimeError(detail)
    except ImportError:
        raise RuntimeError(
            "Невозможно проверить лицензию: модуль requests не найден. "
            "Переустановите приложение."
        )
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Не удалось связаться с сервером лицензий: {exc}") from exc

    cache_data = {
        "key": key,
        "valid": True,  # True is safe here: server returned HTTP 200 and did not return valid=False
        "plan": result.get("plan", result.get("license_plan", "unknown")),
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


# ── Startup / periodic validation ────────────────────────────────────────────

def validate_on_startup() -> dict:
    """Always validates online. Used by GET /api/license and the hourly checker.

    Key differences from get_license_status():
      - ALWAYS calls the license server — never skips network via cache age.
      - If server explicitly returns valid=False → revoked, blocked immediately.
      - If server is unreachable (network error / timeout) → also returns
        valid=False. OFFLINE_GRACE_DAYS=0 means no offline bypass whatsoever.

    Returns the same dict shape as get_license_status().
    """
    hwid = _get_hardware_id()
    cached = _load_cached()

    if not cached or not cached.get("key"):
        return {
            "valid": False,
            "hwid": hwid,
            "message": "Лицензия не активирована",
            "requires_activation": True,
        }

    key = cached["key"]
    result = _validate_online(key, hwid)

    if not result.get("offline"):
        # Server responded — trust it unconditionally
        is_valid = bool(result.get("valid", False))
        updated = {
            **cached,
            "valid": is_valid,
            "plan": result.get("plan", cached.get("plan")),
            "expires_at": result.get("expires_at"),
            "message": result.get("message", ""),
            "validated_at": time.time(),
        }
        _save_cache(updated)
        return {
            "valid": is_valid,
            "plan": updated.get("plan"),
            "expires_at": updated.get("expires_at"),
            "hwid": hwid,
            "key": key[:12] + "****",
            "message": result.get("message", ""),
        }

    # Network error or requests module unavailable — NO offline grace period.
    # The license server must explicitly confirm validity on every startup.
    # If the server is unreachable the app is blocked immediately.
    return {
        "valid": False,
        "hwid": hwid,
        "message": (
            "Нет связи с сервером лицензий. "
            "Проверьте подключение к интернету и перезапустите приложение."
        ),
        "offline": True,
    }
