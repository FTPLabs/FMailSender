"""
  Экран активации лицензии.
  Фикс: если check_license() возвращает None сразу после активации — делаем retry.
  """
  import time
  from PyQt6.QtWidgets import (
      QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
      QPushButton, QProgressBar, QFrame, QSizePolicy, QSpacerItem,
      QApplication
  )
  from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer
  from PyQt6.QtGui import QFont, QClipboard
  from PyQt6.QtSvgWidgets import QSvgWidget
  from PyQt6.QtCore import QByteArray

  from core.license import activate_license, generate_hwid, LicenseInfo, KEY_PREFIX
  from gui.theme import Colors, Spacing, Typography, Radii


  MAIL_ICON_SVG = b"""<svg width="52" height="52" viewBox="0 0 52 52" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="g1" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#7C3AED"/>
      <stop offset="100%" style="stop-color:#06B6D4"/>
    </linearGradient>
  </defs>
  <rect width="52" height="52" rx="14" fill="url(#g1)" opacity="0.15"/>
  <rect x="2" y="2" width="48" height="48" rx="12" fill="none" stroke="url(#g1)" stroke-width="2"/>
  <rect x="10" y="16" width="32" height="20" rx="3" fill="none" stroke="#8B5CF6" stroke-width="1.8"/>
  <path d="M10 18 L26 28 L42 18" stroke="#06B6D4" stroke-width="1.8" fill="none" stroke-linecap="round"/>
  </svg>"""


  class ActivationWorker(QThread):
      progress = pyqtSignal(int, str)
      finished = pyqtSignal(bool, str, object)

      def __init__(self, key: str):
          super().__init__()
          self._key = key

      def run(self):
          def _cb(step: int, msg: str):
              self.progress.emit(step, msg)

          success, message = activate_license(self._key, progress_callback=_cb)
          if success:
              from core.license import check_license
              # Retry до 3 раз — license.dat мог не успеть записаться
              info = None
              for attempt in range(3):
                  valid, info, _ = check_license()
                  if valid and info:
                      break
                  time.sleep(0.3)
              self.finished.emit(True, message, info)
          else:
              self.finished.emit(False, message, None)


  class ActivationScreen(QWidget):
      activation_success = pyqtSignal(object)

      def __init__(self, hint_message: str = "", parent=None):
          super().__init__(parent)
          self._hwid = generate_hwid()
          self._worker: ActivationWorker = None
          self._hint = hint_message
          self._setup_ui()

      def _setup_ui(self):
          root = QVBoxLayout(self)
          root.setContentsMargins(0, 0, 0, 0)
          root.setSpacing(0)

          root.addStretch(1)

          h_layout = QHBoxLayout()
          h_layout.setContentsMargins(0, 0, 0, 0)
          h_layout.addStretch(1)

          card = QFrame()
          card.setObjectName("activation_card")
          card.setStyleSheet(f"""
              QFrame#activation_card {{
                  background: rgba(10, 10, 26, 0.95);
                  border: 1px solid rgba(139, 92, 246, 0.35);
                  border-radius: 20px;
              }}
          """)
          card.setMinimumWidth(420)
          card.setMaximumWidth(560)
          card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

          card_layout = QVBoxLayout(card)
          card_layout.setContentsMargins(40, 36, 40, 36)
          card_layout.setSpacing(0)

          # ── Icon ────────────────────────────────────────────────────────
          icon_row = QHBoxLayout()
          icon_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
          icon_svg = QSvgWidget()
          icon_svg.load(QByteArray(MAIL_ICON_SVG))
          icon_svg.setFixedSize(52, 52)
          icon_row.addWidget(icon_svg)
          card_layout.addLayout(icon_row)
          card_layout.addSpacing(16)

          # ── Title ────────────────────────────────────────────────────────
          title = QLabel("FMail Sender Pro")
          title.setAlignment(Qt.AlignmentFlag.AlignCenter)
          title.setStyleSheet(
              f"font-size: 22px; font-weight: bold; color: {Colors.TEXT_PRIMARY}; background: transparent;"
          )
          card_layout.addWidget(title)
          card_layout.addSpacing(6)

          subtitle = QLabel("Введите лицензионный ключ для активации")
          subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
          subtitle.setWordWrap(True)
          subtitle.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 13px; background: transparent;")
          card_layout.addWidget(subtitle)
          card_layout.addSpacing(20)

          # ── HWID ─────────────────────────────────────────────────────────
          hwid_row = QHBoxLayout()
          hwid_lbl = QLabel("HWID:")
          hwid_lbl.setFixedWidth(46)
          hwid_lbl.setStyleSheet(f"color: {Colors.CYAN}; font-size: 12px; font-weight: 600; background: transparent;")

          self.hwid_input = QLineEdit(self._hwid)
          self.hwid_input.setReadOnly(True)
          self.hwid_input.setStyleSheet(
              f"background: rgba(255,255,255,0.04); border: 1px solid rgba(139,92,246,0.18); "
              f"border-radius: 7px; color: {Colors.TEXT_SECONDARY}; font-size: 12px; padding: 5px 10px;"
          )

          btn_copy_hwid = QPushButton("Копировать HWID")
          btn_copy_hwid.setObjectName("btn_secondary")
          btn_copy_hwid.setFixedHeight(32)
          btn_copy_hwid.setStyleSheet(
              f"font-size:12px; padding: 0 12px; border-radius: 7px; "
              f"background: rgba(139,92,246,0.12); color: {Colors.TEXT_SECONDARY}; border: 1px solid rgba(139,92,246,0.20);"
          )
          btn_copy_hwid.clicked.connect(self._copy_hwid)
          btn_copy_hwid.setCursor(Qt.CursorShape.PointingHandCursor)

          hwid_row.addWidget(hwid_lbl)
          hwid_row.addWidget(self.hwid_input, 1)
          hwid_row.addSpacing(8)
          hwid_row.addWidget(btn_copy_hwid)
          card_layout.addLayout(hwid_row)
          card_layout.addSpacing(14)

          # ── License key input ────────────────────────────────────────────
          key_lbl = QLabel("Лицензионный ключ")
          key_lbl.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 11px; background: transparent;")
          card_layout.addWidget(key_lbl)
          card_layout.addSpacing(5)

          self.key_input = QLineEdit()
          self.key_input.setPlaceholderText(f"{KEY_PREFIX}-XXXXXX-XXXXXX-XXXXXX-XXXXXX")
          self.key_input.setMinimumHeight(42)
          self.key_input.setStyleSheet(
              f"background: rgba(139,92,246,0.07); border: 1.5px solid rgba(139,92,246,0.30); "
              f"border-radius: 9px; color: {Colors.TEXT_PRIMARY}; font-size: 14px; "
              f"font-weight: 600; padding: 8px 14px; letter-spacing: 1px;"
          )
          self.key_input.returnPressed.connect(self._do_activate)
          card_layout.addWidget(self.key_input)
          card_layout.addSpacing(10)

          # ── Status label ──────────────────────────────────────────────────
          self.status_label = QLabel("")
          self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
          self.status_label.setWordWrap(True)
          self.status_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 12px; background: transparent;")
          if self._hint:
              self.status_label.setText(self._hint)
          card_layout.addWidget(self.status_label)
          card_layout.addSpacing(6)

          # ── Progress bar ──────────────────────────────────────────────────
          self.progress_bar = QProgressBar()
          self.progress_bar.setRange(0, 4)
          self.progress_bar.setValue(0)
          self.progress_bar.setTextVisible(False)
          self.progress_bar.setFixedHeight(4)
          self.progress_bar.setVisible(False)
          self.progress_bar.setStyleSheet(
              f"QProgressBar {{ background: rgba(139,92,246,0.12); border-radius: 2px; border: none; }}"
              f"QProgressBar::chunk {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
              f"stop:0 #7C3AED, stop:1 #06B6D4); border-radius: 2px; }}"
          )
          card_layout.addWidget(self.progress_bar)
          card_layout.addSpacing(16)

          # ── Activate button ───────────────────────────────────────────────
          self.btn_activate = QPushButton("Активировать")
          self.btn_activate.setObjectName("btn_primary")
          self.btn_activate.setMinimumHeight(48)
          self.btn_activate.setCursor(Qt.CursorShape.PointingHandCursor)
          self.btn_activate.setStyleSheet(
              f"QPushButton {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
              f"stop:0 #7C3AED, stop:1 #06B6D4); color: white; font-size: 15px; "
              f"font-weight: 700; border-radius: 10px; border: none; }}"
              f"QPushButton:hover {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
              f"stop:0 #6D28D9, stop:1 #0891B2); }}"
              f"QPushButton:disabled {{ background: rgba(139,92,246,0.25); color: rgba(255,255,255,0.4); }}"
          )
          self.btn_activate.clicked.connect(self._do_activate)
          card_layout.addWidget(self.btn_activate)

          h_layout.addWidget(card)
          h_layout.addStretch(1)
          root.addLayout(h_layout)
          root.addStretch(1)

      def _copy_hwid(self):
          QApplication.clipboard().setText(self._hwid)

      def _do_activate(self):
          key = self.key_input.text().strip()
          if not key:
              self._set_error("Введите лицензионный ключ.")
              return

          self.btn_activate.setEnabled(False)
          self.btn_activate.setText("Активация...")
          self.progress_bar.setValue(0)
          self.progress_bar.setVisible(True)
          self.status_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 12px; background: transparent;")
          self.status_label.setText("Подключение к серверу...")

          self._worker = ActivationWorker(key)
          self._worker.progress.connect(self._on_progress)
          self._worker.finished.connect(self._on_finished)
          self._worker.start()

      def _on_progress(self, step: int, msg: str):
          self.progress_bar.setValue(step)
          self.status_label.setText(msg)

      def _on_finished(self, success: bool, message: str, license_info):
          self.btn_activate.setEnabled(True)
          self.btn_activate.setText("Активировать")
          self.progress_bar.setVisible(False)

          if success:
              self.status_label.setStyleSheet(
                  f"color: #10B981; font-size: 12px; font-weight: 600; background: transparent;"
              )
              self.status_label.setText("✅ Лицензия активирована!")
              self.btn_activate.setEnabled(False)

              if license_info:
                  # Открываем главное приложение с задержкой 800ms
                  QTimer.singleShot(800, lambda li=license_info: self.activation_success.emit(li))
              else:
                  # Активация прошла, но check_license не смог прочитать токен
                  # (нет JWT_SECRET в окружении) — перезапуск приложения решит проблему
                  self.status_label.setText(
                      "✅ Лицензия активирована!\n"
                      "Перезапустите приложение для входа."
                  )
          else:
              self._set_error(message)

      def _set_error(self, msg: str):
          self.status_label.setStyleSheet(
              f"color: {Colors.ERROR}; font-size: 12px; background: transparent;"
          )
          self.status_label.setText(f"❌ {msg}")
  