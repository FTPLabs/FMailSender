"""
Экран 5: Рассылка.
Настройки потоков, задержки, расписание, прогресс, пауза/стоп.
"""
import asyncio
import queue
import threading
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QSpinBox, QFrame, QProgressBar, QListWidget,
    QListWidgetItem, QDateTimeEdit, QCheckBox, QGroupBox,
    QMessageBox, QSplitter
)
from PyQt6.QtCore import Qt, QTimer, QDateTime, pyqtSignal
from PyQt6.QtGui import QColor

from core.sender import (
    SendingEngine, SmtpAccount, Recipient, EmailTemplate,
    CampaignConfig, SendResult
)
from gui.theme import Colors, Spacing


class SendingScreen(QWidget):
    """Экран управления рассылкой."""

    campaign_started = pyqtSignal()
    campaign_finished = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._accounts: list[SmtpAccount] = []
        self._recipients: list[Recipient] = []
        self._template: EmailTemplate = None
        self._engine: SendingEngine = None
        self._log_queue: queue.Queue = queue.Queue()
        self._is_running = False
        self._start_time: float = 0.0
        self._sent = 0
        self._total = 0

        self._setup_ui()

        # Таймер для обновления GUI из очереди логов
        self._gui_timer = QTimer()
        self._gui_timer.setInterval(200)
        self._gui_timer.timeout.connect(self._flush_log_queue)
        self._gui_timer.start()

        # Таймер скорости
        self._speed_timer = QTimer()
        self._speed_timer.setInterval(5000)
        self._speed_timer.timeout.connect(self._update_speed)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        layout.setSpacing(Spacing.LG)

        # ── Заголовок ────────────────────────────
        title = QLabel("Запуск рассылки")
        title.setObjectName("section_header")
        layout.addWidget(title)

        # ── Статус подготовки ────────────────────
        self.status_card = QFrame()
        self.status_card.setObjectName("card")
        status_layout = QHBoxLayout(self.status_card)

        self.accounts_status = _status_chip("Аккаунты: —")
        self.recipients_status = _status_chip("Получатели: —")
        self.template_status = _status_chip("Письмо: —")

        status_layout.addWidget(self.accounts_status)
        status_layout.addWidget(self.recipients_status)
        status_layout.addWidget(self.template_status)
        status_layout.addStretch()
        layout.addWidget(self.status_card)

        # ── Разделитель ───────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Левая часть — настройки
        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)
        settings_layout.setSpacing(Spacing.LG)
        settings_layout.setContentsMargins(0, 0, 0, 0)

        # Потоки
        threads_group = QGroupBox("Потоки отправки")
        threads_layout = QVBoxLayout(threads_group)

        threads_row = QHBoxLayout()
        self.threads_label = QLabel("Потоков: 5")
        self.threads_label.setObjectName("label_subtitle")
        threads_row.addWidget(self.threads_label)
        threads_row.addStretch()
        threads_layout.addLayout(threads_row)

        self.threads_slider = QSlider(Qt.Orientation.Horizontal)
        self.threads_slider.setRange(1, 50)
        self.threads_slider.setValue(5)
        self.threads_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.threads_slider.setTickInterval(10)
        self.threads_slider.valueChanged.connect(
            lambda v: self.threads_label.setText(f"Потоков: {v}")
        )
        threads_layout.addWidget(self.threads_slider)

        hint = QLabel("Рекомендуется 5-15 для стабильной доставки")
        hint.setObjectName("label_muted")
        threads_layout.addWidget(hint)
        settings_layout.addWidget(threads_group)

        # Задержки
        delays_group = QGroupBox("Задержки между письмами")
        delays_layout = QFormLayout(delays_group)

        self.min_delay_spin = QSpinBox()
        self.min_delay_spin.setRange(0, 60000)
        self.min_delay_spin.setValue(500)
        self.min_delay_spin.setSuffix(" мс")
        delays_layout.addRow("Минимальная:", self.min_delay_spin)

        self.max_delay_spin = QSpinBox()
        self.max_delay_spin.setRange(0, 300000)
        self.max_delay_spin.setValue(2000)
        self.max_delay_spin.setSuffix(" мс")
        delays_layout.addRow("Максимальная:", self.max_delay_spin)

        self.pause_after_spin = QSpinBox()
        self.pause_after_spin.setRange(1, 10000)
        self.pause_after_spin.setValue(50)
        self.pause_after_spin.setSuffix(" писем")
        delays_layout.addRow("Пауза после:", self.pause_after_spin)

        self.pause_duration_spin = QSpinBox()
        self.pause_duration_spin.setRange(1, 3600)
        self.pause_duration_spin.setValue(60)
        self.pause_duration_spin.setSuffix(" сек")
        delays_layout.addRow("Длительность паузы:", self.pause_duration_spin)

        settings_layout.addWidget(delays_group)

        # Расписание
        schedule_group = QGroupBox("Расписание")
        schedule_layout = QVBoxLayout(schedule_group)

        self.schedule_check = QCheckBox("Отложить запуск")
        self.schedule_check.stateChanged.connect(self._on_schedule_changed)
        schedule_layout.addWidget(self.schedule_check)

        self.datetime_picker = QDateTimeEdit()
        self.datetime_picker.setDateTime(QDateTime.currentDateTime().addSecs(3600))
        self.datetime_picker.setCalendarPopup(True)
        self.datetime_picker.setEnabled(False)
        schedule_layout.addWidget(self.datetime_picker)

        settings_layout.addWidget(schedule_group)
        settings_layout.addStretch()

        # Кнопки управления
        controls_layout = QHBoxLayout()

        self.start_btn = QPushButton("▶ Запустить рассылку")
        self.start_btn.setObjectName("btn_success")
        self.start_btn.setFixedHeight(44)
        self.start_btn.clicked.connect(self._start_campaign)
        controls_layout.addWidget(self.start_btn)

        self.pause_btn = QPushButton("⏸ Пауза")
        self.pause_btn.setEnabled(False)
        self.pause_btn.setFixedHeight(44)
        self.pause_btn.clicked.connect(self._toggle_pause)
        controls_layout.addWidget(self.pause_btn)

        self.stop_btn = QPushButton("⏹ Стоп")
        self.stop_btn.setObjectName("btn_danger")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setFixedHeight(44)
        self.stop_btn.clicked.connect(self._stop_campaign)
        controls_layout.addWidget(self.stop_btn)

        settings_layout.addLayout(controls_layout)
        splitter.addWidget(settings_widget)

        # Правая часть — прогресс и лог
        progress_widget = QWidget()
        progress_layout = QVBoxLayout(progress_widget)
        progress_layout.setSpacing(Spacing.MD)
        progress_layout.setContentsMargins(0, 0, 0, 0)

        # KPI в реальном времени
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(Spacing.SM)
        self.kpi_sent_lbl = _kpi_mini("Отправлено", "0")
        self.kpi_success_lbl = _kpi_mini("Успешно", "0", Colors.SUCCESS)
        self.kpi_errors_lbl = _kpi_mini("Ошибки", "0", Colors.ERROR)
        self.kpi_speed_lbl = _kpi_mini("Скорость", "0/мин")
        self.kpi_eta_lbl = _kpi_mini("Оставшееся", "—")

        for kpi in [self.kpi_sent_lbl, self.kpi_success_lbl, self.kpi_errors_lbl,
                    self.kpi_speed_lbl, self.kpi_eta_lbl]:
            kpi_row.addWidget(kpi)
        progress_layout.addLayout(kpi_row)

        # Прогресс-бар
        progress_label_row = QHBoxLayout()
        progress_label_row.addWidget(QLabel("Прогресс:"))
        self.progress_pct_label = QLabel("0%")
        self.progress_pct_label.setObjectName("label_muted")
        progress_label_row.addWidget(self.progress_pct_label)
        progress_label_row.addStretch()
        progress_layout.addLayout(progress_label_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

        # Лог событий
        log_label = QLabel("Лог событий:")
        log_label.setObjectName("label_muted")
        progress_layout.addWidget(log_label)

        self.log_list = QListWidget()
        self.log_list.setAlternatingRowColors(True)
        progress_layout.addWidget(self.log_list, 1)

        # Кнопка очистки лога
        clear_btn = QPushButton("Очистить лог")
        clear_btn.setObjectName("btn_icon")
        clear_btn.clicked.connect(self.log_list.clear)
        progress_layout.addWidget(clear_btn, 0, Qt.AlignmentFlag.AlignRight)

        splitter.addWidget(progress_widget)
        splitter.setSizes([380, 620])
        layout.addWidget(splitter, 1)

    def _on_schedule_changed(self, state):
        self.datetime_picker.setEnabled(bool(state))

    def set_accounts(self, accounts: list) -> None:
        self._accounts = accounts
        count = len(accounts)
        active = sum(1 for a in accounts if a.is_active)
        self.accounts_status.setText(f"Аккаунты: {active}/{count}")
        self.accounts_status.setStyleSheet(
            f"color: {Colors.SUCCESS};" if active > 0 else f"color: {Colors.ERROR};"
        )

    def set_recipients(self, recipients: list) -> None:
        self._recipients = recipients
        self.recipients_status.setText(f"Получатели: {len(recipients)}")
        self.recipients_status.setStyleSheet(f"color: {Colors.SUCCESS};")

    def set_template(self, template) -> None:
        self._template = template
        self.template_status.setText("Письмо: ✓ Готово")
        self.template_status.setStyleSheet(f"color: {Colors.SUCCESS};")

    def _validate_ready(self) -> bool:
        if not self._accounts or not any(a.is_active for a in self._accounts):
            QMessageBox.warning(self, "Нет аккаунтов", "Добавьте хотя бы один активный SMTP-аккаунт")
            return False
        if not self._recipients:
            QMessageBox.warning(self, "Нет получателей", "Загрузите список получателей")
            return False
        if not self._template or not self._template.subject:
            QMessageBox.warning(self, "Нет письма", "Создайте письмо для рассылки")
            return False
        return True

    def _start_campaign(self):
        if not self._validate_ready():
            return

        threads = self.threads_slider.value()
        config = CampaignConfig(
            min_delay_ms=self.min_delay_spin.value(),
            max_delay_ms=self.max_delay_spin.value(),
            pause_after_n=self.pause_after_spin.value(),
            pause_duration_sec=self.pause_duration_spin.value(),
            max_threads=threads,
        )

        self._engine = SendingEngine(
            accounts=self._accounts,
            config=config,
            log_queue=self._log_queue,
        )
        self._total = len(self._recipients)
        self._sent = 0
        self._start_time = __import__("time").time()

        self.progress_bar.setMaximum(self._total)
        self.progress_bar.setValue(0)

        self._engine.on_progress = self._on_progress
        self._engine.on_finished = self._on_finished

        self._is_running = True
        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self._speed_timer.start()
        self.campaign_started.emit()

        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self._engine.run_campaign(self._recipients, self._template)
            )
            loop.close()

        threading.Thread(target=run, daemon=True).start()

    def _on_progress(self, sent: int, total: int, result: SendResult):
        """Вызывается из воркера — обновляет GUI через очередь."""
        self._log_queue.put_nowait({
            "type": "progress",
            "sent": sent,
            "total": total,
            "result": result,
        })

    def _on_finished(self, results: list):
        self._log_queue.put_nowait({"type": "finished", "results": results})

    def _flush_log_queue(self):
        """Вытаскивает сообщения из очереди и обновляет GUI (вызывается в главном потоке)."""
        while not self._log_queue.empty():
            try:
                item = self._log_queue.get_nowait()
            except queue.Empty:
                break

            if isinstance(item, dict) and item.get("type") == "progress":
                sent = item["sent"]
                total = item["total"]
                result: SendResult = item["result"]

                self._sent = sent
                self.progress_bar.setValue(sent)
                pct = int(sent / total * 100) if total > 0 else 0
                self.progress_pct_label.setText(f"{pct}%")

                stats = self._engine.stats if self._engine else {}
                self.kpi_sent_lbl.findChild(QLabel, "value").setText(str(sent))
                self.kpi_success_lbl.findChild(QLabel, "value").setText(str(stats.get("success", 0)))
                self.kpi_errors_lbl.findChild(QLabel, "value").setText(str(stats.get("errors", 0)))

                # Лог
                icon = "✓" if result.success else "✗"
                color = Colors.SUCCESS if result.success else Colors.ERROR
                item_widget = QListWidgetItem(f"[{result.recipient_email}] {icon} {result.error if not result.success else 'отправлено'}")
                item_widget.setForeground(QColor(color))
                self.log_list.insertItem(0, item_widget)
                if self.log_list.count() > 200:
                    self.log_list.takeItem(self.log_list.count() - 1)

            elif isinstance(item, dict) and item.get("type") == "finished":
                self._is_running = False
                self.start_btn.setEnabled(True)
                self.pause_btn.setEnabled(False)
                self.stop_btn.setEnabled(False)
                self._speed_timer.stop()
                self.campaign_finished.emit(item.get("results", []))

                results = item.get("results", [])
                succ = sum(1 for r in results if r.success)
                fail = sum(1 for r in results if not r.success)
                self._add_log(f"Кампания завершена. Успешно: {succ}, Ошибок: {fail}")

            elif isinstance(item, dict) and "msg" in item:
                level = item.get("level", "INFO")
                color = Colors.TEXT_SECONDARY
                if level == "ERROR":
                    color = Colors.ERROR
                elif level == "WARN":
                    color = Colors.WARNING
                log_item = QListWidgetItem(f"[{item['time'][-8:]}] {item['msg']}")
                log_item.setForeground(QColor(color))
                self.log_list.insertItem(0, log_item)

    def _add_log(self, msg: str, color: str = Colors.TEXT_SECONDARY):
        item = QListWidgetItem(msg)
        item.setForeground(QColor(color))
        self.log_list.insertItem(0, item)

    def _update_speed(self):
        if not self._is_running:
            return
        elapsed = __import__("time").time() - self._start_time
        if elapsed > 0:
            speed = int(self._sent / elapsed * 60)
            self.kpi_speed_lbl.findChild(QLabel, "value").setText(f"{speed}/мин")
            remaining = self._total - self._sent
            if speed > 0:
                eta_min = remaining / speed
                self.kpi_eta_lbl.findChild(QLabel, "value").setText(f"{eta_min:.0f} мин")

    def _toggle_pause(self):
        if not self._engine:
            return
        if self._engine._is_paused:
            self._engine.resume()
            self.pause_btn.setText("⏸ Пауза")
            self._add_log("Рассылка возобновлена", Colors.SUCCESS)
        else:
            self._engine.pause()
            self.pause_btn.setText("▶ Продолжить")
            self._add_log("Рассылка приостановлена", Colors.WARNING)

    def _stop_campaign(self):
        reply = QMessageBox.question(
            self, "Остановить рассылку",
            "Вы уверены, что хотите остановить рассылку?\nОтправленные письма нельзя вернуть.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self._engine:
                self._engine.stop()
            self._add_log("Остановка рассылки...", Colors.ERROR)


def _status_chip(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"background: {Colors.BG_SURFACE3}; color: {Colors.TEXT_MUTED};"
        f"padding: 4px 10px; border-radius: 4px; font-size: 12px;"
    )
    return lbl


def _kpi_mini(title: str, value: str, color: str = Colors.TEXT_PRIMARY) -> QFrame:
    frame = QFrame()
    frame.setObjectName("kpi_card")
    frame.setFixedHeight(64)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(Spacing.MD, Spacing.SM, Spacing.MD, Spacing.SM)
    layout.setSpacing(2)

    val_lbl = QLabel(value)
    val_lbl.setObjectName("value")
    val_lbl.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {color};")
    layout.addWidget(val_lbl)

    title_lbl = QLabel(title.upper())
    title_lbl.setObjectName("label_kpi_title")
    layout.addWidget(title_lbl)

    return frame
