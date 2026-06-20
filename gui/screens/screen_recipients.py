"""
Recipients Screen v3.6.2
Manage email recipient lists: import, validate, deduplicate, export.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QListWidget, QListWidgetItem,
    QPushButton, QFileDialog, QMessageBox, QProgressDialog,
    QTextEdit, QSplitter, QLineEdit,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont

from gui.theme import Colors, Spacing, Typography


class RecipientsScreen(QWidget):
    """Email recipient list manager."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._emails: list[str] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(16)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Получатели")
        title.setObjectName("section_header")
        hdr.addWidget(title)
        hdr.addStretch()

        for label, slot, name in [
            ("↙ Импорт из файла", self._import_file, "btn_secondary"),
            ("✓ Дедупликация",    self._dedup,       "btn_secondary"),
            ("✓ Валидация",       self._validate,    "btn_secondary"),
            ("↗ Экспорт",         self._export,      "btn_secondary"),
            ("Очистить",          self._clear,       "btn_danger"),
        ]:
            b = QPushButton(label)
            b.setObjectName(name)
            b.setFixedHeight(34)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            hdr.addWidget(b)

        layout.addLayout(hdr)

        # Stats bar
        stats = QHBoxLayout()
        self._lbl_count   = self._badge("0 адресов",      Colors.TEXT_MUTED)
        self._lbl_valid   = self._badge("0 валидных",     Colors.GREEN)
        self._lbl_invalid = self._badge("0 невалидных",   Colors.RED)
        self._lbl_dups    = self._badge("0 дубликатов",   Colors.AMBER)
        for lbl in (self._lbl_count, self._lbl_valid, self._lbl_invalid, self._lbl_dups):
            stats.addWidget(lbl)
        stats.addStretch()
        layout.addLayout(stats)

        # Quick-add
        add_row = QHBoxLayout()
        self._add_input = QLineEdit()
        self._add_input.setPlaceholderText("email@example.com или вставьте список через запятую/новую строку")
        add_btn = QPushButton("Добавить")
        add_btn.setObjectName("btn_secondary")
        add_btn.setFixedHeight(34)
        add_btn.setFixedWidth(100)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._quick_add)
        add_row.addWidget(self._add_input, 1)
        add_row.addWidget(add_btn)
        layout.addLayout(add_row)

        # Main list
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)

        self._list = QListWidget()
        self._list.setFont(QFont(Typography.FAMILY_MONO, Typography.SIZE_SM))
        self._list.setStyleSheet(f"""
            QListWidget {{
                background: transparent;
                border: none;
                color: {Colors.TEXT_PRIMARY};
            }}
            QListWidget::item {{
                padding: 5px 14px;
                border-bottom: 1px solid rgba(255,255,255,0.04);
            }}
            QListWidget::item:selected {{
                background: rgba(139,92,246,0.12);
                color: {Colors.TEXT_PRIMARY};
            }}
        """)
        card_layout.addWidget(self._list)
        layout.addWidget(card, 1)

    def _badge(self, text: str, color: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {color}; font-size: {Typography.SIZE_SM}pt; "
            f"background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); "
            f"border-radius: 6px; padding: 4px 10px;"
        )
        return lbl

    def _refresh_list(self):
        self._list.clear()
        for email in self._emails:
            self._list.addItem(QListWidgetItem(email))
        self._lbl_count.setText(f"{len(self._emails)} адресов")

    def _quick_add(self):
        raw = self._add_input.text().strip()
        if not raw:
            return
        new_emails = [e.strip() for e in raw.replace(",", "\n").split("\n") if e.strip()]
        self._emails.extend(new_emails)
        self._add_input.clear()
        self._refresh_list()

    def _import_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Импорт получателей", "",
            "Text (*.txt);;CSV (*.csv);;Excel (*.xlsx);;All (*.*)"
        )
        if not path:
            return
        try:
            if path.endswith(".xlsx"):
                import openpyxl
                wb = openpyxl.load_workbook(path)
                ws = wb.active
                for row in ws.iter_rows(values_only=True):
                    for cell in row:
                        if cell and "@" in str(cell):
                            self._emails.append(str(cell).strip())
            else:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if "@" in line:
                            self._emails.append(line)
            self._refresh_list()
            QMessageBox.information(
                self, "Импорт",
                f"Импортировано {len(self._emails)} адресов"
            )
        except Exception as e:
            QMessageBox.critical(self, "Ошибка импорта", str(e))

    def _dedup(self):
        before = len(self._emails)
        try:
            from core.duplicate_detector import DuplicateDetector
            detector = DuplicateDetector()
            self._emails = detector.filter(self._emails)
        except ImportError:
            seen = set()
            result = []
            for email in self._emails:
                key = email.lower().strip()
                if key not in seen:
                    seen.add(key)
                    result.append(email)
            self._emails = result
        after = len(self._emails)
        self._lbl_dups.setText(f"{before - after} дубликатов")
        self._refresh_list()
        QMessageBox.information(
            self, "Дедупликация",
            f"Удалено дубликатов: {before - after}\nОсталось: {after}"
        )

    def _validate(self):
        import re
        pattern = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
        valid   = [e for e in self._emails if pattern.match(e)]
        invalid = [e for e in self._emails if not pattern.match(e)]
        self._lbl_valid.setText(f"{len(valid)} валидных")
        self._lbl_invalid.setText(f"{len(invalid)} невалидных")
        self._emails = valid
        self._refresh_list()
        QMessageBox.information(
            self, "Валидация",
            f"Валидных: {len(valid)}\nНевалидных (удалено): {len(invalid)}"
        )

    def _export(self):
        if not self._emails:
            QMessageBox.information(self, "Экспорт", "Список пуст")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт получателей", "recipients.txt",
            "Text (*.txt);;CSV (*.csv)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(self._emails))
            QMessageBox.information(self, "Экспорт", f"Сохранено: {path}")

    def _clear(self):
        if not self._emails:
            return
        reply = QMessageBox.question(
            self, "Очистить", "Удалить все адреса?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._emails.clear()
            self._refresh_list()

    def get_emails(self) -> list[str]:
        return list(self._emails)
