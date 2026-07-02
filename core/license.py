"""
FMailSender — License validation module v1.4.0
Validates license against fmail.shop license server.
Caches valid license locally for offline startup.

License key format: FMSND-XXXXXX-XXXXXX-XXXXXX-XXXXXX
(Legacy format FM-XXXXXXXX-XXXXXXXX-XXXXXXXX also accepted)

Remote API:
  POST https://fmail.shop/v1/verify   — validate existing key + hwid
  POST https://fmail.shop/v1/activate — bind key to hwid

v1.4.0 fixes:
  - WMIC subprocess calls REMOVED — replaced with:
      1. winreg  (MachineGuid — <1 ms, always works)
      2. wmi Python package  (Win32_ComputerSystemProduct + Win32_Processor)
      3. PowerShell Get-WmiObject fallback (if wmi package unavailable)
      4. MAC + OS info  (non-Windows / all above failed)
  - Max HWID latency reduced from 10 s → <1 s on modern Windows
  - WMIC was deprecated in Win 10 21H1 and removed in some Win 11 builds
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

# HWID is stable for the lifetime of the process — cache after first call.
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

    Sources (in order of priority):
      1. Windows MachineGuid (winreg — <1 ms, always works on Windows)
      2. Win32_ComputerSystemProduct.UUID  (wmi Python package — <100 ms)
      3. Win32_Processor.ProcessorId       (wmi Python package — <100 ms)
      4. PowerShell Get-WmiObject fallback (if wmi package unavailable)
      5. MAC + OS info (non-Windows / all above failed)

    v1.4.0: WMIC subprocess calls removed — they were deprecated in
    Windows 10 21H1 and removed in some Windows 11 builds, causing
    hangs and empty results.

    Result is cached for the lifetime of the process.
    """
    global _hwid_cache
    if _hwid_cache is not None:
        return _hwid_cache

    components: list[str] = []

    # ── 1. Windows MachineGuid (registry, <1 ms) ──────────────────────────────
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

    # ── 2 & 3. wmi Python package (fast, no subprocess) ───────────────────────
    if len(components) < 2:
        try:
            import wmi as _wmi
            _c = _wmi.WMI(find_classes=False)

            # UUID from Win32_ComputerSystemProduct
            try:
                for _item in _c.Win32_ComputerSystemProduct():
                    _val = getattr(_item, "UUID", "") or ""
                    _val = _val.strip()
                    if _val and "FFFFFFFF" not in _val.upper() and len(_val) > 8:
                        components.append(f"mb:{_val}")
                        break
            except Exception:
                pass

            # ProcessorId from Win32_Processor
            try:
                for _item in _c.Win32_Processor():
                    _val = getattr(_item, "ProcessorId", "") or ""
                    _val = _val.strip()
                    if _val:
                        components.append(f"cpu:{_val}")
                        break
            except Exception:
                pass

        except Exception:
            # wmi not available — try PowerShell fallback
            _ps_tried = False
            if sys.platform == "win32" and len(components) < 2:
                try:
                    import subprocess as _sp
                    _CF = 0x08000000  # CREATE_NO_WINDOW
                    _r = _sp.run(
                        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                         "(Get-WmiObject Win32_ComputerSystemProduct).UUID"],
                        capture_output=True, text=True, timeout=8,
                        creationflags=_CF,
                    )
                    _val = (_r.stdout or "").strip()
                    if _val and "FFFFFFFF" not in _val.upper() and len(_val) > 8:
                        components.append(f"mb:{_val}")
                    _ps_tried = True
                except Exception:
                    pass

                if not _ps_tried or len(components) < 2:
                    try:
                        _r = _sp.run(
                            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                             "(Get-WmiObject Win32_Processor).ProcessorId"],
                            capture_output=True, text=True, timeout=8,
                            creationflags=_CF,
                        )
                        _val = (_r.stdout or "").strip()
                        if _val:
                            components.append(f"cpu:{_val}")
                    except Exception:
                        pass

    # ── 4. Fallback: MAC + OS info (non-Windows / WMIC/wmi unavailable) ───────
    if not components:
        try:
            _node = uuid.getnode()
            components.append(
                f"mac:{_node}:{platform.machine()}:{platform.node() or 'x'}"
            )
        except Exception:
            components.append("fallback")

    _raw = "|".join(sorted(components))  # sorted for determinism
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


def _decode_jwt_payload(token: str) -> dict:
    """Decode JWT payload without verification (server already validated).
    Returns empty dict on any error.
    """
    try:
        import base64
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        payload_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        return json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        return {}


def _parse_error_detail(resp) -> str:
    """Parse error detail from a non-200 response body."""
    try:
        data = resp.json()
        return (
            data.get("detail")
            or data.get("error")
            or data.get("message")
            or f"HTTP {resp.status_code}"
        )
    except Exception:
        return f"HTTP {resp.status_code}"


