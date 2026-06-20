"""
Sending Screen v3.6.2
Sending controls, settings, progress, live log.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QFrame, QProgressBar, QTextEdit, QPushButton,
    QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from gui.theme import Colors, Spacing, Typography


class SendingScreen(QWidget):
    """Email sending controller with real-time progress and log."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_running = False
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(16)

        # Title
        title = QLabel("Рассылка")
        title.setObjectName("section_header")
        layout.addWidget(title)

        # Top row: settings + controls
        top = QHBoxLayout()

        # Settings card
        settings_card = QFrame()
        settings_card.setObjectName("card")
        settings_layout = QFormLayout(settings_card)
        settings_layout.setContentsMargins(18, 16, 18, 16)
        settings_layout.setSpacing(10)

        self._delay_min = QDoubleSpinBox()
        self._delay_min.setRange(0.1, 60.0)
        self._delay_min.setValue(1.0)
        self._delay_min.setSuffix(" сек")
        self._delay_min.setSingleStep(0.5)

        self._delay_max = QDoubleSpinBox()
        self._delay_max.setRange(0.1, 300.0)
        self._delay_max.setValue(3.0)
        self._delay_max.setSuffix(" сек")
        self._delay_max.setSingleStep(0.5)

        self._threads = QSpinBox()
        self._threads.setRange(1, 20)
        self._threads.setValue(3)

        self._batch_size = QSpinBox()
        self._batch_size.setRange(1, 1000)
        self._batch_size.setValue(50)

        self._mode = QComboBox()
        self._mode.addItems(["Последовательно", "Параллельно", "Warmup (прогрев)"])

        self._chk_skip_bounce = QCheckBox("Пропускать bounce-листинг")
        self._chk_skip_bounce.setStyleSheet(f"color: {Colors.TEXT_MUTED};")
        self._chk_skip_bounce.setChecked(True)

        self._chk_deduplicate = QCheckBox("Дедупликация на лету")
        self._chk_deduplicate.setStyleSheet(f"color: {Colors.TEXT_MUTED};")
        self._chk_deduplicate.setChecked(True)

        settings_layout.addRow("Задержка мин:", self._delay_min)
        settings_layout.addRow("Задержка макс:", self._delay_max)
        settings_layout.addRow("Потоки:", self._threads)
        settings_layout.addRow("Пакет:", self._batch_size)
        settings_layout.addRow("Режим:", self._mode)
        settings_layout.addRow(self._chk_skip_bounce)
        settings_layout.addRow(self._chk_deduplicate)
        top.addWidget(settings_card, 1)

        # Controls card
        ctrl_card = QFrame()
        ctrl_card.setObjectName("card")
        ctrl_layout = QVBoxLayout(ctrl_card)
        ctrl_layout.setContentsMargins(18, 16, 18, 16)
        ctrl_layout.setSpacing(12)
        ctrl_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        ctrl_title = QLabel("Управление")
        ctrl_title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-weight: 600; background: transparent; border: none;")
        ctrl_layout.addWidget(ctrl_title)

        self._btn_start = QPushButton("▶  Начать рассылку")
        self._btn_start.setObjectName("btn_primary")
        self._btn_start.setFixedHeight(42)
        self._btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_start.clicked.connect(self._toggle_sending)
        ctrl_layout.addWidget(self._btn_start)

        self._btn_pause = QPushButton("⏸  Пауза")
        self._btn_pause.setObjectName("btn_secondary")
        self._btn_pause.setFixedHeight(38)
        self._btn_pause.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_pause.setEnabled(False)
        ctrl_layout.addWidget(self._btn_pause)

        self._btn_stop = QPushButton("■  Остановить")
        self._btn_stop.setObjectName("btn_danger")
        self._btn_stop.setFixedHeight(38)
        self._btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._stop_sending)
        ctrl_layout.addWidget(self._btn_stop)

        ctrl_layout.addStretch()

        # Status indicator
        self._status_indicator = QLabel("● Готово")
        self._status_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_indicator.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: {Typography.SIZE_SM}pt; background: transparent; border: none;"
        )
        ctrl_layout.addWidget(self._status_indicator)
        top.addWidget(ctrl_card)
        layout.addLayout(top)

        # Progress
        prog_card = QFrame()
        prog_card.setObjectName("card")
        prog_layout = QVBoxLayout(prog_card)
        prog_layout.setContentsMargins(18, 14, 18, 14)
        prog_layout.setSpacing(8)

        prog_hdr = QHBoxLayout()
        prog_lbl = QLabel("Прогресс")
        prog_lbl.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-weight: 600; background: transparent; border: none;")
        prog_hdr.addWidget(prog_lbl)
        prog_hdr.addStretch()
        self._prog_count = QLabel("0 / 0")
        self._prog_count.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: {Typography.SIZE_SM}pt; background: transparent; border: none;")
        prog_hdr.addWidget(self._prog_count)
        prog_layout.addLayout(prog_hdr)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(6)
        prog_layout.addWidget(self._progress_bar)

        stat_row = QHBoxLayout()
        self._lbl_sent    = self._mini_stat("Отправлено: 0",  Colors.GREEN)
        self._lbl_errors  = self._mini_stat("Ошибок: 0",      Colors.RED)
        self._lbl_bounced = self._mini_stat("Bounce: 0",      Colors.AMBER)
        self._lbl_speed   = self._mini_stat("Скорость: —",    Colors.TEXT_MUTED)
        for lbl in (self._lbl_sent, self._lbl_errors, self._lbl_bounced, self._lbl_speed):
            stat_row.addWidget(lbl)
        stat_row.addStretch()
        prog_layout.addLayout(stat_row)
        layout.addWidget(prog_card)

        # Log
        log_card = QFrame()
        log_card.setObjectName("card")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(14, 12, 14, 12)
        log_layout.setSpacing(8)

        log_hdr = QHBoxLayout()
        log_title = QLabel("Лог рассылки")
        log_title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-weight: 600; background: transparent; border: none;")
        log_hdr.addWidget(log_title)
        log_hdr.addStretch()
        clear_btn = QPushButton("Очистить")
        clear_btn.setObjectName("btn_icon")
        clear_btn.setFixedHeight(28)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_log)
        log_hdr.addWidget(clear_btn)
        log_layout.addLayout(log_hdr)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont(Typography.FAMILY_MONO, Typography.SIZE_SM))
        self._log.setStyleSheet(
            f"background: {Colors.BG_SURFACE}; border: none; border-radius: 8px;"
            f"color: {Colors.TEXT_PRIMARY}; padding: 8px;"
        )
        log_layout.addWidget(self._log)
        layout.addWidget(log_card, 1)

    def _mini_stat(self, text: str, color: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {color}; font-size: {Typography.SIZE_SM}pt; "
            f"background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.07); "
            f"border-radius: 6px; padding: 3px 10px;"
        )
        return lbl

    def _clear_log(self):
        self._log.clear()

    def append_log(self, message: str, color: str = ""):
        if color:
            self._log.append(f'<span style="color:{color}">{message}</span>')
        else:
            self._log.append(message)
        self._log.verticalScrollBar().setValue(self._log.verticalScrollBar().maximum())

    def _toggle_sending(self):
        if not self._is_running:
            self._start_sending()
        else:
            self._stop_sending()

    def _start_sending(self):
        self._is_running = True
        self._btn_start.setText("⏸  Пауза / Остановить")
        self._btn_start.setObjectName("btn_danger")
        self._btn_start.style().unpolish(self._btn_start)
        self._btn_start.style().polish(self._btn_start)
        self._btn_stop.setEnabled(True)
        self._status_indicator.setText("● Отправка...")
        self._status_indicator.setStyleSheet(
            f"color: {Colors.GREEN}; font-size: {Typography.SIZE_SM}pt; background: transparent; border: none;"
        )
        self.append_log("▶ Рассылка запущена", Colors.GREEN)

    def _stop_sending(self):
        self._is_running = False
        self._btn_start.setText("▶  Начать рассылку")
        self._btn_start.setObjectName("btn_primary")
        self._btn_start.style().unpolish(self._btn_start)
        self._btn_start.style().polish(self._btn_start)
        self._btn_pause.setEnabled(False)
        self._btn_stop.setEnabled(False)
        self._status_indicator.setText("● Остановлено")
        self._status_indicator.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: {Typography.SIZE_SM}pt; background: transparent; border: none;"
        )
        self.append_log("■ Рассылка остановлена", Colors.AMBER)

    def update_progress(self, sent: int, total: int, errors: int = 0,
                        bounced: int = 0, speed: float = 0.0):
        pct = int(sent / total * 100) if total > 0 else 0
        self._progress_bar.setValue(pct)
        self._prog_count.setText(f"{sent} / {total}")
        self._lbl_sent.setText(f"Отправлено: {sent}")
        self._lbl_errors.setText(f"Ошибок: {errors}")
        self._lbl_bounced.setText(f"Bounce: {bounced}")
        self._lbl_speed.setText(f"Скорость: {speed:.1f}/мин")

    def get_settings(self) -> dict:
        return {
            "delay_min": self._delay_min.value(),
            "delay_max": self._delay_max.value(),
            "threads":   self._threads.value(),
            "batch":     self._batch_size.value(),
            "mode":      self._mode.currentText(),
            "skip_bounce": self._chk_skip_bounce.isChecked(),
            "dedup":     self._chk_deduplicate.isChecked(),
        }
