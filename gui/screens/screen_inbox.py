"""
Экран: Ответы — читает входящие письма со всех аккаунтов через IMAP
и позволяет отвечать прямо из приложения.
"""
from __future__ import annotations

import email
import imaplib
import smtplib
import ssl
import threading
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QSplitter,
    QTextEdit, QFrame, QProgressBar, QAbstractItemView,
    QDialog, QDialogButtonBox, QLineEdit, QFormLayout,
    QComboBox, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import QColor, QFont

from gui.theme import Colors, Spacing, Radii, Typography


# ─────────────────────────────────────────────────────────────────────────────
# Вспомогательные функции
# ─────────────────────────────────────────────────────────────────────────────

def _decode_str(s: str | bytes | None) -> str:
    if s is None:
        return ""
    if isinstance(s, bytes):
        parts = decode_header(s.decode("utf-8", errors="replace"))
    else:
        parts = decode_header(s)
    result = []
    for part, enc in parts:
        if isinstance(part, bytes):
            result.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            result.append(str(part))
    return " ".join(result)


def _get_body(msg: email.message.Message) -> str:
    """Извлекает текстовое тело письма (plain-text предпочтительно)."""
    html_body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            disp = str(part.get("Content-Disposition", ""))
            if "attachment" in disp:
                continue
            if ct == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(part.get_content_charset() or "utf-8", errors="replace")
            elif ct == "text/html" and not html_body:
                payload = part.get_payload(decode=True)
                if payload:
                    html_body = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
    return html_body or "(нет содержимого)"


def _imap_host(smtp_host: str) -> str:
    """Авто-определение IMAP хоста из SMTP хоста."""
    return smtp_host.replace("smtp.", "imap.", 1) if smtp_host.startswith("smtp.") else smtp_host


# ─────────────────────────────────────────────────────────────────────────────
# Фоновый поток загрузки писем
# ─────────────────────────────────────────────────────────────────────────────

class _FetchWorker(QThread):
    messages_ready = pyqtSignal(list)   # list[dict]
    error_occurred = pyqtSignal(str, str)  # account_login, error_msg
    finished_all   = pyqtSignal()

    def __init__(self, accounts: list[dict], parent=None):
        super().__init__(parent)
        self._accounts = accounts

    def run(self):
        all_messages: list[dict] = []
        for acc in self._accounts:
            try:
                msgs = self._fetch_account(acc)
                all_messages.extend(msgs)
            except Exception as e:
                self.error_occurred.emit(acc.get("login", "?"), str(e))

        all_messages.sort(key=lambda m: m.get("date_raw", ""), reverse=True)
        self.messages_ready.emit(all_messages)
        self.finished_all.emit()

    def _fetch_account(self, acc: dict) -> list[dict]:
        imap_host = acc.get("imap_host") or _imap_host(acc.get("host", ""))
        imap_port = int(acc.get("imap_port", 993))
        imap_ssl  = acc.get("imap_ssl", True)
        login     = acc.get("login", "")
        password  = acc.get("password", "")

        if not imap_host or not login or not password:
            return []

        ctx = ssl.create_default_context()
        if imap_ssl:
            M = imaplib.IMAP4_SSL(imap_host, imap_port, ssl_context=ctx)
        else:
            M = imaplib.IMAP4(imap_host, imap_port)
            M.starttls(ssl_context=ctx)

        M.login(login, password)
        M.select("INBOX")

        # Ищем последние 50 писем
        _, data = M.search(None, "ALL")
        uids = data[0].split()
        uids = uids[-50:]  # последние 50

        result = []
        for uid in reversed(uids):
            _, msg_data = M.fetch(uid, "(RFC822)")
            if not msg_data or not msg_data[0]:
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            result.append({
                "uid":          uid.decode(),
                "account":      login,
                "from":         _decode_str(msg.get("From", "")),
                "to":           _decode_str(msg.get("To", "")),
                "subject":      _decode_str(msg.get("Subject", "(без темы)")),
                "date":         _decode_str(msg.get("Date", "")),
                "date_raw":     msg.get("Date", ""),
                "reply_to":     _decode_str(msg.get("Reply-To", msg.get("From", ""))),
                "message_id":   msg.get("Message-ID", ""),
                "body":         _get_body(msg),
                "_raw":         raw,
            })

        M.logout()
        return result


# ─────────────────────────────────────────────────────────────────────────────
# Диалог ответа
# ─────────────────────────────────────────────────────────────────────────────

