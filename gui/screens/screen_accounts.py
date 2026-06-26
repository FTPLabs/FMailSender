"""
Screen 2: SMTP Account Management.
Add, test, delete accounts. Passwords stored encrypted via Fernet.
Proxy support: socks5/socks4/http per-account or global.
v3.0.0 fixes:
  - ProxyManager.parse() поддерживает user:pass@host:port формат
  - ProxyCheckWorker: TCP-проверка + определение страны через ip-api.com
  - Автопроверка всех аккаунтов при загрузке экрана
  - AccountDialog: добавлены IMAP-поля (были в _fill но не в _setup_ui)
  - _autofill_smtp: исправлен IndentationError (6 пробелов -> 4)
  - _import_proxies: проверка прокси с отображением стран
"""
import asyncio
import json
import os
import platform
import re
import socket
import threading
import urllib.request
import urllib.parse
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QSpinBox, QCheckBox, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QHeaderView, QDialog, QFormLayout,
    QMessageBox, QDialogButtonBox, QTextEdit, QFrame,
    QFileDialog, QProgressBar, QProgressDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot, QTimer, QSize
from PyQt6.QtGui import QColor

from core.license import get_storage_key
from core.sender import SmtpAccount, test_smtp_connection, get_smtp_config_for_domain
from gui.theme import Colors, Spacing
from gui import icons

import random


# Порты, характерные для HTTP-прокси (автоопределение типа при отсутствии схемы)
_HTTP_PROXY_PORTS_SET: frozenset = frozenset({80, 8080, 8088, 8118, 3128, 3129, 8443, 8888, 8889, 9999})


def _guess_proxy_scheme_by_port(port_str: str) -> str:
    """Определяет схему прокси по порту при отсутствии явной схемы."""
    try:
        return "http" if int(port_str) in _HTTP_PROXY_PORTS_SET else "socks5"
    except (ValueError, TypeError):
        return "socks5"


class ProxyManager:
    """Менеджер прокси с ротацией: round_robin или random.

    Поддерживаемые форматы:
      socks5://user:pass@host:port   — SOCKS5 (явная схема)
      socks4://host:port             — SOCKS4 (явная схема)
      http://host:port               — HTTP (явная схема)
      https://host:port              — HTTPS (явная схема)
      user:pass@host:port            — автоопределение типа по порту
      host:port                      — автоопределение типа по порту
      host:port:user:pass            — автоопределение типа по порту
      user:pass:host:port            — автоопределение типа по порту

    Автоопределение: 8080/3128/8888/8118/... → http://; остальные → socks5://
    """

    def __init__(self, raw_list: list[str] | None = None, mode: str = "round_robin"):
        self._mode = mode
        self._index = 0
        self._lock = threading.Lock()
        self._proxies: list[str] = []
        for raw in (raw_list or []):
            normalized = self.parse(raw)
            if normalized:
                self._proxies.append(normalized)

    @staticmethod
    def parse(raw: str) -> str | None:
        """Нормализует строку прокси в URL-формат. None если невалидно.

        Если схема не указана явно — тип определяется по порту:
          80, 8080, 3128, 8888, 8118, 3129, 8443, 8889, 9999 → http://
          Все остальные порты → socks5://
        """
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            return None
        # Уже URL-формат (есть схема вида socks5:// http:// https:// socks4://)
        if "://" in raw:
            return raw
        # Формат user:pass@host:port (без схемы, но есть @)
        if "@" in raw:
            try:
                creds, hostport = raw.rsplit("@", 1)
                host, port_str = hostport.rsplit(":", 1)
                int(port_str)
                if host and creds:
                    scheme = _guess_proxy_scheme_by_port(port_str)
                    return f"{scheme}://{creds}@{host}:{port_str}"
            except (ValueError, AttributeError):
                return None
        parts = raw.split(":")
        if len(parts) == 2:
            try:
                int(parts[1])
                scheme = _guess_proxy_scheme_by_port(parts[1])
                return f"{scheme}://{parts[0]}:{parts[1]}"
            except ValueError:
                return None
        if len(parts) == 4:
            # host:port:user:pass
            try:
                int(parts[1])
                scheme = _guess_proxy_scheme_by_port(parts[1])
                return f"{scheme}://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
            except ValueError:
                pass
            # user:pass:host:port
            try:
                int(parts[3])
                scheme = _guess_proxy_scheme_by_port(parts[3])
                return f"{scheme}://{parts[0]}:{parts[1]}@{parts[2]}:{parts[3]}"
            except ValueError:
                pass
        return None

    def next_proxy(self) -> str | None:
        with self._lock:
            if not self._proxies:
                return None
            if self._mode == "random":
                return random.choice(self._proxies)
            proxy = self._proxies[self._index % len(self._proxies)]
            self._index += 1
            return proxy

    @property
    def count(self) -> int:
        return len(self._proxies)

    def to_list(self) -> list[str]:
        return list(self._proxies)


