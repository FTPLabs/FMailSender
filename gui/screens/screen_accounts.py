"""
SMTP Accounts Screen v3.6.2
Manage SMTP accounts: add, remove, check, import.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QDialog, QFormLayout,
    QLineEdit, QComboBox, QSpinBox, QMessageBox,
    QFileDialog,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont

from gui.theme import Colors, Spacing, Typography


class AccountsScreen(QWidget):
    """SMTP account manager with validation support."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._accounts: list[dict] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(16)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("SMTP Аккаунты")
        title.setObjectName("section_header")
        hdr.addWidget(title)
        hdr.addStretch()

        btn_import = QPushButton("↙ Импорт")
        btn_import.setObjectName("btn_secondary")
        btn_import.setFixedHeight(34)
        btn_import.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_import.clicked.connect(self._import_accounts)

        btn_add = QPushButton("+ Добавить")
        btn_add.setObjectName("btn_primary")
        btn_add.setFixedHeight(34)
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.clicked.connect(self._add_account)

        btn_check = QPushButton("✓ Проверить все")
        btn_check.setObjectName("btn_secondary")
        btn_check.setFixedHeight(34)
        btn_check.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_check.clicked.connect(self._check_all)

        hdr.addWidget(btn_import)
        hdr.addWidget(btn_check)
        hdr.addWidget(btn_add)
        layout.addLayout(hdr)

        # Stats row
        stats_row = QHBoxLayout()
        self._lbl_total  = self._stat_label("0 аккаунтов")
        self._lbl_active = self._stat_label("0 активных", Colors.GREEN)
        self._lbl_failed = self._stat_label("0 с ошибкой", Colors.RED)
        stats_row.addWidget(self._lbl_total)
        stats_row.addWidget(self._lbl_active)
        stats_row.addWidget(self._lbl_failed)
        stats_row.addStretch()
        layout.addLayout(stats_row)

        # Table card
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["Email", "Сервер", "Порт", "TLS", "Статус", "Действия"]
        )
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col in (2, 3, 4, 5):
            self._table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        card_layout.addWidget(self._table)
        layout.addWidget(card, 1)

    def _stat_label(self, text: str, color: str = Colors.TEXT_MUTED) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {color}; font-size: {Typography.SIZE_SM}pt; "
            f"background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); "
            f"border-radius: 6px; padding: 4px 10px;"
        )
        return lbl

    def _refresh_table(self):
        self._table.setRowCount(0)
        active = 0
        failed = 0
        for acc in self._accounts:
            row = self._table.rowCount()
            self._table.insertRow(row)
            status = acc.get("status", "—")
            if status == "ok":
                active += 1
                status_color = Colors.GREEN
            elif status in ("error", "failed"):
                failed += 1
                status_color = Colors.RED
            else:
                status_color = Colors.TEXT_MUTED

            self._table.setItem(row, 0, QTableWidgetItem(acc.get("email", "")))
            self._table.setItem(row, 1, QTableWidgetItem(acc.get("host", "")))
            self._table.setItem(row, 2, QTableWidgetItem(str(acc.get("port", ""))))
            tls_item = QTableWidgetItem("SSL" if acc.get("ssl") else "STARTTLS" if acc.get("starttls") else "Нет")
            self._table.setItem(row, 3, tls_item)
            status_item = QTableWidgetItem(status)
            status_item.setForeground(QColor(status_color))
            self._table.setItem(row, 4, status_item)

            del_btn = QPushButton("Удалить")
            del_btn.setObjectName("btn_danger")
            del_btn.setFixedHeight(28)
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.clicked.connect(lambda checked, r=row: self._delete_account(r))
            self._table.setCellWidget(row, 5, del_btn)
            self._table.setRowHeight(row, 42)

        self._lbl_total.setText(f"{len(self._accounts)} аккаунтов")
        self._lbl_active.setText(f"{active} активных")
        self._lbl_failed.setText(f"{failed} с ошибкой")

    def _add_account(self):
        dlg = AccountDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            data["status"] = "—"
            self._accounts.append(data)
            self._refresh_table()

    def _delete_account(self, row: int):
        if 0 <= row < len(self._accounts):
            self._accounts.pop(row)
            self._refresh_table()

    def _import_accounts(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Импорт аккаунтов", "",
            "Text files (*.txt);;CSV (*.csv);;All (*.*)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                lines = [l.strip() for l in f if l.strip()]
            added = 0
            for line in lines:
                parts = line.split(":")
                if len(parts) >= 4:
                    self._accounts.append({
                        "email": parts[0], "password": parts[1],
                        "host": parts[2], "port": int(parts[3]) if parts[3].isdigit() else 587,
                        "ssl": False, "starttls": True, "status": "—",
                    })
                    added += 1
            self._refresh_table()
            QMessageBox.information(self, "Импорт", f"Импортировано: {added} аккаунтов")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка импорта", str(e))

    def _check_all(self):
        if not self._accounts:
            QMessageBox.information(self, "Проверка", "Нет аккаунтов для проверки")
            return
        try:
            from core.smtp_validator import SMTPValidator
            for i, acc in enumerate(self._accounts):
                try:
                    valid = SMTPValidator.check(
                        acc["host"], acc["port"],
                        acc["email"], acc.get("password", ""),
                        ssl=acc.get("ssl", False),
                    )
                    self._accounts[i]["status"] = "ok" if valid else "error"
                except Exception:
                    self._accounts[i]["status"] = "error"
            self._refresh_table()
        except ImportError:
            QMessageBox.warning(self, "Предупреждение", "Модуль smtp_validator недоступен")

    def get_accounts(self) -> list[dict]:
        return [a for a in self._accounts if a.get("status") == "ok"]


class AccountDialog(QDialog):
    """Dialog for adding a single SMTP account."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить аккаунт")
        self.setMinimumWidth(400)
        self.setStyleSheet(f"background: {Colors.BG_SURFACE};")
        self._build_ui()

    def _build_ui(self):
        layout = QFormLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        self._email    = QLineEdit(); self._email.setPlaceholderText("user@example.com")
        self._password = QLineEdit(); self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._host     = QLineEdit(); self._host.setPlaceholderText("smtp.example.com")
        self._port     = QSpinBox(); self._port.setRange(1, 65535); self._port.setValue(587)
        self._tls      = QComboBox()
        self._tls.addItems(["STARTTLS", "SSL/TLS", "Нет"])

        layout.addRow("Email:",    self._email)
        layout.addRow("Пароль:",   self._password)
        layout.addRow("SMTP сервер:", self._host)
        layout.addRow("Порт:",     self._port)
        layout.addRow("TLS:",      self._tls)

        btn_row = QHBoxLayout()
        cancel = QPushButton("Отмена")
        cancel.setObjectName("btn_secondary")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Добавить")
        ok.setObjectName("btn_primary")
        ok.clicked.connect(self.accept)
        btn_row.addWidget(cancel)
        btn_row.addWidget(ok)
        layout.addRow(btn_row)

    def get_data(self) -> dict:
        tls_text = self._tls.currentText()
        return {
            "email":    self._email.text().strip(),
            "password": self._password.text(),
            "host":     self._host.text().strip(),
            "port":     self._port.value(),
            "ssl":      tls_text == "SSL/TLS",
            "starttls": tls_text == "STARTTLS",
        }