class ReplyDialog(QDialog):
    def __init__(self, original: dict, accounts: list[dict], parent=None):
        super().__init__(parent)
        self._original = original
        self._accounts = accounts
        self.setWindowTitle("Ответить на письмо")
        self.setMinimumSize(600, 420)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        layout.setSpacing(Spacing.SM)

        form = QFormLayout()
        form.setSpacing(Spacing.SM)
        form.setContentsMargins(0, 0, 0, 0)

        # Аккаунт-отправитель
        self.acc_combo = QComboBox()
        orig_acc = self._original.get("account", "")
        idx = 0
        for i, acc in enumerate(self._accounts):
            self.acc_combo.addItem(acc.get("login", ""))
            if acc.get("login") == orig_acc:
                idx = i
        self.acc_combo.setCurrentIndex(idx)
        form.addRow("Отправить с:", self.acc_combo)

        # Кому
        self.to_edit = QLineEdit()
        self.to_edit.setText(self._original.get("reply_to") or self._original.get("from", ""))
        form.addRow("Кому:", self.to_edit)

        # Тема
        subj = self._original.get("subject", "")
        if not subj.lower().startswith("re:"):
            subj = f"Re: {subj}"
        self.subj_edit = QLineEdit()
        self.subj_edit.setText(subj)
        form.addRow("Тема:", self.subj_edit)

        layout.addLayout(form)

        # Тело ответа
        self.body_edit = QTextEdit()
        orig_body = self._original.get("body", "")
        snippet = "\n\n— Исходное письмо:\n" + "\n".join(
            f"> {line}" for line in orig_body.splitlines()[:30]
        )
        self.body_edit.setPlainText(snippet)
        self.body_edit.setPlaceholderText("Введите текст ответа...")
        layout.addWidget(self.body_edit, 1)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.button(QDialogButtonBox.StandardButton.Ok).setText("Отправить")
        btn_box.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        btn_box.accepted.connect(self._send)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _send(self):
        acc_idx = self.acc_combo.currentIndex()
        if acc_idx < 0 or acc_idx >= len(self._accounts):
            QMessageBox.warning(self, "Ошибка", "Выберите аккаунт отправителя.")
            return
        acc = self._accounts[acc_idx]
        to_addr  = self.to_edit.text().strip()
        subject  = self.subj_edit.text().strip()
        body_txt = self.body_edit.toPlainText()

        if not to_addr:
            QMessageBox.warning(self, "Ошибка", "Укажите получателя.")
            return

        try:
            self._do_send(acc, to_addr, subject, body_txt)
            QMessageBox.information(self, "Готово", "Письмо отправлено!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка отправки", str(e))

    def _do_send(self, acc: dict, to_addr: str, subject: str, body: str):
        msg = MIMEMultipart("alternative")
        msg["From"]       = f"{acc.get('display_name', '')} <{acc.get('login', '')}>"
        msg["To"]         = to_addr
        msg["Subject"]    = subject
        msg["In-Reply-To"] = self._original.get("message_id", "")
        msg["References"]  = self._original.get("message_id", "")
        msg.attach(MIMEText(body, "plain", "utf-8"))

        host     = acc.get("host", "")
        port     = int(acc.get("port", 587))
        login    = acc.get("login", "")
        password = acc.get("password", "")
        use_ssl  = acc.get("use_ssl", False)
        use_tls  = acc.get("use_tls", True)

        if use_ssl:
            server = smtplib.SMTP_SSL(host, port)
        else:
            server = smtplib.SMTP(host, port)
            if use_tls:
                server.starttls()

        server.login(login, password)
        server.sendmail(login, [to_addr], msg.as_bytes())
        server.quit()


# ─────────────────────────────────────────────────────────────────────────────
# Главный экран «Ответы»
# ─────────────────────────────────────────────────────────────────────────────

class InboxScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._accounts: list[dict] = []
        self._messages: list[dict] = []
        self._worker: Optional[_FetchWorker] = None
        self._setup_ui()

    def set_accounts(self, accounts: list[dict]):
        self._accounts = list(accounts)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        layout.setSpacing(Spacing.MD)

        # ── Заголовок + кнопки ────────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("Ответы")
        title.setStyleSheet(
            f"font-size: {Typography.SIZE_LG}px; font-weight: {Typography.WEIGHT_BOLD};"
            f" color: {Colors.TEXT_PRIMARY};"
        )
        header.addWidget(title)
        header.addStretch()

        self._refresh_btn = QPushButton("  Обновить")
        self._refresh_btn.setObjectName("btn_secondary")
        self._refresh_btn.clicked.connect(self._refresh)
        header.addWidget(self._refresh_btn)

        self._reply_btn = QPushButton("  Ответить")
        self._reply_btn.clicked.connect(self._open_reply)
        self._reply_btn.setEnabled(False)
        header.addWidget(self._reply_btn)

        layout.addLayout(header)

        # ── Прогрессбар ───────────────────────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedHeight(3)
        self._progress.setVisible(False)
        self._progress.setObjectName("progress_flat")
        layout.addWidget(self._progress)

        # ── Разделитель: список | превью ──────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Таблица писем
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Аккаунт", "От", "Тема", "Дата"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.setColumnWidth(0, 150)
        self._table.setColumnWidth(1, 200)
        self._table.setColumnWidth(3, 140)
        self._table.selectionModel().selectionChanged.connect(self._on_select)
        splitter.addWidget(self._table)

        # Панель превью
        preview_panel = QFrame()
        preview_panel.setObjectName("card")
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)

        self._preview_from    = QLabel("—")
        self._preview_from.setStyleSheet(f"font-weight: {Typography.WEIGHT_BOLD}; color: {Colors.TEXT_PRIMARY};")
        self._preview_subject = QLabel("—")
        self._preview_subject.setWordWrap(True)
        self._preview_subject.setStyleSheet(f"font-size: {Typography.SIZE_MD}px; color: {Colors.TEXT_PRIMARY};")
        self._preview_date    = QLabel("")
        self._preview_date.setStyleSheet(f"font-size: {Typography.SIZE_XS}px; color: {Colors.TEXT_MUTED};")

        self._preview_body = QTextEdit()
        self._preview_body.setReadOnly(True)
        self._preview_body.setObjectName("card_inner")
        self._preview_body.setStyleSheet(
            f"background: {Colors.BG_SURFACE3};"
            f" color: {Colors.TEXT_PRIMARY};"
            f" border: 1px solid {Colors.BORDER};"
            " border-radius: 8px;"
            " padding: 10px;"
        )

        preview_layout.addWidget(self._preview_from)
        preview_layout.addWidget(self._preview_subject)
        preview_layout.addWidget(self._preview_date)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background: {Colors.BORDER}; margin: 4px 0;")
        preview_layout.addWidget(sep)
        preview_layout.addWidget(self._preview_body)

        splitter.addWidget(preview_panel)
        splitter.setSizes([480, 360])
        layout.addWidget(splitter, 1)

        # Статус-строка
        self._status_lbl = QLabel("Нажмите «Обновить» для загрузки писем.")
        self._status_lbl.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: {Typography.SIZE_XS}px;")
        layout.addWidget(self._status_lbl)

    # ── Загрузка писем ────────────────────────────────────────────────────

    def _refresh(self):
        if self._worker and self._worker.isRunning():
            return

        if not self._accounts:
            QMessageBox.information(self, "Ответы", "Сначала добавьте аккаунты на вкладке «Аккаунты».")
            return

        self._progress.setVisible(True)
        self._status_lbl.setText("Загрузка писем…")
        self._refresh_btn.setEnabled(False)

        self._worker = _FetchWorker(self._accounts)
        self._worker.messages_ready.connect(self._on_messages)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.finished_all.connect(self._on_done)
        self._worker.start()

    def _on_messages(self, messages: list[dict]):
        self._messages = messages
        self._table.setRowCount(0)
        for msg in messages:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(msg.get("account", "")))
            self._table.setItem(row, 1, QTableWidgetItem(msg.get("from", "")))
            self._table.setItem(row, 2, QTableWidgetItem(msg.get("subject", "")))
            date_str = msg.get("date", "")[:25]
            self._table.setItem(row, 3, QTableWidgetItem(date_str))
            self._table.setRowHeight(row, 32)

    def _on_error(self, login: str, error: str):
        self._status_lbl.setText(f"Ошибка {login}: {error[:80]}")

    def _on_done(self):
        self._progress.setVisible(False)
        self._refresh_btn.setEnabled(True)
        total = len(self._messages)
        self._status_lbl.setText(f"Загружено {total} писем со всех аккаунтов.")

    # ── Выбор письма ──────────────────────────────────────────────────────

    def _on_select(self):
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            self._reply_btn.setEnabled(False)
            return
        idx = rows[0].row()
        if idx < 0 or idx >= len(self._messages):
            return
        msg = self._messages[idx]
        self._preview_from.setText(msg.get("from", ""))
        self._preview_subject.setText(msg.get("subject", ""))
        self._preview_date.setText(msg.get("date", ""))
        self._preview_body.setPlainText(msg.get("body", ""))
        self._reply_btn.setEnabled(True)

    # ── Диалог ответа ─────────────────────────────────────────────────────

    def _open_reply(self):
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return
        idx = rows[0].row()
        if idx < 0 or idx >= len(self._messages):
            return
        dlg = ReplyDialog(self._messages[idx], self._accounts, parent=self)
        dlg.exec()
