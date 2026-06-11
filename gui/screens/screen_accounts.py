"""
Screen 2: SMTP Account Management.
Add, test, delete accounts. Passwords stored encrypted via Fernet.
"""
import asyncio
import json
import os
from pathlib import Path
from PyQt6.QtWidgets import (
  QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
  QLineEdit, QComboBox, QSpinBox, QCheckBox, QTableWidget,
  QTableWidgetItem, QHeaderView, QDialog, QFormLayout,
  QMessageBox, QDialogButtonBox, QTextEdit, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QColor

from core.license import get_storage_key
from core.sender import SmtpAccount, test_smtp_connection, get_smtp_config_for_domain
from gui.theme import Colors, Spacing

try:
  from cryptography.fernet import Fernet
  _HAS_FERNET = True
except ImportError:
  _HAS_FERNET = False


ACCOUNTS_FILE = Path(os.environ.get("APPDATA", ".")) / "EmailSenderPro" / "accounts.dat"


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
      data.append({
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
      })
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
          result.append(SmtpAccount(
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
          ))
      return result
  except Exception:
      return []


class AccountDialog(QDialog):
  _test_done = pyqtSignal(bool, str)  # thread-safe: success, log

  def __init__(self, parent=None, account: SmtpAccount = None):
      super().__init__(parent)
      self.setWindowTitle("Добавить аккаунт" if not account else "Редактировать аккаунт")
      self.setMinimumWidth(460)
      self._editing = account
      self._setup_ui()
      self._test_done.connect(self._on_test_done)
      if account:
          self._fill(account)

  def _setup_ui(self):
      layout = QVBoxLayout(self)
      layout.setSpacing(Spacing.LG)
      layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)

      form = QFormLayout()
      form.setSpacing(Spacing.MD)

      self.email_input = QLineEdit()
      self.email_input.setPlaceholderText("user@example.com")
      self.email_input.textChanged.connect(self._on_email_changed)
      form.addRow("Email:", self.email_input)

      self.password_input = QLineEdit()
      self.password_input.setPlaceholderText("Пароль или App Password")
      self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
      form.addRow("Пароль:", self.password_input)

      self.display_name_input = QLineEdit()
      self.display_name_input.setPlaceholderText("Имя отправителя (необязательно)")
      form.addRow("Имя:", self.display_name_input)

      host_row = QHBoxLayout()
      self.host_input = QLineEdit()
      self.host_input.setPlaceholderText("smtp.gmail.com")
      host_row.addWidget(self.host_input)
      self.port_spin = QSpinBox()
      self.port_spin.setRange(1, 65535)
      self.port_spin.setValue(465)
      self.port_spin.setFixedWidth(80)
      host_row.addWidget(QLabel("Порт:"))
      host_row.addWidget(self.port_spin)
      form.addRow("SMTP сервер:", host_row)

      ssl_row = QHBoxLayout()
      self.ssl_check = QCheckBox("SSL (порт 465)")
      self.ssl_check.setChecked(True)
      ssl_row.addWidget(self.ssl_check)
      self.tls_check = QCheckBox("STARTTLS (порт 587)")
      ssl_row.addWidget(self.tls_check)
      ssl_row.addStretch()
      form.addRow("Шифрование:", ssl_row)

      limits_row = QHBoxLayout()
      self.daily_spin = QSpinBox()
      self.daily_spin.setRange(1, 100000)
      self.daily_spin.setValue(500)
      self.daily_spin.setSuffix("/день")
      limits_row.addWidget(self.daily_spin)
      self.hourly_spin = QSpinBox()
      self.hourly_spin.setRange(1, 10000)
      self.hourly_spin.setValue(50)
      self.hourly_spin.setSuffix("/час")
      limits_row.addWidget(self.hourly_spin)
      form.addRow("Лимиты:", limits_row)

      layout.addLayout(form)

      test_btn = QPushButton("Проверить подключение")
      test_btn.setObjectName("btn_icon")
      test_btn.clicked.connect(self._test_connection)
      layout.addWidget(test_btn)

      self.test_result = QTextEdit()
      self.test_result.setReadOnly(True)
      self.test_result.setMaximumHeight(80)
      self.test_result.setPlaceholderText("Результат проверки...")
      layout.addWidget(self.test_result)

      buttons = QDialogButtonBox(
          QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
      )
      buttons.accepted.connect(self.accept)
      buttons.rejected.connect(self.reject)
      layout.addWidget(buttons)

  def _on_email_changed(self, email: str):
      if "@" in email:
          domain = email.split("@")[1].lower()
          config = get_smtp_config_for_domain(domain)
          if config:
              self.host_input.setText(config["host"])
              self.port_spin.setValue(config["port"])
              self.ssl_check.setChecked(config.get("use_ssl", False))
              self.tls_check.setChecked(config.get("use_tls", False))

  def _fill(self, account: SmtpAccount):
      self.email_input.setText(account.email)
      self.password_input.setText(account.password)
      self.display_name_input.setText(account.display_name)
      self.host_input.setText(account.host)
      self.port_spin.setValue(account.port)
      self.ssl_check.setChecked(account.use_ssl)
      self.tls_check.setChecked(account.use_tls)
      self.daily_spin.setValue(account.daily_limit)
      self.hourly_spin.setValue(account.hourly_limit)

  def _test_connection(self):
      account = self.get_account()
      if not account:
          return
      self.test_result.setPlainText("Подключение...")

      async def run():
          return await test_smtp_connection(account)

      import threading

      def do():
          import asyncio
          loop = asyncio.new_event_loop()
          success, log = loop.run_until_complete(run())
          loop.close()
          self._test_done.emit(success, log)  # безопасная передача в GUI-поток

      threading.Thread(target=do, daemon=True).start()

  def _on_test_done(self, success: bool, log: str) -> None:
      """Вызывается в GUI-потоке через сигнал."""
      color = Colors.SUCCESS if success else Colors.ERROR
      self.test_result.setStyleSheet(f"color:{color};")
      self.test_result.setPlainText(log)

  def get_account(self) -> SmtpAccount | None:
      email = self.email_input.text().strip()
      password = self.password_input.text()
      host = self.host_input.text().strip()
      if not email or not password or not host:
          return None
      return SmtpAccount(
          email=email,
          password=password,
          host=host,
          port=self.port_spin.value(),
          use_ssl=self.ssl_check.isChecked(),
          use_tls=self.tls_check.isChecked(),
          display_name=self.display_name_input.text().strip(),
          daily_limit=self.daily_spin.value(),
          hourly_limit=self.hourly_spin.value(),
      )


