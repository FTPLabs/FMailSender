"""
Экран 2: SMTP-аккаунты.
Таблица аккаунтов, добавление/редактирование, тест подключения, ротация.
"""
import asyncio
import json
import threading
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QFormLayout, QLineEdit, QComboBox, QSpinBox, QCheckBox,
    QFrame, QMessageBox, QProgressDialog, QTextEdit
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor

from core.sender import SmtpAccount, test_smtp_connection, get_smtp_config_for_domain
from gui.theme import Colors, Spacing

ACCOUNTS_FILE = Path("data/accounts.json")


def _load_accounts() -> list[SmtpAccount]:
    if ACCOUNTS_FILE.exists():
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            accounts = []
            for d in raw:
                a = SmtpAccount(
                    email=d["email"],
                    password=d["password"],
                    host=d["host"],
                    port=d["port"],
                    use_ssl=d.get("use_ssl", True),
                    use_tls=d.get("use_tls", False),
                    display_name=d.get("display_name", ""),
                    daily_limit=d.get("daily_limit", 500),
                    hourly_limit=d.get("hourly_limit", 50),
                    warmup_day=d.get("warmup_day", 0),
                )
                accounts.append(a)
            return accounts
        except Exception:
            pass
    return []


def _save_accounts(accounts: list[SmtpAccount]) -> None:
    ACCOUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = []
    for a in accounts:
        data.append({
            "email": a.email,
            "password": a.password,
            "host": a.host,
            "port": a.port,
            "use_ssl": a.use_ssl,
            "use_tls": a.use_tls,
            "display_name": a.display_name,
            "daily_limit": a.daily_limit,
            "hourly_limit": a.hourly_limit,
            "warmup_day": a.warmup_day,
        })
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class AddAccountDialog(QDialog):
    """Диалог добавления/редактирования SMTP-аккаунта."""

    def __init__(self, account: SmtpAccount = None, parent=None):
        super().__init__(parent)
        self._account = account
        self.setWindowTitle("Добавить SMTP-аккаунт" if not account else "Редактировать аккаунт")
        self.setMinimumWidth(480)
        self.setModal(True)
        self._setup_ui()
        if account:
            self._fill_from_account(account)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(Spacing.LG)
        layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)

        # Провайдер (быстрый выбор)
        provider_row = QHBoxLayout()
        provider_label = QLabel("Провайдер:")
        provider_label.setFixedWidth(120)
        provider_row.addWidget(provider_label)

        self.provider_combo = QComboBox()
        self.provider_combo.addItems([
            "Custom SMTP", "Gmail", "Outlook/Hotmail", "Yahoo Mail",
            "Mail.ru", "Yandex", "iCloud"
        ])
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        provider_row.addWidget(self.provider_combo)
        layout.addLayout(provider_row)

        # Форма
        form = QFormLayout()
        form.setSpacing(Spacing.MD)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.display_name_input = QLineEdit()
        self.display_name_input.setPlaceholderText("Иван Иванов (необязательно)")
        form.addRow("Имя отправителя:", self.display_name_input)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("your@email.com")
        self.email_input.textChanged.connect(self._on_email_changed)
        form.addRow("Email:", self.email_input)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Пароль или App Password")
        form.addRow("Пароль:", self.password_input)

        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("smtp.example.com")
        form.addRow("SMTP Host:", self.host_input)

        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(465)
        form.addRow("Порт:", self.port_input)

        self.ssl_check = QCheckBox("SSL/TLS (порт 465)")
        self.ssl_check.setChecked(True)
        form.addRow("", self.ssl_check)

        self.starttls_check = QCheckBox("STARTTLS (порт 587)")
        form.addRow("", self.starttls_check)

        self.daily_limit_input = QSpinBox()
        self.daily_limit_input.setRange(1, 10000)
        self.daily_limit_input.setValue(500)
        form.addRow("Лимит в день:", self.daily_limit_input)

        self.hourly_limit_input = QSpinBox()
        self.hourly_limit_input.setRange(1, 1000)
        self.hourly_limit_input.setValue(50)
        form.addRow("Лимит в час:", self.hourly_limit_input)

        layout.addLayout(form)

        # Лог тестирования
        self.test_log = QTextEdit()
        self.test_log.setReadOnly(True)
        self.test_log.setMaximumHeight(120)
        self.test_log.setPlaceholderText("Нажмите 'Тест' для проверки подключения...")
        layout.addWidget(self.test_log)

        # Кнопки
        btn_row = QHBoxLayout()
        btn_row.setSpacing(Spacing.SM)

        self.test_btn = QPushButton("Тест подключения")
        self.test_btn.clicked.connect(self._test_connection)
        btn_row.addWidget(self.test_btn)
        btn_row.addStretch()

        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self.save_btn = QPushButton("Сохранить")
        self.save_btn.setObjectName("btn_primary")
        self.save_btn.clicked.connect(self._save)
        btn_row.addWidget(self.save_btn)

        layout.addLayout(btn_row)

    def _on_email_changed(self, text: str):
        """Автоопределение настроек по домену."""
        if "@" in text:
            domain = text.split("@")[-1].lower().strip()
            cfg = get_smtp_config_for_domain(domain)
            if cfg:
                self.host_input.setText(cfg.get("host", ""))
                self.port_input.setValue(cfg.get("port", 465))
                self.ssl_check.setChecked(cfg.get("use_ssl", True))
                self.starttls_check.setChecked(cfg.get("use_tls", False))
                self.provider_combo.setCurrentText(self._domain_to_provider(domain))

    def _domain_to_provider(self, domain: str) -> str:
        mapping = {
            "gmail.com": "Gmail",
            "googlemail.com": "Gmail",
            "outlook.com": "Outlook/Hotmail",
            "hotmail.com": "Outlook/Hotmail",
            "live.com": "Outlook/Hotmail",
            "yahoo.com": "Yahoo Mail",
            "mail.ru": "Mail.ru",
            "yandex.ru": "Yandex",
            "yandex.com": "Yandex",
            "icloud.com": "iCloud",
        }
        return mapping.get(domain, "Custom SMTP")

    def _on_provider_changed(self, provider: str):
        configs = {
            "Gmail": ("smtp.gmail.com", 465, True, False),
            "Outlook/Hotmail": ("smtp.office365.com", 587, False, True),
            "Yahoo Mail": ("smtp.mail.yahoo.com", 465, True, False),
            "Mail.ru": ("smtp.mail.ru", 465, True, False),
            "Yandex": ("smtp.yandex.ru", 465, True, False),
            "iCloud": ("smtp.mail.me.com", 587, False, True),
        }
        if provider in configs:
            host, port, ssl, tls = configs[provider]
            self.host_input.setText(host)
            self.port_input.setValue(port)
            self.ssl_check.setChecked(ssl)
            self.starttls_check.setChecked(tls)

    def _fill_from_account(self, a: SmtpAccount):
        self.email_input.setText(a.email)
        self.password_input.setText(a.password)
        self.host_input.setText(a.host)
        self.port_input.setValue(a.port)
        self.ssl_check.setChecked(a.use_ssl)
        self.starttls_check.setChecked(a.use_tls)
        self.display_name_input.setText(a.display_name)
        self.daily_limit_input.setValue(a.daily_limit)
        self.hourly_limit_input.setValue(a.hourly_limit)

    def _test_connection(self):
        self.test_btn.setEnabled(False)
        self.test_log.setText("Тестирование подключения...")

        account = self._build_account()
        if not account:
            self.test_log.setText("Заполните все обязательные поля")
            self.test_btn.setEnabled(True)
            return

        def run():
            loop = asyncio.new_event_loop()
            success, log = loop.run_until_complete(test_smtp_connection(account))
            loop.close()

            def update():
                self.test_log.setText(log)
                if success:
                    self.test_log.setStyleSheet(f"color: {Colors.SUCCESS};")
                else:
                    self.test_log.setStyleSheet(f"color: {Colors.ERROR};")
                self.test_btn.setEnabled(True)

            QTimer.singleShot(0, update)

        threading.Thread(target=run, daemon=True).start()

    def _build_account(self) -> SmtpAccount | None:
        email = self.email_input.text().strip()
        password = self.password_input.text()
        host = self.host_input.text().strip()
        if not email or not password or not host:
            return None
        return SmtpAccount(
            email=email,
            password=password,
            host=host,
            port=self.port_input.value(),
            use_ssl=self.ssl_check.isChecked(),
            use_tls=self.starttls_check.isChecked(),
            display_name=self.display_name_input.text().strip(),
            daily_limit=self.daily_limit_input.value(),
            hourly_limit=self.hourly_limit_input.value(),
        )

    def _save(self):
        account = self._build_account()
        if not account:
            QMessageBox.warning(self, "Ошибка", "Заполните обязательные поля: Email, Пароль, Host")
            return
        self._result_account = account
        self.accept()

    def get_account(self) -> SmtpAccount | None:
        return getattr(self, "_result_account", None)


