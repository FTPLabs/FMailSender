"""
Animated background widget with floating orbs and dot grid.
CyberPro design v3.6.2
"""
from __future__ import annotations
import math
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QPainter, QColor, QRadialGradient, QPen, QBrush


class AnimatedBackground(QWidget):
    """
    Dark animated background with:
    - 3 soft gradient orbs (violet, cyan, deep-violet)
    - Dot grid overlay
    - Slow pulsing aurora sweep
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tick = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(50)  # 20 fps — smooth but cheap
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

    def _on_tick(self):
        self._tick += 1
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        t = self._tick

        # ── Base fill ────────────────────────────────────────────────────
        painter.fillRect(0, 0, w, h, QColor(4, 4, 16))

        # ── Orb 1: Violet (primary) ───────────────────────────────────────
        self._draw_orb(
            painter, w * 0.25, h * 0.35,
            int(w * 0.55),
            (139, 92, 246),
            0.055 + 0.012 * math.sin(t * 0.03),
        )
        # ── Orb 2: Cyan (secondary) ───────────────────────────────────────
        self._draw_orb(
            painter, w * 0.78, h * 0.65,
            int(w * 0.45),
            (6, 182, 212),
            0.040 + 0.010 * math.sin(t * 0.025 + 1.2),
        )
        # ── Orb 3: Deep violet ────────────────────────────────────────────
        self._draw_orb(
            painter, w * 0.60, h * 0.18,
            int(w * 0.38),
            (91, 33, 182),
            0.035 + 0.008 * math.sin(t * 0.02 + 2.5),
        )

        # ── Dot grid ─────────────────────────────────────────────────────
        grid_step = 28
        dot_color = QColor(80, 80, 140, 18)
        painter.setPen(QPen(dot_color, 1.2))
        for gx in range(0, w + grid_step, grid_step):
            for gy in range(0, h + grid_step, grid_step):
                painter.drawPoint(gx, gy)

        painter.end()

    @staticmethod
    def _draw_orb(painter: QPainter, cx: float, cy: float,
                  radius: int, rgb: tuple, alpha: float):
        grad = QRadialGradient(cx, cy, radius)
        r, g, b = rgb
        a_center = int(255 * alpha)
        a_mid    = int(255 * alpha * 0.4)
        grad.setColorAt(0.0, QColor(r, g, b, a_center))
        grad.setColorAt(0.5, QColor(r, g, b, a_mid))
        grad.setColorAt(1.0, QColor(r, g, b, 0))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(
            int(cx - radius), int(cy - radius),
            radius * 2, radius * 2,
        )
