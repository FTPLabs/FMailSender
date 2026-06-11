"""
Система лицензирования: HWID-генератор, проверка ключа, JWT-токен.
Поддерживает offline grace period 72ч и демо-режим.
"""
import os
import sys
import uuid
import json
import time
import hmac as _hmac_mod
import logging
import ctypes
import hashlib
import base64
import platform
import subprocess
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime, timedelta

from cryptography.fernet import Fernet
import jwt
import requests

from core._version import APP_VERSION

logger = logging.getLogger("license")

# ──────────────────────────────────────────────
# Константы
# ──────────────────────────────────────────────
_env_salt = os.environ.get("ESP_HWID_SALT", "")
if not _env_salt:
    logger.warning("ESP_HWID_SALT not set — using built-in fallback. MUST set ESP_HWID_SALT env var in production.")
    _env_salt = "ESP-HWID-SALT-8f4e2a1c-9b3d-4f7e-8a2b-1c5d9e3f7a0b"
HWID_SALT: str = _env_salt

LICENSE_API_URL = "https://api.emailsenderpro.io/v1/activate"
OFFLINE_GRACE_HOURS = 72
LICENSE_FILE = Path(os.environ.get("APPDATA", ".")) / "EmailSenderPro" / "license.dat"

# ── ДЕМО-РЕЖИМ ───────────────────────────────
# True  = приложение запускается без лицензии (для тестирования)
# False = требуется действующий лицензионный ключ
DEMO_MODE = False
DEMO_KEY = "ESP-DEMO0-DEMO0-DEMO0-DEMO0"


# ──────────────────────────────────────────────
# Защита: анти-отладчик (только предупреждение, без выхода)
# ──────────────────────────────────────────────

def _check_debugger() -> bool:
    if platform.system() != "Windows":
        return False
    try:
        return bool(ctypes.windll.kernel32.IsDebuggerPresent())
    except Exception:
        return False


def security_check() -> None:
    """Выполняет проверку безопасности. Логирует предупреждение при отладчике."""
    if _check_debugger():
        logger.warning("Debugger detected — running in debug mode")


# ──────────────────────────────────────────────
# HWID-генератор
# ──────────────────────────────────────────────

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
    """
    Генерирует уникальный HWID устройства.
    Формат: XXXX-XXXX-XXXX-XXXX
    """
    components = [
        _get_cpu_id(),
        _get_mac_address(),
        _get_disk_serial(),
        _get_board_id(),
        HWID_SALT,
    ]
    raw = "|".join(components).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest().upper()
    groups = [digest[i:i+4] for i in range(0, 16, 4)]
    return "-".join(groups)


# ──────────────────────────────────────────────
# Шифрование license.dat
# ──────────────────────────────────────────────

def _get_fernet_key() -> bytes:
    hwid = generate_hwid()
    key_material = hashlib.sha256(
        (hwid + HWID_SALT).encode()
    ).digest()
    return base64.urlsafe_b64encode(key_material)


def get_storage_key() -> bytes:
    """Публичная обёртка для получения ключа шифрования хранимых учётных данных."""
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


# ──────────────────────────────────────────────
# Валидация ключа
# ──────────────────────────────────────────────

def validate_key_format(key: str) -> bool:
    import re
    pattern = r"^ESP-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}$"
    return bool(re.match(pattern, key.upper()))


# ──────────────────────────────────────────────
# LicenseInfo
# ──────────────────────────────────────────────

class LicenseInfo:
    def __init__(self, payload: dict):
        self.plan: str = payload.get("plan", "STARTER")
        self.max_threads: int = payload.get("max_threads", 5)
        self.max_recipients: int = payload.get("max_recipients", 1000)
        exp = payload.get("exp", 0)
        self.expires_at: datetime = datetime.fromtimestamp(exp) if exp else datetime(2099, 12, 31)
        self.email: str = payload.get("email", "")
        self.hwid: str = payload.get("hwid", "")
        self.is_demo: bool = payload.get("is_demo", False)
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


def _make_demo_license() -> LicenseInfo:
    """Создаёт демо-лицензию с ограниченным доступом (3 потока, 50 получателей, 7 дней)."""
    return LicenseInfo({
        "plan": "DEMO",
        "max_threads": 3,
        "max_recipients": 50,
        "exp": int((datetime.now() + timedelta(days=7)).timestamp()),
        "email": "demo@emailsenderpro.io",
        "hwid": "DEMO",
        "is_demo": True,
    })


# ──────────────────────────────────────────────
# Активация и проверка лицензии
# ──────────────────────────────────────────────

