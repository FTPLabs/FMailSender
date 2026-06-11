"""
Экран активации лицензии.
Фикс: адаптивная вёрстка — текст и элементы не растягиваются вместе с окном.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QProgressBar, QFrame, QSizePolicy, QSpacerItem,
    QApplication
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QClipboard
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtCore import QByteArray

from core.license import activate_license, generate_hwid, LicenseInfo, DEMO_KEY, KEY_PREFIX
from gui.theme import Colors, Spacing, Typography, Radii


MAIL_ICON_SVG = b"""<svg width="52" height="52" viewBox="0 0 52 52" xmlns="http://www.w3.org/2000/svg">
<defs>
  <linearGradient id="g1" x1="0%" y1="0%" x2="100%" y2="100%">
    <stop offset="0%" style="stop-color:#7C3AED"/>
    <stop offset="100%" style="stop-color:#06B6D4"/>
  </linearGradient>
</defs>
<rect width="52" height="52" rx="14" fill="url(#g1)" opacity="0.15"/>
<rect x="2" y="2" width="48" height="48" rx="12" fill="none" stroke="url(#g1)" stroke-width="2"/>
<rect x="10" y="16" width="32" height="20" rx="3" fill="none" stroke="#8B5CF6" stroke-width="1.8"/>
<path d="M10 18 L26 28 L42 18" stroke="#06B6D4" stroke-width="1.8" fill="none" stroke-linecap="round"/>
</svg>"""


class ActivationWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str, object)

    def __init__(self, key: str):
        super().__init__()
        self._key = key

    def run(self):
        def _cb(step: int, msg: str):
            self.progress.emit(step, msg)

        success, message = activate_license(self._key, progress_callback=_cb)
        if success:
            from core.license import check_license
            valid, info, _ = check_license()
            self.finished.emit(True, message, info)
        else:
            self.finished.emit(False, message, None)


class ActivationScreen(QWidget):
    activation_success = pyqtSignal(object)

    def __init__(self, hint_message: str = "", parent=None):
        super().__init__(parent)
        self._hwid = generate_hwid()
        self._worker: ActivationWorker = None
        self._hint = hint_message
        self._setup_ui()

    def _setup_ui(self):
        # Root layout fills full widget
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Outer centering — no fixed sizes, uses stretch
        root.addStretch(1)

        # Card — fixed max-width, but horizontally centered via stretch
        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.addStretch(1)

        card = QFrame()
        card.setObjectName("activation_card")
        card.setStyleSheet(f"""
            QFrame#activation_card {{
                background: rgba(10, 10, 26, 0.95);
                border: 1px solid rgba(139, 92, 246, 0.35);
                border-radius: 20px;
            }}
        """)
        # Constrain width but allow height to grow naturally
        card.setMinimumWidth(420)
        card.setMaximumWidth(560)
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 36, 40, 36)
        card_layout.setSpacing(0)

        # ── Icon ────────────────────────────────────────────────────────
        icon_row = QHBoxLayout()
        icon_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_svg = QSvgWidget()
        icon_svg.load(QByteArray(MAIL_ICON_SVG))
        icon_svg.setFixedSize(52, 52)
        icon_row.addWidget(icon_svg)
        card_layout.addLayout(icon_row)
        card_layout.addSpacing(16)

        # ── Title ────────────────────────────────────────────────────────
        title = QLabel("FMail Sender Pro")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"font-size: 22px; font-weight: bold; color: {Colors.TEXT_PRIMARY}; background: transparent;"
        )
        card_layout.addWidget(title)
        card_layout.addSpacing(6)

        subtitle = QLabel("Введите лицензионный ключ для активации")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 13px; background: transparent;")
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(20)

        # ── Demo key hint ────────────────────────────────────────────────
        demo_frame = QFrame()
        demo_frame.setStyleSheet(
            "background: rgba(6,182,212,0.08); border: 1px solid rgba(6,182,212,0.25); border-radius: 8px;"
        )
        demo_lay = QHBoxLayout(demo_frame)
        demo_lay.setContentsMargins(12, 8, 12, 8)
        demo_lbl = QLabel(f"Демо-ключ для тестирования")
        demo_lbl.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 11px; background: transparent;")
        demo_val = QLabel(f"<b style='color:{Colors.CYAN};'>{DEMO_KEY}</b>")
        demo_val.setTextFormat(Qt.TextFormat.RichText)
        demo_val.setStyleSheet("background: transparent;")
        demo_lay.addWidget(demo_lbl)
        demo_lay.addStretch()

        btn_copy_demo = QPushButton("Скопировать")
        btn_copy_demo.setObjectName("btn_secondary")
        btn_copy_demo.setFixedHeight(26)
        btn_copy_demo.setStyleSheet(
            f"font-size:11px; padding: 0 8px; border-radius: 5px; "
            f"background: rgba(6,182,212,0.12); color: {Colors.CYAN}; border: 1px solid rgba(6,182,212,0.25);"
        )
        btn_copy_demo.clicked.connect(lambda: self._fill_key(DEMO_KEY))
        btn_copy_demo.setCursor(Qt.CursorShape.PointingHandCursor)

        btn_fill_demo = QPushButton("Заполнить")
        btn_fill_demo.setObjectName("btn_secondary")
        btn_fill_demo.setFixedHeight(26)
        btn_fill_demo.setStyleSheet(
            f"font-size:11px; padding: 0 8px; border-radius: 5px; "
            f"background: rgba(139,92,246,0.12); color: {Colors.ACCENT}; border: 1px solid rgba(139,92,246,0.25);"
        )
        btn_fill_demo.clicked.connect(lambda: self._fill_key(DEMO_KEY))
        btn_fill_demo.setCursor(Qt.CursorShape.PointingHandCursor)

        demo_lay.addWidget(btn_copy_demo)
        demo_lay.addSpacing(4)
        demo_lay.addWidget(btn_fill_demo)
        card_layout.addWidget(demo_frame)
        card_layout.addSpacing(16)

        # ── HWID ─────────────────────────────────────────────────────────
        hwid_row = QHBoxLayout()
        hwid_lbl = QLabel("HWID:")
        hwid_lbl.setFixedWidth(46)
        hwid_lbl.setStyleSheet(f"color: {Colors.CYAN}; font-size: 12px; font-weight: 600; background: transparent;")

        self.hwid_input = QLineEdit(self._hwid)
        self.hwid_input.setReadOnly(True)
        self.hwid_input.setStyleSheet(
            f"background: rgba(255,255,255,0.04); border: 1px solid rgba(139,92,246,0.18); "
            f"border-radius: 7px; color: {Colors.TEXT_SECONDARY}; font-size: 12px; padding: 5px 10px;"
        )

        btn_copy_hwid = QPushButton("Копировать HWID")
        btn_copy_hwid.setObjectName("btn_secondary")
        btn_copy_hwid.setFixedHeight(32)
        btn_copy_hwid.setStyleSheet(
            f"font-size:12px; padding: 0 12px; border-radius: 7px; "
            f"background: rgba(139,92,246,0.12); color: {Colors.TEXT_SECONDARY}; border: 1px solid rgba(139,92,246,0.20);"
        )
        btn_copy_hwid.clicked.connect(self._copy_hwid)
        btn_copy_hwid.setCursor(Qt.CursorShape.PointingHandCursor)

        hwid_row.addWidget(hwid_lbl)
        hwid_row.addWidget(self.hwid_input, 1)
        hwid_row.addSpacing(8)
        hwid_row.addWidget(btn_copy_hwid)
        card_layout.addLayout(hwid_row)
        card_layout.addSpacing(14)

        # ── License key input ────────────────────────────────────────────
        key_lbl = QLabel("Лицензионный ключ")
        key_lbl.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 11px; background: transparent;")
        card_layout.addWidget(key_lbl)
        card_layout.addSpacing(4)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText(f"{KEY_PREFIX}-XXXXXX-XXXXXX-XXXXXX-XXXXXX")
        self.key_input.setMinimumHeight(40)
        self.key_input.setStyleSheet(
            f"background: rgba(255,255,255,0.04); border: 1px solid rgba(139,92,246,0.28); "
            f"border-radius: 9px; color: {Colors.TEXT_PRIMARY}; font-size: 14px; "
            f"font-family: 'Consolas', monospace; padding: 8px 14px; letter-spacing: 1px;"
        )
        self.key_input.returnPressed.connect(self._start_activation)
        card_layout.addWidget(self.key_input)
        card_layout.addSpacing(6)

        # ── Status / hint ────────────────────────────────────────────────
        self.status_label = QLabel(self._hint or "Активация...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 12px; background: transparent;")
        card_layout.addWidget(self.status_label)
        card_layout.addSpacing(8)

        # ── Progress bar ─────────────────────────────────────────────────
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 4)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(5)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        card_layout.addWidget(self.progress_bar)
        card_layout.addSpacing(16)

        # ── Activate button ──────────────────────────────────────────────
        self.btn_activate = QPushButton("Активировать")
        self.btn_activate.setMinimumHeight(44)
        self.btn_activate.setStyleSheet(
            "font-size: 15px; font-weight: 600; border-radius: 10px; "
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            "  stop:0 #7C3AED, stop:1 #06B6D4); "
            "color: white; border: none;"
        )
        self.btn_activate.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_activate.clicked.connect(self._start_activation)
        card_layout.addWidget(self.btn_activate)

        h_layout.addWidget(card)
        h_layout.addStretch(1)
        root.addLayout(h_layout)
        root.addStretch(1)

    def _fill_key(self, key: str):
        self.key_input.setText(key)
        QApplication.clipboard().setText(key)

    def _copy_hwid(self):
        QApplication.clipboard().setText(self._hwid)
        self.status_label.setText("HWID скопирован!")
        self.status_label.setStyleSheet(f"color: {Colors.CYAN}; font-size: 12px; background: transparent;")

    def _start_activation(self):
        key = self.key_input.text().strip()
        if not key:
            self._set_error("Введите лицензионный ключ")
            return

        self.btn_activate.setEnabled(False)
        self.btn_activate.setText("Активация...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 12px; background: transparent;")
        self.status_label.setText("Подключение к серверу...")

        self._worker = ActivationWorker(key)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, step: int, msg: str):
        self.progress_bar.setValue(step)
        self.status_label.setText(msg)

    def _on_finished(self, success: bool, message: str, license_info):
        self.btn_activate.setEnabled(True)
        self.btn_activate.setText("Активировать")
        self.progress_bar.setVisible(False)

        if success:
            self.status_label.setStyleSheet(
                f"color: {Colors.SUCCESS}; font-size: 12px; font-weight: 600; background: transparent;"
            )
            self.status_label.setText(f"✅ {message}")
            if license_info:
                self.activation_success.emit(license_info)
        else:
            self._set_error(message)

    def _set_error(self, msg: str):
        self.status_label.setStyleSheet(
            f"color: {Colors.ERROR}; font-size: 12px; background: transparent;"
        )
        self.status_label.setText(f"❌ {msg}")