def _hwid_mismatch_message() -> str:
    return (
        "Этот ключ уже привязан к другому компьютеру. "
        "Обратитесь в поддержку для сброса привязки HWID."
    )


def get_cached_license_status() -> dict:
    """Return license status from local cache ONLY — no WMI, no network, <1 ms.

    Used by GET /api/license for instant startup response.
    Full online validation runs concurrently via the background task.

    Returns the same dict shape as validate_on_startup() but with
    ``"from_cache": True`` to let callers distinguish the source.
    """
    hwid_hint = _hwid_cache or "pending"
    cached = _load_cached()

    if not cached or not cached.get("key"):
        return {
            "valid": False,
            "hwid": hwid_hint,
            "message": "Лицензия не активирована",
            "requires_activation": True,
            "from_cache": True,
        }

    return {
        "valid": bool(cached.get("valid", False)),
        "plan": cached.get("plan"),
        "expires_at": cached.get("expires_at"),
        "hwid": hwid_hint,
        "key": cached["key"][:12] + "****",
        "message": cached.get("message", ""),
        "from_cache": True,
    }


def _validate_online(key: str, hwid: str, timeout: float = 10.0) -> dict:
    """Call /v1/verify on fmail.shop to validate a key."""
    try:
        import requests
        connect_t = min(timeout, 5.0)
        read_t    = max(timeout, 20.0)
        resp = requests.post(
            LICENSE_VALIDATE_URL,
            json={"key": key, "hwid": hwid},
            timeout=(connect_t, read_t),
        )
        if resp.status_code == 200:
            return resp.json()

        detail = _parse_error_detail(resp)

        if resp.status_code == 403:
            detail_lower = detail.lower()
            if "hwid" in detail_lower or "mismatch" in detail_lower or "device" in detail_lower:
                return {
                    "valid": False,
                    "error": detail,
                    "message": _hwid_mismatch_message(),
                    "hwid_mismatch": True,
                }
            return {
                "valid": False,
                "error": detail,
                "message": f"Лицензия недействительна: {detail}",
            }
        if resp.status_code == 404:
            return {
                "valid": False,
                "error": detail,
                "message": "Лицензионный ключ не найден на сервере.",
            }

        return {"valid": False, "error": f"HTTP {resp.status_code}: {detail}"}

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

        if resp.status_code != 200:
            detail = _parse_error_detail(resp)
            detail_lower = (detail or "").lower()
            if "hwid" in detail_lower or "mismatch" in detail_lower or "device" in detail_lower:
                raise RuntimeError(_hwid_mismatch_message())
            raise RuntimeError(detail or "Ключ недействителен")

        if result.get("valid") is False:
            detail = result.get("detail") or result.get("error") or result.get("message") or "Ключ недействителен"
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

    plan = result.get("plan")
    expires_at = result.get("expires_at")

    if not plan or not expires_at:
        token = result.get("token", "")
        if token:
            payload = _decode_jwt_payload(token)
            if not plan:
                plan = payload.get("plan", "unknown")
            if not expires_at:
                exp_ts = payload.get("exp")
                if exp_ts:
                    import datetime
                    expires_at = datetime.datetime.fromtimestamp(
                        exp_ts, tz=datetime.timezone.utc
                    ).isoformat()

    cache_data = {
        "key": key,
        "valid": True,
        "plan": plan or "unknown",
        "expires_at": expires_at,
        "hwid": hwid,
        "message": result.get("message", "Активировано"),
        "activated_at": time.time(),
        "validated_at": time.time(),
    }
    _save_cache(cache_data)
    logger.info("License activated: plan=%s expires=%s", cache_data["plan"], cache_data.get("expires_at"))

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
      - If server is unreachable → also returns valid=False (no offline grace).

    HWID is cached after first call — subsequent calls within the same process
    are instant (no WMI, no subprocess).
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
        is_valid = bool(result.get("valid", False))
        message = result.get("message", "") or result.get("error", "")
        updated = {
            **cached,
            "valid": is_valid,
            "plan": result.get("plan", cached.get("plan")),
            "expires_at": result.get("expires_at") or cached.get("expires_at"),
            "message": message,
            "validated_at": time.time(),
        }
        _save_cache(updated)
        return {
            "valid": is_valid,
            "plan": updated.get("plan"),
            "expires_at": updated.get("expires_at"),
            "hwid": hwid,
            "key": key[:12] + "****",
            "message": message,
            "hwid_mismatch": result.get("hwid_mismatch", False),
        }

    # Network error or requests unavailable — NO offline grace period.
    return {
        "valid": False,
        "hwid": hwid,
        "message": (
            "Нет связи с сервером лицензий. "
            "Проверьте подключение к интернету и перезапустите приложение."
        ),
        "offline": True,
    }