def activate_license(key: str, progress_callback=None) -> Tuple[bool, str]:
    key_upper = key.strip().upper()

    if key_upper == DEMO_KEY:
        if progress_callback:
            progress_callback(1, "Активация демо-ключа...")
            progress_callback(2, "Проверка ключа...")
            progress_callback(3, "Сохранение лицензии...")
        demo_data = {
            "token": "DEMO",
            "hwid": generate_hwid(),
            "key": key_upper,
            "activated_at": time.time(),
            "last_online": time.time(),
            "is_demo": True,
        }
        try:
            _save_license_data(demo_data)
        except Exception as e:
            logger.warning(f"Could not persist demo license: {e}")
        if progress_callback:
            progress_callback(4, "Демо-лицензия активирована!")
        return True, "Демо-лицензия активирована! (Ключ: ESP-DEMO0-DEMO0-DEMO0-DEMO0)"

    if not validate_key_format(key_upper):
        return False, "Неверный формат ключа. Ожидается: ESP-XXXXX-XXXXX-XXXXX-XXXXX"

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
            headers={"Content-Type": "application/json", "User-Agent": "EmailSenderPro/1.0"},
        )
        response.raise_for_status()
        data = response.json()

        if progress_callback:
            progress_callback(3, "Получение токена лицензии...")

        token_val = data.get("token")
        if not token_val:
            return False, "Сервер не вернул токен. Проверьте ключ."

        seal = _hmac_mod.new(_get_fernet_key(), token_val.encode("utf-8"), "sha256").hexdigest()

        license_data = {
            "token": token_val,
            "hwid": hwid,
            "key": key_upper,
            "activated_at": time.time(),
            "last_online": time.time(),
            "is_demo": False,
            "seal": seal,
        }
        _save_license_data(license_data)

        if progress_callback:
            progress_callback(4, "Лицензия успешно активирована!")

        return True, "Активация успешна!"

    except requests.ConnectionError:
        return False, "Нет подключения к интернету. Проверьте сеть."
    except requests.Timeout:
        return False, "Сервер не отвечает. Попробуйте позже."
    except requests.HTTPError as e:
        if e.response.status_code == 403:
            return False, "Ключ уже используется на другом устройстве."
        elif e.response.status_code == 404:
            return False, "Ключ не найден или недействителен."
        return False, f"Ошибка сервера: {e.response.status_code}"
    except Exception as e:
        return False, f"Ошибка активации: {str(e)}"


def is_activated() -> bool:
    if DEMO_MODE:
        return True
    data = _load_license_data()
    return data is not None


def check_license() -> Tuple[bool, Optional[LicenseInfo], str]:
    """
    Проверяет текущую лицензию при запуске приложения.
    Если DEMO_MODE=True — всегда возвращает валидную демо-лицензию.
    """
    if DEMO_MODE:
        return True, _make_demo_license(), "Демо-режим активен"

    data = _load_license_data()
    if not data:
        return False, None, "Лицензия не найдена. Активируйте приложение.\n\nДемо-ключ: ESP-DEMO0-DEMO0-DEMO0-DEMO0"

    hwid = generate_hwid()

    if data.get("is_demo") or data.get("token") == "DEMO":
        return True, _make_demo_license(), "Демо-лицензия активна"

    if data.get("hwid") != hwid:
        return False, None, "Лицензия привязана к другому устройству. Активируйте повторно."

    token_val = data.get("token", "")

    saved_seal = data.get("seal", "")
    if saved_seal:
        expected_seal = _hmac_mod.new(_get_fernet_key(), token_val.encode("utf-8"), "sha256").hexdigest()
        if not _hmac_mod.compare_digest(saved_seal, expected_seal):
            logger.warning("License seal mismatch — file may have been tampered with")
            return False, None, "Файл лицензии повреждён. Активируйте повторно."

    try:
        payload = jwt.decode(token_val, options={"verify_signature": False})
        license_info = LicenseInfo(payload)

        if license_info.is_expired:
            return False, None, f"Лицензия истекла {license_info.expires_at.strftime('%d.%m.%Y')}."

        data["last_online"] = time.time()
        try:
            _save_license_data(data)
        except Exception:
            pass

        return True, license_info, "OK"

    except jwt.DecodeError:
        last_online = data.get("last_online", 0.0)
        hours_offline = (time.time() - last_online) / 3600
        if hours_offline <= OFFLINE_GRACE_HOURS:
            remaining = int(OFFLINE_GRACE_HOURS - hours_offline)
            logger.info(f"Offline mode: {remaining}h grace period remaining")
            saved_payload = {
                "plan": data.get("plan", "STARTER"),
                "max_threads": data.get("max_threads", 5),
                "max_recipients": data.get("max_recipients", 1000),
                "exp": int((datetime.now() + timedelta(hours=remaining)).timestamp()),
                "email": data.get("email", ""),
                "hwid": hwid,
                "is_demo": False,
            }
            return True, LicenseInfo(saved_payload), f"Оффлайн-режим: осталось {remaining}ч"
        return False, None, f"Нет подключения к интернету более {OFFLINE_GRACE_HOURS}ч. Подключитесь для проверки лицензии."
    except Exception as e:
        logger.error(f"License check error: {e}")
        return False, None, f"Ошибка проверки лицензии: {e}"
