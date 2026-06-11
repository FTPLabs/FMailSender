"""
Screen 2: SMTP Account Management.
Add, test, delete accounts. Passwords stored encrypted via Fernet.
Proxy support: socks5/socks4/http per-account or global.
"""
import asyncio
import json
import os
import re
import threading
from pathlib import Path
from PyQt6.QtWidgets import (
  QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
  QLineEdit, QComboBox, QSpinBox, QCheckBox, QTableWidget,
  QTableWidgetItem, QHeaderView, QDialog, QFormLayout,
  QMessageBox, QDialogButtonBox, QTextEdit, QFrame,
  QFileDialog, QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot, QSettings, QTimer
from PyQt6.QtGui import QColor

from core.license import get_storage_key
from core.sender import SmtpAccount, test_smtp_connection, get_smtp_config_for_domain
from gui.theme import Colors, Spacing

try:
  from cryptography.fernet import Fernet
  _HAS_FERNET = True
except ImportError:
  _HAS_FERNET = False


# FIX: unified data folder — was "EmailSenderPro", now "FMailSender" to match license.py path
ACCOUNTS_FILE = Path(os.environ.get("APPDATA", ".")) / "FMailSender" / "accounts.dat"

# ──────────────────────────────────────────────
# Encryption helpers
# ──────────────────────────────────────────────

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


# ──────────────────────────────────────────────
# Persistence
# ──────────────────────────────────────────────

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
      # Save proxy if present
      if hasattr(a, "proxy") and a.proxy:
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
          if "proxy" in d:
              acc.proxy = d["proxy"]
          result.append(acc)
      return result
  except Exception:
      return []


# ──────────────────────────────────────────────
# File parser (email:pass lists)
# ──────────────────────────────────────────────

# FIX: regex was truncated — now properly closed with $ and flags
_EMAIL_RE = re.compile(r'^[^@]+@[^@]+\.[^@]+$', re.IGNORECASE)


def _parse_accounts_file(text: str) -> list[dict]:
  """Parse accounts file. Supported formats:
  email:password
  email;password
  email|password
  email,password
  email:password:host:port
  email:password:host:port:ssl  (ssl=true/false/1/0)
  email:password:host:port:ssl:proxy  (proxy=socks5://user:pass@host:port)
  """
  results = []
  seen: set[str] = set()
  for raw_line in text.splitlines():
      line = raw_line.strip()
      if not line or line.startswith('#'):
          continue
      parts = None
      for sep in [':', ';', '|', ',']:
          if sep in line:
              # FIX: maxsplit=5 preserves passwords containing the separator char
              parts = line.split(sep, 5)
              break
      if not parts or len(parts) < 2:
          continue
      email = parts[0].strip().lower()
      password = parts[1].strip()
      # Validate email with fixed regex
      if not _EMAIL_RE.match(email):
          continue
      if email in seen:
          continue
      seen.add(email)
      host_override = parts[2].strip() if len(parts) > 2 else ""
      port_override = int(parts[3]) if len(parts) > 3 and parts[3].strip().isdigit() else 0
      ssl_override = None
      if len(parts) > 4:
          v = parts[4].strip().lower()
          ssl_override = v in ('true', '1', 'ssl', 'yes')
      proxy_override = parts[5].strip() if len(parts) > 5 else ""
      results.append({
          "email": email,
          "password": password,
          "host_override": host_override,
          "port_override": port_override,
          "ssl_override": ssl_override,
          "proxy_override": proxy_override,
      })
  return results


# ──────────────────────────────────────────────
# Single account dialog
# ──────────────────────────────────────────────

class AccountDialog(QDialog):
  _test_done = pyqtSignal(bool, str)  # thread-safe: success, log

  def __init__(self, parent=None, account: SmtpAccount = None):
      super().__init__(parent)
      self.setWindowTitle("Добавить аккаунт" if not account else "Редактировать аккаунт")
      self.setMinimumWidth(500)
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

      # ── Proxy section ──────────────────────────────
      proxy_row = QHBoxLayout()
      self.proxy_type_combo = QComboBox()
      self.proxy_type_combo.addItems(["Без прокси", "SOCKS5", "SOCKS4", "HTTP"])
      self.proxy_type_combo.setFixedWidth(110)
      self.proxy_type_combo.currentIndexChanged.connect(self._on_proxy_type_changed)
      proxy_row.addWidget(self.proxy_type_combo)
      self.proxy_host_input = QLineEdit()
      self.proxy_host_input.setPlaceholderText("хост прокси")
      self.proxy_host_input.setEnabled(False)
      proxy_row.addWidget(self.proxy_host_input)
      self.proxy_port_spin = QSpinBox()
      self.proxy_port_spin.setRange(1, 65535)
      self.proxy_port_spin.setValue(1080)
      self.proxy_port_spin.setFixedWidth(75)
      self.proxy_port_spin.setEnabled(False)
      proxy_row.addWidget(self.proxy_port_spin)
      self.proxy_user_input = QLineEdit()
      self.proxy_user_input.setPlaceholderText("логин (необяз.)")
      self.proxy_user_input.setEnabled(False)
      proxy_row.addWidget(self.proxy_user_input)
      self.proxy_pass_input = QLineEdit()
      self.proxy_pass_input.setPlaceholderText("пароль (необяз.)")
      self.proxy_pass_input.setEchoMode(QLineEdit.EchoMode.Password)
      self.proxy_pass_input.setEnabled(False)
      proxy_row.addWidget(self.proxy_pass_input)
      form.addRow("Прокси:", proxy_row)

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

  def _on_proxy_type_changed(self, idx: int):
      enabled = idx > 0
      self.proxy_host_input.setEnabled(enabled)
      self.proxy_port_spin.setEnabled(enabled)
      self.proxy_user_input.setEnabled(enabled)
      self.proxy_pass_input.setEnabled(enabled)

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
      # Fill proxy if present
      proxy = getattr(account, "proxy", "") or ""
      if proxy:
          self._fill_proxy_from_url(proxy)

  def _fill_proxy_from_url(self, proxy_url: str):
      """Parse proxy URL like socks5://user:pass@host:port into UI fields."""
      import urllib.parse
      try:
          parsed = urllib.parse.urlparse(proxy_url)
          scheme = parsed.scheme.lower()
          type_map = {"socks5": 1, "socks4": 2, "http": 3, "https": 3}
          idx = type_map.get(scheme, 0)
          self.proxy_type_combo.setCurrentIndex(idx)
          self._on_proxy_type_changed(idx)
          self.proxy_host_input.setText(parsed.hostname or "")
          if parsed.port:
              self.proxy_port_spin.setValue(parsed.port)
          if parsed.username:
              self.proxy_user_input.setText(parsed.username)
          if parsed.password:
              self.proxy_pass_input.setText(parsed.password)
      except Exception:
          pass

  def _build_proxy_url(self) -> str:
      idx = self.proxy_type_combo.currentIndex()
      if idx == 0:
          return ""
      scheme = ["", "socks5", "socks4", "http"][idx]
      host = self.proxy_host_input.text().strip()
      port = self.proxy_port_spin.value()
      user = self.proxy_user_input.text().strip()
      pwd = self.proxy_pass_input.text()
      if not host:
          return ""
      if user and pwd:
          return f"{scheme}://{user}:{pwd}@{host}:{port}"
      return f"{scheme}://{host}:{port}"

  def _test_connection(self):
      account = self.get_account()
      if not account:
          return
      proxy_url = self._build_proxy_url()
      self.test_result.setPlainText("Подключение" + (f" через прокси {proxy_url}..." if proxy_url else "..."))

      async def run():
          return await test_smtp_connection(account)

      def do():
          import asyncio
          loop = asyncio.new_event_loop()
          success, log = loop.run_until_complete(run())
          loop.close()
          self._test_done.emit(success, log)

      threading.Thread(target=do, daemon=True).start()

  def _on_test_done(self, success: bool, log: str) -> None:
      color = Colors.SUCCESS if success else Colors.ERROR
      self.test_result.setStyleSheet(f"color:{color};")
      self.test_result.setPlainText(log)

  def get_account(self) -> SmtpAccount | None:
      email = self.email_input.text().strip()
      password = self.password_input.text()
      host = self.host_input.text().strip()
      if not email or not password or not host:
          return None
      acc = SmtpAccount(
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
      proxy = self._build_proxy_url()
      if proxy:
          acc.proxy = proxy
      return acc


# ──────────────────────────────────────────────
# Bulk import dialog
# ──────────────────────────────────────────────

class BulkImportAccountsDialog(QDialog):
  """Диалог массового импорта SMTP-аккаунтов из файла."""

  def __init__(self, parent=None):
      super().__init__(parent)
      self.setWindowTitle("Массовый импорт аккаунтов")
      self.setMinimumSize(760, 520)
      self._parsed: list[SmtpAccount] = []
      self._setup_ui()

  def _setup_ui(self):
      layout = QVBoxLayout(self)
      layout.setSpacing(Spacing.LG)
      layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)

      info = QLabel(
          "<b>Поддерживаемые форматы:</b><br>"
          "• <code>email:пароль</code> &nbsp;&nbsp;"
          "• <code>email;пароль</code> &nbsp;&nbsp;"
          "• <code>email|пароль</code> &nbsp;&nbsp;"
          "• <code>email,пароль</code><br>"
          "• <code>email:пароль:smtp-хост:порт</code> &nbsp;—&nbsp; явные настройки<br>"
          "• <code>email:пароль:smtp-хост:порт:ssl:socks5://host:port</code> &nbsp;—&nbsp; с прокси<br>"
          "<span style='color:#888;'>SMTP определяется автоматически: Gmail, Outlook, Yahoo, Mail.ru, Yandex, GMX…</span>"
      )
      info.setWordWrap(True)
      info.setObjectName("label_muted")
      layout.addWidget(info)

      file_row = QHBoxLayout()
      self.file_label = QLabel("Файл не выбран")
      self.file_label.setObjectName("label_muted")
      file_row.addWidget(self.file_label, 1)
      browse_btn = QPushButton("Выбрать файл…")
      browse_btn.setObjectName("btn_icon")
      browse_btn.clicked.connect(self._browse_file)
      file_row.addWidget(browse_btn)
      layout.addLayout(file_row)

      self.text_area = QTextEdit()
      self.text_area.setPlaceholderText(
          "или вставьте список сюда:\n"
          "user1@gmail.com:password1\n"
          "user2@mail.ru:password2\n"
          "user3@gmx.com:password3:mail.gmx.com:587\n"
          "user4@yahoo.com:password4:smtp.mail.yahoo.com:465:ssl:socks5://127.0.0.1:1080"
      )
      self.text_area.setMaximumHeight(120)
      layout.addWidget(self.text_area)

      self._parse_timer = QTimer()
      self._parse_timer.setSingleShot(True)
      self._parse_timer.setInterval(600)
      self._parse_timer.timeout.connect(self._parse)
      self.text_area.textChanged.connect(self._parse_timer.start)

      opts_row = QHBoxLayout()
      self._verify_check = QCheckBox("Проверить подключение для всех импортированных аккаунтов")
      self._verify_check.setChecked(True)
      opts_row.addWidget(self._verify_check)
      opts_row.addStretch()
      layout.addLayout(opts_row)

      self.preview_label = QLabel("Предпросмотр: начните вводить или откройте файл")
      layout.addWidget(self.preview_label)

      self.table = QTableWidget()
      self.table.setColumnCount(7)
      self.table.setHorizontalHeaderLabels(["Email", "SMTP Сервер", "Порт", "Шифр.", "Прокси", "Статус", "Пароль"])
      self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
      self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
      self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
      self.table.setAlternatingRowColors(True)
      layout.addWidget(self.table, 1)

      buttons = QDialogButtonBox(
          QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
      )
      buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Импортировать")
      buttons.accepted.connect(self.accept)
      buttons.rejected.connect(self.reject)
      layout.addWidget(buttons)

  def _browse_file(self):
      path, _ = QFileDialog.getOpenFileName(
          self, "Выбрать файл с аккаунтами", "",
          "Текстовые файлы (*.txt *.csv *.tsv *.dat);;Все файлы (*)"
      )
      if path:
          self.file_label.setText(path)
          try:
              text = ""
              for enc in ('utf-8', 'utf-8-sig', 'cp1251', 'latin-1'):
                  try:
                      text = open(path, encoding=enc).read()
                      break
                  except UnicodeDecodeError:
                      continue
              self.text_area.setPlainText(text)
              self._parse_timer.stop()
              self._parse()
          except Exception as e:
              QMessageBox.warning(self, "Ошибка", f"Не удалось прочитать файл: {e}")

  def _parse(self):
      from PyQt6.QtGui import QColor as _QColor
      text = self.text_area.toPlainText()
      parsed = _parse_accounts_file(text)
      self._parsed = []
      self.table.setRowCount(0)

      for item in parsed:
          email = item["email"]
          domain = email.split("@")[1]
          cfg = get_smtp_config_for_domain(domain)
          if item["host_override"]:
              host = item["host_override"]
              port = item["port_override"] or (465 if item["ssl_override"] is not False else 587)
              use_ssl = item["ssl_override"] if item["ssl_override"] is not None else True
              use_tls = not use_ssl
          elif cfg:
              host = cfg["host"]
              port = cfg["port"]
              use_ssl = cfg["use_ssl"]
              use_tls = cfg["use_tls"]
          else:
              host = f"mail.{domain}"
              port = 587
              use_ssl = False
              use_tls = True

          proxy = item.get("proxy_override", "")
          enc_str = "SSL" if use_ssl else "STARTTLS"
          status = "✓ Авто" if cfg else ("✓ Явный" if item["host_override"] else "⚠ Неизвестен")

          row = self.table.rowCount()
          self.table.insertRow(row)
          self.table.setItem(row, 0, QTableWidgetItem(email))
          self.table.setItem(row, 1, QTableWidgetItem(host))
          self.table.setItem(row, 2, QTableWidgetItem(str(port)))
          self.table.setItem(row, 3, QTableWidgetItem(enc_str))
          self.table.setItem(row, 4, QTableWidgetItem(proxy or "—"))
          status_item = QTableWidgetItem(status)
          status_item.setForeground(_QColor(Colors.SUCCESS if "✓" in status else Colors.WARNING))
          self.table.setItem(row, 5, status_item)
          self.table.setItem(row, 6, QTableWidgetItem("●●●●●●"))

          acc = SmtpAccount(
              email=email,
              password=item["password"],
              host=host,
              port=port,
              use_ssl=use_ssl,
              use_tls=use_tls,
          )
          if proxy:
              acc.proxy = proxy
          self._parsed.append(acc)

      self.preview_label.setText(
          f"Предпросмотр: найдено <b>{len(self._parsed)}</b> аккаунтов"
          f" из {len(text.splitlines())} строк"
      )

  def get_accounts(self) -> list[SmtpAccount]:
      return self._parsed

  def should_verify(self) -> bool:
      return self._verify_check.isChecked()


# ──────────────────────────────────────────────
# Main accounts screen
# ──────────────────────────────────────────────

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
      bulk_btn = QPushButton("Импорт из файла")
      bulk_btn.setObjectName("btn_icon")
      bulk_btn.clicked.connect(self._bulk_import)
      header_row.addWidget(bulk_btn)
      add_btn = QPushButton("+ Добавить аккаунт")
      add_btn.setObjectName("btn_primary")
      add_btn.clicked.connect(self._add_account)
      header_row.addWidget(add_btn)
      layout.addLayout(header_row)

      stats_card = QFrame()
      stats_card.setObjectName("card")
      stats_layout = QHBoxLayout(stats_card)
      self.stats_label = QLabel("Аккаунтов: 0 | Активных: 0 | С прокси: 0")
      self.stats_label.setObjectName("label_muted")
      stats_layout.addWidget(self.stats_label)
      stats_layout.addStretch()
      layout.addWidget(stats_card)

      self.table = QTableWidget()
      self.table.setColumnCount(8)
      self.table.setHorizontalHeaderLabels([
          "Email", "SMTP Сервер", "Порт", "Шифр.",
          "Лимит/день", "Лимит/час", "Прокси", "Статус"
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
      proxy_count = 0
      for i, acc in enumerate(self._accounts):
          self.table.setItem(i, 0, QTableWidgetItem(acc.email))
          self.table.setItem(i, 1, QTableWidgetItem(acc.host))
          self.table.setItem(i, 2, QTableWidgetItem(str(acc.port)))
          enc = "SSL" if acc.use_ssl else ("TLS" if acc.use_tls else "Нет")
          self.table.setItem(i, 3, QTableWidgetItem(enc))
          self.table.setItem(i, 4, QTableWidgetItem(str(acc.daily_limit)))
          self.table.setItem(i, 5, QTableWidgetItem(str(acc.hourly_limit)))
          proxy = getattr(acc, "proxy", "") or ""
          if proxy:
              proxy_count += 1
          proxy_display = proxy.split("@")[-1] if "@" in proxy else (proxy or "—")
          self.table.setItem(i, 6, QTableWidgetItem(proxy_display))
          status_item = QTableWidgetItem("Активен" if acc.is_active else "Отключён")
          status_item.setForeground(
              QColor(Colors.SUCCESS) if acc.is_active else QColor(Colors.TEXT_MUTED)
          )
          self.table.setItem(i, 7, status_item)
      active = sum(1 for a in self._accounts if a.is_active)
      self.stats_label.setText(
          f"Аккаунтов: {len(self._accounts)} | Активных: {active} | С прокси: {proxy_count}"
      )
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

  def _bulk_import(self):
      dlg = BulkImportAccountsDialog(self)
      if dlg.exec() == QDialog.DialogCode.Accepted:
          new_accounts = dlg.get_accounts()
          existing_emails = {a.email for a in self._accounts}
          added = 0
          for acc in new_accounts:
              if acc.email not in existing_emails:
                  self._accounts.append(acc)
                  existing_emails.add(acc.email)
                  added += 1
          save_accounts(self._accounts)
          self._refresh_table()
          QMessageBox.information(self, "Импорт завершён", f"Добавлено {added} аккаунтов.")

  def _test_selected(self):
      row = self.table.currentRow()
      if row < 0:
          QMessageBox.information(self, "Тест", "Выберите аккаунт из таблицы")
          return
      acc = self._accounts[row]
      proxy = getattr(acc, "proxy", "") or ""
      proxy_info = f" (прокси: {proxy})" if proxy else ""
      QMessageBox.information(self, "Тест", f"Проверка {acc.email}{proxy_info}...")

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
