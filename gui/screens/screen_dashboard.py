"""
Экран 1: Dashboard — KPI-карточки, график активности 24ч, статус SMTP.
"""
import time
import random
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QSizePolicy, QGridLayout
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QPolygon, QPainterPath
from PyQt6.QtCore import QPoint, QRectF

from gui.theme import Colors, Typography, Spacing


class KpiCard(QFrame):
    """Карточка KPI с анимацией чисел."""

    def __init__(self, title: str, value: int = 0, color: str = Colors.TEXT_PRIMARY, parent=None):
        super().__init__(parent)
        self.setObjectName("kpi_card")
        self._current_value = value
        self._target_value = value
        self._color = color

        layout = QVBoxLayout(self)
        layout.setSpacing(Spacing.SM)
        layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)

        self.value_label = QLabel(str(value))
        self.value_label.setObjectName("label_kpi_value")
        self.value_label.setStyleSheet(f"color: {color};")
        layout.addWidget(self.value_label)

        self.title_label = QLabel(title.upper())
        self.title_label.setObjectName("label_kpi_title")
        layout.addWidget(self.title_label)

        # Анимация цифр
        self._anim_timer = QTimer()
        self._anim_timer.setInterval(30)
        self._anim_timer.timeout.connect(self._animate_step)

    def set_value(self, value: int, animate: bool = True) -> None:
        self._target_value = value
        if animate and abs(value - self._current_value) > 0:
            self._anim_timer.start()
        else:
            self._current_value = value
            self.value_label.setText(self._format(value))

    def _format(self, v: int) -> str:
        if v >= 1_000_000:
            return f"{v/1_000_000:.1f}M"
        if v >= 1_000:
            return f"{v/1_000:.1f}K"
        return str(v)

    def _animate_step(self):
        diff = self._target_value - self._current_value
        if abs(diff) < 1:
            self._current_value = self._target_value
            self._anim_timer.stop()
        else:
            self._current_value += diff * 0.15
        self.value_label.setText(self._format(int(self._current_value)))


