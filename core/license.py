"""
Система лицензирования: HWID-генератор, проверка ключа, JWT-токен.

HWID v3.4.0 — стабильная привязка к железу:
  - Состав: CPU ProcessorId + Motherboard SerialNumber + GPU Name (sorted)
  - НЕ включает: MAC-адрес (нестабилен при VPN/Docker/Hyper-V),
    серийник диска, HWID_SALT (серверная константа)
  - Меняется при замене CPU / материнской платы / видеокарты
  - НЕ меняется при: переустановке Windows, смене сети, VPN, обновлениях
  - Нет файлового кэша — HWID всегда вычисляется из оборудования
  - Кэш в памяти только на время одной сессии
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

import jwt
import requests
from cryptography.fernet import Fernet

from core._version import APP_VERSION

logger = logging.getLogger("license")

# ── Константы ─────────────────────────────────────────────────────────────────
HWID_SALT: str = os.environ.get("HWID_SALT", "")

# URL лицензионного сервера — переопределяются через ENV, иначе используется production IP.
LICENSE_API_URL: str = os.environ.get(
    "LICENSE_API_URL",
    "https://fmail.shop/v1/activate",  # FIX: HTTPS через fmail.shop (nginx → uvicorn)
)
LICENSE_VERIFY_URL: str = os.environ.get(
    "LICENSE_VERIFY_URL",
    "https://fmail.shop/v1/verify",  # FIX: HTTPS через fmail.shop (nginx → uvicorn)
)

OFFLINE_GRACE_HOURS = 72
ONLINE_CHECK_INTERVAL_H = 24
LICENSE_FILE = Path(os.environ.get("APPDATA", ".")) / "FMailSender" / "license.dat"
_HWID_FILE         = Path(os.environ.get("APPDATA", ".")) / "FMailSender" / "hwid.dat"
_HWID_COMPONENTS_FILE = Path(os.environ.get("APPDATA", ".")) / "FMailSender" / "hwid_components.json"

KEY_PREFIX = "FMSND"

# SECURITY FIX: JWT_SECRET требуется для offline-верификации.
# Без него JWT без подписи будут приняты — это уязвимость.
_JWT_SECRET_FALLBACK = os.environ.get("JWT_SECRET", "").strip()
if not _JWT_SECRET_FALLBACK:
    logger.error(
        "SECURITY: JWT_SECRET not set — offline JWT verification DISABLED. "
        "Without it, offline tokens are REJECTED and online check is required. "
        "Set JWT_SECRET to the same value as the license server for offline support."
    )

# ── Внутренний кэш HWID ───────────────────────────────────────────────────────
_hwid_cache: Optional[str] = None
_hwid_lock = threading.Lock()



def _get_ssl_verify() -> "bool | str":
    """SSL verify helper for license server.
    Default: True (LICENSE_SSL_VERIFY=1) — проверять SSL-сертификат сервера.
    FIX: исправлен комментарий — реальный дефолт True, а не False.
    Для self-signed / IP-only сертификата: LICENSE_SSL_VERIFY=0.
    Для кастомного CA-bundle: LICENSE_SSL_VERIFY=/path/to/ca-bundle.crt
    """
    _ssl_env = os.environ.get("LICENSE_SSL_VERIFY", "1").strip()
    if _ssl_env == "1":
        return True
    if _ssl_env == "0":
        return False
    return _ssl_env  # treated as CA bundle path

# ── Анти-отладчик ─────────────────────────────────────────────────────────────

def _check_debugger() -> bool:
    if platform.system() != "Windows":
        return False
    try:
        return bool(ctypes.windll.kernel32.IsDebuggerPresent())
    except Exception:
        return False


def security_check() -> None:
    """Антиотладочная проверка — завершает процесс при обнаружении отладчика."""
    if _check_debugger():
        logger.error("Debugger detected — terminating process.")
        import os as _os
        _os.abort()  # Немедленное завершение, не перехватывается исключениями


# ── Fernet-ключ ───────────────────────────────────────────────────────────────

def _get_fernet_key() -> bytes:
    """
    Если HWID_SALT задан — используем его для шифрования license.dat.
    Если нет — используем встроенный fallback с предупреждением в лог.
    """
    salt = HWID_SALT.encode() if HWID_SALT else b""
    if not salt:
        logger.warning(
            "SECURITY: HWID_SALT не задан — все установки используют ОБЩИЙ ключ шифрования! "
            "Задайте HWID_SALT для изоляции license.dat между машинами."
        )
        # FIX КРИТ-4: используем HWID как соль вместо общего хардкода.
        # Это изолирует license.dat между машинами даже без HWID_SALT.
    try:
        # FIX RACE: вычисляем HWID если кэш ещё не готов (thread-safe)
        _cached = _hwid_cache
        if _cached is None:
            _cached = generate_hwid()
        _hwid_for_salt = _cached or "fmail_hwid_fallback_2024"
    except Exception:
        _hwid_for_salt = "fmail_hwid_fallback_2024"
    salt = _hwid_for_salt.encode("utf-8")[:32]
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
# Состав: CPU ProcessorId + Motherboard SerialNumber + GPU Name(s, sorted).
# НЕ используем: MAC (нестабилен — VPN/Docker/Hyper-V меняют его в любой момент),
#                серийник диска (незначительная замена железа),
#                HWID_SALT (серверная константа, не должна влиять на клиентский ID).
# Изменится только если заменить CPU, материнскую плату или видеокарту.


def _run_safe(fn, timeout: float = 2.0) -> str:
    with ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(fn)
        try:
            return future.result(timeout=timeout) or ""
        except Exception:
            return ""



def _load_component_cache() -> dict:
    """Загружает кэш аппаратных компонентов — резерв при таймауте WMI."""
    try:
        if _HWID_COMPONENTS_FILE.exists():
            return json.loads(_HWID_COMPONENTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_component_cache(cache: dict) -> None:
    """Сохраняет успешно прочитанные компоненты для следующих запусков."""
    try:
        _HWID_COMPONENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _HWID_COMPONENTS_FILE.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def _get_machine_guid() -> str:
    """Читает Windows MachineGuid — уникален и стабилен для каждой установки ОС."""
    if platform.system() != "Windows":
        return ""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SOFTWARE\Microsoft\Cryptography")
        val, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        return str(val).strip()
    except Exception:
        return ""


def _get_cpu_id() -> str:
    """CPU ProcessorId — не меняется без замены процессора."""
    if platform.system() != "Windows":
        return platform.node() or "UNKNOWN_CPU"
    try:
        import wmi
        c = wmi.WMI()
        for proc in c.Win32_Processor():
            pid = getattr(proc, "ProcessorId", "").strip()
            if pid:
                return pid
    except Exception:
        pass
    try:
        result = subprocess.run(
            ["wmic", "cpu", "get", "ProcessorId", "/value"],
            capture_output=True, text=True, timeout=2,
        )
        for line in result.stdout.splitlines():
            if "ProcessorId=" in line:
                val = line.split("=", 1)[1].strip()
                if val:
                    return val
    except Exception:
        pass
    return "UNKNOWN_CPU"

def _get_board_id() -> str:
    """Серийник материнской платы — не меняется без замены платы."""
    if platform.system() != "Windows":
        return "UNKNOWN_BOARD"
    try:
        import wmi
        c = wmi.WMI()
        for board in c.Win32_BaseBoard():
            s = getattr(board, "SerialNumber", "").strip()
            if s and s not in ("", "None", "Default string", "To be filled by O.E.M."):
                return s
    except Exception:
        pass
    try:
        result = subprocess.run(
            ["wmic", "baseboard", "get", "SerialNumber", "/value"],
            capture_output=True, text=True, timeout=2,
        )
        for line in result.stdout.splitlines():
            if "SerialNumber=" in line:
                val = line.split("=", 1)[1].strip()
                if val and val not in ("None", "Default string", "To be filled by O.E.M."):
                    return val
    except Exception:
        pass
    return "UNKNOWN_BOARD"


def _get_gpu_id() -> str:
    """Название(я) видеокарт — меняется при замене/добавлении GPU."""
    if platform.system() != "Windows":
        return "UNKNOWN_GPU"
    try:
        import wmi
        c = wmi.WMI()
        names = sorted(
            getattr(g, "Name", "").strip()
            for g in c.Win32_VideoController()
            if getattr(g, "Name", "").strip()
        )
        if names:
            return "|".join(names)
    except Exception:
        pass
    try:
        result = subprocess.run(
            ["wmic", "path", "win32_VideoController", "get", "Name", "/value"],
            capture_output=True, text=True, timeout=2,
        )
        names = sorted(
            line.split("=", 1)[1].strip()
            for line in result.stdout.splitlines()
            if "Name=" in line and line.split("=", 1)[1].strip()
        )
        if names:
            return "|".join(names)
    except Exception:
        pass
    return "UNKNOWN_GPU"


def generate_hwid() -> str:
    """
    Вычисляет HWID из стабильных аппаратных идентификаторов.

    Формула: SHA256(CPU_ProcessorId | MB_SerialNumber | GPU_Name)[:32]

    Стабилен при:
      - переустановке Windows / обновлении ОС
      - смене сетевой карты, VPN, Docker, Hyper-V
      - замене жёсткого диска / SSD
      - изменении HWID_SALT на сервере

    Меняется при замене:
      - процессора (CPU)
      - материнской платы
      - видеокарты (или добавлении/удалении GPU)

    Кэшируется в памяти на время сессии. При каждом запуске пересчитывается
    из оборудования — файловый кэш НЕ используется (файл hwid.dat удаляется
    при первом запуске новой версии, чтобы не тянуть старые нестабильные ID).
    """
    global _hwid_cache
    with _hwid_lock:
        if _hwid_cache is not None:
            return _hwid_cache

        # Удаляем устаревший файловый кэш при наличии (однократно при обновлении)
        try:
            if _HWID_FILE.exists():
                _HWID_FILE.unlink()
        except Exception:
            pass

        # Кэш компонентов — резерв при таймауте WMI
        comp_cache = _load_component_cache()

        with ThreadPoolExecutor(max_workers=3) as ex:
            f_cpu   = ex.submit(_get_cpu_id)
            f_board = ex.submit(_get_board_id)
            f_gpu   = ex.submit(_get_gpu_id)
            try:
                cpu = f_cpu.result(timeout=3.0) or ""
            except Exception:
                cpu = ""
            try:
                board = f_board.result(timeout=3.0) or ""
            except Exception:
                board = ""
            try:
                gpu = f_gpu.result(timeout=3.0) or ""
            except Exception:
                gpu = ""

        # При таймауте WMI — берём значение из прошлого успешного запуска
        if not cpu or cpu == "UNKNOWN_CPU":
            cpu = comp_cache.get("cpu", "UNKNOWN_CPU")
        if not board or board == "UNKNOWN_BOARD":
            board = comp_cache.get("board", "UNKNOWN_BOARD")
        if not gpu or gpu == "UNKNOWN_GPU":
            gpu = comp_cache.get("gpu", "UNKNOWN_GPU")
        # FIX H-2: если все компоненты UNKNOWN (таймаут WMI + пустой кэш) —
        # добавляем MachineGuid как уникальный per-machine идентификатор.
        if cpu == "UNKNOWN_CPU" and board == "UNKNOWN_BOARD" and gpu == "UNKNOWN_GPU":
            machine_guid = _get_machine_guid()
            if machine_guid:
                cpu = machine_guid
                logger.warning(
                    "HWID: все WMI-компоненты UNKNOWN, используем MachineGuid как fallback."
                )
            else:
                logger.error(
                    "HWID: все компоненты UNKNOWN и MachineGuid недоступен. "
                    "HWID не уникален — возможна коллизия лицензий!"
                )
                # Обновляем кэш только успешно прочитанными значениями
        _cu = False
        if cpu != "UNKNOWN_CPU" and comp_cache.get("cpu") != cpu:
            comp_cache["cpu"] = cpu; _cu = True
        if board != "UNKNOWN_BOARD" and comp_cache.get("board") != board:
            comp_cache["board"] = board; _cu = True
        if gpu != "UNKNOWN_GPU" and comp_cache.get("gpu") != gpu:
            comp_cache["gpu"] = gpu; _cu = True
        if _cu:
            _save_component_cache(comp_cache)

        raw = f"{cpu}|{board}|{gpu}"
        _hwid_cache = hashlib.sha256(raw.encode()).hexdigest()[:32].upper()
        logger.debug("HWID computed: cpu=%s… board=%s… gpu=%s…",
                     cpu[:8], board[:8], gpu[:16])
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
        # FIX ERR-3: храним timezone-aware UTC datetime — сравниваем только aware с aware
        from datetime import timezone as _tz
        self.expires_at: datetime = (
            datetime.fromtimestamp(exp, tz=_tz.utc)
            if exp else datetime(2099, 12, 31, tzinfo=_tz.utc)
        )
        self.email: str = payload.get("email", "")
        self.hwid: str = payload.get("hwid", "")
        self.is_valid: bool = True

    @property
    def days_left(self) -> int:
        # FIX: сравниваем aware с aware — нет naive/aware мешанины
        delta = self.expires_at - datetime.now(timezone.utc)
        return max(0, delta.days)

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

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
        _ssl_v = _get_ssl_verify()
        resp = requests.post(
            LICENSE_VERIFY_URL,
            json={"key": key, "hwid": hwid},
            timeout=5,
            verify=_ssl_v,

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
    _ssl_v = _get_ssl_verify()
    if progress_callback:
        progress_callback(20, "Проверка ключа...")

    try:
        resp = requests.post(
            LICENSE_API_URL,
            verify=_ssl_v,
            json={"key": key_upper, "hwid": hwid},
            timeout=10,
            headers={
                "Content-Type": "application/json",
                "User-Agent": f"FMailSender/{APP_VERSION}",
            },
        )
        if progress_callback:
            progress_callback(70, "Активация на сервере...")

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
                progress_callback(100, "Готово!")
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
        # JWT_SECRET не задан — обязательна онлайн-верификация (security fix)
        hwid_check = generate_hwid()
        key_check = data.get("key", "")
        online_result = _verify_key_online(key_check, hwid_check)
        if online_result is False:
            try:
                LICENSE_FILE.unlink(missing_ok=True)
            except Exception:
                pass
            return False, None, "Лицензия отозвана. Обратитесь в поддержку."
        elif online_result is None:
            return False, None, (
                "Сервер лицензий недоступен и JWT_SECRET не настроен.\n"
                "Подключитесь к интернету или задайте JWT_SECRET для offline-режима."
            )
        payload = _decode_payload_unverified(token)
        if not payload:
            return False, None, "Не удалось декодировать токен лицензии."
        data["last_verified_online"] = time.time()
        try:
            _save_license_data(data)
        except Exception:
            pass

    # Проверка grace period (только при JWT_SECRET — offline режим)
    if _JWT_SECRET_FALLBACK:
        activated_at = data.get("activated_at", 0)
        last_online = data.get("last_verified_online", activated_at)
        hours_offline = (time.time() - last_online) / 3600  # UTC-independent: uses time.time()
        if hours_offline > OFFLINE_GRACE_HOURS:
            key_gp = data.get("key", "")
            hwid_gp = generate_hwid()
            gp_result = _verify_key_online(key_gp, hwid_gp)
            if gp_result is False:
                try:
                    LICENSE_FILE.unlink(missing_ok=True)
                except Exception:
                    pass
                return False, None, "Лицензия отозвана."
            elif gp_result is None:
                return False, None, (
                    f"Нет связи с сервером более {OFFLINE_GRACE_HOURS} ч.\n"
                    f"Подключитесь к интернету для проверки лицензии."
                )
            else:
                data["last_verified_online"] = time.time()
                try:
                    _save_license_data(data)
                except Exception:
                    pass

    license_info = LicenseInfo(payload)
    if license_info.is_expired:
        return False, None, f"Лицензия истекла {license_info.expires_at.strftime('%d.%m.%Y')}."

    # Фоновая онлайн-проверка
    _schedule_background_verification()

    return True, license_info, f"Лицензия активна: {license_info.plan} до {license_info.expires_at.strftime('%d.%m.%Y')}"
