"""
Экран 4: Списки получателей.
Импорт CSV/XLSX/TXT, маппинг полей, валидация email, дедупликация, группы, unsubscribe.
"""
import csv
import json
import logging
import re
import threading
from pathlib import Path
from typing import List

logger = logging.getLogger("recipients")

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QFrame, QProgressBar, QComboBox, QDialog, QFormLayout,
    QDialogButtonBox, QListWidget, QListWidgetItem, QCheckBox,
    QMessageBox, QLineEdit, QTabWidget, QSplitter, QTextEdit
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor

from core.sender import Recipient
from core.spam_checker import validate_email_format
from gui.theme import Colors, Spacing

RECIPIENTS_DIR = Path("data/recipients")
UNSUBSCRIBE_FILE = Path("data/unsubscribe.json")
BLACKLIST_FILE = Path("data/blacklist.json")


def _load_unsubscribe() -> set:
    if UNSUBSCRIBE_FILE.exists():
        try:
            with open(UNSUBSCRIBE_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception as e:
            logger.warning(f"Ошибка загрузки unsubscribe-листа: {e}")
    return set()


def _save_unsubscribe(emails: set) -> None:
    UNSUBSCRIBE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(UNSUBSCRIBE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(emails), f, ensure_ascii=False)


class FieldMappingDialog(QDialog):
    """Диалог маппинга колонок CSV → поля Recipient."""

    RECIPIENT_FIELDS = ["email", "first_name", "last_name", "company",
                        "custom_1", "custom_2", "custom_3", "custom_4", "custom_5"]

    def __init__(self, csv_columns: List[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Маппинг полей")
        self.setMinimumWidth(460)
        self._csv_columns = csv_columns
        self._mapping: dict = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(Spacing.LG)
        layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)

        info = QLabel("Сопоставьте колонки CSV с полями получателя:")
        info.setObjectName("label_muted")
        layout.addWidget(info)

        form = QFormLayout()
        self._combos: dict = {}

        for field in self.RECIPIENT_FIELDS:
            combo = QComboBox()
            combo.addItem("— не использовать —")
            combo.addItems(self._csv_columns)

            # Автоматическое определение по имени колонки
            for i, col in enumerate(self._csv_columns):
                if col.lower() in (field.lower(), field.replace("_", "").lower(),
                                   field.replace("_name", "").lower()):
                    combo.setCurrentIndex(i + 1)
                    break
                # Специальные случаи
                if field == "email" and "mail" in col.lower():
                    combo.setCurrentIndex(i + 1)
                elif field == "first_name" and ("first" in col.lower() or "имя" in col.lower()):
                    combo.setCurrentIndex(i + 1)
                elif field == "last_name" and ("last" in col.lower() or "фамил" in col.lower()):
                    combo.setCurrentIndex(i + 1)
                elif field == "company" and ("compan" in col.lower() or "компан" in col.lower()):
                    combo.setCurrentIndex(i + 1)

            self._combos[field] = combo
            label_text = {
                "email": "Email *", "first_name": "Имя", "last_name": "Фамилия",
                "company": "Компания", "custom_1": "Поле 1", "custom_2": "Поле 2",
                "custom_3": "Поле 3", "custom_4": "Поле 4", "custom_5": "Поле 5",
            }.get(field, field)
            form.addRow(label_text + ":", combo)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self):
        self._mapping = {}
        for field, combo in self._combos.items():
            if combo.currentIndex() > 0:
                self._mapping[field] = self._csv_columns[combo.currentIndex() - 1]
        if "email" not in self._mapping:
            QMessageBox.warning(self, "Ошибка", "Необходимо указать колонку Email")
            return
        self.accept()

    def get_mapping(self) -> dict:
        return self._mapping


class RecipientsScreen(QWidget):
    """Экран управления списками получателей."""

    list_ready = pyqtSignal(list)  # List[Recipient]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._recipients: List[Recipient] = []
        self._unsubscribe: set = _load_unsubscribe()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        layout.setSpacing(Spacing.LG)

        # ── Заголовок ────────────────────────────
        header_row = QHBoxLayout()
        title = QLabel("Список получателей")
        title.setObjectName("section_header")
        header_row.addWidget(title)
        header_row.addStretch()

        import_btn = QPushButton("Импорт CSV/XLSX/TXT")
        import_btn.setObjectName("btn_primary")
        import_btn.clicked.connect(self._import_file)
        header_row.addWidget(import_btn)

        add_manual_btn = QPushButton("+ Добавить вручную")
        add_manual_btn.clicked.connect(self._add_manual)
        header_row.addWidget(add_manual_btn)

        layout.addLayout(header_row)

        # ── Статистика ────────────────────────────
        stats_row = QHBoxLayout()
        self.total_label = _stat_label("Всего: 0")
        self.valid_label = _stat_label("Валидных: 0", Colors.SUCCESS)
        self.invalid_label = _stat_label("Невалидных: 0", Colors.ERROR)
        self.unsub_label = _stat_label("Отписавшихся: 0", Colors.WARNING)
        self.dupes_label = _stat_label("Дубликатов: 0", Colors.TEXT_MUTED)

        for lbl in [self.total_label, self.valid_label, self.invalid_label,
                    self.unsub_label, self.dupes_label]:
            stats_row.addWidget(lbl)
        stats_row.addStretch()

        layout.addLayout(stats_row)

        # ── Фильтры ───────────────────────────────
        filter_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по email, имени, компании...")
        self.search_input.textChanged.connect(self._filter_table)
        filter_row.addWidget(self.search_input, 1)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Все", "Валидные", "Невалидные", "Отписавшиеся"])
        self.filter_combo.currentTextChanged.connect(self._filter_table)
        self.filter_combo.setFixedWidth(150)
        filter_row.addWidget(self.filter_combo)

        dedup_btn = QPushButton("Удалить дубликаты")
        dedup_btn.clicked.connect(self._deduplicate)
        filter_row.addWidget(dedup_btn)

        layout.addLayout(filter_row)

        # ── Прогресс валидации ────────────────────
        self.validation_bar = QProgressBar()
        self.validation_bar.setVisible(False)
        self.validation_label = QLabel("")
        self.validation_label.setObjectName("label_muted")
        self.validation_label.setVisible(False)
        layout.addWidget(self.validation_bar)
        layout.addWidget(self.validation_label)

        # ── Таблица ───────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "#", "Email", "Имя", "Фамилия", "Компания", "Статус", "Действия"
        ])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, 1)

        # ── Нижняя панель ─────────────────────────
        bottom_row = QHBoxLayout()

        export_btn = QPushButton("Экспорт в CSV")
        export_btn.clicked.connect(self._export_csv)
        bottom_row.addWidget(export_btn)

        manage_unsub_btn = QPushButton("Управление отписками")
        manage_unsub_btn.clicked.connect(self._manage_unsubscribe)
        bottom_row.addWidget(manage_unsub_btn)

        bottom_row.addStretch()

        self.use_list_btn = QPushButton("Использовать список →")
        self.use_list_btn.setObjectName("btn_primary")
        self.use_list_btn.setEnabled(False)
        self.use_list_btn.clicked.connect(self._emit_list)
        bottom_row.addWidget(self.use_list_btn)

        layout.addLayout(bottom_row)

    def _import_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Импорт получателей", "",
            "Таблицы (*.csv *.xlsx *.txt);;CSV (*.csv);;Excel (*.xlsx);;TXT (*.txt)"
        )
        if not path:
            return

        ext = Path(path).suffix.lower()
        try:
            if ext == ".csv" or ext == ".txt":
                self._import_csv(path)
            elif ext == ".xlsx":
                self._import_xlsx(path)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка импорта", str(e))

    def _import_csv(self, path: str):
        # Автодетект разделителя
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            sample = f.read(4096)

        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        separator = dialect.delimiter if dialect else ","

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f, delimiter=separator)
            columns = reader.fieldnames or []
            if not columns:
                QMessageBox.warning(self, "Ошибка", "Файл не содержит заголовков")
                return
            rows = list(reader)

        # Маппинг полей
        mapping_dialog = FieldMappingDialog(columns, parent=self)
        if mapping_dialog.exec() != QDialog.DialogCode.Accepted:
            return

        mapping = mapping_dialog.get_mapping()
        recipients = []
        for row in rows:
            email = row.get(mapping.get("email", ""), "").strip()
            if not email:
                continue
            r = Recipient(
                email=email,
                first_name=row.get(mapping.get("first_name", ""), "").strip(),
                last_name=row.get(mapping.get("last_name", ""), "").strip(),
                company=row.get(mapping.get("company", ""), "").strip(),
                custom_1=row.get(mapping.get("custom_1", ""), "").strip(),
                custom_2=row.get(mapping.get("custom_2", ""), "").strip(),
                custom_3=row.get(mapping.get("custom_3", ""), "").strip(),
                custom_4=row.get(mapping.get("custom_4", ""), "").strip(),
                custom_5=row.get(mapping.get("custom_5", ""), "").strip(),
            )
            recipients.append(r)

        self._process_imported(recipients)

    def _import_xlsx(self, path: str):
        try:
            import openpyxl
        except ImportError:
            QMessageBox.warning(self, "Ошибка", "Установите openpyxl: pip install openpyxl")
            return

        wb = openpyxl.load_workbook(path, read_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return

        headers = [str(h).strip() if h else f"col_{i}" for i, h in enumerate(rows[0])]
        mapping_dialog = FieldMappingDialog(headers, parent=self)
        if mapping_dialog.exec() != QDialog.DialogCode.Accepted:
            return

        mapping = mapping_dialog.get_mapping()
        recipients = []
        for row in rows[1:]:
            row_dict = {headers[i]: str(v).strip() if v else "" for i, v in enumerate(row)}
            email = row_dict.get(mapping.get("email", ""), "").strip()
            if not email:
                continue
            r = Recipient(
                email=email,
                first_name=row_dict.get(mapping.get("first_name", ""), "").strip(),
                last_name=row_dict.get(mapping.get("last_name", ""), "").strip(),
                company=row_dict.get(mapping.get("company", ""), "").strip(),
            )
            recipients.append(r)

        wb.close()
        self._process_imported(recipients)

    def _process_imported(self, new_recipients: List[Recipient]):
        """Дедупликация и добавление получателей."""
        existing_emails = {r.email.lower() for r in self._recipients}
        added = 0
        dupes = 0

        for r in new_recipients:
            if r.email.lower() in existing_emails:
                dupes += 1
            else:
                self._recipients.append(r)
                existing_emails.add(r.email.lower())
                added += 1

        self._refresh_table()
        QMessageBox.information(
            self, "Импорт завершён",
            f"Добавлено: {added}\nДубликатов пропущено: {dupes}"
        )

    def _refresh_table(self):
        """Обновляет таблицу с получателями."""
        self.table.setRowCount(len(self._recipients))
        valid_count = 0
        invalid_count = 0
        unsub_count = 0

        for row, r in enumerate(self._recipients):
            self.table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self.table.setItem(row, 1, QTableWidgetItem(r.email))
            self.table.setItem(row, 2, QTableWidgetItem(r.first_name))
            self.table.setItem(row, 3, QTableWidgetItem(r.last_name))
            self.table.setItem(row, 4, QTableWidgetItem(r.company))

            # Статус
            is_valid = validate_email_format(r.email)
            is_unsub = r.email.lower() in self._unsubscribe

            if is_unsub:
                status = "Отписался"
                color = Colors.WARNING
                unsub_count += 1
            elif is_valid:
                status = "✓ Валидный"
                color = Colors.SUCCESS
                valid_count += 1
            else:
                status = "✗ Невалидный"
                color = Colors.ERROR
                invalid_count += 1

            status_item = QTableWidgetItem(status)
            status_item.setForeground(QColor(color))
            self.table.setItem(row, 5, status_item)

            # Кнопка удаления
            del_btn = QPushButton("✕")
            del_btn.setObjectName("btn_icon")
            del_btn.setFixedSize(28, 28)
            del_btn.clicked.connect(lambda _, idx=row: self._delete_recipient(idx))
            self.table.setCellWidget(row, 6, del_btn)
            self.table.setRowHeight(row, 40)

        total = len(self._recipients)
        self.total_label.setText(f"Всего: {total}")
        self.valid_label.setText(f"Валидных: {valid_count}")
        self.invalid_label.setText(f"Невалидных: {invalid_count}")
        self.unsub_label.setText(f"Отписавшихся: {unsub_count}")
        self.use_list_btn.setEnabled(valid_count > 0)

    def _filter_table(self):
        """Фильтрует строки таблицы."""
        search = self.search_input.text().lower()
        filter_mode = self.filter_combo.currentText()

        for row in range(self.table.rowCount()):
            email_item = self.table.item(row, 1)
            status_item = self.table.item(row, 5)
            if not email_item:
                continue

            email = email_item.text().lower()
            name = (self.table.item(row, 2) or QTableWidgetItem("")).text().lower()
            company = (self.table.item(row, 4) or QTableWidgetItem("")).text().lower()
            status = (status_item or QTableWidgetItem("")).text()

            match_search = not search or search in email or search in name or search in company
            match_filter = (
                filter_mode == "Все" or
                (filter_mode == "Валидные" and "Валидный" in status) or
                (filter_mode == "Невалидные" and "Невалидный" in status) or
                (filter_mode == "Отписавшиеся" and "Отписался" in status)
            )
            self.table.setRowHidden(row, not (match_search and match_filter))

    def _deduplicate(self):
        before = len(self._recipients)
        seen = set()
        unique = []
        for r in self._recipients:
            key = r.email.lower()
            if key not in seen:
                seen.add(key)
                unique.append(r)
        self._recipients = unique
        removed = before - len(self._recipients)
        self._refresh_table()
        self.dupes_label.setText(f"Удалено дубликатов: {removed}")
        if removed > 0:
            QMessageBox.information(self, "Дедупликация", f"Удалено дубликатов: {removed}")

    def _delete_recipient(self, row: int):
        if 0 <= row < len(self._recipients):
            self._recipients.pop(row)
            self._refresh_table()

    def _add_manual(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Добавить получателя")
        layout = QFormLayout(dialog)
        email_input = QLineEdit()
        first_input = QLineEdit()
        last_input = QLineEdit()
        company_input = QLineEdit()
        layout.addRow("Email *:", email_input)
        layout.addRow("Имя:", first_input)
        layout.addRow("Фамилия:", last_input)
        layout.addRow("Компания:", company_input)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            email = email_input.text().strip()
            if email:
                r = Recipient(
                    email=email,
                    first_name=first_input.text().strip(),
                    last_name=last_input.text().strip(),
                    company=company_input.text().strip(),
                )
                self._recipients.append(r)
                self._refresh_table()

    def _manage_unsubscribe(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Список отписавшихся")
        dialog.setMinimumSize(400, 400)
        layout = QVBoxLayout(dialog)

        info = QLabel(f"Всего отписавшихся: {len(self._unsubscribe)}")
        layout.addWidget(info)

        text = QTextEdit()
        text.setPlainText("\n".join(sorted(self._unsubscribe)))
        text.setPlaceholderText("По одному email на строку")
        layout.addWidget(text)

        save_btn = QPushButton("Сохранить")
        save_btn.setObjectName("btn_primary")
        layout.addWidget(save_btn)

        def save():
            lines = [l.strip() for l in text.toPlainText().splitlines() if l.strip()]
            self._unsubscribe = set(lines)
            _save_unsubscribe(self._unsubscribe)
            info.setText(f"Всего отписавшихся: {len(self._unsubscribe)}")
            self._refresh_table()

        save_btn.clicked.connect(save)
        dialog.exec()

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт в CSV", "recipients.csv", "CSV files (*.csv)"
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["email", "first_name", "last_name", "company",
                             "custom_1", "custom_2", "custom_3"])
            for r in self._recipients:
                writer.writerow([r.email, r.first_name, r.last_name, r.company,
                                 r.custom_1, r.custom_2, r.custom_3])
        QMessageBox.information(self, "Экспорт", f"Сохранено: {path}")

    def _emit_list(self):
        """Отправляет валидных получателей (без отписок) в следующий экран."""
        valid = [
            r for r in self._recipients
            if validate_email_format(r.email) and r.email.lower() not in self._unsubscribe
        ]
        self.list_ready.emit(valid)

    def get_recipients(self) -> List[Recipient]:
        return [
            r for r in self._recipients
            if validate_email_format(r.email) and r.email.lower() not in self._unsubscribe
        ]


def _stat_label(text: str, color: str = Colors.TEXT_SECONDARY) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {color}; font-size: 12px;")
    lbl.setObjectName("card")
    lbl.setContentsMargins(8, 4, 8, 4)
    return lbl
