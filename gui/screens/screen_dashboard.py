"""
Dashboard — CyberPro style: KPI cards with neon glow, activity chart v/c gradient.
Keeps all public API: update_stats(), update_activity(), update_campaign_results().
"""
import random
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QBrush, QPainterPath, QLinearGradient
)

from gui.theme import Colors, Spacing


# KPI Card
class KpiCard(QFrame):
    """CyberPro KPI card — glass border, neon accent, animated counter."""

    def __init__(self, title: str, value: int = 0,
                 color: str = Colors.ACCENT, parent=None):
        super().__init__(parent)
        self._current_value: float = float(value)
        self._target_value: float = float(value)
        self._color = color
        self.setStyleSheet(
            "QFrame {"
            "  background: rgba(255,255,255,0.025);"
            "  border: 1px solid rgba(139,92,246,0.14);"
            "  border-radius: 12px;"
            "}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(6)
        self._title_lbl = QLabel(title.upper())
        self._title_lbl.setStyleSheet(
            "color: " + Colors.TEXT_SECONDARY + "; font-size: 11px;"
            " font-weight: 600; letter-spacing: 0.08em;"
            " background: transparent; border: none;"
        )
        layout.addWidget(self._title_lbl)
        self.value_label = QLabel(self._fmt(value))
        self.value_label.setStyleSheet(
            "color: " + color + "; font-size: 28px; font-weight: 700;"
            " font-family: monospace; background: transparent; border: none;"
        )
        layout.addWidget(self.value_label)
        self._anim_timer = QTimer()
        self._anim_timer.setInterval(20)
        self._anim_timer.timeout.connect(self._step)

    def _fmt(self, v: float) -> str:
        iv = int(v)
        if iv >= 1_000_000:
            return f"{iv/1_000_000:.1f}M"
        if iv >= 1_000:
            return f"{iv/1_000:.1f}K"
        return str(iv)

    def set_value(self, value: int, animate: bool = True) -> None:
        self._target_value = float(value)
        if animate and abs(value - self._current_value) > 0.5:
            self._anim_timer.start()
        else:
            self._current_value = float(value)
            self.value_label.setText(self._fmt(value))

    def _step(self) -> None:
        diff = self._target_value - self._current_value
        if abs(diff) < 1.0:
            self._current_value = self._target_value
            self._anim_timer.stop()
        else:
            self._current_value += diff * 0.18
        self.value_label.setText(self._fmt(self._current_value))


# Activity Chart
class ActivityChart(QWidget):
    """CyberPro chart — violet/cyan gradient fill, smooth cubic bezier, glow dot."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(150)
        self.setObjectName("activity_chart")
        self._data: list[int] = [0] * 24
        self.setStyleSheet("background: transparent;")

    def set_data(self, data: list[int]) -> None:
        self._data = data[:24] if len(data) >= 24 else data + [0] * (24 - len(data))
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        pl, pr, pt, pb = 46, 16, 10, 28
        cw = w - pl - pr
        ch = h - pt - pb
        max_v = max(self._data) if self._data and max(self._data) > 0 else 1
        p.fillRect(0, 0, w, h, QColor(0, 0, 0, 0))
        gpen = QPen(QColor(80, 80, 140, 30))
        gpen.setStyle(Qt.PenStyle.DashLine)
        gpen.setDashPattern([4.0, 5.0])
        for i in range(4):
            y = pt + ch * i // 3
            p.setPen(gpen)
            p.drawLine(pl, y, pl + cw, y)
            val = int(max_v * (3 - i) / 3)
            p.setPen(QColor(Colors.TEXT_MUTED))
            lbl = f"{val//1000}k" if val >= 1000 else str(val)
            p.drawText(2, y + 4, lbl)
        hour_now = datetime.now().hour
        p.setPen(QColor(Colors.TEXT_MUTED))
        for i in range(0, 24, 6):
            x = pl + cw * i // 23
            hour = (hour_now - 23 + i) % 24
            p.drawText(x - 14, h - 4, f"{hour:02d}:00")
        if len(self._data) < 2:
            return
        pts = []
        for i, val in enumerate(self._data):
            x = pl + cw * i // (len(self._data) - 1)
            y = pt + ch - int(ch * val / max_v)
            pts.append((float(x), float(y)))
        path = QPainterPath()
        path.moveTo(pts[0][0], pts[0][1])
        for i in range(len(pts) - 1):
            x0, y0 = pts[i]; x1, y1 = pts[i+1]
            path.cubicTo(x0 + (x1-x0)/3, y0,
                         x0 + 2*(x1-x0)/3, y1,
                         x1, y1)
        fill = QPainterPath(path)
        fill.lineTo(pts[-1][0], float(pt + ch))
        fill.lineTo(float(pl), float(pt + ch))
        fill.closeSubpath()
        grad = QLinearGradient(0, pt, 0, pt + ch)
        grad.setColorAt(0.0, QColor(139, 92, 246, 60))
        grad.setColorAt(0.55, QColor(6, 182, 212, 18))
        grad.setColorAt(1.0, QColor(6, 182, 212, 0))
        p.fillPath(fill, QBrush(grad))
        lpen = QPen(QColor(Colors.ACCENT))
        lpen.setWidth(2)
        lpen.setCapStyle(Qt.PenCapStyle.RoundCap)
        lpen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.strokePath(path, lpen)
        lx, ly = pts[-1]
        p.setPen(Qt.PenStyle.NoPen)
        for radius, alpha in [(14, 8), (8, 28), (5, 70)]:
            p.setBrush(QBrush(QColor(139, 92, 246, alpha)))
            p.drawEllipse(int(lx)-radius, int(ly)-radius, radius*2, radius*2)
        p.setBrush(QBrush(QColor(Colors.ACCENT)))
        p.setPen(QPen(QColor(Colors.BG_BASE), 2))
        p.drawEllipse(int(lx)-4, int(ly)-4, 8, 8)
        p.end()


# Dashboard Screen
class DashboardScreen(QWidget):
    """Дашборд — KPI карточки + график активности (CyberPro)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stats = {"sent_today": 0, "success": 0, "errors": 0, "queued": 0}
        self._activity_data: list[int] = [0] * 24
        self._setup_ui()
        self._refresh_timer = QTimer()
        self._refresh_timer.setInterval(5000)
        self._refresh_timer.timeout.connect(self._refresh_demo)

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        root.setSpacing(Spacing.LG)
        hdr = QHBoxLayout()
        title = QLabel("Дашборд")
        title.setStyleSheet(
            "color: " + Colors.TEXT_PRIMARY + "; font-size: 22px; font-weight: 700;"
            " background: transparent; border: none;"
        )
        hdr.addWidget(title)
        hdr.addStretch()
        self.date_label = QLabel(datetime.now().strftime("%d %B %Y, %H:%M"))
        self.date_label.setStyleSheet(
            "color: " + Colors.TEXT_SECONDARY + "; font-size: 12px;"
            " background: transparent; border: none;"
        )
        hdr.addWidget(self.date_label)
        root.addLayout(hdr)
        clock = QTimer(self)
        clock.setInterval(60000)
        clock.timeout.connect(
            lambda: self.date_label.setText(datetime.now().strftime("%d %B %Y, %H:%M"))
        )
        clock.start()
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(Spacing.MD)
        self.kpi_sent    = KpiCard("Отправлено", 0, Colors.CYAN)
        self.kpi_success = KpiCard("Успешно",    0, Colors.SUCCESS)
        self.kpi_errors  = KpiCard("Ошибки",     0, Colors.ERROR)
        self.kpi_queued  = KpiCard("В очереди",  0, Colors.WARNING)
        for card in [self.kpi_sent, self.kpi_success, self.kpi_errors, self.kpi_queued]:
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            card.setFixedHeight(96)
            kpi_row.addWidget(card)
        root.addLayout(kpi_row)
        chart_card = QFrame()
        chart_card.setStyleSheet(
            "QFrame {"
            "  background: rgba(255,255,255,0.02);"
            "  border: 1px solid rgba(139,92,246,0.12);"
            "  border-radius: 12px;"
            "}"
        )
        cc_layout = QVBoxLayout(chart_card)
        cc_layout.setContentsMargins(20, 16, 20, 16)
        cc_layout.setSpacing(12)
        cc_hdr = QHBoxLayout()
        chart_title = QLabel("Активность за 24 часа")
        chart_title.setStyleSheet(
            "color: " + Colors.TEXT_PRIMARY + "; font-size: 14px; font-weight: 600;"
            " background: transparent; border: none;"
        )
        cc_hdr.addWidget(chart_title)
        cc_hdr.addStretch()
        self.chart_stat_label = QLabel("0 писем сегодня")
        self.chart_stat_label.setStyleSheet(
            "color: " + Colors.TEXT_SECONDARY + "; font-size: 12px;"
            " background: transparent; border: none;"
        )
        cc_hdr.addWidget(self.chart_stat_label)
        cc_layout.addLayout(cc_hdr)
        self.activity_chart = ActivityChart()
        cc_layout.addWidget(self.activity_chart)
        root.addWidget(chart_card)
        ev_card = QFrame()
        ev_card.setStyleSheet(
            "QFrame {"
            "  background: rgba(255,255,255,0.02);"
            "  border: 1px solid rgba(139,92,246,0.12);"
            "  border-radius: 12px;"
            "}"
        )
        ev_layout = QVBoxLayout(ev_card)
        ev_layout.setContentsMargins(20, 16, 20, 16)
        ev_layout.setSpacing(8)
        ev_title = QLabel("Последние события")
        ev_title.setStyleSheet(
            "color: " + Colors.TEXT_PRIMARY + "; font-size: 14px; font-weight: 600;"
            " background: transparent; border: none;"
        )
        ev_layout.addWidget(ev_title)
        self.events_label = QLabel(
            '<span style="color:' + Colors.TEXT_MUTED + '">Нет активных кампаний. '
            "Запустите рассылку для отображения событий.</span>"
        )
        self.events_label.setWordWrap(True)
        self.events_label.setStyleSheet("background: transparent; border: none;")
        ev_layout.addWidget(self.events_label)
        root.addWidget(ev_card)
        root.addStretch()

    def update_stats(self, stats: dict) -> None:
        self._stats = stats
        self.kpi_sent.set_value(stats.get("sent_today", 0))
        self.kpi_success.set_value(stats.get("success", 0))
        self.kpi_errors.set_value(stats.get("errors", 0))
        self.kpi_queued.set_value(stats.get("queued", 0))
        self.chart_stat_label.setText(f"{stats.get('sent_today', 0)} писем сегодня")

    def update_activity(self, hourly_data: list[int]) -> None:
        self._activity_data = hourly_data
        self.activity_chart.set_data(hourly_data)

    def add_event(self, event_text: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        current = self.events_label.text()
        if "Нет активных" in current:
            new_text = ('<span style="color:' + Colors.TEXT_SECONDARY
                        + '">['+ ts + ']</span> ' + event_text)
        else:
            new_text = (current + '<br><span style="color:' + Colors.TEXT_SECONDARY
                        + '">['+ ts + ']</span> ' + event_text)
        self.events_label.setText(new_text)

    def update_campaign_results(self, results: list) -> None:
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
        self._refresh_timer.start()
        self._refresh_demo()

    def _refresh_demo(self) -> None:
        import random as _r
        self._stats["sent_today"] += _r.randint(5, 25)
        self._stats["success"] += _r.randint(4, 22)
        self._stats["errors"] = max(0, self._stats["sent_today"] - self._stats["success"])
        self._stats["queued"] = _r.randint(0, 50)
        self.kpi_sent.set_value(self._stats["sent_today"])
        self.kpi_success.set_value(self._stats["success"])
        self.kpi_errors.set_value(self._stats["errors"])
        self.kpi_queued.set_value(self._stats["queued"])
        hour = datetime.now().hour
        self._activity_data[hour] += _r.randint(1, 10)
        self.activity_chart.set_data(self._activity_data)
        self.chart_stat_label.setText(f"{self._stats['sent_today']} писем сегодня")