class AccountsScreen(QWidget):
  accounts_changed = pyqtSignal(list)

  def __init__(self, parent=None):
      super().__init__(parent)
      self._accounts: list[SmtpAccount] = load_accounts()
      self._setup_ui()
      self._refresh_table()

  def _setup_ui(self):
      layout = QVBoxLayout(self)
      layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
      layout.setSpacing(Spacing.LG)

      header_row = QHBoxLayout()
      title = QLabel("SMTP Аккаунты")
      title.setObjectName("section_header")
      header_row.addWidget(title)
      header_row.addStretch()
      add_btn = QPushButton("+ Добавить аккаунт")
      add_btn.setObjectName("btn_primary")
      add_btn.clicked.connect(self._add_account)
      header_row.addWidget(add_btn)
      layout.addLayout(header_row)

      stats_card = QFrame()
      stats_card.setObjectName("card")
      stats_layout = QHBoxLayout(stats_card)
      self.stats_label = QLabel("Аккаунтов: 0 | Активных: 0")
      self.stats_label.setObjectName("label_muted")
      stats_layout.addWidget(self.stats_label)
      stats_layout.addStretch()
      layout.addWidget(stats_card)

      self.table = QTableWidget()
      self.table.setColumnCount(7)
      self.table.setHorizontalHeaderLabels([
          "Email", "SMTP Сервер", "Порт", "Шифр.",
          "Лимит/день", "Лимит/час", "Статус"
      ])
      self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
      self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
      self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
      self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
      self.table.setAlternatingRowColors(True)
      layout.addWidget(self.table, 1)

      actions_row = QHBoxLayout()
      edit_btn = QPushButton("Редактировать")
      edit_btn.clicked.connect(self._edit_selected)
      actions_row.addWidget(edit_btn)
      test_btn = QPushButton("Проверить подключение")
      test_btn.clicked.connect(self._test_selected)
      actions_row.addWidget(test_btn)
      toggle_btn = QPushButton("Вкл/Выкл")
      toggle_btn.clicked.connect(self._toggle_selected)
      actions_row.addWidget(toggle_btn)
      del_btn = QPushButton("Удалить")
      del_btn.setObjectName("btn_danger")
      del_btn.clicked.connect(self._delete_selected)
      actions_row.addWidget(del_btn)
      actions_row.addStretch()
      layout.addLayout(actions_row)

  def _refresh_table(self):
      self.table.setRowCount(len(self._accounts))
      for i, acc in enumerate(self._accounts):
          self.table.setItem(i, 0, QTableWidgetItem(acc.email))
          self.table.setItem(i, 1, QTableWidgetItem(acc.host))
          self.table.setItem(i, 2, QTableWidgetItem(str(acc.port)))
          enc = "SSL" if acc.use_ssl else ("TLS" if acc.use_tls else "Нет")
          self.table.setItem(i, 3, QTableWidgetItem(enc))
          self.table.setItem(i, 4, QTableWidgetItem(str(acc.daily_limit)))
          self.table.setItem(i, 5, QTableWidgetItem(str(acc.hourly_limit)))
          status_item = QTableWidgetItem("Активен" if acc.is_active else "Отключён")
          status_item.setForeground(
              QColor(Colors.SUCCESS) if acc.is_active else QColor(Colors.TEXT_MUTED)
          )
          self.table.setItem(i, 6, status_item)
      active = sum(1 for a in self._accounts if a.is_active)
      self.stats_label.setText(f"Аккаунтов: {len(self._accounts)} | Активных: {active}")
      self.accounts_changed.emit(self._accounts)

  def _add_account(self):
      dlg = AccountDialog(self)
      if dlg.exec() == QDialog.DialogCode.Accepted:
          acc = dlg.get_account()
          if acc:
              self._accounts.append(acc)
              save_accounts(self._accounts)
              self._refresh_table()

  def _edit_selected(self):
      row = self.table.currentRow()
      if row < 0:
          return
      dlg = AccountDialog(self, self._accounts[row])
      if dlg.exec() == QDialog.DialogCode.Accepted:
          acc = dlg.get_account()
          if acc:
              self._accounts[row] = acc
              save_accounts(self._accounts)
              self._refresh_table()

  def _test_selected(self):
      row = self.table.currentRow()
      if row < 0:
          QMessageBox.information(self, "Тест", "Выберите аккаунт из таблицы")
          return
      acc = self._accounts[row]
      QMessageBox.information(self, "Тест", f"Проверка {acc.email}...")
      import threading
      def do():
          import asyncio
          loop = asyncio.new_event_loop()
          success, log = loop.run_until_complete(test_smtp_connection(acc))
          loop.close()
          status = "OK" if success else "ОШИБКА"
          QMessageBox.information(self, f"Тест — {status}", log)
      threading.Thread(target=do, daemon=True).start()

  def _toggle_selected(self):
      row = self.table.currentRow()
      if row < 0:
          return
      self._accounts[row].is_active = not self._accounts[row].is_active
      save_accounts(self._accounts)
      self._refresh_table()

  def _delete_selected(self):
      row = self.table.currentRow()
      if row < 0:
          return
      reply = QMessageBox.question(
          self, "Удалить?",
          f"Удалить аккаунт {self._accounts[row].email}?",
          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
      )
      if reply == QMessageBox.StandardButton.Yes:
          self._accounts.pop(row)
          save_accounts(self._accounts)
          self._refresh_table()
