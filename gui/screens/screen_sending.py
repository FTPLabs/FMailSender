"""
Экран 5: Рассылка. Потоки, задержки, расписание, прогресс, лог.
"""
import asyncio
import queue
import threading
import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QSpinBox, QFrame, QProgressBar, QListWidget,
    QListWidgetItem, QDateTimeEdit, QCheckBox, QGroupBox,
    QFormLayout, QMessageBox, QSplitter
)
from PyQt6.QtCore import Qt, QTimer, QDateTime, pyqtSignal
from core.sender import SendingEngine, SmtpAccount, Recipient, EmailTemplate, CampaignConfig, SendResult
from gui.theme import Colors, Spacing


def _status_chip(text):
    lbl = QLabel(text)
    lbl.setObjectName("label_muted")
    return lbl


def _kpi_mini(title, value, color=None):
    color = color or Colors.TEXT_PRIMARY
    card = QFrame()
    card.setObjectName("kpi_card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(2)
    val_lbl = QLabel(value)
    val_lbl.setStyleSheet(f"font-size:18px;font-weight:bold;color:{color};")
    val_lbl.setObjectName("_kpi_val")
    layout.addWidget(val_lbl)
    title_lbl = QLabel(title.upper())
    title_lbl.setObjectName("label_kpi_title")
    layout.addWidget(title_lbl)
    return card


class SendingScreen(QWidget):
    campaign_started = pyqtSignal()
    campaign_finished = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._accounts = []
        self._recipients = []
        self._template = None
        self._engine = None
        self._log_queue = queue.Queue()
        self._is_running = False
        self._start_time = 0.0
        self._sent = 0
        self._total = 0
        self._setup_ui()
        self._gui_timer = QTimer()
        self._gui_timer.setInterval(200)
        self._gui_timer.timeout.connect(self._flush_log_queue)
        self._gui_timer.start()
        self._manually_stopped = False
        self._speed_timer = QTimer()
        self._speed_timer.setInterval(5000)
        self._speed_timer.timeout.connect(self._update_speed)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        layout.setSpacing(Spacing.LG)
        title = QLabel("Запуск рассылки")
        title.setObjectName("section_header")
        layout.addWidget(title)
        status_card = QFrame()
        status_card.setObjectName("card")
        sl = QHBoxLayout(status_card)
        self.accounts_status = _status_chip("Аккаунты: —")
        self.recipients_status = _status_chip("Получатели: —")
        self.template_status = _status_chip("Письмо: —")
        for w in [self.accounts_status, self.recipients_status, self.template_status]:
            sl.addWidget(w)
        sl.addStretch()
        layout.addWidget(status_card)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setSpacing(Spacing.LG)
        ll.setContentsMargins(0, 0, 0, 0)
        tg = QGroupBox("Потоки отправки")
        tgl = QVBoxLayout(tg)
        trow = QHBoxLayout()
        self.threads_label = QLabel("Потоков: 5")
        self.threads_label.setObjectName("label_subtitle")
        trow.addWidget(self.threads_label)
        trow.addStretch()
        tgl.addLayout(trow)
        self.threads_slider = QSlider(Qt.Orientation.Horizontal)
        self.threads_slider.setRange(1, 50)
        self.threads_slider.setValue(5)
        self.threads_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.threads_slider.setTickInterval(10)
        self.threads_slider.valueChanged.connect(lambda v: self.threads_label.setText(f"Потоков: {v}"))
        tgl.addWidget(self.threads_slider)
        hint = QLabel("Рекомендуется 5-15 для стабильной доставки")
        hint.setObjectName("label_muted")
        tgl.addWidget(hint)
        ll.addWidget(tg)
        dg = QGroupBox("Задержки между письмами")
        dgl = QFormLayout(dg)
        self.min_delay_spin = QSpinBox()
        self.min_delay_spin.setRange(0, 60000)
        self.min_delay_spin.setValue(500)
        self.min_delay_spin.setSuffix(" мс")
        dgl.addRow("Минимальная:", self.min_delay_spin)
        self.max_delay_spin = QSpinBox()
        self.max_delay_spin.setRange(0, 300000)
        self.max_delay_spin.setValue(2000)
        self.max_delay_spin.setSuffix(" мс")
        dgl.addRow("Максимальная:", self.max_delay_spin)
        self.pause_after_spin = QSpinBox()
        self.pause_after_spin.setRange(1, 10000)
        self.pause_after_spin.setValue(50)
        self.pause_after_spin.setSuffix(" писем")
        dgl.addRow("Пауза после:", self.pause_after_spin)
        self.pause_duration_spin = QSpinBox()
        self.pause_duration_spin.setRange(1, 3600)
        self.pause_duration_spin.setValue(60)
        self.pause_duration_spin.setSuffix(" сек")
        dgl.addRow("Длительность паузы:", self.pause_duration_spin)
        ll.addWidget(dg)
        sg = QGroupBox("Расписание")
        sgl = QVBoxLayout(sg)
        self.schedule_check = QCheckBox("Отложить запуск")
        self.schedule_check.stateChanged.connect(lambda s: self.datetime_picker.setEnabled(bool(s)))
        sgl.addWidget(self.schedule_check)
        self.datetime_picker = QDateTimeEdit()
        self.datetime_picker.setDateTime(QDateTime.currentDateTime().addSecs(3600))
        self.datetime_picker.setCalendarPopup(True)
        self.datetime_picker.setEnabled(False)
        sgl.addWidget(self.datetime_picker)
        ll.addWidget(sg)
        ll.addStretch()
        controls = QHBoxLayout()
        self.start_btn = QPushButton("Запустить рассылку")
        self.start_btn.setObjectName("btn_success")
        self.start_btn.setFixedHeight(44)
        self.start_btn.clicked.connect(self._start_campaign)
        controls.addWidget(self.start_btn)
        self.pause_btn = QPushButton("Пауза")
        self.pause_btn.setEnabled(False)
        self.pause_btn.setFixedHeight(44)
        self.pause_btn.clicked.connect(self._toggle_pause)
        controls.addWidget(self.pause_btn)
        self.stop_btn = QPushButton("Стоп")
        self.stop_btn.setObjectName("btn_danger")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setFixedHeight(44)
        self.stop_btn.clicked.connect(self._stop_campaign)
        controls.addWidget(self.stop_btn)
        ll.addLayout(controls)
        splitter.addWidget(left)
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setSpacing(Spacing.MD)
        rl.setContentsMargins(0, 0, 0, 0)
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(Spacing.SM)
        self.kpi_sent_lbl = _kpi_mini("Отправлено", "0")
        self.kpi_success_lbl = _kpi_mini("Успешно", "0", Colors.SUCCESS)
        self.kpi_errors_lbl = _kpi_mini("Ошибки", "0", Colors.ERROR)
        self.kpi_speed_lbl = _kpi_mini("Скорость", "0/мин")
        self.kpi_eta_lbl = _kpi_mini("Осталось", "—")
        for k in [self.kpi_sent_lbl, self.kpi_success_lbl, self.kpi_errors_lbl, self.kpi_speed_lbl, self.kpi_eta_lbl]:
            kpi_row.addWidget(k)
        rl.addLayout(kpi_row)
        prow = QHBoxLayout()
        prow.addWidget(QLabel("Прогресс:"))
        self.progress_pct_label = QLabel("0%")
        self.progress_pct_label.setObjectName("label_muted")
        prow.addWidget(self.progress_pct_label)
        prow.addStretch()
        rl.addLayout(prow)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        rl.addWidget(self.progress_bar)
        log_lbl = QLabel("Лог событий:")
        log_lbl.setObjectName("label_muted")
        rl.addWidget(log_lbl)
        self.log_list = QListWidget()
        self.log_list.setAlternatingRowColors(True)
        rl.addWidget(self.log_list, 1)
        clear_btn = QPushButton("Очистить лог")
        clear_btn.setObjectName("btn_icon")
        clear_btn.clicked.connect(self.log_list.clear)
        rl.addWidget(clear_btn, 0, Qt.AlignmentFlag.AlignRight)
        splitter.addWidget(right)
        splitter.setSizes([380, 620])
        layout.addWidget(splitter, 1)

    def set_accounts(self, accounts):
        self._accounts = accounts
        active = sum(1 for a in accounts if a.is_active)
        self.accounts_status.setText(f"Аккаунты: {active}/{len(accounts)}")
        self.accounts_status.setStyleSheet(f"color:{Colors.SUCCESS};" if active > 0 else f"color:{Colors.ERROR};")

    def set_recipients(self, recipients):
        self._recipients = recipients
        self.recipients_status.setText(f"Получатели: {len(recipients)}")
        self.recipients_status.setStyleSheet(f"color:{Colors.SUCCESS};")

    def set_template(self, template):
        self._template = template
        self.template_status.setText("Письмо: готово")
        self.template_status.setStyleSheet(f"color:{Colors.SUCCESS};")

    def _validate_ready(self):
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
        config = CampaignConfig(
            min_delay_ms=self.min_delay_spin.value(),
            max_delay_ms=self.max_delay_spin.value(),
            pause_after_n=self.pause_after_spin.value(),
            pause_duration_sec=self.pause_duration_spin.value(),
            max_threads=self.threads_slider.value(),
        )
        self._engine = SendingEngine(accounts=self._accounts, config=config, log_queue=self._log_queue)
        self._total = len(self._recipients)
        self._sent = 0
        self._start_time = time.time()
        self.progress_bar.setMaximum(self._total)
        self.progress_bar.setValue(0)
        self._engine.on_progress = self._on_progress
        self._engine.on_finished = self._on_finished
        self._manually_stopped = False
        self._is_running = True
        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self._speed_timer.start()
        self.campaign_started.emit()
        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._engine.run_campaign(self._recipients, self._template))
            loop.close()
        threading.Thread(target=run, daemon=True).start()

    def _on_progress(self, sent, total, result):
        self._log_queue.put_nowait({"type": "progress", "sent": sent, "total": total, "result": result})

    def _on_finished(self, results):
        self._log_queue.put_nowait({"type": "finished", "results": results})

    def _flush_log_queue(self):
        while not self._log_queue.empty():
            try:
                item = self._log_queue.get_nowait()
            except queue.Empty:
                break
            if not isinstance(item, dict):
                continue
            t = item.get("type")
            if t == "log":
                self.log_list.addItem(QListWidgetItem(item["message"]))
                self.log_list.scrollToBottom()
            elif t == "progress":
                sent, total = item["sent"], item["total"]
                self._sent = sent
                self.progress_bar.setValue(sent)
                pct = int(sent / total * 100) if total > 0 else 0
                self.progress_pct_label.setText(f"{pct}%")
                stats = self._engine.stats if self._engine else {}
                self._set_kpi(self.kpi_sent_lbl, str(sent))
                self._set_kpi(self.kpi_success_lbl, str(stats.get("success", 0)))
                self._set_kpi(self.kpi_errors_lbl, str(stats.get("errors", 0)))
            elif t == "finished":
                self._on_campaign_done(item["results"])

    def _set_kpi(self, card, value):
        lbl = card.findChild(QLabel, "_kpi_val")
        if lbl:
            lbl.setText(value)

    def _update_speed(self):
        if not self._is_running or not self._start_time:
            return
        elapsed = time.time() - self._start_time
        if elapsed > 0 and self._sent > 0:
            speed = self._sent / elapsed * 60
            self._set_kpi(self.kpi_speed_lbl, f"{speed:.0f}/мин")
            if speed > 0:
                self._set_kpi(self.kpi_eta_lbl, f"{(self._total - self._sent) / speed:.0f} мин")

    def _toggle_pause(self):
        if not self._engine:
            return
        if self._engine._paused:
            self._engine.resume()
            self.pause_btn.setText("Пауза")
        else:
            self._engine.pause()
            self.pause_btn.setText("Продолжить")

    def _stop_campaign(self):
        self._manually_stopped = True
        if self._engine:
            self._engine.stop()
        self._finish_ui()

    def _on_campaign_done(self, results):
        self._finish_ui()
        # Всегда эмитируем сигнал — аналитика и дашборд должны получить данные
        real_results = [r for r in results if r.error != "stopped"]
        self.campaign_finished.emit(real_results if real_results else results)
        if not self._manually_stopped:
            success = sum(1 for r in results if r.success)
            QMessageBox.information(
                self, "Рассылка завершена",
                f"Итого: {len(results)} писем\nУспешно: {success}\nОшибок: {len(results) - success}"
            )

    def _finish_ui(self):
        self._is_running = False
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self._speed_timer.stop()
