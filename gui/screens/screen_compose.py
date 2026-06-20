"""
Compose Screen v3.6.2
Email editor: subject, from-name, HTML / plain-text body, attachments, preview.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QFrame, QLineEdit, QTextEdit, QPlainTextEdit,
    QPushButton, QFileDialog, QListWidget, QListWidgetItem,
    QTabWidget, QSplitter, QCheckBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from gui.theme import Colors, Spacing, Typography


class ComposeScreen(QWidget):
    """Email composition editor."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._attachments: list[str] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(16)

        # Title
        title = QLabel("Письмо")
        title.setObjectName("section_header")
        layout.addWidget(title)

        # Metadata card
        meta_card = QFrame()
        meta_card.setObjectName("card")
        meta_layout = QFormLayout(meta_card)
        meta_layout.setContentsMargins(18, 16, 18, 16)
        meta_layout.setSpacing(10)

        self._from_name    = QLineEdit(); self._from_name.setPlaceholderText("Имя отправителя (необязательно)")
        self._reply_to     = QLineEdit(); self._reply_to.setPlaceholderText("reply@example.com")
        self._subject      = QLineEdit(); self._subject.setPlaceholderText("Тема письма")
        self._subject.setFont(QFont(Typography.FAMILY, Typography.SIZE_MD))

        meta_layout.addRow("Имя отправителя:", self._from_name)
        meta_layout.addRow("Reply-To:",        self._reply_to)
        meta_layout.addRow("Тема:",            self._subject)

        # Options row
        opts_row = QHBoxLayout()
        self._chk_track_open  = QCheckBox("Трекинг открытий")
        self._chk_track_click = QCheckBox("Трекинг кликов")
        self._chk_unsubscribe = QCheckBox("Ссылка отписки")
        for chk in (self._chk_track_open, self._chk_track_click, self._chk_unsubscribe):
            chk.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: {Typography.SIZE_SM}pt;")
            opts_row.addWidget(chk)
        opts_row.addStretch()
        meta_layout.addRow("Опции:", opts_row)
        layout.addWidget(meta_card)

        # Body editor (tabs: HTML / Plain / Preview)
        body_card = QFrame()
        body_card.setObjectName("card")
        body_layout = QVBoxLayout(body_card)
        body_layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("QTabWidget::pane { padding: 0; }")

        # HTML tab
        html_container = QWidget()
        html_layout = QVBoxLayout(html_container)
        html_layout.setContentsMargins(12, 10, 12, 12)
        html_layout.setSpacing(8)

        html_toolbar = QHBoxLayout()
        for lbl, ph in [("Вставить шаблон", ""), ("AI-улучшить", ""), ("Проверить SPAM", "")]:
            b = QPushButton(lbl)
            b.setObjectName("btn_icon")
            b.setFixedHeight(28)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            html_toolbar.addWidget(b)
        html_toolbar.addStretch()
        html_layout.addLayout(html_toolbar)

        self._html_editor = QTextEdit()
        self._html_editor.setFont(QFont(Typography.FAMILY_MONO, Typography.SIZE_SM))
        self._html_editor.setPlaceholderText("<html>\n  <body>\n    <p>Привет, {{name}}!</p>\n  </body>\n</html>")
        html_layout.addWidget(self._html_editor, 1)
        self._tabs.addTab(html_container, "HTML")

        # Plain text tab
        plain_container = QWidget()
        plain_layout = QVBoxLayout(plain_container)
        plain_layout.setContentsMargins(12, 10, 12, 12)
        self._plain_editor = QPlainTextEdit()
        self._plain_editor.setFont(QFont(Typography.FAMILY_MONO, Typography.SIZE_SM))
        self._plain_editor.setPlaceholderText("Привет, {{name}}!\n\nТекст письма...")
        plain_layout.addWidget(self._plain_editor)
        self._tabs.addTab(plain_container, "Текст")

        body_layout.addWidget(self._tabs)
        layout.addWidget(body_card, 1)

        # Attachments
        attach_card = QFrame()
        attach_card.setObjectName("card")
        attach_layout = QVBoxLayout(attach_card)
        attach_layout.setContentsMargins(14, 12, 14, 12)
        attach_layout.setSpacing(8)

        attach_hdr = QHBoxLayout()
        attach_title = QLabel("Вложения")
        attach_title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-weight: 600; background: transparent; border: none;")
        attach_hdr.addWidget(attach_title)
        attach_hdr.addStretch()
        add_attach = QPushButton("+ Прикрепить")
        add_attach.setObjectName("btn_secondary")
        add_attach.setFixedHeight(30)
        add_attach.setCursor(Qt.CursorShape.PointingHandCursor)
        add_attach.clicked.connect(self._add_attachment)
        attach_hdr.addWidget(add_attach)
        attach_layout.addLayout(attach_hdr)

        self._attach_list = QListWidget()
        self._attach_list.setMaximumHeight(80)
        self._attach_list.setStyleSheet(
            f"background: transparent; border: none; color: {Colors.TEXT_MUTED}; font-size: {Typography.SIZE_SM}pt;"
        )
        attach_layout.addWidget(self._attach_list)
        layout.addWidget(attach_card)

    def _add_attachment(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Прикрепить файлы", "", "All files (*.*)"
        )
        for p in paths:
            self._attachments.append(p)
            self._attach_list.addItem(QListWidgetItem(f"📎 {p.split('/')[-1].split(chr(92))[-1]}"))

    def get_config(self) -> dict:
        return {
            "from_name":   self._from_name.text().strip(),
            "reply_to":    self._reply_to.text().strip(),
            "subject":     self._subject.text().strip(),
            "html_body":   self._html_editor.toHtml(),
            "plain_body":  self._plain_editor.toPlainText(),
            "attachments": list(self._attachments),
            "track_opens":   self._chk_track_open.isChecked(),
            "track_clicks":  self._chk_track_click.isChecked(),
            "unsubscribe":   self._chk_unsubscribe.isChecked(),
        }
