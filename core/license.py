"""
Система лицензирования: HWID-генератор, проверка ключа, JWT-токен.
Поддерживает offline grace period 72ч и защиту от отладчика/VM.
"""
import os
import sys
import uuid
import json
import time
import ctypes
import hashlib
import base64
import platform
import subprocess
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime, timedelta

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
import jwt
import requests

# ──────────────────────────────────────────────
# Константы
# ──────────────────────────────────────────────
HWID_SALT = "ESP-HWID-SALT-8f4e2a1c-9b3d-4f7e-8a2b-1c5d9e3f7a0b"
LICENSE_API_URL = "https://api.emailsenderpro.io/v1/activate"
OFFLINE_GRACE_HOURS = 72
LICENSE_FILE = Path(os.environ.get("APPDATA", ".")) / "EmailSenderPro" / "license.dat"

# RSA публичный ключ (base64 + XOR обфускация)
# В продакшене заменить на реальный ключ от сервера лицензий
_OBFUSCATED_PUB_KEY_B64 = (
    "LS0tLS1CRUdJTiBQVUJMSUMgS0VZLS0tLS0KTUlJQklqQU5CZ2txaGtpRzl3MEJBUUVG"
    "QUFPQ0FROEFNSUlCQ2dLQ0FRRUF3ekZ4cW9YZ2dEbmFUZXN0S2V5Cg=="
)
_XOR_KEY = 0x5A


def _deobfuscate_key(obf: str) -> bytes:
    """Деобфусцирует публичный ключ через XOR + base64."""
    raw = base64.b64decode(obf)
    return bytes(b ^ _XOR_KEY for b in raw)


# ──────────────────────────────────────────────
# Защита: анти-отладчик и VM-детектор
# ──────────────────────────────────────────────

def _check_debugger() -> bool:
    """Проверяет наличие отладчика (только Windows)."""
    if platform.system() != "Windows":
        return False
    try:
        return bool(ctypes.windll.kernel32.IsDebuggerPresent())
    except Exception:
        return False


def _check_vm() -> bool:
    """Проверяет запуск в виртуальной машине через реестр (только Windows)."""
    if platform.system() != "Windows":
        return False
    vm_keys = [
        r"SOFTWARE\VMware, Inc.\VMware Tools",
        r"SOFTWARE\Oracle\VirtualBox Guest Additions",
        r"SYSTEM\CurrentControlSet\Services\vmmouse",
        r"SYSTEM\CurrentControlSet\Services\vmhgfs",
    ]
    try:
        import winreg
        for key_path in vm_keys:
            try:
                winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
                return True
            except FileNotFoundError:
                continue
    except Exception:
        pass
    return False


def security_check() -> None:
    """Выполняет проверку безопасности. При обнаружении — silent exit."""
    if _check_debugger() or _check_vm():
        sys.exit(0)


# ──────────────────────────────────────────────
# HWID-генератор
# ──────────────────────────────────────────────

def _get_cpu_id() -> str:
    """Получает идентификатор процессора."""
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
    """Получает MAC-адрес сетевой карты."""
    return hex(uuid.getnode())[2:].upper().zfill(12)


def _get_disk_serial() -> str:
    """Получает серийный номер основного диска."""
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
    """Получает идентификатор материнской платы."""
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
    # Форматируем в группы по 4 символа
    groups = [digest[i:i+4] for i in range(0, 16, 4)]
    return "-".join(groups)


# ──────────────────────────────────────────────
# Шифрование license.dat
# ──────────────────────────────────────────────

def _get_fernet_key() -> bytes:
    """Генерирует ключ Fernet на основе HWID (детерминированный)."""
    hwid = generate_hwid()
    key_material = hashlib.sha256(
        (hwid + HWID_SALT).encode()
    ).digest()
    return base64.urlsafe_b64encode(key_material)


def _save_license_data(data: dict) -> None:
    """Сохраняет данные лицензии в зашифрованный файл."""
    LICENSE_FILE.parent.mkdir(parents=True, exist_ok=True)
    f = Fernet(_get_fernet_key())
    encrypted = f.encrypt(json.dumps(data).encode())
    LICENSE_FILE.write_bytes(encrypted)


def _load_license_data() -> Optional[dict]:
    """Загружает и расшифровывает данные лицензии."""
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
    """
    Проверяет формат лицензионного ключа.
    Формат: ESP-XXXXX-XXXXX-XXXXX-XXXXX
    """
    import re
    pattern = r"^ESP-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}$"
    return bool(re.match(pattern, key.upper()))


