"""
Inbox Screen v3.6.2
Incoming mail monitor: bounce classification, reply monitor, auto-responder.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QTabWidget, QTextEdit,
    QCheckBox, QLineEdit,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

from gui.theme import Colors, Spacing, Typography


class InboxScreen(QWidget):
    """Incoming mail: bounce reports, replies, auto-response rules."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bounce_list: list[dict] = []
        self._reply_list:  list[dict] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(16)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Входящие")
        title.setObjectName("section_header")
        hdr.addWidget(title)
        hdr.addStretch()
        refresh_btn = QPushButton("↻ Обновить")
        refresh_btn.setObjectName("btn_secondary")
        refresh_btn.setFixedHeight(34)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self._refresh)
        hdr.addWidget(refresh_btn)
        layout.addLayout(hdr)

        # Stats row
        stats = QHBoxLayout()
        self._lbl_hard   = self._badge("Hard bounce: 0",  Colors.RED)
        self._lbl_soft   = self._badge("Soft bounce: 0",  Colors.AMBER)
        self._lbl_reply  = self._badge("Ответы: 0",       Colors.BLUE)
        self._lbl_unsub  = self._badge("Отписки: 0",      Colors.TEXT_MUTED)
        for lbl in (self._lbl_hard, self._lbl_soft, self._lbl_reply, self._lbl_unsub):
            stats.addWidget(lbl)
        stats.addStretch()
        layout.addLayout(stats)

        # Tabs: Bounce | Replies | Auto-rules
        self._tabs = QTabWidget()

        # ── Bounce tab ────────────────────────────────────────────────────
        bounce_widget = QWidget()
        bounce_layout = QVBoxLayout(bounce_widget)
        bounce_layout.setContentsMargins(0, 12, 0, 0)

        bounce_card = QFrame()
        bounce_card.setObjectName("card")
        bounce_card_layout = QVBoxLayout(bounce_card)
        bounce_card_layout.setContentsMargins(0, 0, 0, 0)

        self._bounce_table = QTableWidget(0, 5)
        self._bounce_table.setHorizontalHeaderLabels(
            ["Email", "Тип", "Код", "Причина", "Дата"]
        )
        self._bounce_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._bounce_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 4):
            self._bounce_table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents
            )
        self._bounce_table.verticalHeader().setVisible(False)
        self._bounce_table.setShowGrid(False)
        self._bounce_table.setAlternatingRowColors(True)
        self._bounce_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._bounce_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        bounce_card_layout.addWidget(self._bounce_table)

        bounce_layout.addWidget(bounce_card, 1)

        bounce_action_row = QHBoxLayout()
        add_to_bl = QPushButton("Добавить в blacklist")
        add_to_bl.setObjectName("btn_danger")
        add_to_bl.setFixedHeight(34)
        add_to_bl.setCursor(Qt.CursorShape.PointingHandCursor)
        export_bounce = QPushButton("↗ Экспорт hard-bounce")
        export_bounce.setObjectName("btn_secondary")
        export_bounce.setFixedHeight(34)
        export_bounce.setCursor(Qt.CursorShape.PointingHandCursor)
        bounce_action_row.addWidget(add_to_bl)
        bounce_action_row.addWidget(export_bounce)
        bounce_action_row.addStretch()
        bounce_layout.addLayout(bounce_action_row)
        self._tabs.addTab(bounce_widget, "Bounce")

        # ── Replies tab ───────────────────────────────────────────────────
        reply_widget = QWidget()
        reply_layout = QVBoxLayout(reply_widget)
        reply_layout.setContentsMargins(0, 12, 0, 0)

        reply_card = QFrame()
        reply_card.setObjectName("card")
        reply_card_layout = QVBoxLayout(reply_card)
        reply_card_layout.setContentsMargins(0, 0, 0, 0)

        self._reply_table = QTableWidget(0, 4)
        self._reply_table.setHorizontalHeaderLabels(["От", "Тема", "Дата", "Статус"])
        self._reply_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._reply_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col in (2, 3):
            self._reply_table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents
            )
        self._reply_table.verticalHeader().setVisible(False)
        self._reply_table.setShowGrid(False)
        self._reply_table.setAlternatingRowColors(True)
        self._reply_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        reply_card_layout.addWidget(self._reply_table)
        reply_layout.addWidget(reply_card, 1)
        self._tabs.addTab(reply_widget, "Ответы")

        # ── Auto-rules tab ────────────────────────────────────────────────
        auto_widget = QWidget()
        auto_layout = QVBoxLayout(auto_widget)
        auto_layout.setContentsMargins(0, 12, 0, 0)

        auto_card = QFrame()
        auto_card.setObjectName("card")
        auto_card_layout = QVBoxLayout(auto_card)
        auto_card_layout.setContentsMargins(18, 16, 18, 16)
        auto_card_layout.setSpacing(12)

        auto_title = QLabel("Правила автоответа")
        auto_title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-weight: 600; background: transparent; border: none;")
        auto_card_layout.addWidget(auto_title)

        self._chk_auto_unsub = QCheckBox("Автоматически обрабатывать отписки")
        self._chk_auto_unsub.setChecked(True)
        self._chk_bounce_bl  = QCheckBox("Добавлять hard-bounce в blacklist автоматически")
        self._chk_bounce_bl.setChecked(True)
        self._chk_auto_reply = QCheckBox("Автоответ на входящие письма")

        for chk in (self._chk_auto_unsub, self._chk_bounce_bl, self._chk_auto_reply):
            chk.setStyleSheet(f"color: {Colors.TEXT_MUTED};")
            auto_card_layout.addWidget(chk)

        auto_card_layout.addWidget(QLabel("Текст автоответа:"))
        self._auto_reply_text = QTextEdit()
        self._auto_reply_text.setMaximumHeight(100)
        self._auto_reply_text.setPlaceholderText("Спасибо за ваше письмо. Мы ответим в ближайшее время.")
        auto_card_layout.addWidget(self._auto_reply_text)
        auto_card_layout.addStretch()

        save_btn = QPushButton("Сохранить правила")
        save_btn.setObjectName("btn_primary")
        save_btn.setFixedHeight(38)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        auto_card_layout.addWidget(save_btn)

        auto_layout.addWidget(auto_card)
        self._tabs.addTab(auto_widget, "Автоправила")

        layout.addWidget(self._tabs, 1)

    def _badge(self, text: str, color: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {color}; font-size: {Typography.SIZE_SM}pt; "
            f"background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); "
            f"border-radius: 6px; padding: 4px 10px;"
        )
        return lbl

    def _refresh(self):
        pass  # Hook for real IMAP/POP3 polling

    def add_bounce(self, email: str, btype: str, code: str,
                   reason: str, date: str):
        row = self._bounce_table.rowCount()
        self._bounce_table.insertRow(row)
        self._bounce_table.setItem(row, 0, QTableWidgetItem(email))
        type_item = QTableWidgetItem(btype)
        color = Colors.RED if btype.lower() == "hard" else Colors.AMBER
        type_item.setForeground(QColor(color))
        self._bounce_table.setItem(row, 1, type_item)
        self._bounce_table.setItem(row, 2, QTableWidgetItem(code))
        self._bounce_table.setItem(row, 3, QTableWidgetItem(reason))
        self._bounce_table.setItem(row, 4, QTableWidgetItem(date))
        self._bounce_table.setRowHeight(row, 40)

        hard = sum(1 for r in range(self._bounce_table.rowCount())
                   if self._bounce_table.item(r, 1) and
                   self._bounce_table.item(r, 1).text().lower() == "hard")
        soft = self._bounce_table.rowCount() - hard
        self._lbl_hard.setText(f"Hard bounce: {hard}")
        self._lbl_soft.setText(f"Soft bounce: {soft}")
