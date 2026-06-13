"""
Screen 2: SMTP Account Management.
Add, test, delete accounts. Passwords stored encrypted via Fernet.
Proxy support: socks5/socks4/http per-account or global.
"""
import asyncio
import json
import os
import platform
import re
import threading
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QSpinBox, QCheckBox, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QHeaderView, QDialog, QFormLayout,
    QMessageBox, QDialogButtonBox, QTextEdit, QFrame,
    QFileDialog, QProgressBar,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot, QSettings, QTimer
from PyQt6.QtGui import QColor

from core.license import get_storage_key
from core.sender import SmtpAccount, test_smtp_connection, get_smtp_config_for_domain
from gui.theme import Colors, Spacing


import random


class ProxyManager:
    """Менеджер прокси с ротацией: round_robin или random.

    Поддерживаемые форматы:
      socks5://user:pass@host:port
      socks4://host:port
      http://host:port
      https://user:pass@host:port
      host:port               -> socks5://host:port
      host:port:user:pass     -> socks5://user:pass@host:port
      user:pass:host:port     -> socks5://user:pass@host:port
    """

    def __init__(self, raw_list: list[str] | None = None, mode: str = "round_robin"):
        self._mode = mode  # "round_robin" | "random"
        self._index = 0
        import threading
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
        # Уже URL-формат
        if "://" in raw:
            return raw
        parts = raw.split(":")
        if len(parts) == 2:
            # host:port
            try:
                int(parts[1])
                return f"socks5://{parts[0]}:{parts[1]}"
            except ValueError:
                return None
        if len(parts) == 4:
            # Пробуем host:port:user:pass
            try:
                int(parts[1])
                return f"socks5://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
            except ValueError:
                pass
            # Пробуем user:pass:host:port
            try:
                int(parts[3])
                return f"socks5://{parts[0]}:{parts[1]}@{parts[2]}:{parts[3]}"
            except ValueError:
                pass
        return None

    def next_proxy(self) -> str | None:
        """Возвращает следующий прокси или None если список пуст."""
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


try:
    from cryptography.fernet import Fernet
    _HAS_FERNET = True
except ImportError:
    _HAS_FERNET = False


def _get_data_dir() -> Path:
    """Return a platform-appropriate data directory for FMailSender."""
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
        try:
            ok, msg = loop.run_until_complete(test_smtp_connection(self._account))
        finally:
            loop.close()
        self.result_ready.emit(ok, msg)


