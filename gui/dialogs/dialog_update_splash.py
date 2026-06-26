"""
UpdateSplashDialog — pre-launch update dialog.
CyberPro design: #040410 BG, violet/cyan orbs, glassmorphism card.
Appears BEFORE the main window, blocks until user chooses an action.

Actions:
  • Установить патч  — downloads only changed .py files, then restarts
  • Пропустить версию — saves skip preference, never shown again for this tag
  • Напомнить позже  — closes, shows again after 24 h
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QByteArray, QSize
from PyQt6.QtGui import (
    QColor, QFont, QLinearGradient, QPainter, QPainterPath,
    QPixmap, QRadialGradient,
)
from PyQt6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QSizePolicy, QSpacerItem, QVBoxLayout, QWidget,
)

try:
    from PyQt6.QtSvg import QSvgRenderer
    _HAS_SVG = True
except ImportError:
    _HAS_SVG = False

from core.updater import (
    UpdateInfo, apply_patch, fetch_patch_manifest,
    Downloader, apply_update_windows,
)
from core.update_settings import (
    skip_version, set_remind_later, clear_remind_later,
)
from gui.theme import Colors, Typography

  try:
      from core.utils import resource_path as _resource_path
      _RESOURCE_PATH_OK = True
  except ImportError:
      _RESOURCE_PATH_OK = False


# ── Inline SVGs ─────────────────────────────────────────────────────────────

_SHIELD_UPDATE_SVG = b"""<svg width="56" height="56" viewBox="0 0 56 56" xmlns="http://www.w3.org/2000/svg">
<defs>
  <linearGradient id="g1" x1="0%" y1="0%" x2="100%" y2="100%">
    <stop offset="0%" stop-color="#7C3AED"/>
    <stop offset="100%" stop-color="#06B6D4"/>
  </linearGradient>
  <filter id="glow">
    <feGaussianBlur stdDeviation="2.5" result="coloredBlur"/>
    <feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
</defs>
<rect width="56" height="56" rx="15" fill="url(#g1)" opacity="0.12"/>
<rect x="2" y="2" width="52" height="52" rx="13" fill="none" stroke="url(#g1)" stroke-width="1.5"/>
<path d="M28 10 L46 17 L46 30 C46 40 28 47 28 47 C28 47 10 40 10 30 L10 17 Z"
  fill="none" stroke="#8B5CF6" stroke-width="1.8" stroke-linejoin="round" filter="url(#glow)"/>
<path d="M22 28 L26 32 L34 24" stroke="#06B6D4" stroke-width="2.2"
  stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""

_ROCKET_SVG = b"""<svg width="20" height="20" viewBox="0 0 24 24" fill="none"
  xmlns="http://www.w3.org/2000/svg" stroke="white" stroke-width="1.75"
  stroke-linecap="round" stroke-linejoin="round">
<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/>
<path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/>
<path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/>
<path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>
</svg>"""

_ZAP_SVG = b"""<svg width="14" height="14" viewBox="0 0 24 24" fill="none"
  xmlns="http://www.w3.org/2000/svg" stroke="#22c55e" stroke-width="2"
  stroke-linecap="round" stroke-linejoin="round">
<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
</svg>"""

_SKIP_SVG = b"""<svg width="16" height="16" viewBox="0 0 24 24" fill="none"
  xmlns="http://www.w3.org/2000/svg" stroke="#6666AA" stroke-width="1.75"
  stroke-linecap="round" stroke-linejoin="round">
<circle cx="12" cy="12" r="10"/>
<line x1="8" y1="12" x2="16" y2="12"/>
</svg>"""


def _svg_pixmap(data: bytes, size: int) -> QPixmap:
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    if _HAS_SVG:
        r = QSvgRenderer(QByteArray(data))
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r.render(p)
        p.end()
    return px


def _load_logo_pixmap(size: int) -> "QPixmap | None":
      """Загружает оригинальный логотип fmail_logo.png из assets. Возвращает None при ошибке."""
      try:
          import os, sys
          if _RESOURCE_PATH_OK:
              logo_path = _resource_path("assets", "images", "fmail_logo.png")
          else:
              base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
              # gui/dialogs/ -> gui/ -> repo_root
              base = os.path.dirname(os.path.dirname(base))
              logo_path = os.path.join(base, "assets", "images", "fmail_logo.png")
          from PyQt6.QtGui import QPixmap
          from PyQt6.QtCore import Qt
          pix = QPixmap(logo_path)
          if not pix.isNull():
              return pix.scaled(
                  size, size,
                  Qt.AspectRatioMode.KeepAspectRatio,
                  Qt.TransformationMode.SmoothTransformation,
              )
      except Exception:
          pass
      return None


  def _fmt_size(b: int) -> str:
    if b >= 1_048_576:
        return f"{b / 1_048_576:.1f} МБ"
    if b >= 1024:
        return f"{b / 1024:.0f} КБ"
    return f"{b} Б"