class ProxyCheckWorker(QThread):
    """Реальная проверка прокси: SOCKS5/SOCKS4/HTTP рукопожатие + пинг + страна через ip-api.com."""
    result = pyqtSignal(int, bool, str, str, int, bool)  # index, valid, country, error, ping_ms, smtp_ok
    finished = pyqtSignal(int, int)                 # valid_count, total

    TIMEOUT = 7  # сек на каждую попытку

    def __init__(self, proxies: list[str], parent=None):
        super().__init__(parent)
        self._proxies = proxies
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        valid_count = 0
        for i, proxy_url in enumerate(self._proxies):
            if self._cancelled:
                break
            valid, country, error, ping_ms = self._check_one(proxy_url)
            smtp_ok = False
            if valid:
                valid_count += 1
                # FIX v4.5.4: дополнительно проверяем SMTP-порт 587 через прокси
                smtp_ok = self._check_smtp_via_proxy(proxy_url)
            self.result.emit(i, valid, country, error, ping_ms, smtp_ok)
        self.finished.emit(valid_count, len(self._proxies))


    @classmethod
    def _check_smtp_via_proxy(cls, proxy_url: str) -> bool:
        """FIX v4.5.4: проверяет, открыт ли SMTP-порт 587 через данный прокси.
        Подключается к smtp.gmail.com:587 и ищет баннер «220».
        Возвращает True только если SMTP доступен.
        """
        import ssl as _ssl
        SMTP_HOST = "smtp.gmail.com"
        SMTP_PORT = 587
        TIMEOUT = 8

        _auto = "://" not in proxy_url
        _url = ("socks5://" + proxy_url) if _auto else proxy_url
        parsed = urllib.parse.urlparse(_url)
        px_host = parsed.hostname or ""
        px_port = parsed.port or 1080
        scheme = (parsed.scheme or "socks5").lower()
        uname = parsed.username or ""
        upass = parsed.password or ""

        if not px_host:
            return False

        try:
            if "socks" in scheme and not _auto:
                # SOCKS5 → raw tunnel → smtp.gmail.com:587
                s = cls._socks5_connect_raw(px_host, px_port, SMTP_HOST, SMTP_PORT,
                                             username=uname, password=upass, timeout=TIMEOUT)
            else:
                # HTTP CONNECT → smtp.gmail.com:587
                import base64 as _b64
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(TIMEOUT)
                s.connect((px_host, px_port))
                lines = [
                    f"CONNECT {SMTP_HOST}:{SMTP_PORT} HTTP/1.1",
                    f"Host: {SMTP_HOST}:{SMTP_PORT}",
                    "Proxy-Connection: Keep-Alive",
                ]
                if uname:
                    cred = _b64.b64encode(f"{uname}:{upass}".encode()).decode()
                    lines.append(f"Proxy-Authorization: Basic {cred}")
                s.sendall(("\r\n".join(lines) + "\r\n\r\n").encode())
                resp = b""
                while b"\r\n\r\n" not in resp and len(resp) < 4096:
                    chunk = s.recv(256)
                    if not chunk:
                        break
                    resp += chunk
                if b"200" not in (resp.split(b"\r\n")[0] if resp else b""):
                    s.close()
                    return False
            # Читаем SMTP-баннер (220 ...)
            s.settimeout(TIMEOUT)
            banner = b""
            while b"\n" not in banner and len(banner) < 512:
                chunk = s.recv(128)
                if not chunk:
                    break
                banner += chunk
            s.close()
            return banner.startswith(b"220")
        except Exception:
            return False

    @classmethod
    def _check_one(cls, proxy_url: str) -> tuple[bool, str, str, int]:
        """Реальная проверка через SOCKS5/SOCKS4/HTTP.
        Возвращает (valid, country, error, ping_ms).
        """
        import time as _time

        if not proxy_url or not proxy_url.strip():
            return False, "", "Пустой URL", 0

        _auto_detect = "://" not in proxy_url
        if _auto_detect:
            proxy_url = "socks5://" + proxy_url   # временно для urlparse

        parsed = urllib.parse.urlparse(proxy_url)
        host = parsed.hostname or ""
        port = parsed.port or 1080
        scheme = (parsed.scheme or "socks5").lower()
        uname = parsed.username or ""
        upass = parsed.password or ""

        if not host:
            return False, "", "Нет хоста в URL", 0

        # ── SOCKS5 / SOCKS4 — реальное рукопожатие, чистый stdlib (без PySocks) ──
        if "socks" in scheme and not _auto_detect:
            try:
                t0 = _time.monotonic()
                s = cls._socks5_connect_raw(
                    host, port, "ip-api.com", 80,
                    username=uname, password=upass,
                    timeout=cls.TIMEOUT,
                )
                ping_ms = int((_time.monotonic() - t0) * 1000)
                # HTTP через туннель
                s.sendall(
                    b"GET /json/?fields=status,country,countryCode HTTP/1.0\r\n"
                    b"Host: ip-api.com\r\nUser-Agent: FMailSender/4.0\r\n\r\n"
                )
                raw = b""
                while True:
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    raw += chunk
                    if len(raw) > 32768:
                        break
                s.close()
                if b"\r\n\r\n" in raw:
                    body = raw.split(b"\r\n\r\n", 1)[1].decode("utf-8", "replace").strip()
                    try:
                        d = json.loads(body)
                        if d.get("status") == "success":
                            cc = d.get("countryCode", "")
                            ctry = d.get("country", cc)
                            flag = _cc_flag_emoji(cc)
                            return True, f"{flag} {ctry}".strip(), "", ping_ms
                    except Exception:
                        pass
                return True, "", "", ping_ms
            except Exception as e:
                return False, "", str(e)[:80], 0

        # ── HTTP/HTTPS прокси ИЛИ авто-определение ────────────────────────────
        # При авто-определении: сначала пробуем SOCKS5 (короткий таймаут),
        # при неудаче — HTTP CONNECT. Это прозрачно работает для любого типа.
        def _try_http_connect_check():
            import base64 as _b64
            import ssl as _ssl_mod
            s2 = None
            try:
                t0 = _time.monotonic()
                s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s2.settimeout(cls.TIMEOUT)
                s2.connect((host, port))
                lines = [
                    "CONNECT ip-api.com:443 HTTP/1.1",
                    "Host: ip-api.com:443",
                    "Proxy-Connection: Keep-Alive",
                ]
                if uname:
                    cred = _b64.b64encode(f"{uname}:{upass}".encode()).decode()
                    lines.append(f"Proxy-Authorization: Basic {cred}")
                s2.sendall(("\r\n".join(lines) + "\r\n\r\n").encode())
                resp = b""
                while b"\r\n\r\n" not in resp and len(resp) < 4096:
                    chunk = s2.recv(256)
                    if not chunk:
                        break
                    resp += chunk
                if b"200" not in resp.split(b"\r\n")[0]:
                    first = resp.split(b"\r\n")[0].decode("utf-8", "replace")
                    return False, "", f"HTTP прокси: {first[:80]}", 0
                # HTTPS через туннель
                ctx = _ssl_mod.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = _ssl_mod.CERT_NONE
                s2 = ctx.wrap_socket(s2, server_hostname="ip-api.com")
                ping_ms = int((_time.monotonic() - t0) * 1000)
                req = (
                    "GET /json/?fields=status,country,countryCode HTTP/1.0\r\n"
                    "Host: ip-api.com\r\nUser-Agent: FMailSender/4.0\r\n\r\n"
                )
                s2.sendall(req.encode())
                raw = b""
                while True:
                    chunk = s2.recv(4096)
                    if not chunk:
                        break
                    raw += chunk
                    if len(raw) > 32768:
                        break
                s2.close()
                if b"\r\n\r\n" in raw:
                    body = raw.split(b"\r\n\r\n", 1)[1].decode("utf-8", "replace").strip()
                    try:
                        d = json.loads(body)
                        if d.get("status") == "success":
                            cc = d.get("countryCode", "")
                            ctry = d.get("country", cc)
                            flag = _cc_flag_emoji(cc)
                            return True, f"{flag} {ctry}".strip(), "", ping_ms
                    except Exception:
                        pass
                return True, "", "", ping_ms
            except Exception as e:
                if s2:
                    try:
                        s2.close()
                    except Exception:
                        pass
                return False, "", str(e)[:80], 0

        if _auto_detect:
            # Пробуем SOCKS5 (3 с) → при неудаче HTTP CONNECT
            try:
                t0 = _time.monotonic()
                s = cls._socks5_connect_raw(
                    host, port, "ip-api.com", 80,
                    username=uname, password=upass,
                    timeout=min(cls.TIMEOUT, 3),
                )
                ping_ms = int((_time.monotonic() - t0) * 1000)
                s.sendall(
                    b"GET /json/?fields=status,country,countryCode HTTP/1.0\r\n"
                    b"Host: ip-api.com\r\nUser-Agent: FMailSender/4.0\r\n\r\n"
                )
                raw = b""
                while True:
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    raw += chunk
                    if len(raw) > 32768:
                        break
                s.close()
                if b"\r\n\r\n" in raw:
                    body = raw.split(b"\r\n\r\n", 1)[1].decode("utf-8", "replace").strip()
                    try:
                        d = json.loads(body)
                        if d.get("status") == "success":
                            cc = d.get("countryCode", "")
                            ctry = d.get("country", cc)
                            flag = _cc_flag_emoji(cc)
                            return True, f"{flag} {ctry}".strip(), "", ping_ms
                    except Exception:
                        pass
                return True, "", "", ping_ms
            except OSError:
                # SOCKS5 не ответил или не тот протокол — пробуем HTTP CONNECT
                return _try_http_connect_check()
            except Exception:
                return _try_http_connect_check()
        else:
            # Явный http:// или https://
            return _try_http_connect_check()


    @staticmethod
    def _socks5_connect_raw(
        proxy_host: str, proxy_port: int,
        target_host: str, target_port: int,
        username: str = "", password: str = "",
        timeout: int = 7,
    ):
        """RFC-1928 SOCKS5 + RFC-1929 user/pass auth — только stdlib, без PySocks.

        Возвращает подключённый socket.socket уже прошедший через прокси.
        """
        import socket as _socket
        import struct as _struct

        s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((proxy_host, proxy_port))

        # ── 1. Приветствие (предлагаем методы аутентификации) ────────────
        if username:
            s.sendall(b"\x05\x02\x00\x02")   # no-auth и user/pass
        else:
            s.sendall(b"\x05\x01\x00")        # только no-auth

        resp = s.recv(2)
        if len(resp) < 2 or resp[0] != 0x05:
            s.close()
            raise Exception("Не SOCKS5 — сервер вернул неожиданный ответ")
        if resp[1] == 0xFF:
            s.close()
            raise Exception("SOCKS5: сервер отклонил все методы аутентификации")

        # ── 2. Аутентификация user/pass (RFC 1929) ───────────────────────
        if resp[1] == 0x02:
            if not username:
                s.close()
                raise Exception("SOCKS5: сервер требует логин/пароль, но они не заданы")
            un = username.encode("utf-8")
            pw = (password or "").encode("utf-8")
            s.sendall(b"\x01" + bytes([len(un)]) + un + bytes([len(pw)]) + pw)
            auth = s.recv(2)
            if len(auth) < 2 or auth[1] != 0x00:
                s.close()
                raise Exception("SOCKS5: неверные учётные данные (auth rejected)")

        # ── 3. CONNECT к цели ─────────────────────────────────────────────
        tb = target_host.encode("utf-8") if isinstance(target_host, str) else target_host
        s.sendall(
            b"\x05\x01\x00\x03"           # VER=5 CMD=CONNECT RSV=0 ATYP=DOMAINNAME
            + bytes([len(tb)]) + tb
            + _struct.pack(">H", target_port)
        )

        hdr = b""
        while len(hdr) < 4:
            chunk = s.recv(4 - len(hdr))
            if not chunk:
                s.close()
                raise Exception("SOCKS5: соединение закрыто до получения ответа")
            hdr += chunk

        if hdr[1] != 0x00:
            _errs = {
                1: "общий сбой", 2: "запрещено политикой",
                3: "сеть недоступна", 4: "хост недоступен",
                5: "соединение отклонено", 6: "TTL истёк",
                7: "команда не поддерживается", 8: "тип адреса не поддерживается",
            }
            s.close()
            raise Exception(f"SOCKS5 CONNECT отклонён: {_errs.get(hdr[1], f'код {hdr[1]}')}")

        # Дочитываем BNDADDR/BNDPORT (нам не нужны, но нужно слить буфер)
        atyp = hdr[3]
        if atyp == 0x01:
            s.recv(6)       # IPv4 (4) + port (2)
        elif atyp == 0x03:
            n = s.recv(1)[0]
            s.recv(n + 2)   # domain + port
        elif atyp == 0x04:
            s.recv(18)      # IPv6 (16) + port (2)

        return s


def _cc_flag_emoji(cc: str) -> str:
    """Преобразует 2-буквенный код страны (ISO 3166-1 alpha-2) в emoji-флаг.
    Пример: 'US' → '🇺🇸', 'RU' → '🇷🇺', 'DE' → '🇩🇪'
    Использует Unicode Regional Indicator Symbols (U+1F1E6–U+1F1FF).
    """
    cc = (cc or "").strip().upper()
    if len(cc) != 2 or not cc.isalpha():
        return ""
    # Regional Indicator 'A' = U+1F1E6
    return chr(0x1F1E6 + ord(cc[0]) - ord("A")) + chr(0x1F1E6 + ord(cc[1]) - ord("A"))


# ── Кэш стран/флагов прокси: proxy_url → "🇷🇺 Russia" ───────────────────────
# Персистентен на время сессии — страна не теряется при _refresh_table()
_proxy_country_cache: dict[str, str] = {}

# Семафор ограничивает одновременные запросы к ip-api.com (45 req/min free tier)
_country_api_semaphore = threading.Semaphore(3)


try:
    from cryptography.fernet import Fernet
    _HAS_FERNET = True
except ImportError:
    _HAS_FERNET = False


def _get_data_dir() -> Path:
    if platform.system() == "Windows":
        base = os.environ.get("APPDATA", str(Path.home()))
    elif platform.system() == "Darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
    return Path(base) / "FMailSender"


ACCOUNTS_FILE = _get_data_dir() / "accounts.dat"
PROXY_FILE    = _get_data_dir() / "proxies.dat"


# Глобальные прокси: сохраняются на диск + кеш в памяти для скорости
_SESSION_PROXIES: list[str] = []
_GLOBAL_PROXIES_FILE = Path(__file__).parent.parent.parent / "data" / "global_proxies.json"


