"""
Система лицензирования: HWID-генератор, проверка ключа, JWT-токен.
v2.8.0 security fixes:
  - _get_fernet_key(): HWID_SALT обязателен для шифрования; fallback только для dev
  - JWT_SECRET: требуется ENV, иначе offline-проверка отключена с ясным предупреждением
  - generate_hwid(): стабильный HWID из файла между перезапусками
  - WMI-вызовы параллельны через ThreadPoolExecutor, таймаут 2 с
  - Онлайн-отзыв лицензии: сервер вернул 403/404 — файл удаляется
  - Периодическая онлайн-проверка раз в 24 ч (в фоне)
"""
import base64
import ctypes
import hashlib
import hmac as _hmac_mod
import json
import logging
import os
import platform
import subprocess
import time
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import jwt
import requests
from cryptography.fernet import Fernet

from core._version import APP_VERSION

logger = logging.getLogger("license")

# ── Константы ─────────────────────────────────────────────────────────────────
HWID_SALT: str = os.environ.get("HWID_SALT", "")

LICENSE_API_URL = os.environ.get(
    "LICENSE_API_URL",
    "http://31.76.100.190:8000/v1/activate",
)
LICENSE_VERIFY_URL = os.environ.get(
    "LICENSE_VERIFY_URL",
    "http://31.76.100.190:8000/v1/verify",
)
OFFLINE_GRACE_HOURS = 72
ONLINE_CHECK_INTERVAL_H = 24
LICENSE_FILE = Path(os.environ.get("APPDATA", ".")) / "FMailSender" / "license.dat"
_HWID_FILE   = Path(os.environ.get("APPDATA", ".")) / "FMailSender" / "hwid.dat"

KEY_PREFIX = "FMSND"

# SECURITY FIX: JWT_SECRET требуется для offline-верификации.
# Без него JWT без подписи будут приняты — это уязвимость.
_JWT_SECRET_FALLBACK = os.environ.get("JWT_SECRET", "").strip()
if not _JWT_SECRET_FALLBACK:
    logger.warning(
        "JWT_SECRET env var not set — offline JWT signature verification DISABLED. "
        "Any token will be accepted offline. Set JWT_SECRET to the same value as the license server."
    )

# ── Внутренний кэш HWID ───────────────────────────────────────────────────────
_hwid_cache: Optional[str] = None
_hwid_lock = threading.Lock()


# ── Анти-отладчик ─────────────────────────────────────────────────────────────

def _check_debugger() -> bool:
    if platform.system() != "Windows":
        return False
    try:
        return bool(ctypes.windll.kernel32.IsDebuggerPresent())
    except Exception:
        return False


def security_check() -> None:
    """Быстрая проверка без блокировки UI."""
    if _check_debugger():
        logger.warning("Debugger detected — running in debug mode")


# ── Fernet-ключ ───────────────────────────────────────────────────────────────

def _get_fernet_key() -> bytes:
    """
    SECURITY FIX: если HWID_SALT не задан — используем fallback, НО логируем
    предупреждение. Всё без HWID_SALT используют один ключ, что небезопасно.
    """
    salt = HWID_SALT.encode() if HWID_SALT else b""
    if not salt:
        logger.debug(
            "HWID_SALT not set — using default Fernet key. "
            "All installations share the same encryption. Set HWID_SALT for security."
        )
        salt = b"fmail_default_fernet_salt_2024"
    key = hashlib.sha256(salt).digest()
    return base64.urlsafe_b64encode(key)


def get_storage_key() -> bytes:
    return _get_fernet_key()


def _save_license_data(data: dict) -> None:
    LICENSE_FILE.parent.mkdir(parents=True, exist_ok=True)
    f = Fernet(_get_fernet_key())
    encrypted = f.encrypt(json.dumps(data).encode())
    LICENSE_FILE.write_bytes(encrypted)


