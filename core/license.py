"""
FMailSender — License validation module v1.3.0
Validates license against fmail.shop license server.
Caches valid license locally for offline startup.

License key format: FMSND-XXXXXX-XXXXXX-XXXXXX-XXXXXX
(Legacy format FM-XXXXXXXX-XXXXXXXX-XXXXXXXX also accepted)

Remote API:
  POST https://fmail.shop/v1/verify   — validate existing key + hwid
  POST https://fmail.shop/v1/activate — bind key to hwid

v1.3.0 fixes:
  - WMIC calls now run in PARALLEL → max 5s instead of 15s
  - _validate_online() now parses error body on non-200 responses
  - activate_license_key() now parses JWT payload to extract plan/expires_at
  - HWID mismatch produces a clear Russian-language error message
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

    FIX v1.3.0: WMIC calls now run in PARALLEL via ThreadPoolExecutor.
    Max latency drops from 15s (3×5s sequential) to 5s (3×5s parallel).

    Result is cached for the lifetime of the process.
    """
    global _hwid_cache
    if _hwid_cache is not None:
        return _hwid_cache

    import subprocess as _sp
    _CF = 0x08000000  # CREATE_NO_WINDOW — скрыть консоль wmic на Windows
    components: list = []

    # 1. Windows MachineGuid — синхронный, быстрый (реестр, <1 ms)
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

    # 2 & 3. WMIC calls — run in PARALLEL to reduce latency from 10s to 5s
    def _wmic_uuid():
        try:
            _r = _sp.run(
                ["wmic", "csproduct", "get", "UUID", "/value"],
                capture_output=True, text=True, timeout=5, creationflags=_CF,
            )
            for _line in _r.stdout.splitlines():
                if "UUID=" in _line:
                    _val = _line.split("=", 1)[-1].strip()
                    if _val and "FFFFFFFF" not in _val.upper() and len(_val) > 8:
                        return f"mb:{_val}"
        except Exception:
            pass
        return None

    def _wmic_cpu():
        try:
            _r = _sp.run(
                ["wmic", "cpu", "get", "ProcessorId", "/value"],
                capture_output=True, text=True, timeout=5, creationflags=_CF,
            )
            for _line in _r.stdout.splitlines():
                if "ProcessorId=" in _line:
                    _val = _line.split("=", 1)[-1].strip()
                    if _val:
                        return f"cpu:{_val}"
        except Exception:
            pass
        return None

    try:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=2) as _pool:
            _futs = [_pool.submit(_wmic_uuid), _pool.submit(_wmic_cpu)]
            for _f in as_completed(_futs):
                _val = _f.result()
                if _val:
                    components.append(_val)
    except Exception:
        # Fallback: sequential if ThreadPoolExecutor fails
        _v = _wmic_uuid()
        if _v:
            components.append(_v)
        _v = _wmic_cpu()
        if _v:
            components.append(_v)

    # 4. Fallback (non-Windows / WMIC unavailable)
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
        # Base64url → base64 padding fix
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
    """Return license status from local cache ONLY — no WMIC, no network, <1 ms.

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
    """Call /v1/verify on fmail.shop to validate a key.

    FIX v1.3.0: Non-200 responses now have their body parsed for error detail.
    HWID mismatch (HTTP 403) now produces a clear Russian message.
    """
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

        # Parse error detail from response body
        detail = _parse_error_detail(resp)

        # Friendly messages for known HTTP codes
        if resp.status_code == 403:
            # Check if it's specifically HWID mismatch
            detail_lower = detail.lower()
            if "hwid" in detail_lower or "mismatch" in detail_lower or "device" in detail_lower:
                return {
                    "valid": False,
                    "error": detail,
                    "message": _hwid_mismatch_message(),
                    "hwid_mismatch": True,
                }
            # Could be revoked or expired
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
    """Activate a license key on this machine via /v1/activate.

    FIX v1.3.0: Server returns {"token": "JWT..."}.
    We now decode the JWT payload to extract plan / expires_at so the cache
    is fully populated — the UI can show the correct plan and expiry date.
    """
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
            # Clear HWID mismatch message
            detail_lower = (detail or "").lower()
            if "hwid" in detail_lower or "mismatch" in detail_lower or "device" in detail_lower:
                raise RuntimeError(_hwid_mismatch_message())
            raise RuntimeError(detail or "Ключ недействителен")

        # HTTP 200 — check if server explicitly returned valid=false
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

    # FIX v1.3.0: server returns either {token, valid, plan, expires_at}
    # (new format) or just {token} (old format). For old format, decode JWT.
    plan = result.get("plan")
    expires_at = result.get("expires_at")

    if not plan or not expires_at:
        # Decode JWT to get plan and expiry
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
        # Use result message if present, otherwise build one from error
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

    # Network error or requests module unavailable — NO offline grace period.
    return {
        "valid": False,
        "hwid": hwid,
        "message": (
            "Нет связи с сервером лицензий. "
            "Проверьте подключение к интернету и перезапустите приложение."
        ),
        "offline": True,
    }
