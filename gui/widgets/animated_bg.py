"""
AnimatedBackground — CyberPro style:
  3 floating neon orbs (violet, cyan, deep violet)
  Aurora sweep band (slow opacity pulse)
  Dot-grid overlay
  Dark gradient base: #040410
"""
import math
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QPainter, QColor, QRadialGradient, QLinearGradient, QPen


class _Orb:
    """One floating orb with independent phase/speed."""
    def __init__(self, cx: float, cy: float, r: float,
                 color: tuple, speed_x: float, speed_y: float, phase: float = 0.0):
        self.cx = cx; self.cy = cy; self.r = r
        self.color = color
        self.speed_x = speed_x; self.speed_y = speed_y
        self.phase = phase
        self.t = phase

    def update(self, dt: float) -> None:
        self.t += dt

    def pos(self, w: int, h: int) -> tuple:
        x = self.cx * w + math.sin(self.t * self.speed_x + self.phase) * 0.18 * w
        y = self.cy * h + math.cos(self.t * self.speed_y + self.phase * 1.3) * 0.15 * h
        return x, y


class AnimatedBackground(QWidget):
    """
    Full-window animated background widget — CyberPro style.
    Place as first child of main window; set WA_TranslucentBackground on all
    stacked screens so orbs show through.
    """

    _ORBS = [
        _Orb(0.25, 0.30, 0.40, (139, 92, 246),  0.35, 0.28, 0.0),
        _Orb(0.75, 0.65, 0.38, (6, 182, 212),    0.28, 0.22, 2.1),
        _Orb(0.60, 0.20, 0.32, (91, 33, 182),    0.22, 0.18, 4.3),
    ]
    _FPS = 30
    _DT  = 1.0 / _FPS

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._aurora_t = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(int(1000 / self._FPS))
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self) -> None:
        for orb in self._ORBS:
            orb.update(self._DT)
        self._aurora_t += self._DT * 0.15
        self.update()

    def hideEvent(self, event) -> None:
        # Останавливаем таймер когда окно скрыто/свёрнуто — не жжём CPU впустую.
        self._timer.stop()
        super().hideEvent(event)

    def showEvent(self, event) -> None:
        if not self._timer.isActive():
            self._timer.start()
        super().showEvent(event)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # 1. Dark base gradient
        base = QLinearGradient(0, 0, 0, h)
        base.setColorAt(0.0, QColor("#040410"))
        base.setColorAt(0.5, QColor("#060614"))
        base.setColorAt(1.0, QColor("#040410"))
        p.fillRect(0, 0, w, h, base)

        # 2. Dot grid
        dot_pen = QPen(QColor(80, 80, 140, 18))
        dot_pen.setWidth(1)
        p.setPen(dot_pen)
        step = 28
        for gx in range(0, w + step, step):
            for gy in range(0, h + step, step):
                p.drawPoint(gx, gy)

        # 3. Aurora sweep band
        aurora_opacity = 0.04 + 0.025 * math.sin(self._aurora_t * math.pi * 2)
        aurora = QLinearGradient(0, int(h * 0.3), w, int(h * 0.7))
        aurora.setColorAt(0.0, QColor(0, 0, 0, 0))
        aurora.setColorAt(0.3, QColor(139, 92, 246, int(255 * aurora_opacity)))
        aurora.setColorAt(0.6, QColor(6, 182, 212, int(255 * aurora_opacity * 0.6)))
        aurora.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(0, 0, w, h, aurora)

        # 4. Orbs (Screen blend for neon glow)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
        for orb in self._ORBS:
            ox, oy = orb.pos(w, h)
            radius = orb.r * min(w, h)
            r2, g2, b2 = orb.color
            grad = QRadialGradient(ox, oy, radius)
            grad.setColorAt(0.0, QColor(r2, g2, b2, 55))
            grad.setColorAt(0.35, QColor(r2, g2, b2, 22))
            grad.setColorAt(0.7, QColor(r2, g2, b2, 8))
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(grad)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(int(ox - radius), int(oy - radius),
                          int(radius * 2), int(radius * 2))

        p.end()