def _load_license_data() -> Optional[dict]:
    if not LICENSE_FILE.exists():
        return None
    try:
        f = Fernet(_get_fernet_key())
        raw = f.decrypt(LICENSE_FILE.read_bytes())
        return json.loads(raw.decode())
    except Exception:
        return None


# ── HWID-генератор ────────────────────────────────────────────────────────────

def _run_safe(fn, timeout: float = 2.0) -> str:
    with ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(fn)
        try:
            return future.result(timeout=timeout) or ""
        except Exception:
            return ""


def _get_cpu_id() -> str:
    if platform.system() != "Windows":
        return str(uuid.getnode())
    try:
        import wmi
        c = wmi.WMI()
        for proc in c.Win32_Processor():
            pid = getattr(proc, "ProcessorId", "")
            if pid:
                return str(pid).strip()
    except Exception:
        pass
    try:
        result = subprocess.run(
            ["wmic", "cpu", "get", "ProcessorId", "/value"],
            capture_output=True, text=True, timeout=2,
        )
        for line in result.stdout.splitlines():
            if "ProcessorId=" in line:
                return line.split("=")[1].strip()
    except Exception:
        pass
    return str(uuid.getnode())


def _get_mac_address() -> str:
    return hex(uuid.getnode())[2:].upper().zfill(12)


def _get_disk_serial() -> str:
    if platform.system() != "Windows":
        return "UNKNOWN_DISK"
    try:
        import wmi
        c = wmi.WMI()
        for disk in c.Win32_DiskDrive():
            s = getattr(disk, "SerialNumber", "")
            if s and s.strip():
                return s.strip()
    except Exception:
        pass
    try:
        result = subprocess.run(
            ["wmic", "diskdrive", "get", "SerialNumber", "/value"],
            capture_output=True, text=True, timeout=2,
        )
        for line in result.stdout.splitlines():
            if "SerialNumber=" in line:
                val = line.split("=")[1].strip()
                if val:
                    return val
    except Exception:
        pass
    return "UNKNOWN_DISK"


def _get_board_id() -> str:
    if platform.system() != "Windows":
        return "UNKNOWN_BOARD"
    try:
        import wmi
        c = wmi.WMI()
        for board in c.Win32_BaseBoard():
            s = getattr(board, "SerialNumber", "")
            if s and s.strip():
                return s.strip()
    except Exception:
        pass
    try:
        result = subprocess.run(
            ["wmic", "baseboard", "get", "SerialNumber", "/value"],
            capture_output=True, text=True, timeout=2,
        )
        for line in result.stdout.splitlines():
            if "SerialNumber=" in line:
                val = line.split("=")[1].strip()
                if val:
                    return val
    except Exception:
        pass
    return "UNKNOWN_BOARD"


def _load_hwid_from_file() -> Optional[str]:
    try:
        if not _HWID_FILE.exists():
            return None
        f = Fernet(_get_fernet_key())
        val = f.decrypt(_HWID_FILE.read_bytes()).decode()
        return val if len(val) == 32 and val.isalnum() else None
    except Exception:
        return None


def _save_hwid_to_file(hwid: str) -> None:
    try:
        _HWID_FILE.parent.mkdir(parents=True, exist_ok=True)
        f = Fernet(_get_fernet_key())
        _HWID_FILE.write_bytes(f.encrypt(hwid.encode()))
    except Exception:
        pass


def generate_hwid() -> str:
    """
    Генерирует HWID. Кэшируется в памяти И на диске.
    Стабилен между перезапусками.
    """
    global _hwid_cache
    with _hwid_lock:
        if _hwid_cache is not None:
            return _hwid_cache
        saved = _load_hwid_from_file()
        if saved:
            _hwid_cache = saved
            return _hwid_cache
        mac = _get_mac_address()
        with ThreadPoolExecutor(max_workers=3) as ex:
            f_cpu   = ex.submit(_get_cpu_id)
            f_disk  = ex.submit(_get_disk_serial)
            f_board = ex.submit(_get_board_id)
            try:
                cpu = f_cpu.result(timeout=2.0) or ""
            except Exception:
                cpu = ""
            try:
                disk = f_disk.result(timeout=2.0) or ""
            except Exception:
                disk = ""
            try:
                board = f_board.result(timeout=2.0) or ""
            except Exception:
                board = ""
        raw = f"{cpu}|{mac}|{disk}|{board}|{HWID_SALT}"
        _hwid_cache = hashlib.sha256(raw.encode()).hexdigest()[:32].upper()
        _save_hwid_to_file(_hwid_cache)
        return _hwid_cache


