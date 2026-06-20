"""
Dashboard Screen v3.6.2
Real-time stats, KPI cards, sending progress, live log.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QTextEdit, QProgressBar, QPushButton,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from gui.theme import Colors, Spacing, Typography


def _card() -> QFrame:
    f = QFrame()
    f.setObjectName("card")
    return f


def _kpi_card(title: str, value: str, color: str = Colors.ACCENT_LIGHT) -> QFrame:
    card = QFrame()
    card.setObjectName("kpi_card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(6)

    t = QLabel(title.upper())
    t.setObjectName("label_kpi_title")
    layout.addWidget(t)

    v = QLabel(value)
    v.setObjectName("label_kpi_value")
    v.setStyleSheet(f"color: {color}; font-size: {Typography.SIZE_2XL}pt; font-weight: 700; background: transparent; border: none;")
    layout.addWidget(v)

    return card, v


class DashboardScreen(QWidget):
    """Main dashboard: KPIs, progress, live activity log."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._start_demo_updates()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(18)

        # Title
        title = QLabel("Дашборд")
        title.setObjectName("section_header")
        layout.addWidget(title)

        # ── KPI Row ──────────────────────────────────────────────────────
        kpi_row = QWidget()
        kpi_row.setStyleSheet("background: transparent;")
        kpi_layout = QHBoxLayout(kpi_row)
        kpi_layout.setContentsMargins(0, 0, 0, 0)
        kpi_layout.setSpacing(14)

        card1, self._kpi_sent     = _kpi_card("Отправлено",   "0",      Colors.ACCENT_LIGHT)
        card2, self._kpi_success  = _kpi_card("Успешно",      "0",      Colors.GREEN)
        card3, self._kpi_bounce   = _kpi_card("Bounce",       "0",      Colors.AMBER)
        card4, self._kpi_accounts = _kpi_card("Аккаунты",     "0 / 0",  Colors.BLUE)

        kpi_layout.addWidget(card1)
        kpi_layout.addWidget(card2)
        kpi_layout.addWidget(card3)
        kpi_layout.addWidget(card4)
        layout.addWidget(kpi_row)

        # ── Progress ─────────────────────────────────────────────────────
        progress_card = _card()
        progress_layout = QVBoxLayout(progress_card)
        progress_layout.setContentsMargins(18, 16, 18, 16)
        progress_layout.setSpacing(10)

        prog_header = QHBoxLayout()
        prog_title = QLabel("Прогресс рассылки")
        prog_title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-weight: 600; background: transparent; border: none;")
        prog_header.addWidget(prog_title)
        prog_header.addStretch()
        self._prog_label = QLabel("0 / 0")
        self._prog_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: {Typography.SIZE_SM}pt; background: transparent; border: none;")
        prog_header.addWidget(self._prog_label)
        progress_layout.addLayout(prog_header)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(6)
        progress_layout.addWidget(self._progress_bar)

        # Speed / ETA row
        eta_row = QHBoxLayout()
        self._speed_label = QLabel("Скорость: — писем/мин")
        self._speed_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: {Typography.SIZE_SM}pt; background: transparent; border: none;")
        eta_row.addWidget(self._speed_label)
        eta_row.addStretch()
        self._eta_label = QLabel("ETA: —")
        self._eta_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: {Typography.SIZE_SM}pt; background: transparent; border: none;")
        eta_row.addWidget(self._eta_label)
        progress_layout.addLayout(eta_row)
        layout.addWidget(progress_card)

        # ── Live Log ─────────────────────────────────────────────────────
        log_card = _card()
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(18, 14, 18, 14)
        log_layout.setSpacing(10)

        log_header = QHBoxLayout()
        log_title = QLabel("Live-лог")
        log_title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-weight: 600; background: transparent; border: none;")
        log_header.addWidget(log_title)
        log_header.addStretch()
        clear_btn = QPushButton("Очистить")
        clear_btn.setObjectName("btn_icon")
        clear_btn.setFixedHeight(28)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_log)
        log_header.addWidget(clear_btn)
        log_layout.addLayout(log_header)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont(Typography.FAMILY_MONO, Typography.SIZE_SM))
        self._log.setStyleSheet(
            f"background: {Colors.BG_SURFACE}; border: none; border-radius: 8px;"
            f"color: {Colors.TEXT_PRIMARY}; padding: 8px;"
        )
        self._log.setMinimumHeight(200)
        log_layout.addWidget(self._log)
        layout.addWidget(log_card, 1)

    def _clear_log(self):
        self._log.clear()

    def append_log(self, message: str, color: str = ""):
        if color:
            self._log.append(f'<span style="color:{color}">{message}</span>')
        else:
            self._log.append(message)
        self._log.verticalScrollBar().setValue(
            self._log.verticalScrollBar().maximum()
        )

    def update_stats(self, sent: int, success: int, bounce: int,
                     accounts_active: int, accounts_total: int,
                     progress: int, total: int,
                     speed: float = 0.0, eta: str = "—"):
        self._kpi_sent.setText(str(sent))
        self._kpi_success.setText(str(success))
        self._kpi_bounce.setText(str(bounce))
        self._kpi_accounts.setText(f"{accounts_active} / {accounts_total}")
        pct = int(sent / total * 100) if total > 0 else 0
        self._progress_bar.setValue(pct)
        self._prog_label.setText(f"{sent} / {total}")
        self._speed_label.setText(f"Скорость: {speed:.1f} писем/мин")
        self._eta_label.setText(f"ETA: {eta}")

    def _start_demo_updates(self):
        self.append_log(
            "✦ FMailSender v3.6.2 запущен", Colors.ACCENT_LIGHT
        )
        self.append_log("Система готова к работе.", Colors.GREEN)