def save_global_proxies(proxies: list[str]) -> None:
    """Сохраняет прокси на диск (data/global_proxies.json) и в кеш сессии."""
    global _SESSION_PROXIES
    _SESSION_PROXIES = list(proxies)
    try:
        _GLOBAL_PROXIES_FILE.parent.mkdir(parents=True, exist_ok=True)
        import json as _j
        _GLOBAL_PROXIES_FILE.write_text(
            _j.dumps(proxies, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def load_global_proxies() -> list[str]:
    """Возвращает пул прокси: из кеша сессии или читает с диска (data/global_proxies.json)."""
    global _SESSION_PROXIES
    if _SESSION_PROXIES:
        return list(_SESSION_PROXIES)
    try:
        if _GLOBAL_PROXIES_FILE.exists():
            import json as _j
            data = _j.loads(_GLOBAL_PROXIES_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                _SESSION_PROXIES = [str(p) for p in data if p]
                return list(_SESSION_PROXIES)
    except Exception:
        pass
    return []


def distribute_proxies(accounts: "list[SmtpAccount]", proxies: list[str]) -> None:
    """Распределяет прокси по аккаунтам round-robin (каждый получает свой, циклически).

    Каждый аккаунт получает:
      - .proxy  — персональный прокси (round-robin из пула)
      - .proxy_list — весь пул для ротации на уровне отправки
    """
    if not proxies:
        return
    for i, acc in enumerate(accounts):
        acc.proxy                = proxies[i % len(proxies)]
        acc.proxy_list           = proxies
        acc.proxy_rotation_random = False


def _encrypt_password(password: str) -> str:
    if not _HAS_FERNET:
        return password
    try:
        f = Fernet(get_storage_key())
        return f.encrypt(password.encode()).decode()
    except Exception:
        return password


def _decrypt_password(encrypted: str) -> str:
    if not _HAS_FERNET:
        return encrypted
    try:
        f = Fernet(get_storage_key())
        return f.decrypt(encrypted.encode()).decode()
    except Exception:
        return encrypted


def save_accounts(accounts: list[SmtpAccount]) -> None:
    ACCOUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = []
    for a in accounts:
        entry = {
            "email": a.email,
            "password_enc": _encrypt_password(a.password),
            "host": a.host,
            "port": a.port,
            "use_ssl": a.use_ssl,
            "use_tls": a.use_tls,
            "display_name": a.display_name,
            "daily_limit": a.daily_limit,
            "hourly_limit": a.hourly_limit,
            "is_active": a.is_active,
            "last_test_ok": getattr(a, "last_test_ok", None),
            "last_test_msg": getattr(a, "last_test_msg", ""),
            "imap_host": getattr(a, "imap_host", ""),
            "imap_port": getattr(a, "imap_port", 993),
            "imap_ssl": getattr(a, "imap_ssl", True),
            "refresh_token": getattr(a, "refresh_token", ""),
            "access_token": getattr(a, "access_token", "") or getattr(a, "oauth_token", ""),
            "token_expires_at": getattr(a, "token_expires_at", 0.0),
        }
        # FIX v4.5.2: НЕ сохраняем proxy/proxy_list на диск — они сессионные.
        data.append(entry)
    ACCOUNTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_accounts() -> list[SmtpAccount]:
    if not ACCOUNTS_FILE.exists():
        return []
    try:
        data = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
        result = []
        for d in data:
            raw_pw = d.get("password_enc") or d.get("password", "")
            try:
                password = _decrypt_password(raw_pw)
            except Exception:
                password = raw_pw
            acc = SmtpAccount(
                email=d["email"],
                password=password,
                host=d["host"],
                port=d["port"],
                use_ssl=d.get("use_ssl", True),
                use_tls=d.get("use_tls", False),
                display_name=d.get("display_name", ""),
                daily_limit=d.get("daily_limit", 500),
                hourly_limit=d.get("hourly_limit", 50),
                is_active=d.get("is_active", True),
            )
            # Восстанавливаем результат последнего теста (чтобы не показывать «Не проверено» после перезапуска)
            _lto = d.get("last_test_ok")
            if _lto is not None:
                acc.last_test_ok = bool(_lto)
            acc.last_test_msg = d.get("last_test_msg", "")
            acc.imap_host = d.get("imap_host", "")
            acc.imap_port = d.get("imap_port", 993)
            acc.imap_ssl = d.get("imap_ssl", True)
            acc.refresh_token = d.get("refresh_token", "")
            _saved_at = d.get("access_token", "") or d.get("oauth_token", "")
            if _saved_at:
                acc.access_token = _saved_at
                acc.oauth_token = _saved_at
            acc.token_expires_at = float(d.get("token_expires_at", 0))
            # FIX v4.5.2: НЕ восстанавливаем proxy/proxy_list с диска.
            # Прокси — сессионные данные: импортируются вручную каждую сессию.
            # Это предотвращает использование устаревших/заблокированных прокси.
            result.append(acc)
        return result
    except Exception:
        return []


class TestWorker(QThread):
    result_ready = pyqtSignal(bool, str)

    def __init__(self, account: SmtpAccount, parent=None):
        super().__init__(parent)
        self._account = account

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            ok, msg = loop.run_until_complete(test_smtp_connection(self._account))
        finally:
            loop.close()
        self.result_ready.emit(ok, msg)


class BulkImportWorker(QThread):
    """Imports SMTP accounts from text file (email:password format)."""
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(int, int)
    error = pyqtSignal(str)

    def __init__(self, path: str, existing_emails: set, parent=None):
        super().__init__(parent)
        self._path = path
        self._existing = existing_emails
        self.new_accounts: list[SmtpAccount] = []

    def run(self):
        try:
            lines = Path(self._path).read_text(encoding="utf-8", errors="replace").splitlines()
            lines = [l.strip() for l in lines if l.strip() and not l.startswith("#")]
            total = len(lines)
            imported = 0
            skipped = 0
            for i, line in enumerate(lines):
                self.progress.emit(i + 1, total)
                # Умное определение разделителя: | (pipe), ; или :
                # Форматы:
                #   email|pass|refresh_token   — Outlook OAuth2 (pipe)
                #   email:pass:token            — Rambler/прочие
                #   email;pass;alias            — Google Workspace alias
                _refresh_token_import = ""
                if "|" in line and line.count("|") >= 1:
                    # Pipe-формат: email|password|refresh_token
                    _sep = "|"
                elif ";" in line and ":" not in line.split(";")[0]:
                    _sep = ";"
                else:
                    _sep = ":"
                parts = line.split(_sep)
                if len(parts) < 2:
                    skipped += 1
                    continue
                email = parts[0].strip()
                alias = parts[2].strip() if len(parts) >= 3 and _sep == ";" else ""
                password = parts[1].strip()
                # Для pipe-формата третье поле — refresh_token для OAuth2
                if _sep == "|" and len(parts) >= 3:
                    _refresh_token_import = parts[2].strip()
                    # FIX_B003: 4-field pipe email|pass|token|client_id
                    _oauth_client_id_import = parts[3].strip() if len(parts) >= 4 else ""
                if not email or "@" not in email:
                    skipped += 1
                    continue
                if email.lower() in self._existing:
                    skipped += 1
                    continue
                domain = email.split("@")[-1].lower()
                cfg = get_smtp_config_for_domain(domain)
                if not cfg:
                    skipped += 1
                    continue
                acc = SmtpAccount(
                    email=email, password=password,
                    host=cfg["host"], port=cfg["port"],
                    use_ssl=cfg.get("use_ssl", True),
                    use_tls=cfg.get("use_tls", False),
                )
                acc.imap_host = cfg.get("imap_host", "")
                acc.imap_port = cfg.get("imap_port", 993)
                acc.imap_ssl = cfg.get("imap_ssl", True)
                if _refresh_token_import:
                    acc.refresh_token = _refresh_token_import
                    # Для Outlook: при наличии refresh_token — авто-получим access_token при первой отправке
                    acc.oauth_token = ""  # будет заполнено oauth2_refresh модулем
                    # FIX_B003: store explicit client_id from 4th pipe field if given
                    if _oauth_client_id_import:
                        acc.ms_client_id = _oauth_client_id_import
                if alias and "@" in alias:
                    acc.reply_to = alias  # Google Workspace alias
                self.new_accounts.append(acc)
                self._existing.add(email.lower())
                imported += 1
            self.finished.emit(imported, skipped)
        except Exception as e:
            self.error.emit(str(e))


class AccountDialog(QDialog):
    def __init__(self, account: SmtpAccount | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить аккаунт" if account is None else "Редактировать аккаунт")
        self.setMinimumWidth(480)
        self._account = account
        self._setup_ui()
        if account:
            self._fill(account)

    def _setup_ui(self):
        layout = QFormLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("user@gmail.com")
        self.email_edit.textChanged.connect(self._autofill_smtp)
        layout.addRow("Email:", self.email_edit)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("Пароль приложения")
        layout.addRow("Пароль:", self.password_edit)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Имя отправителя (необязательно)")
        layout.addRow("Имя:", self.name_edit)

        self.host_edit = QLineEdit()
        self.host_edit.setPlaceholderText("smtp.gmail.com")
        layout.addRow("SMTP-хост:", self.host_edit)

        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(465)
        layout.addRow("Порт:", self.port_spin)

        proto_row = QHBoxLayout()
        self.ssl_check = QCheckBox("SSL")
        self.ssl_check.setChecked(True)
        self.tls_check = QCheckBox("STARTTLS")
        proto_row.addWidget(self.ssl_check)
        proto_row.addWidget(self.tls_check)
        proto_row.addStretch()
        layout.addRow("Протокол:", proto_row)

        self.daily_spin = QSpinBox()
        self.daily_spin.setRange(1, 100000)
        self.daily_spin.setValue(500)
        self.daily_spin.setSuffix(" писем/день")
        layout.addRow("Дневной лимит:", self.daily_spin)

        self.hourly_spin = QSpinBox()
        self.hourly_spin.setRange(1, 10000)
        self.hourly_spin.setValue(50)
        self.hourly_spin.setSuffix(" писем/час")
        layout.addRow("Часовой лимит:", self.hourly_spin)

        # Прокси
        self.proxy_edit = QTextEdit()
        self.proxy_edit.setPlaceholderText(
            "По одному прокси на строку. Форматы:\n"
            "  user:pass@host:port\n"
            "  socks5://user:pass@host:port\n"
            "  http://host:port\n"
            "  host:port\n"
            "  host:port:user:pass"
        )
        self.proxy_edit.setFixedHeight(90)
        self.proxy_edit.setObjectName("proxy_list_edit")
        layout.addRow("Прокси:", self.proxy_edit)

        self.proxy_rotation_check = QCheckBox("Случайная ротация (иначе round-robin)")
        layout.addRow("", self.proxy_rotation_check)

        # IMAP (для bounce-мониторинга)
        self.imap_host_edit = QLineEdit()
        self.imap_host_edit.setPlaceholderText("imap.gmail.com (необязательно)")
        layout.addRow("IMAP-хост:", self.imap_host_edit)

        imap_port_row = QHBoxLayout()
        self.imap_port_spin = QSpinBox()
        self.imap_port_spin.setRange(1, 65535)
        self.imap_port_spin.setValue(993)
        imap_port_row.addWidget(self.imap_port_spin)
        self.imap_ssl_check = QCheckBox("SSL")
        self.imap_ssl_check.setChecked(True)
        imap_port_row.addWidget(self.imap_ssl_check)
        imap_port_row.addStretch()
        layout.addRow("IMAP порт:", imap_port_row)

        self.active_check = QCheckBox("Активен")
        self.active_check.setChecked(True)
        layout.addRow("", self.active_check)

        # GUI-2 FIX: кнопка теста SMTP прямо в диалоге — мгновенная обратная связь
        test_row = QHBoxLayout()
        self.test_btn = QPushButton("Тест подключения")
        self.test_btn.setIcon(icons.make_icon(icons.POWER))
        self.test_btn.setIconSize(QSize(16, 16))
        self.test_btn.setObjectName("test_smtp_btn")
        self.test_btn.setToolTip("Проверить SMTP-подключение с текущими данными")
        self.test_btn.clicked.connect(self._test_smtp_now)
        self.test_status = QLabel("")
        self.test_status.setObjectName("test_smtp_status")
        test_row.addWidget(self.test_btn)
        test_row.addWidget(self.test_status, 1)
        layout.addRow("", test_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)


    def _test_smtp_now(self):
        """GUI-2 FIX: тест SMTP прямо в диалоге — без закрытия окна, мгновенная обратная связь."""
        from PyQt6.QtWidgets import QApplication
        email    = self.email_edit.text().strip()
        password = self.password_edit.text().strip()
        host     = self.host_edit.text().strip()
        if not email or not password or not host:
            self.test_status.setText("Введите email, пароль и SMTP-хост")
            self.test_status.setStyleSheet("color: #F59E0B;")
            return

        # Получаем прокси из формы (необязательно — тест без прокси разрешён)
        proxy_raw = self.proxy_edit.toPlainText().strip()
        proxy_lines = [
            ProxyManager.parse(l.strip())
            for l in proxy_raw.splitlines()
            if l.strip() and not l.strip().startswith("#")
        ]
        proxy_list = [p for p in proxy_lines if p]

        self.test_btn.setEnabled(False)
        if proxy_list:
            self.test_status.setText("Подключение через прокси…")
        else:
            self.test_status.setText("Прямое подключение (без прокси)…")
        self.test_status.setStyleSheet("color: gray;")
        QApplication.processEvents()
        acc = SmtpAccount(
            email=email, password=password,
            host=host,
            port=self.port_spin.value(),
            use_ssl=self.ssl_check.isChecked(),
            use_tls=self.tls_check.isChecked(),
        )
        if proxy_list:
            acc.proxy_list = proxy_list
            acc.proxy = proxy_list[0]
        self._test_worker = TestWorker(acc, parent=self)

        @pyqtSlot(bool, str)
        def _on_done(ok: bool, msg: str):
            self.test_btn.setEnabled(True)
            if ok:
                self.test_status.setText("Подключение успешно")
                self.test_status.setStyleSheet("color: #10B981;")
            else:
                short = msg[:80] + "…" if len(msg) > 80 else msg
                self.test_status.setText(short)
                self.test_status.setStyleSheet("color: #EF4444;")

        self._test_worker.result_ready.connect(_on_done)
        self._test_worker.start()
    def _autofill_smtp(self, email: str):
        if "@" not in email:
            return
        domain = email.split("@")[-1].strip().lower()
        cfg = get_smtp_config_for_domain(domain)
        if cfg:
            self.host_edit.setText(cfg["host"])
            self.port_spin.setValue(cfg["port"])
            self.ssl_check.setChecked(cfg.get("use_ssl", True))
            self.tls_check.setChecked(cfg.get("use_tls", False))
            # IMAP автозаполнение
            imap_host = cfg.get("imap_host", "")
            if imap_host:
                self.imap_host_edit.setText(imap_host)
                self.imap_port_spin.setValue(cfg.get("imap_port", 993))
                self.imap_ssl_check.setChecked(cfg.get("imap_ssl", True))

    def _fill(self, acc: SmtpAccount):
        self.email_edit.setText(acc.email)
        self.password_edit.setText(acc.password)
        self.name_edit.setText(acc.display_name)
        self.host_edit.setText(acc.host)
        self.port_spin.setValue(acc.port)
        self.ssl_check.setChecked(acc.use_ssl)
        self.tls_check.setChecked(acc.use_tls)
        self.daily_spin.setValue(acc.daily_limit)
        self.hourly_spin.setValue(acc.hourly_limit)
        self.active_check.setChecked(acc.is_active)
        proxy_lines = getattr(acc, "proxy_list", []) or (
            [getattr(acc, "proxy", "")] if getattr(acc, "proxy", "") else []
        )
        self.proxy_edit.setPlainText("\n".join(proxy_lines))
        self.proxy_rotation_check.setChecked(getattr(acc, "proxy_rotation_random", False))
        self.imap_host_edit.setText(getattr(acc, "imap_host", ""))
        self.imap_port_spin.setValue(getattr(acc, "imap_port", 993))
        self.imap_ssl_check.setChecked(getattr(acc, "imap_ssl", True))

    def _validate_and_accept(self):
        email = self.email_edit.text().strip()
        if not email or "@" not in email:
            QMessageBox.warning(self, "Ошибка", "Введите корректный email-адрес")
            return
        if not self.password_edit.text().strip():
            QMessageBox.warning(self, "Ошибка", "Введите пароль")
            return
        if not self.host_edit.text().strip():
            QMessageBox.warning(self, "Ошибка", "Укажите SMTP-хост")
            return
        self.accept()

    def get_account(self) -> SmtpAccount:
        proxy_raw = self.proxy_edit.toPlainText().strip()
        proxy_lines = [
            ProxyManager.parse(l.strip())
            for l in proxy_raw.splitlines()
            if l.strip() and not l.strip().startswith("#")
        ]
        proxy_list = [p for p in proxy_lines if p]

        acc = SmtpAccount(
            email=self.email_edit.text().strip(),
            password=self.password_edit.text().strip(),
            host=self.host_edit.text().strip(),
            port=self.port_spin.value(),
            use_ssl=self.ssl_check.isChecked(),
            use_tls=self.tls_check.isChecked(),
            display_name=self.name_edit.text().strip(),
            daily_limit=self.daily_spin.value(),
            hourly_limit=self.hourly_spin.value(),
            is_active=self.active_check.isChecked(),
        )
        acc.imap_host = self.imap_host_edit.text().strip()
        acc.imap_port = self.imap_port_spin.value()
        acc.imap_ssl = self.imap_ssl_check.isChecked()
        acc.proxy_list = proxy_list
        acc.proxy_rotation_random = self.proxy_rotation_check.isChecked()
        if proxy_list:
            acc.proxy = proxy_list[0]
        return acc



class _CountryWorker(QThread):
    """Асинхронно определяет страну прокси через ip-api.com и обновляет ячейку."""
    result_ready = pyqtSignal(int, str)   # row, flag+text

    def __init__(self, row: int, proxy_url: str, parent=None):
        super().__init__(parent)
        self._row = row
        self._proxy_url = proxy_url

    def run(self):
        # Проверяем кэш — не дёргаем ip-api.com повторно для одного прокси
        cached = _proxy_country_cache.get(self._proxy_url)
        if cached is not None:
            self.result_ready.emit(self._row, cached)
            return
        # Rate-limit: не более 3 одновременных запросов к ip-api.com
        with _country_api_semaphore:
            flag = self._resolve(self._proxy_url)
        # Кэшируем результат на всю сессию
        _proxy_country_cache[self._proxy_url] = flag
        self.result_ready.emit(self._row, flag)

    @staticmethod
    def _cc_flag(cc: str) -> str:
        return _cc_flag_emoji(cc)

    @staticmethod
    def _resolve(proxy_url: str) -> str:
        """Connects THROUGH the proxy to ip-api.com for the real exit-IP country.
        Supports HTTP/HTTPS proxies natively; SOCKS5 via PySocks if available.
        Falls back to direct host-IP lookup on any error.
        """
        try:
            parsed = urllib.parse.urlparse(proxy_url)
            scheme = (parsed.scheme or "http").lower().rstrip("://")
            host = parsed.hostname or ""
            port = parsed.port or (1080 if "socks" in scheme else 8080)
            uname = parsed.username or ""
            upass = parsed.password or ""
            if not host:
                return "—"

            auth = ""
            if uname:
                auth = (f"{urllib.parse.quote(uname,safe='')}"
                        f":{urllib.parse.quote(upass,safe='')}@")

            # HTTP/HTTPS proxy: urllib ProxyHandler
            if scheme in ("http", "https", ""):
                proxy_full = f"http://{auth}{host}:{port}"
                handler = urllib.request.ProxyHandler({"http": proxy_full, "https": proxy_full})
                opener = urllib.request.build_opener(handler)
                for url in [
                    "http://ip-api.com/json/?fields=status,country,countryCode",
                    "http://ipinfo.io/json",
                ]:
                    try:
                        req = urllib.request.Request(url, headers={"User-Agent": "FMailSender/3.1"})
                        with opener.open(req, timeout=7) as resp:
                            d = json.loads(resp.read())
                            cc = d.get("countryCode") or d.get("country","")[:2]
                            ctry = d.get("country", cc)
                            return f"{_CountryWorker._cc_flag(cc)} {ctry}".strip()
                    except Exception:
                        continue

              # SOCKS5/SOCKS4 proxy — FIX: используем pure-stdlib SOCKS5 (как ProxyCheckWorker)
              # вместо PySocks, который часто не установлен. PySocks при ImportError
              # молча проваливался в fallback по IP шлюза → все прокси показывали
              # страну шлюза (напр. Netherlands для gw.foxyproxy.online) вместо exit-IP.
            elif "socks" in scheme:
                try:
                    s = ProxyCheckWorker._socks5_connect_raw(
                        host, port, "ip-api.com", 80,
                        username=uname, password=upass, timeout=7,
                    )
                    s.sendall(
                        b"GET /json/?fields=status,country,countryCode HTTP/1.0\r\n"
                        b"Host: ip-api.com\r\nUser-Agent: FMailSender/4.0\r\n\r\n"
                    )
                    raw = b""
                    while True:
                        c = s.recv(4096)
                        if not c:
                            break
                        raw += c
                        if len(raw) > 32768:
                            break
                    s.close()
                    if b"\r\n\r\n" in raw:
                        body = raw.split(b"\r\n\r\n", 1)[1].decode("utf-8", "replace").strip()
                        d = json.loads(body)
                        if d.get("status") == "success":
                            cc = d.get("countryCode", "")
                            ctry = d.get("country", cc)
                            return f"{_CountryWorker._cc_flag(cc)} {ctry}".strip()
                except Exception:
                    pass

              # Fallback: look up proxy host directly
            req = urllib.request.Request(
                f"http://ip-api.com/json/{host}?fields=country,countryCode",
                headers={"User-Agent": "FMailSender/3.1"},
            )
            with urllib.request.urlopen(req, timeout=4) as resp:
                d = json.loads(resp.read())
                cc = d.get("countryCode","")
                ctry = d.get("country","")
                return f"{_CountryWorker._cc_flag(cc)} {ctry} (хост)".strip()
        except Exception:
            return "—"

class AccountsScreen(QWidget):
    accounts_changed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._accounts: list[SmtpAccount] = []
        self._test_workers: list[TestWorker] = []
        self._import_worker = None
        self._proxy_check_worker = None
        self._test_cancel_event = threading.Event()
        self._hide_invalid_accounts = True  # скрывать невалидные по умолчанию
        self._setup_ui()
        self._load()

    def _setup_ui(self):
          layout = QVBoxLayout(self)
          layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
          layout.setSpacing(Spacing.MD)

          title = QLabel("SMTP-аккаунты")
          title.setObjectName("section_header")
          layout.addWidget(title)

          # ── Основная панель инструментов ──────────────────────────────────
          toolbar = QHBoxLayout()
          toolbar.setSpacing(Spacing.SM)

          add_btn = QPushButton("+ Добавить аккаунт")
          add_btn.setObjectName("btn_primary")
          add_btn.clicked.connect(self._add_account)
          toolbar.addWidget(add_btn)

          import_btn = QPushButton("Импорт (.txt)")
          import_btn.clicked.connect(self._import_accounts)
          toolbar.addWidget(import_btn)

          proxy_import_btn = QPushButton("Импорт прокси")
          proxy_import_btn.setToolTip("Массовый импорт и проверка прокси (с определением страны)")
          proxy_import_btn.clicked.connect(self._import_proxies)
          toolbar.addWidget(proxy_import_btn)

          toolbar.addStretch()

          self.test_all_btn = QPushButton("Проверить все")
          self.test_all_btn.clicked.connect(self._test_all)
          toolbar.addWidget(self.test_all_btn)

          self.cancel_test_btn = QPushButton("Отмена")
          self.cancel_test_btn.setIcon(icons.make_icon(icons.STOP))
          self.cancel_test_btn.setIconSize(QSize(16, 16))
          self.cancel_test_btn.setObjectName("btn_secondary")
          self.cancel_test_btn.clicked.connect(self._cancel_test)
          self.cancel_test_btn.setVisible(False)
          toolbar.addWidget(self.cancel_test_btn)

          self._show_invalid_btn = QPushButton("Показать невалидные")
          self._show_invalid_btn.setObjectName("btn_secondary")
          self._show_invalid_btn.setToolTip(
              "Показать/скрыть аккаунты с неверным логином/паролем.\n"
              "Они не участвуют в рассылке ни при каких условиях."
          )
          self._show_invalid_btn.clicked.connect(self._toggle_invalid_visibility)
          toolbar.addWidget(self._show_invalid_btn)

          layout.addLayout(toolbar)

          # ── Контекстная панель (видна при выборе строк) ───────────────────
          ctx_bar = QHBoxLayout()
          ctx_bar.setSpacing(Spacing.SM)

          self._ctx_select_all_btn = QPushButton("Выбрать все")
          self._ctx_select_all_btn.setObjectName("btn_secondary")
          self._ctx_select_all_btn.clicked.connect(lambda: self.table.selectAll())
          ctx_bar.addWidget(self._ctx_select_all_btn)

          self._ctx_test_btn = QPushButton("Проверить выбранные")
          self._ctx_test_btn.setIcon(icons.make_icon(icons.ZAP))
          self._ctx_test_btn.setIconSize(QSize(16, 16))
          self._ctx_test_btn.setObjectName("btn_secondary")
          self._ctx_test_btn.clicked.connect(self._test_selected)
          self._ctx_test_btn.setVisible(False)
          ctx_bar.addWidget(self._ctx_test_btn)

          self._ctx_del_btn = QPushButton("Удалить")
          self._ctx_del_btn.setIcon(icons.make_icon(icons.TRASH))
          self._ctx_del_btn.setIconSize(QSize(16, 16))
          self._ctx_del_btn.setObjectName("btn_danger")
          self._ctx_del_btn.clicked.connect(self._delete_selected)
          self._ctx_del_btn.setVisible(False)
          ctx_bar.addWidget(self._ctx_del_btn)

          ctx_bar.addStretch()
          layout.addLayout(ctx_bar)

          # ── Таблица ───────────────────────────────────────────────────────
          self.table = QTableWidget(0, 3)
          self.table.setHorizontalHeaderLabels([
              "Email", "Статус", "Прокси",
          ])
          self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
          self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
          self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
          self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
          self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
          self.table.setColumnWidth(2, 160)
          self.table.verticalHeader().setVisible(False)
          self.table.setShowGrid(False)
          self.table.setAlternatingRowColors(True)
          self.table.doubleClicked.connect(self._edit_account)
          self.table.itemSelectionChanged.connect(self._update_contextual_buttons)
          layout.addWidget(self.table)

          self.status_label = QLabel("Аккаунтов: 0")
          self.status_label.setObjectName("label_muted")
          layout.addWidget(self.status_label)
    def get_accounts(self) -> list:
        return self._accounts

    def _load(self):
        self._accounts = load_accounts()
        # FIX v4.5.2: НЕ авто-восстанавливаем прокси из диска при загрузке.
        # Прокси — сессионные, при перезапуске нужно импортировать заново.
        # Аккаунты загружаются БЕЗ прокси-назначений (proxy/proxy_list сброшены load_accounts).
        self._refresh_table()
        self.accounts_changed.emit(self._accounts)
        # Автопроверка при загрузке отключена — слишком много потоков при большом кол-ве аккаунтов

    def _refresh_table(self):
          self.table.setRowCount(0)
          _hide_invalid = getattr(self, '_hide_invalid_accounts', True)
          for acc in self._accounts:
              # FIX v4.5.3: невалидные аккаунты (подтверждённые ошибкой аутентификации) скрываются.
              # Это исключает их из вида — они не используются в рассылке ни при каких условиях.
              if _hide_invalid and getattr(acc, 'last_test_ok', None) is False:
                  continue  # скрываем — неверный логин/пароль
              row = self.table.rowCount()
              self.table.insertRow(row)
              self.table.setRowHeight(row, 32)

              # Колонка 0: Email (с подсказкой: хост, лимиты)
              email_item = QTableWidgetItem(acc.email)
              email_item.setToolTip(
                  f"{acc.email}\n"
                  f"Host: {acc.host}:{acc.port}\n"
                  f"Лимит: {acc.daily_limit}/день, {acc.hourly_limit}/час"
              )
              self.table.setItem(row, 0, email_item)

              # Колонка 1: Статус — коротко + полная причина в tooltip
              _ltok = getattr(acc, 'last_test_ok', None)
              _ltmsg = getattr(acc, 'last_test_msg', "")
              if _ltok is True:
                  _sent = getattr(acc, 'sent_today', 0)
                  status_item = QTableWidgetItem(f"Валидный  {_sent}/{acc.daily_limit}")
                  status_item.setForeground(QColor(Colors.SUCCESS))
                  status_item.setToolTip(f"Аккаунт работает\nОтправлено сегодня: {_sent} из {acc.daily_limit}")
              elif _ltok is False:
                  first_line = (_ltmsg or "Неверный логин или пароль").split('\n')[0]
                  status_item = QTableWidgetItem(f"{first_line[:55]}")
                  status_item.setForeground(QColor(Colors.ERROR))
                  status_item.setToolTip(_ltmsg or "Аккаунт недействителен")
              else:
                  status_item = QTableWidgetItem("Не проверено")
                  status_item.setForeground(QColor("#6666AA"))
                  status_item.setToolTip("Нажмите «Проверить» для проверки аккаунта")
              self.table.setItem(row, 1, status_item)

              # Колонка 2: Прокси (страна из кэша — не теряется при _refresh_table)
              _proxy_raw  = (acc.proxy or "").strip()
              _proxy_pool = [p for p in (getattr(acc, "proxy_list", None) or []) if p.strip()]
              _pool_size  = len(_proxy_pool)
              _cached_country = _proxy_country_cache.get(_proxy_raw, "") if _proxy_raw else ""
              if _pool_size > 1:
                  # Пул из нескольких прокси — показываем страны всех
                  _countries = [c for c in (
                      _proxy_country_cache.get(p.strip(), "") for p in _proxy_pool
                  ) if c and c != "—"]
                  _flag_str = " | ".join(_countries) if _countries else ""
                  _proxy_display = f"Пул: {_pool_size} прокси" + (f"  {_flag_str}" if _flag_str else "")
                  _tooltip = "\n".join(_proxy_pool)
              elif _cached_country and _cached_country != "—":
                  _proxy_display = f"{_cached_country} | {_proxy_raw}"
                  _tooltip = _proxy_raw
              else:
                  _proxy_display = _proxy_raw if _proxy_raw else "—"
                  _tooltip = _proxy_raw or "Прокси не назначен"
              proxy_item = QTableWidgetItem(_proxy_display)
              proxy_item.setForeground(QColor("#6C8EBF" if _proxy_raw else Colors.TEXT_MUTED))
              proxy_item.setToolTip(_tooltip)
              self.table.setItem(row, 2, proxy_item)
              # Запускаем определение страны для ВСЕХ прокси в пуле, чтобы кэш заполнился
              if _pool_size > 1:
                  for _pi, _px in enumerate(_proxy_pool):
                      _px = _px.strip()
                      if _px and not _proxy_country_cache.get(_px):
                          QTimer.singleShot(
                              100 + row * 80 + _pi * 300,
                              lambda r=row, p=_px: self._fetch_proxy_country(r, p),
                          )
              elif _proxy_raw and not _cached_country:
                  QTimer.singleShot(100 + row * 80, lambda r=row, p=_proxy_raw: self._fetch_proxy_country(r, p))

          valid_count = sum(1 for a in self._accounts if getattr(a, 'last_test_ok', None) is True)
          invalid_count = sum(1 for a in self._accounts if getattr(a, 'last_test_ok', None) is False)
          proxy_err_count = sum(1 for a in self._accounts if getattr(a, 'last_test_ok', None) is None and a.last_test_msg)
          untested_count = sum(1 for a in self._accounts if getattr(a, 'last_test_ok', None) is None and not a.last_test_msg)
          sendable = sum(
              1 for a in self._accounts
              if a.is_active and getattr(a, 'last_test_ok', None) is True
          )
          _hidden_info = f" | Скрыто невалидных: {invalid_count}" if (self._hide_invalid_accounts and invalid_count > 0) else ""
          self.status_label.setText(
              f"Всего: {len(self._accounts)} | "
              f"Валидных: {valid_count} | "
              f"Не проверено: {untested_count}"
              + (f" | Ошибка прокси: {proxy_err_count}" if proxy_err_count > 0 else "")
              + _hidden_info +
              f" | К рассылке: {sendable}"
          )

    def _update_contextual_buttons(self):
        """Показывает/скрывает контекстные кнопки в зависимости от выбора строк."""
        selected = len(set(idx.row() for idx in self.table.selectedIndexes()))
        has_sel = selected > 0
        self._ctx_test_btn.setVisible(has_sel)
        self._ctx_del_btn.setVisible(has_sel)
        if has_sel:
            self._ctx_test_btn.setText(f"Проверить ({selected})")
            self._ctx_del_btn.setText(f"Удалить ({selected})")
  
    def _add_account(self):
        dlg = AccountDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            acc = dlg.get_account()
            self._accounts.append(acc)
            save_accounts(self._accounts)
            self._refresh_table()
            self.accounts_changed.emit(self._accounts)
            # Проверяем новый аккаунт сразу
            self._test_single(len(self._accounts) - 1)

    def _edit_account(self, index):
        row = index.row()
        if row < 0 or row >= len(self._accounts):
            return
        acc = self._accounts[row]
        dlg = AccountDialog(account=acc, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._accounts[row] = dlg.get_account()
            save_accounts(self._accounts)
            self._refresh_table()
            self.accounts_changed.emit(self._accounts)

    def _delete_selected(self):
        rows = sorted(
            {idx.row() for idx in self.table.selectedIndexes()},
            reverse=True,
        )
        if not rows:
            return
        if QMessageBox.question(
            self, "Удалить?",
            f"Удалить {len(rows)} аккаунт(ов)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        for row in rows:
            if 0 <= row < len(self._accounts):
                self._accounts.pop(row)
        save_accounts(self._accounts)
        self._refresh_table()
        self.accounts_changed.emit(self._accounts)

    def _test_single(self, row: int):
        """Проверяет один аккаунт по индексу."""
        if row < 0 or row >= len(self._accounts):
          return
        # Статус теперь в колонке 1
        item = self.table.item(row, 1)
        if item:
            item.setText("Проверка...")
            item.setForeground(QColor(Colors.TEXT_MUTED))
        acc = self._accounts[row]
        w = TestWorker(acc, parent=self)

        @pyqtSlot(bool, str)
        def on_result(ok, msg, r=row):
            # FIX v5.2.3: НЕ вызываем _refresh_table() на каждый результат —
            # это пересобирает всю таблицу (O(N)) и вызывает лаг при параллельных проверках.
            # Вместо этого: обновляем только конкретную строку, планируем отложенный refresh.
            try:
                if 0 <= r < len(self._accounts):
                    _ml = (msg or "").lower()
                    _auth_fail = not ok and any(kw in _ml for kw in [
                        "неверный логин", "неверный пароль", "password", "535", "534", "oauth2 отклонён"
                    ])
                    if ok:
                        self._accounts[r].last_test_ok = True
                        self._accounts[r].is_active = True
                    elif _auth_fail:
                        self._accounts[r].last_test_ok = False
                        self._accounts[r].is_active = False
                    else:
                        self._accounts[r].last_test_ok = None  # прокси/сеть — не меняем is_active
                    self._accounts[r].last_test_msg = msg
                    save_accounts(self._accounts)

                    # Обновляем только строку r — без полной пересборки таблицы
                    _ltok = self._accounts[r].last_test_ok
                    _ltmsg = self._accounts[r].last_test_msg or ""
                    _sent = getattr(self._accounts[r], "sent_today", 0)
                    _lim = self._accounts[r].daily_limit
                    _si = self.table.item(r, 1)
                    if _si:
                        if _ltok is True:
                            _si.setText(f"Валидный  {_sent}/{_lim}")
                            _si.setForeground(QColor(Colors.SUCCESS))
                            _si.setToolTip(f"Аккаунт работает\nОтправлено сегодня: {_sent} из {_lim}")
                        elif _ltok is False:
                            _fl = (_ltmsg or "Неверный логин или пароль").split('\n')[0]
                            _si.setText(f"{_fl[:55]}")
                            _si.setForeground(QColor(Colors.ERROR))
                            _si.setToolTip(_ltmsg or "Аккаунт недействителен")
                        else:
                            _si.setText("Ошибка прокси")
                            _si.setForeground(QColor("#f59e0b"))
                            _si.setToolTip(_ltmsg or "Ошибка соединения")

                    # Пересобираем таблицу отложенно — не чаще раза в 600мс
                    if not getattr(self, "_refresh_pending", False):
                        self._refresh_pending = True
                        QTimer.singleShot(600, self._deferred_refresh_after_test)

            except RuntimeError:
                return
            # BUG FIX v4.4.4: уведомляем SendingScreen об обновлённом аккаунте
            try:
                self.accounts_changed.emit(self._accounts)
            except RuntimeError:
                pass
            # Страну показываем только если ещё не определена
            _px = (self._accounts[r].proxy or "").strip() if 0 <= r < len(self._accounts) else ""
            if _px and _px not in _proxy_country_cache:
                self._fetch_proxy_country(r, _px)
            # Очищаем завершённые воркеры
            self._test_workers = [x for x in self._test_workers if x.isRunning()]

        w.result_ready.connect(on_result)
        self._test_workers.append(w)
        w.start()

    def _deferred_refresh_after_test(self) -> None:
        """Вызывается отложенно (QTimer 600мс) после _test_single — делает полный refresh таблицы.
        FIX v5.2.3: вместо вызова _refresh_table() в каждом on_result (O(N) × кол-во потоков)
        объединяем множественные обновления в одно, снижая нагрузку на GUI при пакетной проверке.
        """
        self._refresh_pending = False
        # Если сейчас идёт _test_all (он сам управляет refresh) — пропускаем
        if not self.test_all_btn.isEnabled():
            return
        self._refresh_table()

    def _fetch_proxy_country(self, row: int, proxy_url: str) -> None:
        """Запускает CountryWorker для обновления флага страны в колонке Прокси (2).
        Проверяет кэш — не запускает воркер если страна уже известна.
        Держит сильную ссылку на воркер в _test_workers чтобы Qt/GC его не удалил.
        """
        # Используем кэш — если страна уже определена, просто обновляем ячейку
        cached = _proxy_country_cache.get(proxy_url)
        if cached:
            item = self.table.item(row, 2)
            if item:
                raw = item.toolTip() or proxy_url
                if cached != "—":
                    item.setText(f"{cached} | {raw}")
                item.setForeground(QColor("#6C8EBF"))
            return
        w = _CountryWorker(row, proxy_url, parent=self)

        def _on_country(r: int, flag_text: str, widget=self.table):
            item = widget.item(r, 2)
            if item:
                current = item.text()
                base = current.split(" | ")[-1] if " | " in current else current
                if flag_text and flag_text != "—":
                    item.setText(f"{flag_text} | {base}")
                item.setForeground(QColor("#6C8EBF"))
            # Удаляем воркер из списка после завершения (cleanup)
            self._test_workers = [x for x in self._test_workers if x.isRunning()]

        w.result_ready.connect(_on_country)
        # Держим сильную ссылку — иначе Python GC удалит объект до завершения потока
        self._test_workers.append(w)
        w.start()

    def _test_all(self) -> None:
        """Проверяет все аккаунты батчами (MAX_CONCURRENT=4).

        ИСПРАВЛЕНО:
        - Колонка статуса = 1 (не 5/7, которых не существует в 3-колоночной таблице)
        - Не все потоки сразу: GMX/Rambler блокируют массовые подключения -> ложные ошибки
        - ok_cnt из last_test_ok, не из несуществующей колонки 5
        """
        if not self._accounts:
            return

        MAX_CONCURRENT = 30  # FIX v4.5.3: увеличено с 8 до 30 — в 3-4x быстрее валидация

        self._test_cancel_event.clear()
        self.cancel_test_btn.setVisible(True)
        self.test_all_btn.setEnabled(False)
        self.test_all_btn.setText("Проверяю...")

        # Пометить все как «в очереди» — колонка 1 (Статус)
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 1)
            if item:
                item.setText("В очереди...")
                item.setForeground(QColor(Colors.TEXT_MUTED))

        total = len(self._accounts)
        completed = [0]
        running = [0]
        queue = list(range(total))

        def _start_next():
            """Стартует следующий воркер если есть свободный слот и аккаунты в очереди."""
            while queue and running[0] < MAX_CONCURRENT:
                if self._test_cancel_event.is_set():
                    break
                row = queue.pop(0)
                if row >= len(self._accounts):
                    continue
                acc = self._accounts[row]

                status_item = self.table.item(row, 1)
                if status_item:
                    status_item.setText("Проверка...")
                    status_item.setForeground(QColor(Colors.TEXT_MUTED))

                w = TestWorker(acc, parent=self)
                running[0] += 1

                @pyqtSlot(bool, str)
                def on_result(ok, msg, r=row):
                    running[0] -= 1

                    # FIX v4.5.3: различаем ошибку аутентификации vs ошибку прокси/соединения.
                    # Плохой прокси НЕ означает неверный пароль — аккаунт остаётся активным.
                    _msg_lower = (msg or "").lower()
                    _is_auth_fail = not ok and any(
                        kw in _msg_lower for kw in [
                            "неверный логин", "неверный пароль", "password", "invalid credentials",
                            "oauth2 отклонён", "oauth2 rejected", "535", "534", "530",
                        ]
                    )
                    # Обновить статус — колонка 1 (единственная колонка статуса)
                    si = self.table.item(r, 1)
                    if si:
                        if ok:
                            si.setText("Валидный")
                            si.setForeground(QColor(Colors.SUCCESS))
                        elif _is_auth_fail:
                            si.setText("Невалидный")
                            si.setForeground(QColor(Colors.ERROR))
                        else:
                            si.setText("Ошибка прокси")
                            si.setForeground(QColor("#f59e0b"))  # amber
                        si.setToolTip(msg)

                    if 0 <= r < len(self._accounts):
                        if ok:
                            self._accounts[r].last_test_ok = True
                            self._accounts[r].is_active = True
                        elif _is_auth_fail:
                            # Достоверно неверные учётные данные → деактивировать
                            self._accounts[r].last_test_ok = False
                            self._accounts[r].is_active = False
                        else:
                            # Ошибка прокси/соединения — пароль может быть верным.
                            # last_test_ok=None означает "не проверено" → аккаунт остаётся
                            # в статусе «Не проверено», is_active не меняется.
                            self._accounts[r].last_test_ok = None
                        self._accounts[r].last_test_msg = msg

                    completed[0] += 1
                    done = completed[0]
                    ok_so_far   = sum(1 for a in self._accounts if getattr(a, "last_test_ok", None) is True)
                    fail_so_far = sum(1 for a in self._accounts if getattr(a, "last_test_ok", None) is False)
                    self.status_label.setText(
                        f"Проверено: {done}/{total} | Валидных: {ok_so_far} | Невалидных: {fail_so_far}"
                    )

                    if done >= total or self._test_cancel_event.is_set():
                        # Всё завершено — сохранить, отсортировать, обновить таблицу
                        self._accounts.sort(
                            key=lambda a: (0 if getattr(a, "last_test_ok", None) is True else 1, a.email)
                        )
                        save_accounts(self._accounts)
                        self._refresh_table()
                        # BUG FIX v4.4.4: уведомляем SendingScreen об обновлённых аккаунтах
                        try:
                            self.accounts_changed.emit(self._accounts)
                        except RuntimeError:
                            pass
                        self.test_all_btn.setEnabled(True)
                        self.test_all_btn.setText("Проверить все")
                        self.cancel_test_btn.setVisible(False)
                        ok_final = sum(1 for a in self._accounts if getattr(a, "last_test_ok", None) is True)
                        fail_final = sum(1 for a in self._accounts if getattr(a, "last_test_ok", None) is False)
                        untested_final = sum(1 for a in self._accounts if getattr(a, "last_test_ok", None) is None)
                        sendable_final = sum(
                            1 for a in self._accounts
                            if a.is_active and getattr(a, "last_test_ok", None) is True
                        )
                        self.status_label.setText(
                            f"Всего: {len(self._accounts)} | "
                            f"Валидных: {ok_final} | "
                            f"Невалидных: {fail_final} | "
                            f"Не проверено: {untested_final} | "
                            f"Готово к рассылке: {sendable_final}"
                        )
                    else:
                        # Освободился слот — запускаем следующий
                        _start_next()

                w.result_ready.connect(on_result)
                self._test_workers.append(w)
                w.start()

        _start_next()

    def _run_proxy_check_dialog(self, proxies: list[str]):
        """Диалог проверки прокси с отображением страны и статуса."""
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Проверка прокси ({len(proxies)} шт.)")
        dlg.setMinimumWidth(620)
        dlg.setMinimumHeight(480)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        progress = QProgressBar()
        progress.setRange(0, len(proxies))
        progress.setValue(0)
        lay.addWidget(progress)

        stat_lbl = QLabel("Проверяю прокси...")
        stat_lbl.setObjectName("label_muted")
        lay.addWidget(stat_lbl)

        table = QTableWidget(len(proxies), 6)
        table.setHorizontalHeaderLabels(["Прокси", "Статус", "SMTP :587", "Страна", "Пинг (мс)", "Ошибка"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for i, p in enumerate(proxies):
            table.setItem(i, 0, QTableWidgetItem(p))
            item = QTableWidgetItem("Проверка...")
            item.setForeground(QColor(Colors.TEXT_MUTED))
            table.setItem(i, 1, item)
            table.setItem(i, 2, QTableWidgetItem("…"))
            table.setItem(i, 3, QTableWidgetItem(""))
            table.setItem(i, 4, QTableWidgetItem(""))
            table.setItem(i, 5, QTableWidgetItem(""))
        lay.addWidget(table)

        btn_row = QHBoxLayout()
        use_btn = QPushButton("Использовать валидные")
        use_btn.setIcon(icons.make_icon(icons.ARROW_RIGHT))
        use_btn.setIconSize(QSize(16, 16))
        use_btn.setObjectName("btn_primary")
        use_btn.setEnabled(False)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setObjectName("btn_secondary")
        btn_row.addWidget(use_btn)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        lay.addLayout(btn_row)

        valid_proxies = []
        smtp_blocked_proxies = []  # FIX v4.5.4: прокси что блокируют SMTP
        worker = ProxyCheckWorker(proxies, dlg)

        def on_result(idx, valid, country, error, ping_ms, smtp_ok):
            progress.setValue(idx + 1)
            s_item  = table.item(idx, 1)
            sm_item = table.item(idx, 2)  # SMTP column
            c_item  = table.item(idx, 3)
            p_item  = table.item(idx, 4)
            e_item  = table.item(idx, 5)
            if valid:
                s_item.setText("✓ OK")
                s_item.setForeground(QColor(Colors.SUCCESS))
                if smtp_ok:
                    sm_item.setText("✓ SMTP")
                    sm_item.setForeground(QColor(Colors.SUCCESS))
                else:
                    sm_item.setText("✗ заблок.")
                    sm_item.setForeground(QColor(Colors.ERROR))
                c_item.setText(country or "—")
                ping_color = Colors.SUCCESS if ping_ms < 300 else ("#F59E0B" if ping_ms < 800 else Colors.ERROR)
                p_item.setText(f"{ping_ms} мс")
                p_item.setForeground(QColor(ping_color))
                if smtp_ok:
                    valid_proxies.append(proxies[idx])
                else:
                    # Прокси подключается, но блокирует SMTP — не пригоден для рассылки
                    smtp_blocked_proxies.append(proxies[idx])
            else:
                s_item.setText("✗ Ошибка")
                s_item.setForeground(QColor(Colors.ERROR))
                sm_item.setText("—")
                e_item.setText(error)

        def on_finished(valid_cnt, total):
            _smtp_ok = len(valid_proxies)
            _smtp_bad = len(smtp_blocked_proxies)
            _fail = total - valid_cnt
            parts = [f"✓ {_smtp_ok} готовы к SMTP-рассылке"]
            if _smtp_bad:
                parts.append(f"⚠ {_smtp_bad} блокируют SMTP-порт")
            if _fail:
                parts.append(f"✗ {_fail} недоступны")
            stat_lbl.setText(" | ".join(parts))
            use_btn.setEnabled(_smtp_ok > 0)

        def on_use():
            # Сохраняем в глобальный пул (сохраняется при удалении аккаунтов)
            save_global_proxies(valid_proxies)
            # Round-robin распределение по аккаунтам
            distribute_proxies(self._accounts, valid_proxies)
            save_accounts(self._accounts)
            self._refresh_table()
            self.accounts_changed.emit(self._accounts)
            dlg.accept()
            QMessageBox.information(
                self, "Прокси назначены",
                f"{len(valid_proxies)} валидных прокси назначено {len(self._accounts)} аккаунтам.\n"
                f"Прокси сохранены глобально — при добавлении новых аккаунтов они получат прокси автоматически."
            )

        worker.result.connect(on_result)
        worker.finished.connect(on_finished)
        use_btn.clicked.connect(on_use)
        cancel_btn.clicked.connect(lambda: (worker.cancel(), dlg.reject()))
        self._proxy_check_worker = worker
        worker.start()
        dlg.exec()

    def _import_proxies(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Импорт прокси")
        dlg.setMinimumWidth(540)
        dlg.setMinimumHeight(440)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(12)
        lay.setContentsMargins(20, 20, 20, 20)

        hint = QLabel(
            "Введите прокси — по одному на строку. Поддерживаемые форматы:\n"
            "  user:pass@host:port\n"
            "  socks5://user:pass@host:port\n"
            "  http://user:pass@host:port\n"
            "  host:port\n"
            "  host:port:user:pass"
        )
        hint.setObjectName("label_muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        text_edit = QTextEdit()
        text_edit.setPlaceholderText(
            "user:pass@proxy.example.com:10444\n"
            "socks5://user:pass@host:port\n"
            "192.168.1.1:8080"
        )
        text_edit.setMinimumHeight(180)
        lay.addWidget(text_edit)

        file_row = QHBoxLayout()
        load_file_btn = QPushButton("Загрузить из файла")
        load_file_btn.setIcon(icons.make_icon(icons.UPLOAD))
        load_file_btn.setIconSize(QSize(16, 16))
        load_file_btn.setObjectName("btn_secondary")

        def _load_file():
            path, _ = QFileDialog.getOpenFileName(
                dlg, "Выбрать файл с прокси", "",
                "Текстовые файлы (*.txt *.dat);;Все файлы (*)"
            )
            if path:
                try:
                    text = Path(path).read_text(encoding="utf-8", errors="ignore")
                    text_edit.setPlainText(text)
                except Exception as e:
                    QMessageBox.warning(dlg, "Ошибка", str(e))

        load_file_btn.clicked.connect(_load_file)
        file_row.addWidget(load_file_btn)
        file_row.addStretch()
        lay.addLayout(file_row)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        raw = text_edit.toPlainText().strip()
        if not raw:
            return

        lines = [l.strip() for l in raw.splitlines() if l.strip()]
        valid_proxies = [p for p in (ProxyManager.parse(l) for l in lines) if p]
        invalid_count = len(lines) - len(valid_proxies)

        if not valid_proxies:
            QMessageBox.warning(
                self, "Нет валидных прокси",
                "Ни один прокси не прошёл проверку формата.\n\n"
                "Поддерживаемые форматы:\n"
                "  user:pass@host:port\n"
                "  socks5://user:pass@host:port\n"
                "  host:port\n"
                "  host:port:user:pass"
            )
            return

        msg = f"Распознано: {len(valid_proxies)} прокси"
        if invalid_count:
            msg += f" ({invalid_count} пропущено)"
        msg += "\n\nПроверить прокси и определить страны?"

        reply = QMessageBox.question(
            self, "Прокси загружены", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._run_proxy_check_dialog(valid_proxies)
        else:
            # Назначаем без проверки round-robin + сохраняем в глобальный пул
            save_global_proxies(valid_proxies)
            distribute_proxies(self._accounts, valid_proxies)
            save_accounts(self._accounts)
            self._refresh_table()
            self.accounts_changed.emit(self._accounts)
            QMessageBox.information(
                self, "Прокси назначены",
                f"Назначено {len(valid_proxies)} прокси {len(self._accounts)} аккаунтам.\n"
                f"Прокси сохранены глобально — при добавлении новых аккаунтов они получат прокси автоматически."
            )


    def _test_selected(self) -> None:
        """Проверить выбранные аккаунты батчами (MAX_CONCURRENT=8).

        ИСПРАВЛЕНО: раньше запускало все потоки одновременно без лимита,
        что вызывало перегрузку ОС и зависание ~30% аккаунтов в очереди.
        Теперь использует ту же батчевую очередь что и _test_all().
        """
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()})
        if not rows:
            QMessageBox.information(self, "Нет выбранных", "Выберите строки в таблице для проверки.")
            return

        MAX_CONCURRENT = 8

        self._test_cancel_event.clear()
        self.cancel_test_btn.setVisible(True)
        self.test_all_btn.setEnabled(False)

        # Пометить выбранные как «в очереди» — колонка 1
        for r in rows:
            item = self.table.item(r, 1)
            if item:
                item.setText("В очереди...")
                item.setForeground(QColor(Colors.TEXT_MUTED))

        total = len(rows)
        completed = [0]
        running = [0]
        queue = list(rows)

        def _start_next_sel():
            """Запускает следующий воркер если есть свободный слот."""
            while queue and running[0] < MAX_CONCURRENT:
                if self._test_cancel_event.is_set():
                    break
                row = queue.pop(0)
                if row >= len(self._accounts):
                    continue
                acc = self._accounts[row]

                status_item = self.table.item(row, 1)
                if status_item:
                    status_item.setText("Проверка...")
                    status_item.setForeground(QColor(Colors.TEXT_MUTED))

                w = TestWorker(acc, parent=self)
                running[0] += 1

                @pyqtSlot(bool, str)
                def on_result_sel(ok, msg, r=row):
                    running[0] -= 1
                    si = self.table.item(r, 1)
                    if si:
                        si.setText("Валидный" if ok else "Ошибка")
                        si.setForeground(QColor(Colors.SUCCESS if ok else Colors.ERROR))
                        si.setToolTip(msg)

                    _ml = (msg or "").lower()
                    _auth_fail = not ok and any(kw in _ml for kw in [
                        "неверный логин", "неверный пароль", "password", "535", "534", "oauth2 отклонён"
                    ])
                    if 0 <= r < len(self._accounts):
                        if ok:
                            self._accounts[r].last_test_ok = True
                            self._accounts[r].is_active = True
                        elif _auth_fail:
                            self._accounts[r].last_test_ok = False
                            self._accounts[r].is_active = False
                        else:
                            self._accounts[r].last_test_ok = None  # proxy/conn error
                        self._accounts[r].last_test_msg = msg

                    completed[0] += 1
                    done = completed[0]
                    ok_cnt   = sum(1 for a in self._accounts if getattr(a, "last_test_ok", None) is True)
                    fail_cnt = sum(1 for a in self._accounts if getattr(a, "last_test_ok", None) is False)
                    self.status_label.setText(
                        f"Выбранных проверено: {done}/{total} | Валидных: {ok_cnt} | Невалидных: {fail_cnt}"
                    )

                    if done >= total or self._test_cancel_event.is_set():
                        save_accounts(self._accounts)
                        self._refresh_table()
                        try:
                            self.accounts_changed.emit(self._accounts)
                        except RuntimeError:
                            pass
                        self.test_all_btn.setEnabled(True)
                        self.cancel_test_btn.setVisible(False)
                        self._test_workers = [x for x in self._test_workers if x.isRunning()]
                    else:
                        _start_next_sel()

                w.result_ready.connect(on_result_sel)
                self._test_workers.append(w)
                w.start()

        _start_next_sel()

    def _cancel_test(self) -> None:
        """Отменить текущую проверку всех аккаунтов."""
        self._test_cancel_event.set()
        for w in self._test_workers:
            if w.isRunning():
                w.quit()
        self._test_workers.clear()
        self.test_all_btn.setEnabled(True)
        self.test_all_btn.setText("Проверить все")
        self.cancel_test_btn.setVisible(False)
        self.status_label.setText(f"Проверка отменена | Аккаунтов: {len(self._accounts)}")

    def _test_accounts_by_indices(self, indices: list[int]) -> None:
        """Проверяет ТОЛЬКО аккаунты по указанным индексам через батч-очередь (MAX_CONCURRENT=4).
        Используется после импорта — не перепроверяет уже валидные аккаунты.
        """
        if not indices:
            return

        # Фильтруем невалидные индексы
        valid_indices = [i for i in indices if 0 <= i < len(self._accounts)]
        if not valid_indices:
            return

        MAX_CONCURRENT = 4
        total = len(valid_indices)
        completed = [0]
        running = [0]
        queue = list(valid_indices)

        self.status_label.setText(f"Проверяю {total} новых аккаунтов...")

        # Пометить в очереди
        for row in valid_indices:
            item = self.table.item(row, 1)
            if item:
                item.setText("В очереди...")
                item.setForeground(QColor(Colors.TEXT_MUTED))

        def _start_next():
            while queue and running[0] < MAX_CONCURRENT:
                if self._test_cancel_event.is_set():
                    break
                row = queue.pop(0)
                if row >= len(self._accounts):
                    completed[0] += 1
                    continue
                acc = self._accounts[row]
                si = self.table.item(row, 1)
                if si:
                    si.setText("Проверка...")
                    si.setForeground(QColor(Colors.TEXT_MUTED))

                w = TestWorker(acc, parent=self)
                running[0] += 1

                @pyqtSlot(bool, str)
                def on_result(ok, msg, r=row):
                    running[0] -= 1
                    _ml = (msg or "").lower()
                    _auth_fail = not ok and any(kw in _ml for kw in [
                        "неверный логин", "неверный пароль", "password", "535", "534", "oauth2 отклонён"
                    ])
                    _si = self.table.item(r, 1)
                    if _si:
                        if ok:
                            _si.setText("Валидный")
                            _si.setForeground(QColor(Colors.SUCCESS))
                        elif _auth_fail:
                            _si.setText("Невалидный")
                            _si.setForeground(QColor(Colors.ERROR))
                        else:
                            _si.setText("Ошибка прокси")
                            _si.setForeground(QColor("#f59e0b"))
                        _si.setToolTip(msg)
                    if 0 <= r < len(self._accounts):
                        if ok:
                            self._accounts[r].last_test_ok = True
                            self._accounts[r].is_active = True
                        elif _auth_fail:
                            self._accounts[r].last_test_ok = False
                            self._accounts[r].is_active = False
                        else:
                            self._accounts[r].last_test_ok = None
                        self._accounts[r].last_test_msg = msg
                    completed[0] += 1
                    ok_cnt = sum(1 for a in self._accounts if getattr(a, "last_test_ok", None) is True)
                    fail_cnt = sum(1 for a in self._accounts if getattr(a, "last_test_ok", None) is False)
                    self.status_label.setText(
                        f"Проверено: {completed[0]}/{total} | Валидных: {ok_cnt} | Невалидных: {fail_cnt}"
                    )
                    if completed[0] >= total:
                        save_accounts(self._accounts)
                        self._refresh_table()
                        try:
                            self.accounts_changed.emit(self._accounts)
                        except RuntimeError:
                            pass
                        ok_f = sum(1 for a in self._accounts if getattr(a, "last_test_ok", None) is True)
                        fail_f = sum(1 for a in self._accounts if getattr(a, "last_test_ok", None) is False)
                        unt_f = sum(1 for a in self._accounts if getattr(a, "last_test_ok", None) is None)
                        snd_f = sum(1 for a in self._accounts if a.is_active and getattr(a, "last_test_ok", None) is True)
                        self.status_label.setText(
                            f"Всего: {len(self._accounts)} | Валидных: {ok_f} | "
                            f"Невалидных: {fail_f} | Не проверено: {unt_f} | Готово к рассылке: {snd_f}"
                        )
                    else:
                        _start_next()

                w.result_ready.connect(on_result)
                self._test_workers.append(w)
                w.start()

        _start_next()

    def _toggle_invalid_visibility(self) -> None:
        """Переключает отображение невалидных аккаунтов (last_test_ok=False)."""
        self._hide_invalid_accounts = not self._hide_invalid_accounts
        if self._hide_invalid_accounts:
            self._show_invalid_btn.setText("Показать невалидные")
        else:
            self._show_invalid_btn.setText("Скрыть невалидные")
        self._refresh_table()

    def _save_config(self) -> None:
        """Сохранить аккаунты в файл по выбору пользователя."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить конфиг аккаунтов", "",
            "JSON (*.json);;Все файлы (*)"
        )
        if not path:
            return
        try:
            import json as _j
            data = [
                {
                    "email": a.email,
                    "password": a.password,
                    "host": a.host,
                    "port": a.port,
                    "use_ssl": a.use_ssl,
                    "use_tls": a.use_tls,
                    "display_name": getattr(a, "display_name", ""),
                    "daily_limit": getattr(a, "daily_limit", 500),
                    "hourly_limit": getattr(a, "hourly_limit", 50),
                    "is_active": getattr(a, "is_active", True),
                    "imap_host": getattr(a, "imap_host", ""),
                    "imap_port": getattr(a, "imap_port", 993),
                    "imap_ssl": getattr(a, "imap_ssl", True),
                }
                for a in self._accounts
            ]
            from pathlib import Path as _P
            _P(path).write_text(_j.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            QMessageBox.information(self, "Сохранено", f"Конфиг сохранён:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка сохранения", str(e))

    def _load_config(self) -> None:
        """Загрузить аккаунты из файла по выбору пользователя."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Загрузить конфиг аккаунтов", "",
            "JSON (*.json);;Все файлы (*)"
        )
        if not path:
            return
        try:
            import json as _j
            from pathlib import Path as _P
            raw = _j.loads(_P(path).read_text(encoding="utf-8"))
            loaded = []
            for d in raw:
                a = SmtpAccount(
                    email=d["email"],
                    password=d.get("password",""),
                    host=d["host"],
                    port=d.get("port", 587),
                    use_ssl=d.get("use_ssl", False),
                    use_tls=d.get("use_tls", True),
                    display_name=d.get("display_name",""),
                    daily_limit=d.get("daily_limit", 500),
                    hourly_limit=d.get("hourly_limit", 50),
                    is_active=d.get("is_active", True),
                )
                a.imap_host = d.get("imap_host","")
                a.imap_port = d.get("imap_port", 993)
                a.imap_ssl = d.get("imap_ssl", True)
                loaded.append(a)
            self._accounts = loaded
            save_accounts(self._accounts)
            self._refresh_table()
            self.accounts_changed.emit(self._accounts)
            QMessageBox.information(self, "Загружено", f"Загружено {len(loaded)} аккаунтов из:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка загрузки", str(e))

    def _import_accounts(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Импорт аккаунтов", "", "Text files (*.txt);;All files (*)"
        )
        if not path:
            return

        existing = {a.email.lower() for a in self._accounts}
        worker = BulkImportWorker(path, existing, self)

        progress_dlg = QProgressDialog("Импорт аккаунтов...", "Отмена", 0, 100, self)
        progress_dlg.setWindowTitle("Импорт")
        progress_dlg.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dlg.setMinimumDuration(0)
        progress_dlg.setValue(0)

        def on_progress(cur, total):
            if total > 0:
                progress_dlg.setValue(int(cur * 100 / total))

        def on_finished(imported, errors):
            progress_dlg.close()
            new_accs = worker.new_accounts

            # Авто-распределение прокси из глобального пула на новые аккаунты
            _gproxies = load_global_proxies()
            _proxy_msg = ""
            _start = len(self._accounts)  # FIX v4.5.4: индекс до добавления новых
            if _gproxies and new_accs:
                for i, acc in enumerate(new_accs):
                    acc.proxy = _gproxies[(_start + i) % len(_gproxies)]
                    acc.proxy_list = _gproxies
                    acc.proxy_rotation_random = False
                _proxy_msg = f"\nПрокси из глобального пула ({len(_gproxies)} шт.) назначены автоматически."
            elif new_accs and not _gproxies:
                _proxy_msg = "\n⚠ Глобальный пул прокси пуст — импортируйте прокси через «Импорт прокси»."

            self._accounts.extend(new_accs)
            save_accounts(self._accounts)
            self._refresh_table()
            self.accounts_changed.emit(self._accounts)

            _info = f"Импортировано: {imported}\nПропущено: {errors}{_proxy_msg}"
            if imported > 0 and _gproxies:
                _info += f"\n\nЗапускаю проверку {imported} новых аккаунтов..."
            QMessageBox.information(self, "Импорт завершён", _info)
            self._import_worker = None

            # FIX v4.5.4: тестируем ТОЛЬКО новые аккаунты (не все 50+N)
            if imported > 0 and _gproxies:
                _new_indices = list(range(_start, _start + len(new_accs)))
                QTimer.singleShot(300, lambda idx=_new_indices: self._test_accounts_by_indices(idx))

        def on_error(msg):
            progress_dlg.close()
            QMessageBox.critical(self, "Ошибка импорта", msg)
            self._import_worker = None

        worker.progress.connect(on_progress)
        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        progress_dlg.canceled.connect(worker.quit)
        self._import_worker = worker
        worker.start()
