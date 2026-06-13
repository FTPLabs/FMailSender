"""
Система лицензирования: HWID-генератор, проверка ключа, JWT-токен.
v2.7.0 fixes:
  - HWID кэшируется в памяти (генерируется один раз, не блокирует UI)
  - WMI-вызовы параллельны через ThreadPoolExecutor, таймаут 2 с
  - security_check() не блокирует запуск, прогревает кэш в фоне
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
_JWT_SECRET_FALLBACK = os.environ.get("JWT_SECRET", "")
if not _JWT_SECRET_FALLBACK:
    logger.warning(
        "JWT_SECRET env var not set — offline JWT verification disabled. "
        "Set JWT_SECRET to the same value as the license server."
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
    # HWID прогревается из main() — дублирующий поток убран


# ── Fernet-ключ ───────────────────────────────────────────────────────────────

def _get_fernet_key() -> bytes:
    raw = HWID_SALT.encode() or b"fmail_default_fernet_salt_2024"
    key = hashlib.sha256(raw).digest()
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
    """Запускает fn() в потоке с таймаутом. Возвращает результат или ''."""
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
    """Загружает сохранённый HWID из зашифрованного файла."""
    try:
        if not _HWID_FILE.exists():
            return None
        f = Fernet(_get_fernet_key())
        val = f.decrypt(_HWID_FILE.read_bytes()).decode()
        return val if len(val) == 32 and val.isalnum() else None
    except Exception:
        return None


def _save_hwid_to_file(hwid: str) -> None:
    """Сохраняет HWID в зашифрованный файл для стабильности при перезапусках."""
    try:
        _HWID_FILE.parent.mkdir(parents=True, exist_ok=True)
        f = Fernet(_get_fernet_key())
        _HWID_FILE.write_bytes(f.encrypt(hwid.encode()))
    except Exception:
        pass


def generate_hwid() -> str:
    """
    Генерирует HWID. Кэшируется в памяти И на диске.
    Стабилен между перезапусками: первый запуск генерирует из железа и сохраняет
    в hwid.dat; все последующие запуски загружают из файла.
    """
    global _hwid_cache
    with _hwid_lock:
        if _hwid_cache is not None:
            return _hwid_cache
        # Загружаем с диска если файл есть (стабильно между перезапусками)
        saved = _load_hwid_from_file()
        if saved:
            _hwid_cache = saved
            return _hwid_cache
        # Нет файла — вычисляем из железа и сохраняем
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
    payload_data = {
        "hwid": hwid,
        "key": key_upper,
        "timestamp": int(time.time()),
        "version": APP_VERSION,
    }

    if progress_callback:
        progress_callback(1, "Генерация идентификатора устройства...")
        progress_callback(2, "Подключение к серверу активации...")

    try:
        response = requests.post(
            LICENSE_API_URL,
            json=payload_data,
            timeout=15,
            headers={
                "Content-Type": "application/json",
                "User-Agent": f"FMailSender/{APP_VERSION}",
            },
        )
        response.raise_for_status()
        data = response.json()

        if progress_callback:
            progress_callback(3, "Получение токена лицензии...")

        token_val = data.get("token")
        if not token_val:
            return False, "Сервер не вернул токен. Проверьте ключ."

        cached_payload = _decode_payload_unverified(token_val)

        if _JWT_SECRET_FALLBACK and cached_payload is None:
            try:
                cached_payload = jwt.decode(
                    token_val, _JWT_SECRET_FALLBACK, algorithms=["HS256"]
                )
            except jwt.InvalidTokenError:
                pass

        raw_key = hashlib.sha256((hwid + HWID_SALT).encode()).digest()
        seal = _hmac_mod.new(raw_key, token_val.encode("utf-8"), "sha256").hexdigest()

        license_data = {
            "token": token_val,
            "hwid": hwid,
            "key": key_upper,
            "activated_at": time.time(),
            "last_online": time.time(),
            "last_verified_online": time.time(),
            "seal": seal,
            "cached_payload": cached_payload,
        }

        _save_license_data(license_data)

        if progress_callback:
            progress_callback(4, "Лицензия успешно активирована!")

        return True, f"Активация успешна!\n\nВаш ключ: {key_upper}"

    except requests.ConnectionError:
        return False, "Сервер лицензирования недоступен. Попробуйте позже."
    except requests.Timeout:
        return False, "Сервер не отвечает. Попробуйте позже."
    except requests.HTTPError as e:
        if e.response is not None:
            if e.response.status_code == 403:
                return False, "Ключ уже используется на другом устройстве."
            elif e.response.status_code == 404:
                return False, "Ключ не найден или недействителен."
            return False, f"Ошибка сервера: {e.response.status_code}"
        return False, f"Ошибка HTTP: {e}"
    except Exception as e:
        return False, f"Ошибка активации: {str(e)}"


def is_activated() -> bool:
    data = _load_license_data()
    return data is not None


def check_license() -> Tuple[bool, Optional[LicenseInfo], str]:
    data = _load_license_data()
    if not data:
        return False, None, "Лицензия не найдена. Активируйте приложение."

    hwid = generate_hwid()

    if data.get("hwid") != hwid:
        return False, None, "Лицензия привязана к другому устройству. Активируйте заново."

    token_val = data.get("token", "")
    stored_seal = data.get("seal", "")

    if token_val and stored_seal:
        raw_key = hashlib.sha256((hwid + HWID_SALT).encode()).digest()
        expected_seal = _hmac_mod.new(
            raw_key, token_val.encode("utf-8"), "sha256"
        ).hexdigest()
        if not _hmac_mod.compare_digest(expected_seal, stored_seal):
            return False, None, "Файл лицензии повреждён. Активируйте заново."

    def _get_payload() -> Optional[dict]:
        if _JWT_SECRET_FALLBACK:
            try:
                return jwt.decode(
                    token_val, _JWT_SECRET_FALLBACK, algorithms=["HS256"]
                )
            except jwt.ExpiredSignatureError:
                return None
            except jwt.InvalidTokenError:
                pass
        cached = data.get("cached_payload")
        if cached:
            return cached
        return _decode_payload_unverified(token_val)

    try:
        if _JWT_SECRET_FALLBACK:
            payload = jwt.decode(
                token_val, _JWT_SECRET_FALLBACK, algorithms=["HS256"]
            )
        else:
            payload = _get_payload()
            if payload is None:
                raise jwt.InvalidTokenError("no payload available")

        info = LicenseInfo(payload)
        if info.is_expired:
            return False, None, "Срок лицензии истёк. Продлите подписку."

        data["last_online"] = time.time()
        try:
            _save_license_data(data)
        except Exception:
            pass

        _schedule_background_verification()
        return True, info, "OK"

    except jwt.ExpiredSignatureError:
        return False, None, "Срок лицензии истёк. Продлите подписку."

    except jwt.InvalidTokenError:
        last_online = data.get("last_online", 0)
        if time.time() - last_online < OFFLINE_GRACE_HOURS * 3600:
            hours_left = int(
                OFFLINE_GRACE_HOURS - (time.time() - last_online) / 3600
            )
            logger.warning(f"JWT offline grace: {hours_left}h left")
            cached = (
                data.get("cached_payload") or _decode_payload_unverified(token_val)
            )
            if cached:
                try:
                    info = LicenseInfo(cached)
                    if info.is_expired:
                        return False, None, "Срок лицензии истёк. Продлите подписку."
                    return True, info, f"Офлайн-режим ({hours_left}ч осталось)"
                except Exception:
                    pass
            return False, None, "Ошибка проверки лицензии. Проверьте интернет."
        return False, None, "Лицензия недействительна. Активируйте заново."
