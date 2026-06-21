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
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot, QTimer
from PyQt6.QtGui import QColor

from core.license import get_storage_key
from core.sender import SmtpAccount, test_smtp_connection, get_smtp_config_for_domain
from gui.theme import Colors, Spacing

import random


class ProxyManager:
    """Менеджер прокси с ротацией: round_robin или random.

    Поддерживаемые форматы:
      socks5://user:pass@host:port   — уже URL
      socks4://host:port             — уже URL
      http://host:port               — уже URL
      user:pass@host:port            — без схемы → socks5://user:pass@host:port
      host:port                      → socks5://host:port
      host:port:user:pass            → socks5://user:pass@host:port
      user:pass:host:port            → socks5://user:pass@host:port
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
        """Нормализует строку прокси в URL-формат. None если невалидно."""
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            return None
        # Уже URL-формат (есть схема вида socks5:// http:// etc.)
        if "://" in raw:
            return raw
        # Формат user:pass@host:port (без схемы, но есть @)
        if "@" in raw:
            try:
                creds, hostport = raw.rsplit("@", 1)
                host, port_str = hostport.rsplit(":", 1)
                int(port_str)
                if host and creds:
                    return f"socks5://{creds}@{host}:{port_str}"
            except (ValueError, AttributeError):
                return None
        parts = raw.split(":")
        if len(parts) == 2:
            try:
                int(parts[1])
                return f"socks5://{parts[0]}:{parts[1]}"
            except ValueError:
                return None
        if len(parts) == 4:
            # host:port:user:pass
            try:
                int(parts[1])
                return f"socks5://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
            except ValueError:
                pass
            # user:pass:host:port
            try:
                int(parts[3])
                return f"socks5://{parts[0]}:{parts[1]}@{parts[2]}:{parts[3]}"
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
    """TCP-проверка прокси + определение страны через ip-api.com (бесплатно)."""
    result = pyqtSignal(int, bool, str, str)  # index, valid, country_info, error
    finished = pyqtSignal(int, int)           # valid_count, total

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
            try:
                parsed = urllib.parse.urlparse(proxy_url)
                host = parsed.hostname
                port = parsed.port
                if not host or not port:
                    self.result.emit(i, False, "", "Невалидный URL")
                    continue
                # TCP connect test (5 сек таймаут)
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                err_code = sock.connect_ex((str(host), int(port)))
                sock.close()
                if err_code != 0:
                    self.result.emit(i, False, "", f"Порт закрыт (err {err_code})")
                    continue
                # Определение страны
                country_info = self._get_country(str(host))
                valid_count += 1
                self.result.emit(i, True, country_info, "")
            except Exception as e:
                self.result.emit(i, False, "", str(e)[:60])
        self.finished.emit(valid_count, len(self._proxies))

    @staticmethod
    def _get_country(ip: str) -> str:
        try:
            req = urllib.request.Request(
                f"http://ip-api.com/json/{ip}?fields=country,countryCode",
                headers={"User-Agent": "FMailSender/3.0"},
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                geo = json.loads(resp.read().decode())
                if geo.get("status") == "success":
                    code = geo.get("countryCode", "")
                    name = geo.get("country", "")
                    return f"{code} {name}".strip()
        except Exception:
            pass
        return ""


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
            "imap_host": getattr(a, "imap_host", ""),
            "imap_port": getattr(a, "imap_port", 993),
            "imap_ssl": getattr(a, "imap_ssl", True),
        }
        if hasattr(a, "proxy_list") and a.proxy_list:
            entry["proxy_list"] = a.proxy_list
            entry["proxy"] = a.proxy_list[0]
            entry["proxy_rotation_random"] = getattr(a, "proxy_rotation_random", False)
        elif hasattr(a, "proxy") and a.proxy:
            entry["proxy"] = a.proxy
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
            acc.imap_host = d.get("imap_host", "")
            acc.imap_port = d.get("imap_port", 993)
            acc.imap_ssl = d.get("imap_ssl", True)
            if "proxy_list" in d:
                acc.proxy_list = d["proxy_list"]
                acc.proxy_rotation_random = d.get("proxy_rotation_random", False)
                if d["proxy_list"]:
                    acc.proxy = d["proxy_list"][0]
            elif "proxy" in d:
                acc.proxy = d["proxy"]
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
                # Умное определение разделителя: ; или : (iejesusmirey.com использует ; формат)
                _sep = ";" if ";" in line and ":" not in line.split(";")[0] else ":"
                parts = line.split(_sep)
                if len(parts) < 2:
                    skipped += 1
                    continue
                email = parts[0].strip()
                alias = parts[2].strip() if len(parts) >= 3 and _sep == ";" else ""
                password = ":".join(parts[1:]).strip()
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
        self.test_btn = QPushButton("🔌 Тест подключения")
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
            self.test_status.setText("⚠️  Введите email, пароль и SMTP-хост")
            self.test_status.setStyleSheet("color: orange;")
            return
        self.test_btn.setEnabled(False)
        self.test_status.setText("⏳ Подключение…")
        self.test_status.setStyleSheet("color: gray;")
        QApplication.processEvents()
        acc = SmtpAccount(
            email=email, password=password,
            host=host,
            port=self.port_spin.value(),
            use_ssl=self.ssl_check.isChecked(),
            use_tls=self.tls_check.isChecked(),
        )
        self._test_worker = TestWorker(acc, parent=self)

        @pyqtSlot(bool, str)
        def _on_done(ok: bool, msg: str):
            self.test_btn.setEnabled(True)
            if ok:
                self.test_status.setText("✅ Подключение успешно")
                self.test_status.setStyleSheet("color: #4caf50;")
            else:
                short = msg[:80] + "…" if len(msg) > 80 else msg
                self.test_status.setText(f"❌ {short}")
                self.test_status.setStyleSheet("color: #f44336;")

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
        flag = self._resolve(self._proxy_url)
        self.result_ready.emit(self._row, flag)

    @staticmethod
    def _cc_flag(cc: str) -> str:
        if len(cc) == 2:
            return "".join(chr(0x1F1E0 + ord(c) - ord('A')) for c in cc.upper())
        return "\U0001f30d"

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
                return "\u2753"

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

              # SOCKS5/SOCKS4 proxy
            elif "socks" in scheme:
                try:
                    import socks
                    stype = socks.SOCKS5 if "socks5" in scheme else socks.SOCKS4
                    s = socks.socksocket()
                    s.set_proxy(stype, host, port, True, uname or None, upass or None)
                    s.settimeout(7)
                    s.connect(("ip-api.com", 80))
                    s.send(b"GET /json/?fields=status,country,countryCode HTTP/1.0\r\n"
                           b"Host: ip-api.com\r\nUser-Agent: FMailSender/3.1\r\n\r\n")
                    raw = b""
                    while True:
                        c = s.recv(4096)
                        if not c:
                            break
                        raw += c
                    s.close()
                    if b"\r\n\r\n" in raw:
                        body = raw.split(b"\r\n\r\n", 1)[1].decode("utf-8","replace")
                        d = json.loads(body)
                        cc = d.get("countryCode","")
                        ctry = d.get("country", cc)
                        return f"{_CountryWorker._cc_flag(cc)} {ctry}".strip()
                except ImportError:
                    pass
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
            return "\U0001f310"

class AccountsScreen(QWidget):
    accounts_changed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._accounts: list[SmtpAccount] = []
        self._test_workers: list[TestWorker] = []
        self._import_worker = None
        self._proxy_check_worker = None
        self._test_cancel_event = threading.Event()
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

          self.cancel_test_btn = QPushButton("⏹ Отмена")
          self.cancel_test_btn.setObjectName("btn_secondary")
          self.cancel_test_btn.clicked.connect(self._cancel_test)
          self.cancel_test_btn.setVisible(False)
          toolbar.addWidget(self.cancel_test_btn)

          layout.addLayout(toolbar)

          # ── Контекстная панель (видна при выборе строк) ───────────────────
          ctx_bar = QHBoxLayout()
          ctx_bar.setSpacing(Spacing.SM)

          self._ctx_select_all_btn = QPushButton("Выбрать все")
          self._ctx_select_all_btn.setObjectName("btn_secondary")
          self._ctx_select_all_btn.clicked.connect(lambda: self.table.selectAll())
          ctx_bar.addWidget(self._ctx_select_all_btn)

          self._ctx_test_btn = QPushButton("⚡ Проверить выбранные")
          self._ctx_test_btn.setObjectName("btn_secondary")
          self._ctx_test_btn.clicked.connect(self._test_selected)
          self._ctx_test_btn.setVisible(False)
          ctx_bar.addWidget(self._ctx_test_btn)

          self._ctx_del_btn = QPushButton("🗑 Удалить")
          self._ctx_del_btn.setObjectName("btn_danger")
          self._ctx_del_btn.clicked.connect(self._delete_selected)
          self._ctx_del_btn.setVisible(False)
          ctx_bar.addWidget(self._ctx_del_btn)

          ctx_bar.addStretch()
          layout.addLayout(ctx_bar)

          # ── Таблица ───────────────────────────────────────────────────────
          self.table = QTableWidget(0, 9)
          self.table.setHorizontalHeaderLabels([
              "Email", "Хост", "Порт", "Дн. лимит", "Ч. лимит", "Статус", "Прокси", "Активен", "Отправлено",
          ])
          self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
          self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
          self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
          self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
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
        self._refresh_table()
        self.accounts_changed.emit(self._accounts)
        # Автопроверка при загрузке отключена — слишком много потоков при большом кол-ве аккаунтов

    def _refresh_table(self):
        self.table.setRowCount(0)
        for acc in self._accounts:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(acc.email))
            self.table.setItem(row, 1, QTableWidgetItem(acc.host))
            self.table.setItem(row, 2, QTableWidgetItem(str(acc.port)))
            self.table.setItem(row, 3, QTableWidgetItem(str(acc.daily_limit)))
            self.table.setItem(row, 4, QTableWidgetItem(str(acc.hourly_limit)))
            # Статус: last_test_ok если проверяли, иначе «Не проверено»
            _ltok = getattr(acc, 'last_test_ok', None)
            if _ltok is True:
                status_item = QTableWidgetItem("✓ OK")
                status_item.setForeground(QColor(Colors.SUCCESS))
            elif _ltok is False:
                status_item = QTableWidgetItem("✗ Ошибка")
                status_item.setForeground(QColor(Colors.ERROR))
            else:
                status_item = QTableWidgetItem("❓ Не проверено")
                status_item.setForeground(QColor(Colors.TEXT_MUTED))
            # (setForeground already set above)
            self.table.setItem(row, 5, status_item)

            # Прокси + флаг страны (обновляется CountryWorker после SMTP OK)
            _proxy_raw = (acc.proxy or "").strip()
            _proxy_display = _proxy_raw if _proxy_raw else "—"
            proxy_item = QTableWidgetItem(_proxy_display)
            proxy_item.setForeground(QColor("#6C8EBF" if _proxy_raw else Colors.TEXT_MUTED))
            proxy_item.setToolTip(_proxy_raw or "Прокси не назначен")
            self.table.setItem(row, 6, proxy_item)
            # FIX: запускаем CountryWorker сразу — показываем флаг при загрузке без ожидания теста
            if _proxy_raw:
                QTimer.singleShot(100 + row * 50, lambda r=row, p=_proxy_raw: self._fetch_proxy_country(r, p))
            active_item = QTableWidgetItem("✓" if acc.is_active else "✗")
            active_item.setForeground(
                QColor(Colors.SUCCESS) if acc.is_active else QColor(Colors.ERROR)
            )
            self.table.setItem(row, 7, active_item)
            # Колонка 8: статистика отправленных писем
            _sent = getattr(acc, 'daily_sent', None)
            if _sent is None:
                _sent = getattr(acc, 'sent_today', 0)
            _sent_txt = f"{_sent or 0}/{acc.daily_limit}"
            sent_item = QTableWidgetItem(_sent_txt)
            sent_item.setForeground(QColor(Colors.TEXT_MUTED))
            sent_item.setToolTip(f"Отправлено сегодня: {_sent or 0} из {acc.daily_limit}")
            self.table.setItem(row, 8, sent_item)
        active_count = sum(1 for a in self._accounts if a.is_active)
        self.status_label.setText(f"Аккаунтов: {len(self._accounts)} (активных: {active_count})")


    def _update_contextual_buttons(self):
        """Показывает/скрывает контекстные кнопки в зависимости от выбора строк."""
        selected = len(set(idx.row() for idx in self.table.selectedIndexes()))
        has_sel = selected > 0
        self._ctx_test_btn.setVisible(has_sel)
        self._ctx_del_btn.setVisible(has_sel)
        if has_sel:
            self._ctx_test_btn.setText(f"⚡ Проверить ({selected})")
            self._ctx_del_btn.setText(f"🗑 Удалить ({selected})")
  
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
        item = self.table.item(row, 5)
        if item:
            item.setText("⏳ Проверка...")
            item.setForeground(QColor(Colors.TEXT_MUTED))
        acc = self._accounts[row]
        w = TestWorker(acc, parent=self)

        @pyqtSlot(bool, str)
        def on_result(ok, msg, r=row):
            item = self.table.item(r, 5)
            if item:
                item.setText("✓ OK" if ok else "✗ Ошибка")
                item.setForeground(QColor(Colors.SUCCESS if ok else Colors.ERROR))
                item.setToolTip(msg)
            if 0 <= r < len(self._accounts):
                self._accounts[r].last_test_ok = ok
                # FIX: автоматически деактивируем аккаунт при ошибке, активируем при успехе
                self._accounts[r].is_active = ok
                save_accounts(self._accounts)
                active_item = self.table.item(r, 7)
                if active_item:
                    from PyQt6.QtGui import QColor
                    active_item.setText("✓" if ok else "✗")
                    active_item.setForeground(QColor(Colors.SUCCESS if ok else Colors.ERROR))
                # FIX: прокси-детект всегда — независимо от результата SMTP-теста
                _px = (self._accounts[r].proxy or "") if 0 <= r < len(self._accounts) else ""
                if _px.strip():
                    self._fetch_proxy_country(r, _px.strip())

        w.result_ready.connect(on_result)
        self._test_workers.append(w)
        w.start()

    def _fetch_proxy_country(self, row: int, proxy_url: str) -> None:
        """Запускает CountryWorker для обновления флага страны в таблице."""
        w = _CountryWorker(row, proxy_url, parent=self)
        def _on_country(r, flag_text, widget=self.table):
            item = widget.item(r, 6)
            if item:
                item.setText(flag_text)
                item.setForeground(QColor("#6C8EBF"))
        w.result_ready.connect(_on_country)
        w.start()
        # Не держим ссылку — QThread удалится сам после finished

    def _test_all(self) -> None:
        if not self._accounts:
            return
        self._test_cancel_event.clear()
        self.cancel_test_btn.setVisible(True)
        self.test_all_btn.setEnabled(False)
        self.test_all_btn.setText("\u23f3 Проверяю...")
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 5)
            if item:
                item.setText("⏳ Проверка...")
                item.setForeground(QColor(Colors.TEXT_MUTED))

        total = len(self._accounts)
        completed = [0]

        for row, acc in enumerate(self._accounts):
            w = TestWorker(acc, parent=self)
            final_row = row

            @pyqtSlot(bool, str)
            def on_result(ok, msg, r=final_row):
                item = self.table.item(r, 5)
                if item:
                    item.setText("✓ OK" if ok else "✗ Ошибка")
                    item.setForeground(QColor(Colors.SUCCESS if ok else Colors.ERROR))
                    item.setToolTip(msg)
                if 0 <= r < len(self._accounts):
                    self._accounts[r].last_test_ok = ok
                    # FIX: автоматически деактивируем аккаунт при ошибке, активируем при успехе
                    self._accounts[r].is_active = ok
                    save_accounts(self._accounts)
                    active_item = self.table.item(r, 7)
                    if active_item:
                        active_item.setText("✓" if ok else "✗")
                        active_item.setForeground(QColor(Colors.SUCCESS if ok else Colors.ERROR))
                completed[0] += 1
                if completed[0] >= total:
                    self.test_all_btn.setEnabled(True)
                    self.test_all_btn.setText("Проверить все")
                    self.cancel_test_btn.setVisible(False)
                    ok_cnt = sum(
                        1 for i in range(self.table.rowCount())
                        if self.table.item(i, 5) and "✓" in (self.table.item(i, 5).text() or "")
                    )
                    self.status_label.setText(
                        f"Аккаунтов: {len(self._accounts)} | "
                        f"✓ {ok_cnt} рабочих | "
                        f"✗ {total - ok_cnt} с ошибками"
                    )
                    # Сортировка: валидные аккаунты наверх, невалидные вниз
                    self._accounts.sort(
                        key=lambda a: (0 if getattr(a, 'last_test_ok', None) is True else 1,
                                       a.email)
                    )
                    save_accounts(self._accounts)
                    self._refresh_table()


            w.result_ready.connect(on_result)
            self._test_workers.append(w)
            w.start()

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

        table = QTableWidget(len(proxies), 4)
        table.setHorizontalHeaderLabels(["Прокси", "Статус", "Страна", "Ошибка"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for i, p in enumerate(proxies):
            table.setItem(i, 0, QTableWidgetItem(p))
            item = QTableWidgetItem("⏳ Проверка...")
            item.setForeground(QColor(Colors.TEXT_MUTED))
            table.setItem(i, 1, item)
            table.setItem(i, 2, QTableWidgetItem(""))
            table.setItem(i, 3, QTableWidgetItem(""))
        lay.addWidget(table)

        btn_row = QHBoxLayout()
        use_btn = QPushButton("✓ Использовать валидные")
        use_btn.setObjectName("btn_primary")
        use_btn.setEnabled(False)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setObjectName("btn_secondary")
        btn_row.addWidget(use_btn)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        lay.addLayout(btn_row)

        valid_proxies = []
        worker = ProxyCheckWorker(proxies, dlg)

        def on_result(idx, valid, country, error):
            progress.setValue(idx + 1)
            s_item = table.item(idx, 1)
            c_item = table.item(idx, 2)
            e_item = table.item(idx, 3)
            if valid:
                s_item.setText("✓ OK")
                s_item.setForeground(QColor(Colors.SUCCESS))
                c_item.setText(country or "—")
                valid_proxies.append(proxies[idx])
            else:
                s_item.setText("✗ Ошибка")
                s_item.setForeground(QColor(Colors.ERROR))
                e_item.setText(error)

        def on_finished(valid_cnt, total):
            stat_lbl.setText(f"Готово: {valid_cnt}/{total} валидных")
            use_btn.setEnabled(valid_cnt > 0)

        def on_use():
            # Назначаем валидные прокси аккаунтам round-robin
            for i, acc in enumerate(self._accounts):
                acc.proxy = valid_proxies[i % len(valid_proxies)]
            save_accounts(self._accounts)
            self._refresh_table()
            self.accounts_changed.emit(self._accounts)
            dlg.accept()
            QMessageBox.information(
                self, "Прокси назначены",
                f"✓ {len(valid_proxies)} валидных прокси назначено {len(self._accounts)} аккаунтам."
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
        load_file_btn = QPushButton("📂 Загрузить из файла")
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
            # Назначаем без проверки round-robin
            for i, acc in enumerate(self._accounts):
                acc.proxy = valid_proxies[i % len(valid_proxies)]
            save_accounts(self._accounts)
            self._refresh_table()
            QMessageBox.information(
                self, "Прокси назначены",
                f"Назначено {len(valid_proxies)} прокси {len(self._accounts)} аккаунтам."
            )


    def _test_selected(self) -> None:
        """Проверить выбранные аккаунты (из таблицы)."""
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()})
        if not rows:
            QMessageBox.information(self, "Нет выбранных", "Выберите строки в таблице для проверки.")
            return
        for r in rows:
            self._test_single(r)

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
        self.status_label.setText(f"\u23f9 Проверка отменена | Аккаунтов: {len(self._accounts)}")

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
            self._accounts.extend(worker.new_accounts)
            save_accounts(self._accounts)
            self._refresh_table()
            self.accounts_changed.emit(self._accounts)
            QMessageBox.information(
                self, "Импорт завершён",
                f"Импортировано: {imported}\nПропущено: {errors}",
            )
            self._import_worker = None

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