class AccountDialog(QDialog):
    def __init__(self, account: SmtpAccount | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить аккаунт" if account is None else "Редактировать аккаунт")
        self.setMinimumWidth(460)
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

        # Прокси: поддержка нескольких в формате одного на строку с ротацией
        self.proxy_edit = QTextEdit()
        self.proxy_edit.setPlaceholderText(
            "По одному прокси на строку. Форматы:\n"
            "  socks5://user:pass@host:port\n"
            "  http://host:port\n"
            "  host:port\n"
            "  host:port:user:pass"
        )
        self.proxy_edit.setFixedHeight(80)
        self.proxy_edit.setObjectName("proxy_list_edit")
        layout.addRow("Прокси:", self.proxy_edit)

        self.proxy_rotation_check = QCheckBox("Случайная ротация (иначе round-robin)")
        layout.addRow("", self.proxy_rotation_check)
        self.active_check = QCheckBox("Активен")
        self.active_check.setChecked(True)
        layout.addRow("", self.active_check)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

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
        self.proxy_edit.setPlainText("\n".join(getattr(acc, "proxy_list", []) or ([getattr(acc, "proxy", "")] if getattr(acc, "proxy", "") else [])))
        self.proxy_rotation_check.setChecked(getattr(acc, "proxy_rotation_random", False))

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
        raw_proxies = [l.strip() for l in self.proxy_edit.toPlainText().split("\n") if l.strip()]
        parsed = [ProxyManager.parse(p) for p in raw_proxies]
        parsed = [p for p in parsed if p]
        if parsed:
            acc.proxy_list = parsed
            # Для обратной совместимости первый прокси как acc.proxy
            acc.proxy = parsed[0]
        acc.proxy_rotation_random = self.proxy_rotation_check.isChecked()
        return acc



class BulkImportWorker(QThread):
    """Импорт SMTP-аккаунтов из файла в фоновом потоке — не блокирует UI."""
    progress = pyqtSignal(int, int)   # (текущий, всего)
    finished = pyqtSignal(int, int)   # (импортировано, пропущено)
    error    = pyqtSignal(str)

    def __init__(self, path: str, existing_emails: set, parent=None):
        super().__init__(parent)
        self._path = path
        self._existing = existing_emails
        self.new_accounts: list = []

    def run(self):
        try:
            lines = Path(self._path).read_text(encoding="utf-8", errors="replace").splitlines()
            total = len(lines)
            imported = errors = 0
            for idx, line in enumerate(lines):
                self.progress.emit(idx, total)
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = [p.strip() for p in re.split(r"[;:|\t]", line)]
                if len(parts) < 2:
                    errors += 1
                    continue
                email, password = parts[0], parts[1]
                if "@" not in email or email.lower() in self._existing:
                    errors += 1
                    continue
                domain = email.split("@")[-1].lower()
                cfg = get_smtp_config_for_domain(domain)
                if not cfg:
                    errors += 1
                    continue
                acc = SmtpAccount(
                    email=email,
                    password=password,
                    host=cfg["host"],
                    port=cfg["port"],
                    use_ssl=cfg.get("use_ssl", True),
                    use_tls=cfg.get("use_tls", False),
                )
                self.new_accounts.append(acc)
                self._existing.add(email.lower())
                imported += 1
            self.finished.emit(imported, errors)
        except Exception as e:
            self.error.emit(str(e))


class AccountsScreen(QWidget):
    accounts_changed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._accounts: list[SmtpAccount] = []
        self._test_workers: list[TestWorker] = []
        self._setup_ui()
        self._load()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        layout.setSpacing(Spacing.LG)

        title = QLabel("SMTP-аккаунты")
        title.setObjectName("section_header")
        layout.addWidget(title)

        toolbar = QHBoxLayout()

        add_btn = QPushButton("+ Добавить аккаунт")
        add_btn.setObjectName("btn_primary")
        add_btn.clicked.connect(self._add_account)
        toolbar.addWidget(add_btn)

        import_btn = QPushButton("Импорт (.txt)")
        import_btn.setObjectName("btn_icon")
        import_btn.clicked.connect(self._import_accounts)
        toolbar.addWidget(import_btn)

        toolbar.addStretch()

        self.test_all_btn = QPushButton("Проверить все")
        self.test_all_btn.setObjectName("btn_icon")
        self.test_all_btn.clicked.connect(self._test_all)
        toolbar.addWidget(self.test_all_btn)

        del_btn = QPushButton("Удалить выбранный")
        del_btn.setObjectName("btn_danger")
        del_btn.clicked.connect(self._delete_selected)
        toolbar.addWidget(del_btn)
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Email", "Хост", "Порт", "Дн. лимит", "Ч. лимит", "Статус", "Активен",
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.doubleClicked.connect(self._edit_account)
        layout.addWidget(self.table)

        self.status_label = QLabel("Аккаунтов: 0")
        self.status_label.setObjectName("label_muted")
        layout.addWidget(self.status_label)

    def get_accounts(self) -> list:
        """Return currently loaded list of SmtpAccount objects."""
        return self._accounts

    def _load(self):
        self._accounts = load_accounts()
        self._refresh_table()
        self.accounts_changed.emit(self._accounts)

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
            status_item = QTableWidgetItem("—")
            self.table.setItem(row, 5, status_item)
            active_item = QTableWidgetItem("\u2713" if acc.is_active else "\u2717")
            active_item.setForeground(
                QColor(Colors.SUCCESS) if acc.is_active else QColor(Colors.ERROR)
            )
            self.table.setItem(row, 6, active_item)
        active_count = sum(1 for a in self._accounts if a.is_active)
        self.status_label.setText(f"Аккаунтов: {len(self._accounts)} (активных: {active_count})")

    def _add_account(self):
        dlg = AccountDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            acc = dlg.get_account()
            self._accounts.append(acc)
            save_accounts(self._accounts)
            self._refresh_table()
            self.accounts_changed.emit(self._accounts)

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

    def _test_all(self):
        self.test_all_btn.setEnabled(False)
        for row, acc in enumerate(self._accounts):
            self.table.item(row, 5).setText("Проверка...")
            w = TestWorker(acc, parent=self)
            final_row = row

            @pyqtSlot(bool, str)
            def on_result(ok, msg, r=final_row):
                item = self.table.item(r, 5)
                if item:
                    item.setText("\u2713 OK" if ok else "\u2717 Ошибка")
                    item.setForeground(QColor(Colors.SUCCESS if ok else Colors.ERROR))
                done = all(
                    self.table.item(i, 5) and
                    self.table.item(i, 5).text() not in ("—", "Проверка...")
                    for i in range(self.table.rowCount())
                )
                if done:
                    self.test_all_btn.setEnabled(True)

            w.result_ready.connect(on_result)
            self._test_workers.append(w)
            w.start()

    def _import_accounts(self):
          path, _ = QFileDialog.getOpenFileName(
              self, "Импорт аккаунтов", "", "Text files (*.txt);;All files (*)"
          )
          if not path:
              return

          existing = {a.email.lower() for a in self._accounts}
          worker = BulkImportWorker(path, existing, self)

          from PyQt6.QtWidgets import QProgressDialog
          progress_dlg = QProgressDialog(
              "Импорт аккаунтов...", "Отмена", 0, 100, self
          )
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
                  f"Импортировано: {imported}\nПропущено (дубли/неизвестный домен): {errors}",
              )
              self._import_worker = None

          def on_error(msg):
              progress_dlg.close()
              QMessageBox.critical(self, "Ошибка импорта", msg)
              self._import_worker = None

          worker.progress.connect(on_progress)
          worker.finished.connect(on_finished)
          worker.error.connect(on_error)
          progress_dlg.canceled.connect(worker.terminate)
          self._import_worker = worker
          worker.start()