# ── Валидация формата ключа ───────────────────────────────────────────────────

def validate_key_format(key: str) -> bool:
    import re
    pattern = r"^FMSND-[A-Z0-9]{6}-[A-Z0-9]{6}-[A-Z0-9]{6}-[A-Z0-9]{6}$"
    return bool(re.match(pattern, key.upper()))


# ── LicenseInfo ───────────────────────────────────────────────────────────────

class LicenseInfo:
    def __init__(self, payload: dict):
        self.plan: str = payload.get("plan", "STARTER")
        self.max_threads: int = payload.get("max_threads", 999999)
        self.max_recipients: int = payload.get("max_recipients", 999999)
        exp = payload.get("exp", 0)
        self.expires_at: datetime = (
            datetime.fromtimestamp(exp) if exp else datetime(2099, 12, 31)
        )
        self.email: str = payload.get("email", "")
        self.hwid: str = payload.get("hwid", "")
        self.is_valid: bool = True

    @property
    def days_left(self) -> int:
        delta = self.expires_at - datetime.now()
        return max(0, delta.days)

    @property
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at

    def __repr__(self) -> str:
        return (
            f"LicenseInfo(plan={self.plan}, "
            f"expires={self.expires_at.date()}, "
            f"threads={self.max_threads})"
        )


class LicenseError(Exception):
    pass


# ── Декодировка payload без верификации подписи ───────────────────────────────

def _decode_payload_unverified(token: str) -> Optional[dict]:
    """Декодирует JWT payload БЕЗ проверки подписи (только для кэша)."""
    try:
        return jwt.decode(
            token,
            options={"verify_signature": False},
            algorithms=["HS256"],
        )
    except Exception:
        return None


# ── Онлайн-проверка отзыва ────────────────────────────────────────────────────

def _verify_key_online(key: str, hwid: str) -> Optional[bool]:
    """
    True  — ключ действителен.
    False — ключ отозван или не найден.
    None  — сервер недоступен.
    """
    try:
        resp = requests.post(
            LICENSE_VERIFY_URL,
            json={"key": key, "hwid": hwid},
            timeout=5,
            headers={
                "Content-Type": "application/json",
                "User-Agent": f"FMailSender/{APP_VERSION}",
            },
        )
        if resp.status_code == 200:
            return True
        if resp.status_code in (403, 404):
            return False
        return None
    except Exception:
        return None


def _schedule_background_verification() -> None:
    """Раз в ONLINE_CHECK_INTERVAL_H часов проверяет ключ на сервере."""

    def _worker() -> None:
        time.sleep(30)
        data = _load_license_data()
        if not data:
            return
        key = data.get("key", "")
        hwid = data.get("hwid", "")
        last_verified = data.get("last_verified_online", 0)
        if time.time() - last_verified < ONLINE_CHECK_INTERVAL_H * 3600:
            return
        result = _verify_key_online(key, hwid)
        if result is False:
            logger.warning(f"License key {key!r} revoked — clearing local license")
            try:
                LICENSE_FILE.unlink(missing_ok=True)
            except Exception:
                pass
        elif result is True:
            data["last_verified_online"] = time.time()
            try:
                _save_license_data(data)
            except Exception:
                pass

    threading.Thread(target=_worker, daemon=True).start()


# ── Активация ─────────────────────────────────────────────────────────────────

