"""
Screen 0: License Activation — FMail Sender.
Web3 glassmorphism redesign. Logo, HWID display, key input, activation progress.
Supports demo key activation offline.
"""
import threading
from PyQt6.QtWidgets import (
  QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
  QPushButton, QProgressBar, QGraphicsDropShadowEffect, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QGuiApplication
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtCore import QByteArray

from core.license import generate_hwid, activate_license, validate_key_format, DEMO_KEY
from gui.theme import Colors, Typography, Spacing
from core._version import APP_NAME

# FMail Sender Web3 / Glassmorphism SVG logo
SVG_LOGO = b"""<svg width="80" height="80" viewBox="0 0 80 80" xmlns="http://www.w3.org/2000/svg">
<defs>
  <linearGradient id="g1" x1="0%" y1="0%" x2="100%" y2="100%">
    <stop offset="0%" style="stop-color:#7C3AED;stop-opacity:1"/>
    <stop offset="100%" style="stop-color:#06B6D4;stop-opacity:1"/>
  </linearGradient>
  <linearGradient id="g2" x1="0%" y1="100%" x2="100%" y2="0%">
    <stop offset="0%" style="stop-color:#8B5CF6;stop-opacity:1"/>
    <stop offset="100%" style="stop-color:#0891B2;stop-opacity:1"/>
  </linearGradient>
  <filter id="glow">
    <feGaussianBlur stdDeviation="2.5" result="coloredBlur"/>
    <feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
</defs>
<!-- Outer glass ring -->
<rect width="80" height="80" rx="22" fill="url(#g1)" opacity="0.10"/>
<rect x="1.5" y="1.5" width="77" height="77" rx="20.5" fill="none" stroke="url(#g1)" stroke-width="1.5" opacity="0.6"/>
<!-- Inner neon envelope -->
<rect x="14" y="22" width="52" height="36" rx="5" fill="none" stroke="url(#g2)" stroke-width="2.5" filter="url(#glow)"/>
<path d="M14 26 L40 44 L66 26" stroke="#8B5CF6" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round" filter="url(#glow)"/>
<!-- Hexagonal grid dots (Web3 aesthetic) -->
<circle cx="40" cy="12" r="1.5" fill="#7C3AED" opacity="0.5"/>
<circle cx="52" cy="12" r="1.5" fill="#06B6D4" opacity="0.4"/>
<circle cx="28" cy="12" r="1.5" fill="#06B6D4" opacity="0.4"/>
<circle cx="40" cy="68" r="1.5" fill="#7C3AED" opacity="0.5"/>
</svg>"""


class ActivationScreen(QWidget):
  activation_success = pyqtSignal(object)

  def __init__(self, parent=None, hint_message: str = ""):
      super().__init__(parent)
      self._hwid = generate_hwid()
      self._hint_message = hint_message
      self._setup_ui()

  def _setup_ui(self):
      outer = QVBoxLayout(self)
      outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
      outer.setContentsMargins(40, 40, 40, 40)

      card = QFrame()
      card.setObjectName("activation_container")
      card.setFixedWidth(520)
      shadow = QGraphicsDropShadowEffect()
      shadow.setBlurRadius(60)
      shadow.setOffset(0, 12)
      shadow.setColor(QColor(124, 58, 237, 60))
      card.setGraphicsEffect(shadow)

      layout = QVBoxLayout(card)
      layout.setSpacing(Spacing.LG)
      layout.setContentsMargins(Spacing.XXL, Spacing.XXL, Spacing.XXL, Spacing.XXL)

      # Logo + title
      logo_row = QHBoxLayout()
      logo_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
      svg = QSvgWidget()
      svg.load(QByteArray(SVG_LOGO))
      svg.setFixedSize(80, 80)
      logo_row.addWidget(svg)
      layout.addLayout(logo_row)

      title = QLabel(APP_NAME)
      title.setObjectName("label_title")
      title.setAlignment(Qt.AlignmentFlag.AlignCenter)
      layout.addWidget(title)

      subtitle = QLabel("Введите лицензионный ключ для активации")
      subtitle.setObjectName("label_subtitle")
      subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
      layout.addWidget(subtitle)

      # Demo key hint card
      demo_frame = QFrame()
      demo_frame.setObjectName("card")
      demo_layout = QVBoxLayout(demo_frame)
      demo_layout.setContentsMargins(14, 12, 14, 12)
      demo_layout.setSpacing(6)

      demo_header_row = QHBoxLayout()
      demo_title = QLabel("Демо-ключ для тестирования")
      demo_title.setObjectName("label_muted")
      demo_header_row.addWidget(demo_title)
      demo_badge = QLabel("OFFLINE")
      demo_badge.setObjectName("demo_badge")
      demo_header_row.addWidget(demo_badge)
      demo_layout.addLayout(demo_header_row)

      self.demo_key_label = QLabel(DEMO_KEY)
      self.demo_key_label.setStyleSheet(
          f"color:{Colors.CYAN};font-family:monospace;font-weight:bold;font-size:14px;"
          f"letter-spacing:1px;background:transparent;"
      )
      self.demo_key_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
      demo_layout.addWidget(self.demo_key_label)

      demo_btn_row = QHBoxLayout()
      copy_btn = QPushButton("Копировать")
      copy_btn.setObjectName("btn_secondary")
      copy_btn.clicked.connect(self._copy_demo_key)
      demo_btn_row.addWidget(copy_btn)
      fill_btn = QPushButton("Заполнить →")
      fill_btn.clicked.connect(lambda: self.key_input.setText(DEMO_KEY))
      demo_btn_row.addWidget(fill_btn)
      demo_btn_row.addStretch()
      demo_layout.addLayout(demo_btn_row)
      layout.addWidget(demo_frame)

      # HWID row
      hwid_row = QHBoxLayout()
      hwid_lbl = QLabel("HWID:")
      hwid_lbl.setFixedWidth(50)
      hwid_lbl.setObjectName("label_muted")
      hwid_row.addWidget(hwid_lbl)
      self.hwid_display = QLineEdit(self._hwid)
      self.hwid_display.setReadOnly(True)
      self.hwid_display.setStyleSheet(
          f"color:{Colors.TEXT_MUTED};font-family:monospace;font-size:11px;background:transparent;"
      )
      hwid_row.addWidget(self.hwid_display)
      copy_hwid_btn = QPushButton("Копировать HWID")
      copy_hwid_btn.setObjectName("btn_secondary")
      copy_hwid_btn.clicked.connect(lambda: QGuiApplication.clipboard().setText(self._hwid))
      hwid_row.addWidget(copy_hwid_btn)
      layout.addLayout(hwid_row)

      # Key input
      key_lbl = QLabel("Лицензионный ключ")
      key_lbl.setObjectName("label_muted")
      layout.addWidget(key_lbl)

      self.key_input = QLineEdit()
      self.key_input.setObjectName("key_input")
      self.key_input.setPlaceholderText("FMS-XXXXX-XXXXX-XXXXX-XXXXX")
      self.key_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
      self.key_input.textChanged.connect(self._on_key_changed)
      layout.addWidget(self.key_input)

      self.status_label = QLabel("")
      if self._hint_message:
          self.status_label.setText(self._hint_message)
          self.status_label.setStyleSheet(f"color:{Colors.TEXT_MUTED};font-size:12px;")
      self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
      self.status_label.setWordWrap(True)
      layout.addWidget(self.status_label)

      self.progress_bar = QProgressBar()
      self.progress_bar.setObjectName("activation_bar")
      self.progress_bar.setRange(0, 4)
      self.progress_bar.setValue(0)
      self.progress_bar.setVisible(False)
      layout.addWidget(self.progress_bar)

      self.activate_btn = QPushButton("Активировать")
      self.activate_btn.setObjectName("btn_activate")
      self.activate_btn.setFixedHeight(48)
      self.activate_btn.clicked.connect(self._activate)
      layout.addWidget(self.activate_btn)

      outer.addWidget(card)

  def _copy_demo_key(self):
      QGuiApplication.clipboard().setText(DEMO_KEY)
      self.demo_key_label.setText("✓ Скопировано!")
      QTimer.singleShot(2000, lambda: self.demo_key_label.setText(DEMO_KEY))

  def _on_key_changed(self, text: str):
      upper = text.upper().strip()
      if upper == DEMO_KEY:
          self.status_label.setText("Демо-ключ — работает без интернета")
          self.status_label.setStyleSheet(f"color:{Colors.SUCCESS};")
      elif validate_key_format(text) or text == "":
          self.status_label.setText("")
      else:
          self.status_label.setText("Неверный формат ключа")
          self.status_label.setStyleSheet(f"color:{Colors.WARNING};")

  def _activate(self):
      key = self.key_input.text().strip()
      if not key:
          self.status_label.setText("Введите лицензионный ключ")
          self.status_label.setStyleSheet(f"color:{Colors.ERROR};")
          return

      self.activate_btn.setEnabled(False)
      self.key_input.setEnabled(False)
      self.progress_bar.setVisible(True)
      self.progress_bar.setValue(0)
      self.status_label.setText("Активация...")
      self.status_label.setStyleSheet(f"color:{Colors.TEXT_SECONDARY};")

      def progress_cb(step: int, msg: str):
          QTimer.singleShot(0, lambda: (
              self.progress_bar.setValue(step),
              self.status_label.setText(msg)
          ))

      def run():
          try:
              success, message = activate_license(key, progress_callback=progress_cb)
          except Exception as exc:
              success, message = False, f"Ошибка: {exc}"

          def finish():
              self.progress_bar.setValue(4 if success else 0)
              self.progress_bar.setVisible(not success)
              if success:
                  self.status_label.setText(f"✓ {message}")
                  self.status_label.setStyleSheet(f"color:{Colors.SUCCESS};")
                  from core.license import check_license
                  valid, license_info, _ = check_license()
                  if valid and license_info:
                      QTimer.singleShot(800, lambda: self.activation_success.emit(license_info))
              else:
                  self.status_label.setText(f"✗ {message}")
                  self.status_label.setStyleSheet(f"color:{Colors.ERROR};")
                  self.activate_btn.setEnabled(True)
                  self.key_input.setEnabled(True)

          QTimer.singleShot(0, finish)

      threading.Thread(target=run, daemon=True).start()
