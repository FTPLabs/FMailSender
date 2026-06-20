"""
Activation / License Screen v3.6.2
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from gui.theme import Colors, Spacing, Typography
from gui.widgets.animated_bg import AnimatedBackground


class ActivationScreen(QWidget):
    """License activation screen with HWID display and key input."""

    activation_success = pyqtSignal(object)

    def __init__(self, hint_message: str = "", parent=None):
        super().__init__(parent)
        self._hint = hint_message
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Animated background
        bg = AnimatedBackground(self)
        bg.setGeometry(0, 0, 9999, 9999)
        bg.lower()

        # Center card
        center = QWidget()
        center.setStyleSheet("background: transparent;")
        center_layout = QVBoxLayout(center)
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(520)
        card.setStyleSheet(f"""
            QFrame {{
                background: rgba(13,13,26,0.92);
                border: 1px solid rgba(139,92,246,0.25);
                border-radius: 18px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 40, 40, 40)
        card_layout.setSpacing(20)

        # Logo + Title
        logo = QLabel("✦ FMail Sender")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet(
            f"color: {Colors.ACCENT}; font-size: 22pt; font-weight: 700; background: transparent; border: none;"
        )
        card_layout.addWidget(logo)

        sub = QLabel("Активация лицензии")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: {Typography.SIZE_MD}pt; background: transparent; border: none;"
        )
        card_layout.addWidget(sub)

        # HWID
        hwid_label = QLabel("Идентификатор устройства (HWID):")
        hwid_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: {Typography.SIZE_SM}pt; background: transparent; border: none;")
        card_layout.addWidget(hwid_label)

        self._hwid_field = QLineEdit()
        self._hwid_field.setReadOnly(True)
        self._hwid_field.setPlaceholderText("Загрузка HWID...")
        self._hwid_field.setFont(QFont(Typography.FAMILY_MONO))
        card_layout.addWidget(self._hwid_field)

        copy_btn = QPushButton("Копировать HWID")
        copy_btn.setObjectName("btn_icon")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(self._copy_hwid)
        card_layout.addWidget(copy_btn)

        # License key
        key_label = QLabel("Лицензионный ключ:")
        key_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: {Typography.SIZE_SM}pt; background: transparent; border: none;")
        card_layout.addWidget(key_label)

        self._key_field = QLineEdit()
        self._key_field.setPlaceholderText("XXXXX-XXXXX-XXXXX-XXXXX")
        self._key_field.setFont(QFont(Typography.FAMILY_MONO))
        card_layout.addWidget(self._key_field)

        # Hint
        if self._hint:
            hint = QLabel(self._hint)
            hint.setWordWrap(True)
            hint.setStyleSheet(f"color: {Colors.AMBER}; font-size: {Typography.SIZE_SM}pt; background: transparent; border: none;")
            card_layout.addWidget(hint)

        # Status
        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet("background: transparent; border: none;")
        card_layout.addWidget(self._status_label)

        # Activate button
        self._btn_activate = QPushButton("Активировать")
        self._btn_activate.setObjectName("btn_primary")
        self._btn_activate.setFixedHeight(44)
        self._btn_activate.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_activate.clicked.connect(self._do_activate)
        card_layout.addWidget(self._btn_activate)

        center_layout.addWidget(card, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(center, 1)

        # Load HWID
        self._load_hwid()

    def _load_hwid(self):
        try:
            from core.license import generate_hwid
            hwid = generate_hwid()
            self._hwid_field.setText(hwid)
        except Exception as e:
            self._hwid_field.setText(f"Ошибка: {e}")

    def _copy_hwid(self):
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(self._hwid_field.text())
        self._set_status("HWID скопирован в буфер обмена", Colors.GREEN)

    def _do_activate(self):
        key = self._key_field.text().strip()
        if not key:
            self._set_status("Введите лицензионный ключ", Colors.AMBER)
            return

        self._btn_activate.setEnabled(False)
        self._btn_activate.setText("Проверка...")
        self._set_status("Проверка лицензии...", Colors.TEXT_MUTED)

        try:
            from core.license import activate_license
            ok, info, msg = activate_license(key)
            if ok:
                self._set_status("Лицензия активирована!", Colors.GREEN)
                self.activation_success.emit(info)
            else:
                self._set_status(msg or "Неверный ключ", Colors.RED)
                self._btn_activate.setEnabled(True)
                self._btn_activate.setText("Активировать")
        except Exception as exc:
            self._set_status(f"Ошибка: {exc}", Colors.RED)
            self._btn_activate.setEnabled(True)
            self._btn_activate.setText("Активировать")

    def _set_status(self, text: str, color: str):
        self._status_label.setText(text)
        self._status_label.setStyleSheet(
            f"color: {color}; font-size: {Typography.SIZE_BASE}pt; background: transparent; border: none;"
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Keep animated bg fullscreen
        for child in self.children():
            if isinstance(child, AnimatedBackground):
                child.setGeometry(0, 0, self.width(), self.height())