class AccountsScreen(QWidget):
    """Экран управления SMTP-аккаунтами."""

    accounts_changed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._accounts: list[SmtpAccount] = _load_accounts()
        self._setup_ui()
        self._refresh_table()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        layout.setSpacing(Spacing.LG)

        # ── Заголовок и кнопки ───────────────────
        header_row = QHBoxLayout()
        title = QLabel("SMTP-аккаунты")
        title.setObjectName("section_header")
        header_row.addWidget(title)
        header_row.addStretch()

        self.rotation_combo = QComboBox()
        self.rotation_combo.addItems(["Ротация: round-robin", "Ротация: random", "Ротация: weighted"])
        self.rotation_combo.setFixedWidth(200)
        header_row.addWidget(self.rotation_combo)

        add_btn = QPushButton("+ Добавить аккаунт")
        add_btn.setObjectName("btn_primary")
        add_btn.clicked.connect(self._add_account)
        header_row.addWidget(add_btn)

        layout.addLayout(header_row)

        # ── Таблица аккаунтов ────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Email", "Провайдер", "Статус", "Warm-up",
            "Лимит/день", "Отправлено", "Действия"
        ])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        # ── Нижняя панель ─────────────────────────
        bottom_row = QHBoxLayout()
        self.count_label = QLabel(f"Аккаунтов: 0")
        self.count_label.setObjectName("label_muted")
        bottom_row.addWidget(self.count_label)
        bottom_row.addStretch()

        import_btn = QPushButton("Импорт из CSV")
        import_btn.clicked.connect(self._import_csv)
        bottom_row.addWidget(import_btn)

        layout.addLayout(bottom_row)

    def _refresh_table(self):
        self.table.setRowCount(len(self._accounts))
        for row, acc in enumerate(self._accounts):
            self.table.setItem(row, 0, QTableWidgetItem(acc.email))

            # Провайдер (определяем по хосту)
            domain = acc.email.split("@")[-1] if "@" in acc.email else ""
            provider_map = {
                "gmail.com": "Gmail", "googlemail.com": "Gmail",
                "outlook.com": "Outlook", "hotmail.com": "Outlook",
                "yahoo.com": "Yahoo", "mail.ru": "Mail.ru",
                "yandex.ru": "Yandex", "yandex.com": "Yandex",
            }
            provider = provider_map.get(domain, "Custom")
            self.table.setItem(row, 1, QTableWidgetItem(provider))

            # Статус
            status_item = QTableWidgetItem("● Активен" if acc.is_active else "● Неактивен")
            status_item.setForeground(
                QColor(Colors.SUCCESS) if acc.is_active else QColor(Colors.ERROR)
            )
            self.table.setItem(row, 2, status_item)

            # Warm-up day
            warmup_text = f"День {acc.warmup_day}" if acc.warmup_day > 0 else "Не запущен"
            self.table.setItem(row, 3, QTableWidgetItem(warmup_text))

            self.table.setItem(row, 4, QTableWidgetItem(str(acc.daily_limit)))
            self.table.setItem(row, 5, QTableWidgetItem(str(acc.sent_today)))

            # Кнопки действий
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(4)

            edit_btn = QPushButton("Изменить")
            edit_btn.setFixedHeight(26)
            edit_btn.clicked.connect(lambda _, r=row: self._edit_account(r))
            actions_layout.addWidget(edit_btn)

            del_btn = QPushButton("Удалить")
            del_btn.setObjectName("btn_danger")
            del_btn.setFixedHeight(26)
            del_btn.clicked.connect(lambda _, r=row: self._delete_account(r))
            actions_layout.addWidget(del_btn)

            self.table.setCellWidget(row, 6, actions_widget)
            self.table.setRowHeight(row, 46)

        self.count_label.setText(f"Аккаунтов: {len(self._accounts)} | "
                                  f"Активных: {sum(1 for a in self._accounts if a.is_active)}")

    def _add_account(self):
        dialog = AddAccountDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            account = dialog.get_account()
            if account:
                self._accounts.append(account)
                _save_accounts(self._accounts)
                self._refresh_table()
                self.accounts_changed.emit(self._accounts)

    def _edit_account(self, row: int):
        account = self._accounts[row]
        dialog = AddAccountDialog(account=account, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated = dialog.get_account()
            if updated:
                self._accounts[row] = updated
                _save_accounts(self._accounts)
                self._refresh_table()
                self.accounts_changed.emit(self._accounts)

    def _delete_account(self, row: int):
        email = self._accounts[row].email
        reply = QMessageBox.question(
            self, "Удалить аккаунт",
            f"Удалить аккаунт {email}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._accounts.pop(row)
            _save_accounts(self._accounts)
            self._refresh_table()
            self.accounts_changed.emit(self._accounts)

    def _import_csv(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Импорт аккаунтов из CSV", "", "CSV files (*.csv)"
        )
        if path:
            try:
                import csv
                with open(path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    imported = 0
                    for row in reader:
                        if "email" in row and "password" in row:
                            domain = row["email"].split("@")[-1]
                            cfg = get_smtp_config_for_domain(domain) or {}
                            acc = SmtpAccount(
                                email=row["email"],
                                password=row["password"],
                                host=row.get("host", cfg.get("host", "")),
                                port=int(row.get("port", cfg.get("port", 465))),
                                use_ssl=row.get("use_ssl", str(cfg.get("use_ssl", True))).lower() == "true",
                                display_name=row.get("display_name", ""),
                                daily_limit=int(row.get("daily_limit", 500)),
                            )
                            if acc.host:
                                self._accounts.append(acc)
                                imported += 1
                _save_accounts(self._accounts)
                self._refresh_table()
                self.accounts_changed.emit(self._accounts)
                QMessageBox.information(self, "Импорт", f"Импортировано {imported} аккаунтов")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка импорта", str(e))

    def get_accounts(self) -> list[SmtpAccount]:
        return self._accounts

    def get_rotation_mode(self) -> str:
        text = self.rotation_combo.currentText()
        if "random" in text:
            return "random"
        elif "weighted" in text:
            return "weighted"
        return "round-robin"
