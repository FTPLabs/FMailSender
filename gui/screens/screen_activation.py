"""
Экран 0: Активация лицензии.
Логотип, HWID, поле ввода ключа, прогресс активации.
"""
import threading
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QProgressBar, QGraphicsDropShadowEffect, QFrame
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QClipboard, QGuiApplication, QFont
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtCore import QByteArray

from core.license import generate_hwid, activate_license, validate_key_format
from gui.theme import Colors, Typography, Spacing


SVG_LOGO = b"""
<svg width="80" height="80" viewBox="0 0 80 80" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="g1" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#6366F1;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#818CF8;stop-opacity:1" />
    </linearGradient>
  </defs>
  <rect width="80" height="80" rx="20" fill="url(#g1)" opacity="0.15"/>
  <rect x="2" y="2" width="76" height="76" rx="18" fill="none"
        stroke="url(#g1)" stroke-width="2"/>
  <path d="M16 28 L40 44 L64 28" stroke="#6366F1" stroke-width="2.5"
        fill="none" stroke-linecap="round" stroke-linejoin="round"/>
  <rect x="16" y="26" width="48" height="32" rx="4" fill="none"
        stroke="#6366F1" stroke-width="2.5"/>
</svg>
"""


class ActivationScreen(QWidget):
    """Экран активации лицензии."""

    activation_success = pyqtSignal(object)  # LicenseInfo

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hwid = generate_hwid()
        self._setup_ui()

    def _setup_ui(self):
        # Центрирующий layout
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.setContentsMargins(40, 40, 40, 40)

        # Контейнер карточки
        card = QFrame()
        card.setObjectName("activation_container")
        card.setFixedWidth(480)
        card_shadow = QGraphicsDropShadowEffect()
        card_shadow.setBlurRadius(40)
        card_shadow.setOffset(0, 8)
        card_shadow.setColor(QColor(0, 0, 0, 80))
        card.setGraphicsEffect(card_shadow)

        layout = QVBoxLayout(card)
        layout.setSpacing(Spacing.LG)
        layout.setContentsMargins(Spacing.XXL, Spacing.XXL, Spacing.XXL, Spacing.XXL)

        # ── Логотип ──────────────────────────────
        logo_row = QHBoxLayout()
        logo_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        svg = QSvgWidget()
        svg.load(QByteArray(SVG_LOGO))
        svg.setFixedSize(80, 80)
        logo_row.addWidget(svg)

        layout.addLayout(logo_row)

        # ── Заголовок ────────────────────────────
        title = QLabel("Email Sender Pro")
        title.setObjectName("label_title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = title.font()
        font.setPointSize(22)
        font.setWeight(QFont.Weight.Bold)
        title.setFont(font)
        layout.addWidget(title)

        subtitle = QLabel("Активация лицензии")
        subtitle.setObjectName("label_muted")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(Spacing.LG)

        # ── HWID блок ────────────────────────────
        hwid_label = QLabel("Идентификатор устройства (HWID)")
        hwid_label.setObjectName("label_muted")
        layout.addWidget(hwid_label)

        hwid_row = QHBoxLayout()
        hwid_row.setSpacing(Spacing.SM)

        self.hwid_display = QLabel(self._hwid)
        self.hwid_display.setObjectName("hwid_display")
        self.hwid_display.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        hwid_row.addWidget(self.hwid_display, 1)

        copy_btn = QPushButton("Копировать")
        copy_btn.setObjectName("btn_icon")
        copy_btn.setFixedWidth(90)
        copy_btn.clicked.connect(self._copy_hwid)
        hwid_row.addWidget(copy_btn)

        layout.addLayout(hwid_row)

        layout.addSpacing(Spacing.SM)

        # ── Поле ключа ───────────────────────────
        key_label = QLabel("Лицензионный ключ")
        key_label.setObjectName("label_muted")
        layout.addWidget(key_label)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("ESP-XXXXX-XXXXX-XXXXX-XXXXX")
        self.key_input.setMaxLength(29)
        self.key_input.textChanged.connect(self._on_key_changed)
        self.key_input.returnPressed.connect(self._activate)
        layout.addWidget(self.key_input)

        # Статус валидации ключа
        self.key_status = QLabel("")
        self.key_status.setObjectName("label_muted")
        layout.addWidget(self.key_status)

        layout.addSpacing(Spacing.SM)

        # ── Прогресс-бар ─────────────────────────
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("activation_bar")
        self.progress_bar.setRange(0, 4)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("")
        self.progress_label.setObjectName("label_muted")
        self.progress_label.setVisible(False)
        layout.addWidget(self.progress_label)

        # ── Кнопка активации ─────────────────────
        self.activate_btn = QPushButton("Активировать")
        self.activate_btn.setObjectName("btn_primary")
        self.activate_btn.setFixedHeight(44)
        self.activate_btn.setEnabled(False)
        self.activate_btn.clicked.connect(self._activate)
        layout.addWidget(self.activate_btn)

        # Статус результата
        self.result_label = QLabel("")
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_label.setWordWrap(True)
        self.result_label.setVisible(False)
        layout.addWidget(self.result_label)

        outer.addWidget(card)

    def _copy_hwid(self):
        cb = QGuiApplication.clipboard()
        cb.setText(self._hwid)
        # Анимация обратной связи
        btn = self.sender()
        original = btn.text()
        btn.setText("Скопировано!")
        QTimer.singleShot(1500, lambda: btn.setText(original))

    def _on_key_changed(self, text: str):
        """Live-валидация формата ключа."""
        text = text.upper().replace(" ", "")

        # Автоформатирование (добавляем тире)
        clean = text.replace("-", "")
        formatted = "ESP-"
        if len(clean) > 3:
            body = clean[3:]
            parts = [body[i:i+5] for i in range(0, len(body), 5)]
            formatted = "ESP-" + "-".join(parts[:4])

        if text != formatted and len(text) <= 29:
            self.key_input.blockSignals(True)
            self.key_input.setText(formatted)
            self.key_input.setCursorPosition(len(formatted))
            self.key_input.blockSignals(False)
            text = formatted

        is_valid = validate_key_format(text)
        self.activate_btn.setEnabled(is_valid)

        if len(text) == 0:
            self.key_input.setProperty("class", "")
            self.key_status.setText("")
        elif is_valid:
            self.key_input.setStyleSheet("border-color: #22C55E;")
            self.key_status.setText("✓ Формат ключа верен")
            self.key_status.setStyleSheet(f"color: {Colors.SUCCESS};")
        else:
            self.key_input.setStyleSheet("border-color: #EF4444;")
            self.key_status.setText("Ожидается формат: ESP-XXXXX-XXXXX-XXXXX-XXXXX")
            self.key_status.setStyleSheet(f"color: {Colors.TEXT_MUTED};")

    def _set_loading(self, loading: bool):
        self.activate_btn.setEnabled(not loading)
        self.key_input.setEnabled(not loading)
        self.progress_bar.setVisible(loading)
        self.progress_label.setVisible(loading)
        if loading:
            self.activate_btn.setText("Активация...")
        else:
            self.activate_btn.setText("Активировать")

    def _update_progress(self, step: int, message: str):
        """Обновляет прогресс (вызывается из потока — безопасно через сигналы)."""
        self.progress_bar.setValue(step)
        self.progress_label.setText(message)

    def _activate(self):
        key = self.key_input.text().strip().upper()
        if not validate_key_format(key):
            return

        self._set_loading(True)
        self.result_label.setVisible(False)

        def run():
            def on_progress(step, msg):
                # Qt-безопасное обновление через QTimer
                QTimer.singleShot(0, lambda: self._update_progress(step, msg))

            success, message = activate_license(key, on_progress)

            def on_done():
                self._set_loading(False)
                self.result_label.setVisible(True)
                self.result_label.setText(message)
                if success:
                    self.result_label.setStyleSheet(f"color: {Colors.SUCCESS};")
                    # Небольшая задержка перед переходом на главный экран
                    from core.license import check_license
                    valid, info, _ = check_license()
                    if valid and info:
                        QTimer.singleShot(1500, lambda: self.activation_success.emit(info))
                else:
                    self.result_label.setStyleSheet(f"color: {Colors.ERROR};")

            QTimer.singleShot(0, on_done)

        threading.Thread(target=run, daemon=True).start()