# ── Animated orb background ─────────────────────────────────────────────────

import math


class _AnimBg(QWidget):
    """Lightweight orb painter — same visual as AnimatedBackground widget."""

    _ORBS = [
        (0.20, 0.30, 0.50, (139, 92, 246),  0.35, 0.28, 0.0),
        (0.78, 0.65, 0.42, (6, 182, 212),   0.28, 0.22, 2.1),
        (0.60, 0.18, 0.36, (91, 33, 182),   0.22, 0.18, 4.3),
    ]
    _FPS = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._t = 0.0
        self._aurora_t = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(1000 // self._FPS)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self):
        dt = 1.0 / self._FPS
        self._t += dt
        self._aurora_t += dt * 0.15
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        base = QLinearGradient(0, 0, 0, h)
        base.setColorAt(0.0, QColor("#040410"))
        base.setColorAt(0.5, QColor("#060614"))
        base.setColorAt(1.0, QColor("#040410"))
        p.fillRect(0, 0, w, h, base)

        dot_color = QColor(80, 80, 140, 16)
        step = 30
        p.setPen(dot_color)
        for gx in range(0, w + step, step):
            for gy in range(0, h + step, step):
                p.drawPoint(gx, gy)

        aurora_a = 0.04 + 0.025 * math.sin(self._aurora_t * math.pi * 2)
        aurora = QLinearGradient(0, int(h * 0.3), w, int(h * 0.7))
        aurora.setColorAt(0.0, QColor(0, 0, 0, 0))
        aurora.setColorAt(0.3, QColor(139, 92, 246, int(255 * aurora_a)))
        aurora.setColorAt(0.6, QColor(6, 182, 212, int(255 * aurora_a * 0.6)))
        aurora.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(0, 0, w, h, aurora)

        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
        for cx, cy, r_frac, color, sx, sy, phase in self._ORBS:
            ox = cx * w + math.sin(self._t * sx + phase) * 0.18 * w
            oy = cy * h + math.cos(self._t * sy + phase * 1.3) * 0.15 * h
            radius = r_frac * min(w, h)
            r2, g2, b2 = color
            grad = QRadialGradient(ox, oy, radius)
            grad.setColorAt(0.0, QColor(r2, g2, b2, 60))
            grad.setColorAt(0.35, QColor(r2, g2, b2, 24))
            grad.setColorAt(0.7,  QColor(r2, g2, b2, 8))
            grad.setColorAt(1.0,  QColor(0, 0, 0, 0))
            p.setBrush(grad)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(int(ox - radius), int(oy - radius),
                          int(radius * 2), int(radius * 2))
        p.end()

    def hideEvent(self, e):
        self._timer.stop(); super().hideEvent(e)

    def showEvent(self, e):
        if not self._timer.isActive():
            self._timer.start()
        super().showEvent(e)


# ── Patch worker thread ──────────────────────────────────────────────────────

class _PatchWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(bool, str)

    def __init__(self, info: UpdateInfo):
        super().__init__()
        self._info = info

    def run(self):
        def _cb(cur, tot, fname):
            self.progress.emit(cur, tot, fname)

        ok, err = apply_patch(self._info.patch_files, on_progress=_cb)
        self.finished.emit(ok, err)


class _ManifestWorker(QThread):
    done = pyqtSignal(bool)

    def __init__(self, info: UpdateInfo):
        super().__init__()
        self._info = info

    def run(self):
        ok = fetch_patch_manifest(self._info)
        self.done.emit(ok)


# ── Main dialog ──────────────────────────────────────────────────────────────

class UpdateSplashDialog(QDialog):
    """
    Pre-launch update dialog.
    Call show_if_needed() class method — handles all logic and returns True
    if the app should restart (patch applied).
    """

    def __init__(self, info: UpdateInfo, parent=None):
        super().__init__(parent)
        self._info = info
        self._patch_worker: _PatchWorker | None = None
        self._manifest_worker: _ManifestWorker | None = None
        self._downloader: Downloader | None = None
        self._restart_requested = False
        self._patch_mode = False

        self.setWindowTitle(f"FMail Sender — Доступно обновление v{info.version}")
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setMinimumSize(560, 420)
        self.resize(620, 480)

        self._setup_ui()
        QTimer.singleShot(80, self._load_manifest)

    # ── Layout ───────────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._bg = _AnimBg(self)
        self._bg.setGeometry(0, 0, self.width(), self.height())

        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(1)

        h_row = QHBoxLayout()
        h_row.setContentsMargins(0, 0, 0, 0)
        h_row.addStretch(1)

        card = QFrame()
        card.setObjectName("update_splash_card")
        card.setStyleSheet("""
            QFrame#update_splash_card {
                background: rgba(8, 8, 20, 0.96);
                border: 1px solid rgba(139, 92, 246, 0.40);
                border-radius: 20px;
            }
        """)
        card.setMinimumWidth(480)
        card.setMaximumWidth(580)
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        cl = QVBoxLayout(card)
        cl.setContentsMargins(40, 36, 40, 36)
        cl.setSpacing(0)

        # Icon — оригинальный логотип fmail_logo.png, SVG как запасной вариант
        icon_row = QHBoxLayout()
        icon_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl = QLabel()
        _real_logo = _load_logo_pixmap(64)
        if _real_logo is not None:
            icon_lbl.setPixmap(_real_logo)
            icon_lbl.setFixedSize(64, 64)
        else:
            icon_lbl.setPixmap(_svg_pixmap(_SHIELD_UPDATE_SVG, 56))
            icon_lbl.setFixedSize(56, 56)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("background: transparent; border: none;")
        icon_row.addWidget(icon_lbl)
        cl.addLayout(icon_row)
        cl.addSpacing(16)

        # Title
        title = QLabel(f"FMail Sender v{self._info.version}")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "font-size: 22px; font-weight: 700; "
            f"color: {Colors.TEXT_PRIMARY}; background: transparent;"
        )
        cl.addWidget(title)
        cl.addSpacing(4)

        subtitle = QLabel("Доступно новое обновление")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 13px; background: transparent;"
        )
        cl.addWidget(subtitle)
        cl.addSpacing(20)

        # Patch badge (hidden initially)
        self._badge_row = QHBoxLayout()
        self._badge_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge_icon = QLabel()
        self._badge_icon.setPixmap(_svg_pixmap(_ZAP_SVG, 14))
        self._badge_icon.setFixedSize(18, 18)
        self._badge_icon.setStyleSheet("background: transparent;")
        self._badge_icon.setVisible(False)
        self._badge_row.addWidget(self._badge_icon)
        self._badge_lbl = QLabel()
        self._badge_lbl.setStyleSheet(
            "color: #22c55e; font-size: 12px; font-weight: 600; "
            "background: rgba(34,197,94,0.08); border: 1px solid rgba(34,197,94,0.20); "
            "border-radius: 10px; padding: 2px 10px;"
        )
        self._badge_lbl.setVisible(False)
        self._badge_row.addWidget(self._badge_lbl)
        cl.addLayout(self._badge_row)
        self._badge_spacer = QSpacerItem(0, 0,
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        cl.addSpacerItem(self._badge_spacer)

        # Changelog snippet
        body_text = (self._info.body or "").strip()
        if body_text:
            notes_lbl = QLabel("Что нового:")
            notes_lbl.setStyleSheet(
                f"color: {Colors.TEXT_MUTED}; font-size: 11px; "
                "font-weight: 600; letter-spacing: 0.04em; background: transparent;"
            )
            cl.addSpacing(8)
            cl.addWidget(notes_lbl)
            cl.addSpacing(4)

            max_lines = 4
            lines = body_text.splitlines()
            trimmed = "\n".join(lines[:max_lines])
            if len(lines) > max_lines:
                trimmed += f"\n… ещё {len(lines) - max_lines} строк"

            notes_box = QLabel(trimmed)
            notes_box.setWordWrap(True)
            notes_box.setStyleSheet(
                f"color: {Colors.TEXT_SECONDARY}; font-size: 12px; "
                "background: rgba(255,255,255,0.03); "
                "border: 1px solid rgba(139,92,246,0.12); "
                "border-radius: 8px; padding: 10px 12px;"
            )
            cl.addWidget(notes_box)

        cl.addSpacing(20)

        # Progress bar (hidden initially)
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(4)
        self._progress.setVisible(False)
        self._progress.setStyleSheet(
            "QProgressBar { background: rgba(139,92,246,0.12); "
            "border-radius: 2px; border: none; }"
            "QProgressBar::chunk { background: qlineargradient("
            "x1:0,y1:0,x2:1,y2:0,stop:0 #7C3AED,stop:1 #06B6D4); border-radius: 2px; }"
        )
        cl.addWidget(self._progress)

        self._status_lbl = QLabel("")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 12px; background: transparent;"
        )
        self._status_lbl.setVisible(False)
        cl.addWidget(self._status_lbl)
        cl.addSpacing(4)

        # Buttons
        btn_col = QVBoxLayout()
        btn_col.setSpacing(8)

        self._btn_install = QPushButton("  Установить обновление")
        self._btn_install.setIcon(self._rocket_icon())
        self._btn_install.setIconSize(QSize(18, 18))
        self._btn_install.setMinimumHeight(48)
        self._btn_install.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_install.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #7C3AED, stop:1 #06B6D4); color: white; font-size: 14px; "
            "font-weight: 700; border-radius: 10px; border: none; }"
            "QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #6D28D9, stop:1 #0891B2); }"
            "QPushButton:disabled { background: rgba(139,92,246,0.25); "
            "color: rgba(255,255,255,0.35); }"
        )
        self._btn_install.clicked.connect(self._do_install)
        btn_col.addWidget(self._btn_install)

        aux_row = QHBoxLayout()
        aux_row.setSpacing(8)

        self._btn_skip = QPushButton("Пропустить эту версию")
        self._btn_skip.setMinimumHeight(36)
        self._btn_skip.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_skip.setStyleSheet(
            f"QPushButton {{ color: {Colors.TEXT_MUTED}; font-size: 12px; "
            "background: transparent; border: 1px solid rgba(139,92,246,0.12); "
            "border-radius: 8px; padding: 0 14px; }}"
            f"QPushButton:hover {{ color: {Colors.TEXT_SECONDARY}; "
            "border-color: rgba(139,92,246,0.25); background: rgba(255,255,255,0.03); }}"
        )
        self._btn_skip.clicked.connect(self._do_skip)
        aux_row.addWidget(self._btn_skip)

        self._btn_later = QPushButton("Напомнить позже")
        self._btn_later.setMinimumHeight(36)
        self._btn_later.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_later.setStyleSheet(
            f"QPushButton {{ color: {Colors.TEXT_SECONDARY}; font-size: 12px; "
            "background: rgba(139,92,246,0.08); border: 1px solid rgba(139,92,246,0.20); "
            "border-radius: 8px; padding: 0 14px; }}"
            "QPushButton:hover { background: rgba(139,92,246,0.16); "
            "border-color: rgba(139,92,246,0.40); color: white; }"
        )
        self._btn_later.clicked.connect(self._do_later)
        aux_row.addWidget(self._btn_later)

        btn_col.addLayout(aux_row)
        cl.addLayout(btn_col)

        h_row.addWidget(card)
        h_row.addStretch(1)
        outer.addLayout(h_row)
        outer.addStretch(1)
        root.addLayout(outer)

    @staticmethod
    def _rocket_icon():
        from PyQt6.QtGui import QIcon
        return QIcon(_svg_pixmap(_ROCKET_SVG, 20))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._bg.setGeometry(0, 0, self.width(), self.height())

    # ── Manifest ─────────────────────────────────────────────────────────────

    def _load_manifest(self):
        if not self._info.patch_manifest_url:
            return
        self._manifest_worker = _ManifestWorker(self._info)
        self._manifest_worker.done.connect(self._on_manifest_done)
        self._manifest_worker.start()

    def _on_manifest_done(self, ok: bool):
        if not ok or not self._info.is_patch_available:
            return
        self._patch_mode = True
        patch_kb = self._info.patch_size / 1024
        full_mb = (self._info.download_size / 1_048_576
                   if self._info.download_size else 0)

        badge = f"Быстрый патч: ~{patch_kb:.0f} КБ"
        if full_mb:
            badge += f"  (вместо {full_mb:.0f} МБ EXE)"
        self._badge_lbl.setText(badge)
        self._badge_lbl.setVisible(True)
        self._badge_icon.setVisible(True)

        self._badge_spacer = QSpacerItem(
            0, 6, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum
        )
        self._btn_install.setText("  Применить патч")
        self.adjustSize()

    # ── Actions ──────────────────────────────────────────────────────────────

    def _lock_buttons(self):
        self._btn_install.setEnabled(False)
        self._btn_skip.setEnabled(False)
        self._btn_later.setEnabled(False)

    def _do_install(self):
        self._lock_buttons()
        self._progress.setVisible(True)
        self._status_lbl.setVisible(True)
        clear_remind_later()

        if self._patch_mode and self._info.is_patch_available:
            self._run_patch()
        else:
            self._run_full_download()

    def _run_patch(self):
        self._status_lbl.setText("Загружаем обновление…")
        total = max(len(self._info.patch_files), 1)
        self._progress.setRange(0, total)
        self._progress.setValue(0)

        self._patch_worker = _PatchWorker(self._info)
        self._patch_worker.progress.connect(self._on_patch_progress)
        self._patch_worker.finished.connect(self._on_patch_done)
        self._patch_worker.start()

    def _on_patch_progress(self, cur: int, tot: int, fname: str):
        self._progress.setRange(0, tot)
        self._progress.setValue(cur)
        name = Path(fname).name if fname else ""
        self._status_lbl.setText(f"Обновляем: {name}")

    def _on_patch_done(self, ok: bool, err: str):
        self._progress.setRange(0, 1)
        self._progress.setValue(1)
        if ok:
            n = len(self._info.patch_files)
            self._status_lbl.setStyleSheet(
                "color: #22c55e; font-size: 13px; font-weight: 600; background: transparent;"
            )
            self._status_lbl.setText(
                f"✓ Обновлено {n} файл{'ов' if n != 1 else ''}. "
                "Перезапускаем…"
            )
            self._restart_requested = True
            QTimer.singleShot(900, self._finish_restart)
        else:
            self._status_lbl.setStyleSheet(
                f"color: {Colors.ERROR}; font-size: 12px; background: transparent;"
            )
            self._status_lbl.setText(f"Ошибка: {err}")
            self._btn_install.setEnabled(True)
            self._btn_install.setText("  Повторить")
            self._btn_later.setEnabled(True)

    def _run_full_download(self):
        import tempfile
        tmp = Path(tempfile.mkdtemp(prefix="fms_upd_"))
        dest = tmp / f"FMailSender_{self._info.version}.exe"
        self._status_lbl.setText("Загрузка полного обновления…")
        self._progress.setRange(0, 100)

        def _prog(done: int, total: int):
            pct = int(done / total * 100) if total else 0
            label = (f"{_fmt_size(done)} / {_fmt_size(total)}"
                     if total else _fmt_size(done))
            QTimer.singleShot(0, lambda: (
                self._progress.setValue(pct),
                self._status_lbl.setText(f"Загрузка: {label}"),
            ))

        def _done(ok: bool, err: str):
            QTimer.singleShot(0, lambda: self._on_full_done(ok, err, dest))

        self._downloader = Downloader(
            self._info.download_url, dest,
            on_progress=_prog, on_done=_done,
        )
        self._downloader.start()

    def _on_full_done(self, ok: bool, err: str, dest: Path):
        if ok and dest.exists():
            self._status_lbl.setStyleSheet(
                "color: #22c55e; font-size: 13px; font-weight: 600; background: transparent;"
            )
            self._status_lbl.setText("Загрузка завершена. Устанавливаем…")
            QTimer.singleShot(500, lambda: apply_update_windows(dest))
        else:
            self._status_lbl.setStyleSheet(
                f"color: {Colors.ERROR}; font-size: 12px; background: transparent;"
            )
            self._status_lbl.setText(f"Ошибка загрузки: {err}")
            self._btn_install.setEnabled(True)
            self._btn_later.setEnabled(True)

    def _finish_restart(self):
        self._restart_requested = True
        self.accept()

    def _do_skip(self):
        skip_version(self._info.version)
        self.reject()

    def _do_later(self):
        set_remind_later()
        self.reject()

    def closeEvent(self, e):
        if self._downloader:
            self._downloader.cancel()
        super().closeEvent(e)

    # ── Public factory ───────────────────────────────────────────────────────

    @classmethod
    def show_if_needed(cls, parent=None) -> bool:
        """
        Checks for update and shows dialog if needed.
        Returns True if app should restart (patch applied).
        Call this after QApplication is set up, before showing any window.
        """
        from core.update_settings import is_version_skipped, is_remind_later_active
        from core.updater import check_for_update

        if is_remind_later_active():
            return False

        info = check_for_update(timeout=6.0)
        if info is None:
            return False

        if is_version_skipped(info.version):
            return False

        dlg = cls(info, parent)
        dlg.exec()
        return dlg._restart_requested
