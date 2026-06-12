"""
Система лицензирования: HWID-генератор, проверка ключа, JWT-токен.
Поддерживает offline grace period 72ч с кэшированным payload.
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
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

import jwt
import requests
from cryptography.fernet import Fernet

from core._version import APP_VERSION

logger = logging.getLogger("license")

# ── Константы ─────────────────────────────────────────────────────────────────
HWID_SALT: str = os.environ.get("HWID_SALT", "")

# LICENSE_API_URL — всегда берётся из env на сервере; клиент тоже может переопределить
LICENSE_API_URL = os.environ.get(
    "LICENSE_API_URL",
    "http://31.76.100.190:8000/v1/activate",
)
OFFLINE_GRACE_HOURS = 72
LICENSE_FILE = Path(os.environ.get("APPDATA", ".")) / "FMailSender" / "license.dat"

KEY_PREFIX = "FMSND"
_JWT_SECRET_FALLBACK = os.environ.get("JWT_SECRET", "")


# ── Анти-отладчик ─────────────────────────────────────────────────────────────

def _check_debugger() -> bool:
    if platform.system() != "Windows":
        return False
    try:
        return bool(ctypes.windll.kernel32.IsDebuggerPresent())
    except Exception:
        return False


def security_check() -> None:
    if _check_debugger():
        logger.warning("Debugger detected — running in debug mode")


# ── HWID-генератор ────────────────────────────────────────────────────────────

def _get_cpu_id() -> str:
    if platform.system() == "Windows":
        try:
            import wmi
            c = wmi.WMI()
            for proc in c.Win32_Processor():
                return proc.ProcessorId.strip() if proc.ProcessorId else ""
        except Exception:
            pass
        try:
            result = subprocess.run(
                ["wmic", "cpu", "get", "ProcessorId", "/value"],
                capture_output=True, text=True, timeout=5
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
    if platform.system() == "Windows":
        try:
            import wmi
            c = wmi.WMI()
            for disk in c.Win32_DiskDrive():
                if disk.SerialNumber:
                    return disk.SerialNumber.strip()
        except Exception:
            pass
        try:
            result = subprocess.run(
                ["wmic", "diskdrive", "get", "SerialNumber", "/value"],
                capture_output=True, text=True, timeout=5
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
    if platform.system() == "Windows":
        try:
            import wmi
            c = wmi.WMI()
            for board in c.Win32_BaseBoard():
                if board.SerialNumber:
                    return board.SerialNumber.strip()
        except Exception:
            pass
        try:
            result = subprocess.run(
                ["wmic", "baseboard", "get", "SerialNumber", "/value"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                if "SerialNumber=" in line:
                    val = line.split("=")[1].strip()
                    if val:
                        return val
        except Exception:
            pass
    return "UNKNOWN_BOARD"


def generate_hwid() -> str:
    """Генерирует HWID только из аппаратных компонентов. Формат: XXXX-XXXX-XXXX-XXXX"""
    # HWID_SALT намеренно исключён — HWID должен зависеть только от железа
    components = [
        _get_cpu_id(),
        _get_mac_address(),
        _get_disk_serial(),
        _get_board_id(),
    ]
    raw = "|".join(components).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest().upper()
    groups = [digest[i:i+4] for i in range(0, 16, 4)]
    return "-".join(groups)


# ── Шифрование license.dat ────────────────────────────────────────────────────

def _get_fernet_key() -> bytes:
    hwid = generate_hwid()
    key_material = hashlib.sha256((hwid + HWID_SALT).encode()).digest()
    return base64.urlsafe_b64encode(key_material)


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
        self.expires_at: datetime = datetime.fromtimestamp(exp) if exp else datetime(2099, 12, 31)
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
        return f"LicenseInfo(plan={self.plan}, expires={self.expires_at.date()}, threads={self.max_threads})"


class LicenseError(Exception):
    pass


# ── Активация ─────────────────────────────────────────────────────────────────

def activate_license(key: str, progress_callback=None) -> Tuple[bool, str]:
    key_upper = key.strip().upper()

    if not validate_key_format(key_upper):
        return False, f"Неверный формат ключа.\nОжидается: {KEY_PREFIX}-XXXXXX-XXXXXX-XXXXXX-XXXXXX"

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
                headers={"Content-Type": "application/json", "User-Agent": f"FMailSender/{APP_VERSION}"},
        )
        response.raise_for_status()
        data = response.json()

        if progress_callback:
            progress_callback(3, "Получение токена лицензии...")

        token_val = data.get("token")
        if not token_val:
            return False, "Сервер не вернул токен. Проверьте ключ."

        # Верифицируем и кэшируем payload — используем при офлайн-проверке
        jwt_secret = _JWT_SECRET_FALLBACK
        cached_payload: Optional[dict] = None
        if jwt_secret:
            try:
                cached_payload = jwt.decode(token_val, jwt_secret, algorithms=["HS256"])
            except jwt.InvalidTokenError:
                cached_payload = None

        raw_key = hashlib.sha256((hwid + HWID_SALT).encode()).digest()
        seal = _hmac_mod.new(raw_key, token_val.encode("utf-8"), "sha256").hexdigest()

        license_data = {
            "token": token_val,
            "hwid": hwid,
            "key": key_upper,
            "activated_at": time.time(),
            "last_online": time.time(),
            "seal": seal,
        }
        if cached_payload:
            license_data["cached_payload"] = cached_payload

        _save_license_data(license_data)

        if progress_callback:
            progress_callback(4, "Лицензия успешно активирована!")

        return True, f"Активация успешна!\n\nВаш ключ: {key_upper}"

    except requests.ConnectionError as e:
        err_detail = str(e)
        if "refused" in err_detail.lower() or "actively refused" in err_detail.lower():
            return False, "Сервер лицензирования недоступен. Попробуйте позже."
        return False, f"Ошибка сети: проверьте подключение к интернету."
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

    # Валидация seal
    token_val = data.get("token", "")
    stored_seal = data.get("seal", "")
    if token_val and stored_seal:
        raw_key = hashlib.sha256((hwid + HWID_SALT).encode()).digest()
        expected_seal = _hmac_mod.new(raw_key, token_val.encode("utf-8"), "sha256").hexdigest()
        if not _hmac_mod.compare_digest(expected_seal, stored_seal):
            return False, None, "Файл лицензии повреждён. Активируйте заново."

    jwt_secret = _JWT_SECRET_FALLBACK
    try:
        if jwt_secret:
            payload = jwt.decode(token_val, jwt_secret, algorithms=["HS256"])
        else:
            # Нет JWT_SECRET в клиентском окружении — используем кэшированный payload
            cached = data.get("cached_payload")
            if cached:
                payload = cached
            else:
                raise jwt.InvalidTokenError("no secret and no cached payload")

        info = LicenseInfo(payload)
        if info.is_expired:
            return False, None, "Срок лицензии истёк. Продлите подписку."
        data["last_online"] = time.time()
        try:
            _save_license_data(data)
        except Exception:
            pass
        return True, info, "OK"

    except jwt.ExpiredSignatureError:
        return False, None, "Срок лицензии истёк. Продлите подписку."

    except jwt.InvalidTokenError:
        last_online = data.get("last_online", 0)
        if time.time() - last_online < OFFLINE_GRACE_HOURS * 3600:
            hours_left = int(OFFLINE_GRACE_HOURS - (time.time() - last_online) / 3600)
            logger.warning(f"JWT offline grace: {hours_left}h left")
            # Используем кэшированный payload — безопаснее чем verify_signature=False
            cached = data.get("cached_payload")
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