def _parse_jwt_payload(token: str) -> Optional[dict]:
    """Парсит JWT-токен без верификации (для чтения claims)."""
    try:
        # Декодируем без верификации для получения payload
        payload = jwt.decode(
            token,
            options={"verify_signature": False},
            algorithms=["RS256", "HS256"]
        )
        return payload
    except Exception:
        return None


# ──────────────────────────────────────────────
# Активация и проверка лицензии
# ──────────────────────────────────────────────

class LicenseInfo:
    """Информация о текущей лицензии."""

    def __init__(self, payload: dict):
        self.plan: str = payload.get("plan", "STARTER")          # STARTER/PRO/UNLIMITED
        self.max_threads: int = payload.get("max_threads", 5)
        self.max_recipients: int = payload.get("max_recipients", 1000)
        self.expires_at: datetime = datetime.fromtimestamp(payload.get("exp", 0))
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
    """Ошибка лицензирования."""
    pass


def activate_license(key: str, progress_callback=None) -> Tuple[bool, str]:
    """
    Активирует лицензию через серверный API.

    Args:
        key: Лицензионный ключ в формате ESP-XXXXX-XXXXX-XXXXX-XXXXX
        progress_callback: Функция для обновления прогресса (step: int, message: str)

    Returns:
        (success: bool, message: str)
    """
    if not validate_key_format(key):
        return False, "Неверный формат ключа. Ожидается: ESP-XXXXX-XXXXX-XXXXX-XXXXX"

    hwid = generate_hwid()

    if progress_callback:
        progress_callback(1, "Генерация идентификатора устройства...")

    payload = {
        "hwid": hwid,
        "key": key.upper(),
        "timestamp": int(time.time()),
        "version": "1.0.0",
    }

    if progress_callback:
        progress_callback(2, "Подключение к серверу активации...")

    try:
        response = requests.post(
            LICENSE_API_URL,
            json=payload,
            timeout=15,
            headers={"Content-Type": "application/json", "User-Agent": "EmailSenderPro/1.0"},
        )
        response.raise_for_status()
        data = response.json()

        if progress_callback:
            progress_callback(3, "Получение токена лицензии...")

        token = data.get("token")
        if not token:
            return False, "Сервер не вернул токен. Проверьте ключ."

        # Сохраняем данные лицензии
        license_data = {
            "token": token,
            "hwid": hwid,
            "key": key.upper(),
            "activated_at": time.time(),
            "last_online": time.time(),
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


def check_license() -> Tuple[bool, Optional[LicenseInfo], str]:
    """
    Проверяет текущую лицензию при запуске приложения.

    Returns:
        (is_valid: bool, license_info: Optional[LicenseInfo], message: str)
    """
    data = _load_license_data()
    if not data:
        return False, None, "Лицензия не найдена. Пожалуйста, активируйте приложение."

    hwid = generate_hwid()

    # Проверяем соответствие HWID
    if data.get("hwid") != hwid:
        return False, None, "Лицензия привязана к другому устройству."

    token = data.get("token", "")
    payload = _parse_jwt_payload(token)

    if not payload:
        return False, None, "Повреждённый токен лицензии. Переактивируйте."

    info = LicenseInfo(payload)

    if info.is_expired:
        # Проверяем offline grace period
        last_online = data.get("last_online", 0)
        elapsed_hours = (time.time() - last_online) / 3600
        if elapsed_hours > OFFLINE_GRACE_HOURS:
            return False, None, "Срок действия лицензии истёк. Обновите подписку."
        # Grace period ещё действует
        return True, info, f"Офлайн-режим: осталось {OFFLINE_GRACE_HOURS - int(elapsed_hours)}ч"

    # Обновляем время последнего онлайн-доступа в фоне
    try:
        _refresh_online_timestamp(data)
    except Exception:
        pass

    return True, info, "OK"


def _refresh_online_timestamp(data: dict) -> None:
    """Обновляет метку времени последнего онлайн-доступа."""
    data["last_online"] = time.time()
    _save_license_data(data)


def is_activated() -> bool:
    """Быстрая проверка: активировано ли приложение."""
    valid, _, _ = check_license()
    return valid


def deactivate_license() -> None:
    """Удаляет локальные данные лицензии."""
    if LICENSE_FILE.exists():
        LICENSE_FILE.unlink()