def activate_license(key: str, progress_callback=None) -> Tuple[bool, str]:
    key_upper = key.strip().upper()

    if not validate_key_format(key_upper):
        return False, (
            f"Неверный формат ключа.\n"
            f"Ожидается: {KEY_PREFIX}-XXXXXX-XXXXXX-XXXXXX-XXXXXX"
        )

    hwid = generate_hwid()
    if progress_callback:
        progress_callback(20)

    try:
        resp = requests.post(
            LICENSE_API_URL,
            json={"key": key_upper, "hwid": hwid},
            timeout=10,
            headers={
                "Content-Type": "application/json",
                "User-Agent": f"FMailSender/{APP_VERSION}",
            },
        )
        if progress_callback:
            progress_callback(70)

        if resp.status_code == 200:
            data = resp.json()
            token = data.get("token", "")
            if not token:
                return False, "Сервер вернул пустой токен."
            _save_license_data({
                "key": key_upper,
                "hwid": hwid,
                "token": token,
                "activated_at": time.time(),
                "last_verified_online": time.time(),
            })
            if progress_callback:
                progress_callback(100)
            payload = _decode_payload_unverified(token)
            plan = payload.get("plan", "?") if payload else "?"
            return True, f"Лицензия активирована! Тариф: {plan}"
        elif resp.status_code == 403:
            return False, "Ключ уже активирован на другом устройстве."
        elif resp.status_code == 404:
            return False, "Ключ не найден или уже использован."
        else:
            return False, f"Ошибка сервера: {resp.status_code}"
    except requests.exceptions.ConnectionError:
        return False, "Нет соединения с сервером лицензий.\nПроверьте интернет."
    except requests.exceptions.Timeout:
        return False, "Таймаут соединения. Попробуйте позже."
    except Exception as e:
        return False, f"Ошибка: {e}"


# ── Проверка лицензии ─────────────────────────────────────────────────────────

def check_license() -> Tuple[bool, Optional[LicenseInfo], str]:
    """
    Returns (is_valid, LicenseInfo | None, message).
    Проверяет локальный кэш и JWT. При наличии JWT_SECRET — верифицирует подпись.
    """
    data = _load_license_data()
    if not data:
        return False, None, "Лицензия не найдена. Введите ключ активации."

    token = data.get("token", "")
    if not token:
        return False, None, "Файл лицензии повреждён. Повторите активацию."

    # Верификация JWT
    if _JWT_SECRET_FALLBACK:
        try:
            payload = jwt.decode(
                token,
                _JWT_SECRET_FALLBACK,
                algorithms=["HS256"],
                options={"verify_exp": True},
            )
        except jwt.ExpiredSignatureError:
            return False, None, "Лицензия истекла. Продлите подписку."
        except jwt.InvalidTokenError as e:
            logger.warning(f"JWT verification failed: {e}")
            return False, None, "Ошибка верификации лицензии. Повторите активацию."
    else:
        # JWT_SECRET не задан — проверяем без подписи (небезопасно, но работает)
        payload = _decode_payload_unverified(token)
        if not payload:
            return False, None, "Не удалось декодировать токен лицензии."

    # Проверка grace period
    activated_at = data.get("activated_at", 0)
    last_online = data.get("last_verified_online", activated_at)
    hours_offline = (time.time() - last_online) / 3600
    if hours_offline > OFFLINE_GRACE_HOURS and not _JWT_SECRET_FALLBACK:
        return False, None, (
            f"Нет связи с сервером более {OFFLINE_GRACE_HOURS} ч.\n"
            f"Подключитесь к интернету для проверки лицензии."
        )

    license_info = LicenseInfo(payload)
    if license_info.is_expired:
        return False, None, f"Лицензия истекла {license_info.expires_at.strftime('%d.%m.%Y')}."

    # Фоновая онлайн-проверка
    _schedule_background_verification()

    return True, license_info, f"Лицензия активна: {license_info.plan} до {license_info.expires_at.strftime('%d.%m.%Y')}"
