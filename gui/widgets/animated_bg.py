"""
Animated particle background widget for FMail Sender.
Floating violet/cyan particles with connecting lines and pulsing glow.
~30fps, WA_TransparentForMouseEvents — does not intercept clicks.
"""
import math
import random
from PyQt6.QtCore import Qt, QTimer, QObject, QEvent, QPointF
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QLinearGradient, QRadialGradient,
)
from PyQt6.QtWidgets import QWidget


_COLORS = [
    QColor(139, 92, 246),
    QColor(124, 58, 237),
    QColor(6, 182, 212),
    QColor(167, 139, 250),
    QColor(91, 33, 182),
    QColor(8, 145, 178),
    QColor(196, 181, 253),
]

_ORBS = [
    (0.12, 0.18, 280, QColor(124, 58, 237, 18)),
    (0.88, 0.75, 240, QColor(6, 182, 212, 14)),
    (0.50, 0.92, 200, QColor(139, 92, 246, 12)),
    (0.78, 0.10, 170, QColor(91, 33, 182, 10)),
]


class AnimatedBackground(QWidget):
    """Animated particle field background. Place as child widget, call .lower()."""

    PARTICLE_COUNT = 60
    CONNECTION_DIST_RATIO = 0.17
    FPS = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)

        self._t = 0.0
        rng = random.Random(7)

        self._particles = [
            {
                'x':     rng.uniform(0.0, 1.0),
                'y':     rng.uniform(0.0, 1.0),
                'vx':    rng.uniform(-0.00025, 0.00025),
                'vy':    rng.uniform(-0.00025, 0.00025),
                'size':  rng.uniform(1.2, 3.2),
                'alpha': rng.uniform(0.35, 0.80),
                'ci':    rng.randint(0, len(_COLORS) - 1),
                'phase': rng.uniform(0.0, 6.283),
            }
            for _ in range(self.PARTICLE_COUNT)
        ]

        if parent:
            parent.installEventFilter(self)

        self._timer = QTimer(self)
        self._timer.setInterval(1000 // self.FPS)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def eventFilter(self, obj, event):
        if obj is self.parent() and event.type() == QEvent.Type.Resize:
            self.resize(event.size())
        return False

    def showEvent(self, event):
        if self.parent():
            self.resize(self.parent().size())
        super().showEvent(event)

    def _tick(self):
        self._t += 0.04
        for p in self._particles:
            p['x'] = (p['x'] + p['vx']) % 1.0
            p['y'] = (p['y'] + p['vy']) % 1.0
        self.update()

    def paintEvent(self, _event):
        if not self.isVisible():
            return
        w, h = max(self.width(), 1), max(self.height(), 1)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Transparent bg — parent handles dark surface; no fillRect to avoid black squares

        for ox, oy, radius, base_color in _ORBS:
            cx = int(ox * w)
            cy = int(oy * h)
            pulse = math.sin(self._t * 0.4 + ox * 4.0) * 18
            r = radius + int(pulse)
            grad = QRadialGradient(QPointF(cx, cy), r)
            grad.setColorAt(0.0, base_color)
            faded = QColor(base_color)
            faded.setAlpha(0)
            grad.setColorAt(1.0, faded)
            painter.fillRect(cx - r, cy - r, r * 2, r * 2, QBrush(grad))

        pts = [(p, int(p['x'] * w), int(p['y'] * h)) for p in self._particles]

        max_d = min(w, h) * self.CONNECTION_DIST_RATIO
        max_d2 = max_d * max_d
        for i, (pi, xi, yi) in enumerate(pts):
            for _pj, xj, yj in pts[i + 1:]:
                dx, dy = xi - xj, yi - yj
                d2 = dx * dx + dy * dy
                if d2 < max_d2:
                    alpha = int(45 * (1.0 - d2 / max_d2))
                    pen = QPen(QColor(139, 92, 246, alpha), 1)
                    painter.setPen(pen)
                    painter.drawLine(xi, yi, xj, yj)

        painter.setPen(Qt.PenStyle.NoPen)
        for p, px, py in pts:
            color = _COLORS[p['ci']]
            pulse = 0.72 + 0.28 * abs(math.sin(self._t * 0.8 + p['phase']))
            alpha = int(p['alpha'] * pulse * 255)
            sz = p['size'] * pulse

            gr = int(sz * 7)
            if gr > 1:
                glow_c = QColor(color)
                glow_c.setAlpha(max(1, int(alpha * 0.09)))
                grad_out = QRadialGradient(QPointF(px, py), gr)
                grad_out.setColorAt(0.0, glow_c)
                t_out = QColor(glow_c)
                t_out.setAlpha(0)
                grad_out.setColorAt(1.0, t_out)
                painter.fillRect(px - gr, py - gr, gr * 2, gr * 2, QBrush(grad_out))

            ir = int(sz * 3)
            if ir > 1:
                inner_c = QColor(color)
                inner_c.setAlpha(max(1, int(alpha * 0.35)))
                grad_in = QRadialGradient(QPointF(px, py), ir)
                grad_in.setColorAt(0.0, inner_c)
                t_in = QColor(inner_c)
                t_in.setAlpha(0)
                grad_in.setColorAt(1.0, t_in)
                painter.fillRect(px - ir, py - ir, ir * 2, ir * 2, QBrush(grad_in))

            core = QColor(color)
            core.setAlpha(alpha)
            painter.setBrush(QBrush(core))
            r = max(1, int(sz))
            painter.drawEllipse(px - r, py - r, r * 2, r * 2)

        painter.end()