class ActivityChart(QWidget):
    """Линейный график активности за последние 24 часа — кастомный QPainter."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(140)
        self._data: list[int] = [0] * 24  # по часам
        self.setObjectName("activity_chart")

    def set_data(self, data: list[int]) -> None:
        """Устанавливает данные (24 значения — по одному на час)."""
        self._data = data[:24] if len(data) >= 24 else data + [0] * (24 - len(data))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        pad_left = 48
        pad_right = 16
        pad_top = 12
        pad_bottom = 30

        chart_w = w - pad_left - pad_right
        chart_h = h - pad_top - pad_bottom

        max_val = max(self._data) if self._data and max(self._data) > 0 else 1

        # Фон
        painter.fillRect(self.rect(), QColor(Colors.BG_SURFACE1))

        # Dashed grid
        grid_pen = QPen(QColor(50, 50, 80, 55))
        grid_pen.setStyle(Qt.PenStyle.DashLine)
        grid_pen.setDashPattern([4.0, 6.0])
        grid_pen.setWidth(1)
        painter.setPen(grid_pen)

        for i in range(4):
            y = pad_top + chart_h * i // 3
            painter.drawLine(pad_left, y, pad_left + chart_w, y)
            val = int(max_val * (3 - i) / 3)
            painter.setPen(QColor(Colors.TEXT_MUTED))
            if val >= 1000:
                painter.drawText(2, y + 4, f"{val//1000}k")
            else:
                painter.drawText(2, y + 4, str(val))
            painter.setPen(grid_pen)

        # X-метки (часы)
        hour_now = datetime.now().hour
        painter.setPen(QColor(Colors.TEXT_MUTED))
        for i in range(0, 24, 6):
            x = pad_left + chart_w * i // 23
            hour = (hour_now - 23 + i) % 24
            painter.drawText(x - 12, h - 4, f"{hour:02d}:00")

        if len(self._data) < 2:
            return

        # Координаты точек
        pts = []
        for i, val in enumerate(self._data):
            x = pad_left + chart_w * i // (len(self._data) - 1)
            y = pad_top + chart_h - int(chart_h * val / max_val)
            pts.append((float(x), float(y)))

        # Smooth cubic bezier path
        line_path = QPainterPath()
        line_path.moveTo(pts[0][0], pts[0][1])
        for i in range(len(pts) - 1):
            x0, y0 = pts[i]
            x1, y1 = pts[i + 1]
            cp1x = x0 + (x1 - x0) / 3.0
            cp1y = y0
            cp2x = x0 + 2.0 * (x1 - x0) / 3.0
            cp2y = y1
            line_path.cubicTo(cp1x, cp1y, cp2x, cp2y, x1, y1)

        # Gradient fill
        fill_path = QPainterPath(line_path)
        fill_path.lineTo(pts[-1][0], float(pad_top + chart_h))
        fill_path.lineTo(float(pad_left), float(pad_top + chart_h))
        fill_path.closeSubpath()

        from PyQt6.QtGui import QLinearGradient
        grad = QLinearGradient(0, pad_top, 0, pad_top + chart_h)
        grad.setColorAt(0.0, QColor(139, 92, 246, 72))
        grad.setColorAt(0.55, QColor(6, 182, 212, 25))
        grad.setColorAt(1.0, QColor(6, 182, 212, 0))
        painter.fillPath(fill_path, QBrush(grad))

        # Stroke — violet→cyan
        line_pen = QPen(QColor(Colors.ACCENT))
        line_pen.setWidth(2)
        line_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        line_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.strokePath(line_path, line_pen)

        # Glow dot на последней точке
        lx, ly = pts[-1]
        painter.setPen(Qt.PenStyle.NoPen)
        for radius, alpha in [(12, 10), (7, 32), (4, 80)]:
            painter.setBrush(QBrush(QColor(139, 92, 246, alpha)))
            painter.drawEllipse(int(lx) - radius, int(ly) - radius, radius * 2, radius * 2)
        painter.setBrush(QBrush(QColor(Colors.ACCENT)))
        painter.setPen(QPen(QColor(Colors.BG_BASE), 2))
        painter.drawEllipse(int(lx) - 4, int(ly) - 4, 8, 8)

        painter.end()

    """Главный экран — KPI + график активности."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stats = {
            "sent_today": 0,
            "success": 0,
            "errors": 0,
            "queued": 0,
        }
        self._activity_data: list[int] = [0] * 24
        self._setup_ui()

        # Авто-обновление демо-данных
        self._refresh_timer = QTimer()
        self._refresh_timer.setInterval(5000)
        self._refresh_timer.timeout.connect(self._refresh_demo)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        layout.setSpacing(Spacing.LG)

        # ── Заголовок ────────────────────────────
        header_row = QHBoxLayout()
        title = QLabel("Дашборд")
        title.setObjectName("section_header")
        header_row.addWidget(title)
        header_row.addStretch()

        self.date_label = QLabel(datetime.now().strftime("%d %B %Y, %H:%M"))
        self.date_label.setObjectName("label_muted")
        header_row.addWidget(self.date_label)

        layout.addLayout(header_row)

        # Обновляем время
        clock = QTimer(self)
        clock.setInterval(60000)
        clock.timeout.connect(
            lambda: self.date_label.setText(datetime.now().strftime("%d %B %Y, %H:%M"))
        )
        clock.start()

        # ── KPI-карточки ─────────────────────────
        kpi_grid = QHBoxLayout()
        kpi_grid.setSpacing(Spacing.MD)

        self.kpi_sent = KpiCard("Отправлено сегодня", 0, Colors.TEXT_PRIMARY)
        self.kpi_success = KpiCard("Успешно", 0, Colors.SUCCESS)
        self.kpi_errors = KpiCard("Ошибки", 0, Colors.ERROR)
        self.kpi_queued = KpiCard("В очереди", 0, Colors.WARNING)

        for card in [self.kpi_sent, self.kpi_success, self.kpi_errors, self.kpi_queued]:
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            card.setFixedHeight(100)
            kpi_grid.addWidget(card)

        layout.addLayout(kpi_grid)

        # ── График активности ─────────────────────
        chart_card = QFrame()
        chart_card.setObjectName("card")
        chart_layout = QVBoxLayout(chart_card)
        chart_layout.setSpacing(Spacing.MD)

        chart_header = QHBoxLayout()
        chart_title = QLabel("Активность за 24 часа")
        chart_title.setObjectName("label_subtitle")
        chart_header.addWidget(chart_title)
        chart_header.addStretch()

        self.chart_stat_label = QLabel("0 писем сегодня")
        self.chart_stat_label.setObjectName("label_muted")
        chart_header.addWidget(self.chart_stat_label)

        chart_layout.addLayout(chart_header)

        self.activity_chart = ActivityChart()
        chart_layout.addWidget(self.activity_chart)

        layout.addWidget(chart_card)

        # ── Последние события ─────────────────────
        events_card = QFrame()
        events_card.setObjectName("card")
        events_layout = QVBoxLayout(events_card)
        events_layout.setSpacing(Spacing.SM)

        events_title = QLabel("Последние события")
        events_title.setObjectName("label_subtitle")
        events_layout.addWidget(events_title)

        self.events_label = QLabel(
            '<span style="color:#71717A">Нет активных кампаний. '
            'Запустите рассылку для отображения событий.</span>'
        )
        self.events_label.setWordWrap(True)
        events_layout.addWidget(self.events_label)

        layout.addWidget(events_card)
        layout.addStretch()

    # ── Публичное API ─────────────────────────────────────────────────────────

    def update_stats(self, stats: dict) -> None:
        """Обновляет KPI-карточки из словаря статистики."""
        self._stats = stats
        self.kpi_sent.set_value(stats.get("sent_today", 0))
        self.kpi_success.set_value(stats.get("success", 0))
        self.kpi_errors.set_value(stats.get("errors", 0))
        self.kpi_queued.set_value(stats.get("queued", 0))
        total = stats.get("sent_today", 0)
        self.chart_stat_label.setText(f"{total} писем сегодня")

    def update_activity(self, hourly_data: list[int]) -> None:
        """Обновляет данные графика."""
        self._activity_data = hourly_data
        self.activity_chart.set_data(hourly_data)

    def add_event(self, event_text: str) -> None:
        """Добавляет событие в лог."""
        ts = datetime.now().strftime("%H:%M:%S")
        current = self.events_label.text()
        if "Нет активных" in current:
            new_text = f'<span style="color:#A1A1AA">[{ts}]</span> {event_text}'
        else:
            new_text = current + f'<br><span style="color:#A1A1AA">[{ts}]</span> {event_text}'
        self.events_label.setText(new_text)

    def update_campaign_results(self, results: list) -> None:
        """Обновляет KPI и график по итогам кампании."""
        total = len(results)
        success = sum(1 for r in results if getattr(r, "success", False))
        self._stats["sent_today"] += total
        self._stats["success"] += success
        self._stats["errors"] += total - success
        self._stats["queued"] = 0
        self.kpi_sent.set_value(self._stats["sent_today"])
        self.kpi_success.set_value(self._stats["success"])
        self.kpi_errors.set_value(self._stats["errors"])
        self.kpi_queued.set_value(0)
        hour = datetime.now().hour
        self._activity_data[hour] += success
        self.activity_chart.set_data(self._activity_data)
        self.chart_stat_label.setText(f"{self._stats['sent_today']} писем сегодня")

    def start_demo_mode(self) -> None:
        """Запускает демо-режим с тестовыми данными."""
        self._refresh_timer.start()
        self._refresh_demo()

    def _refresh_demo(self) -> None:
        """Обновляет дашборд случайными демо-данными."""
        self._stats["sent_today"] += random.randint(5, 25)
        self._stats["success"] += random.randint(4, 22)
        self._stats["errors"] = max(0, self._stats["sent_today"] - self._stats["success"])
        self._stats["queued"] = random.randint(0, 50)
        self.kpi_sent.set_value(self._stats["sent_today"])
        self.kpi_success.set_value(self._stats["success"])
        self.kpi_errors.set_value(self._stats["errors"])
        self.kpi_queued.set_value(self._stats["queued"])
        hour = datetime.now().hour
        self._activity_data[hour] += random.randint(1, 10)
        self.activity_chart.set_data(self._activity_data)
        self.chart_stat_label.setText(f"{self._stats['sent_today']} писем сегодня")
