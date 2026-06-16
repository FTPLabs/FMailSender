"""
  Main window: CyberPro sidebar navigation + animated background.
  v3.3: CyberPro design — SVG logo, violet/cyan neon sidebar, glass panels.
  """
  from PyQt6.QtWidgets import (
      QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
      QLabel, QPushButton, QFrame, QStackedWidget, QSizePolicy
  )
  from PyQt6.QtCore import Qt, QByteArray, QSize, pyqtSignal
  from PyQt6.QtSvg import QSvgRenderer
  from PyQt6.QtGui import QPixmap, QPainter, QLinearGradient, QColor

  from gui.theme import Colors, Spacing, Typography
  from gui.screens.screen_dashboard import DashboardScreen
  from gui.screens.screen_accounts import AccountsScreen
  from gui.screens.screen_compose import ComposeScreen
  from gui.screens.screen_recipients import RecipientsScreen
  from gui.screens.screen_sending import SendingScreen
  from gui.screens.screen_analytics import AnalyticsScreen
  from gui.screens.screen_inbox import InboxScreen
  from gui.widgets.animated_bg import AnimatedBackground
  from core.license import LicenseInfo
  from core.updater import start_background_check
  from core._version import APP_NAME


  # ── SVG icon registry (Lucide-style) ─────────────────────────────────────────
  ICONS: dict[str, bytes] = {
      "dashboard":  b'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="COLOR" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>',
      "accounts":   b'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="COLOR" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
      "compose":    b'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="COLOR" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>',
      "recipients": b'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="COLOR" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
      "sending":    b'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="COLOR" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>',
      "analytics":  b'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="COLOR" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>',
      "inbox":      b'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="COLOR" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/></svg>',
  }

  # CyberPro SVG logo (gradient envelope)
  _LOGO_SVG = b"""<svg width="28" height="28" viewBox="0 0 52 52" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="lg" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#7C3AED"/>
        <stop offset="100%" stop-color="#06B6D4"/>
      </linearGradient>
    </defs>
    <rect width="52" height="52" rx="14" fill="url(#lg)" fill-opacity="0.18"/>
    <rect x="2" y="2" width="48" height="48" rx="12" fill="none" stroke="url(#lg)" stroke-width="2"/>
    <rect x="10" y="16" width="32" height="20" rx="3" fill="none" stroke="#8B5CF6" stroke-width="1.8"/>
    <path d="M10 18 L26 28 L42 18" stroke="#06B6D4" stroke-width="1.8" fill="none" stroke-linecap="round"/>
  </svg>"""


  def _svg_to_pixmap(svg_bytes: bytes, size: int) -> QPixmap:
      renderer = QSvgRenderer(QByteArray(svg_bytes))
      pixmap = QPixmap(size, size)
      pixmap.fill(Qt.GlobalColor.transparent)
      painter = QPainter(pixmap)
      painter.setRenderHint(QPainter.RenderHint.Antialiasing)
      renderer.render(painter)
      painter.end()
      return pixmap


  def _make_svg_icon(name: str, color: str) -> QLabel:
      svg_data = ICONS.get(name, b"")
      colored = svg_data.replace(b"COLOR", color.encode("utf-8"))
      lbl = QLabel()
      lbl.setFixedSize(18, 18)
      lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
      lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
      lbl.setStyleSheet("background: transparent; border: none;")
      lbl.setPixmap(_svg_to_pixmap(colored, 18))
      return lbl


  # ── Sidebar nav button ────────────────────────────────────────────────────────
  _BTN_BASE = (
      "QPushButton {"
      "  background: transparent;"
      "  border: none;"
      "  border-radius: 6px;"
      "  text-align: left;"
      "  padding: 0;"
      "}"
      "QPushButton:hover {"
      f"  background: rgba(139, 92, 246, 0.08);"
      "}"
  )
  _BTN_ACTIVE = (
      "QPushButton {"
      "  background: rgba(139, 92, 246, 0.15);"
      "  border: none;"
      "  border-radius: 6px;"
      "  text-align: left;"
      "  padding: 0;"
      "}"
      "QPushButton:hover {"
      "  background: rgba(139, 92, 246, 0.20);"
      "}"
  )


  class SidebarButton(QPushButton):
      def __init__(self, icon_name: str, label: str, badge: str = "", parent=None):
          super().__init__(parent)
          self._icon_name = icon_name
          self._badge_text = badge
          self._active = False

          layout = QHBoxLayout(self)
          layout.setContentsMargins(12, 0, 12, 0)
          layout.setSpacing(10)

          self._icon_widget = _make_svg_icon(icon_name, Colors.TEXT_SECONDARY)
          layout.addWidget(self._icon_widget)

          self._text_label = QLabel(label)
          self._text_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
          self._text_label.setStyleSheet(
              f"color: {Colors.TEXT_SECONDARY}; background: transparent; border: none;"
              f" font-size: 13px; font-weight: 600;"
          )
          layout.addWidget(self._text_label)
          layout.addStretch()

          if badge:
              self._badge_lbl = QLabel(badge)
              self._badge_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
              self._badge_lbl.setStyleSheet(
                  "background: rgba(139,92,246,0.20); color: #8B5CF6;"
                  " border: 1px solid rgba(139,92,246,0.30);"
                  " border-radius: 9px; padding: 1px 6px;"
                  " font-size: 10px; font-family: monospace; font-weight: 600;"
              )
              layout.addWidget(self._badge_lbl)

          self.setFixedHeight(38)
          self.setStyleSheet(_BTN_BASE)
          self.setCursor(Qt.CursorShape.PointingHandCursor)

      def set_active(self, active: bool) -> None:
          self._active = active
          color = Colors.ACCENT if active else Colors.TEXT_SECONDARY
          svg_data = ICONS.get(self._icon_name, b"")
          colored = svg_data.replace(b"COLOR", color.encode("utf-8"))
          self._icon_widget.setPixmap(_svg_to_pixmap(colored, 18))
          self._text_label.setStyleSheet(
              f"color: {'white' if active else Colors.TEXT_SECONDARY};"
              " background: transparent; border: none;"
              " font-size: 13px; font-weight: 600;"
          )
          self.setStyleSheet(_BTN_ACTIVE if active else _BTN_BASE)

      def set_badge(self, text: str) -> None:
          if hasattr(self, "_badge_lbl"):
              self._badge_lbl.setText(text)


  # ── Main Window ───────────────────────────────────────────────────────────────
  class MainWindow(QMainWindow):
      _update_available = pyqtSignal(dict)

      def __init__(self, license_info: LicenseInfo):
          super().__init__()
          self._license = license_info
          self.setWindowTitle(APP_NAME)
          self.setMinimumSize(1100, 680)
          self.resize(1280, 780)
          self._setup_ui()
          self._update_available.connect(self._on_update_found)
          start_background_check(lambda info: self._update_available.emit(info), delay_sec=30.0)

      def _on_update_found(self, info: dict) -> None:
          from PyQt6.QtWidgets import QMessageBox
          tag = info.get("tag_name", "")
          url = info.get("html_url", "")
          QMessageBox.information(
              self,
              "Доступно обновление",
              f"Новая версия {tag} доступна!\n\nСкачать: {url}",
          )

      def _setup_ui(self) -> None:
          central = QWidget()
          self.setCentralWidget(central)
          root = QHBoxLayout(central)
          root.setContentsMargins(0, 0, 0, 0)
          root.setSpacing(0)

          # ── Sidebar ────────────────────────────────────────────────────────
          sidebar = QFrame()
          sidebar.setObjectName("sidebar")
          sidebar.setFixedWidth(220)
          sidebar.setStyleSheet(
              "QFrame#sidebar {"
              f"  background-color: rgba(4, 4, 16, 0.85);"
              f"  border-right: 1px solid rgba(139, 92, 246, 0.12);"
              "}"
          )
          sidebar_layout = QVBoxLayout(sidebar)
          sidebar_layout.setContentsMargins(8, 0, 8, 0)
          sidebar_layout.setSpacing(1)

          # Logo row
          logo_frame = QFrame()
          logo_frame.setFixedHeight(64)
          logo_frame.setStyleSheet(
              "background: transparent;"
              "border-bottom: 1px solid rgba(139, 92, 246, 0.10);"
          )
          logo_layout = QHBoxLayout(logo_frame)
          logo_layout.setContentsMargins(8, 0, 8, 0)
          logo_layout.setSpacing(10)

          logo_icon = QLabel()
          logo_icon.setFixedSize(28, 28)
          logo_icon.setPixmap(_svg_to_pixmap(_LOGO_SVG, 28))
          logo_layout.addWidget(logo_icon)

          logo_text_col = QVBoxLayout()
          logo_text_col.setSpacing(1)
          logo_name = QLabel("FMail Sender Pro")
          logo_name.setStyleSheet(
              "color: #E8E8FF; font-size: 13px; font-weight: 700;"
              " letter-spacing: 0.3px; background: transparent; border: none;"
          )
          logo_text_col.addWidget(logo_name)
          from core._version import APP_VERSION
          ver_lbl = QLabel(f"v{APP_VERSION}")
          ver_lbl.setStyleSheet(
              "color: #8B5CF6; font-size: 10px; font-family: monospace;"
              " background: transparent; border: none;"
          )
          logo_text_col.addWidget(ver_lbl)
          logo_layout.addLayout(logo_text_col)
          logo_layout.addStretch()
          sidebar_layout.addWidget(logo_frame)

          # Demo badge
          if getattr(self._license, "is_demo", False):
              badge = QLabel("DEMO")
              badge.setObjectName("demo_badge")
              badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
              badge.setStyleSheet(
                  "background: rgba(239,68,68,0.15); color: #EF4444;"
                  " border: 1px solid rgba(239,68,68,0.30);"
                  " border-radius: 6px; padding: 3px 8px;"
                  " font-size: 11px; font-weight: 700; margin: 6px 8px 2px 8px;"
              )
              sidebar_layout.addWidget(badge)

          # Nav section
          nav_spacer = QFrame()
          nav_spacer.setFixedHeight(8)
          nav_spacer.setStyleSheet("background: transparent; border: none;")
          sidebar_layout.addWidget(nav_spacer)

          nav_items = [
              ("dashboard",  "Дашборд",       ""),
              ("accounts",   "Аккаунты",      ""),
              ("compose",    "Письмо",        ""),
              ("recipients", "Получатели",    ""),
              ("sending",    "Рассылка",      ""),
              ("analytics",  "Аналитика",     ""),
              ("inbox",      "Ответы",        ""),
          ]
          self._nav_buttons: list[SidebarButton] = []
          self._nav_keys: list[str] = []
          for icon, label, badge in nav_items:
              btn = SidebarButton(icon, label, badge)
              btn.clicked.connect(lambda checked, i=icon: self._navigate(i))
              sidebar_layout.addWidget(btn)
              self._nav_buttons.append(btn)
              self._nav_keys.append(icon)

          sidebar_layout.addStretch()

          # ── Bottom: license + social ──────────────────────────────────────
          _is_lifetime = self._license.plan.upper() in ("LIFETIME", "LIFE", "LTD", "LIFELONG")
          from gui.icons import make_icon, TELEGRAM, LOLZ
          import webbrowser

          bottom_frame = QFrame()
          bottom_frame.setStyleSheet(
              "background: rgba(139,92,246,0.05);"
              " border-top: 1px solid rgba(139,92,246,0.12);"
              " border-radius: 0;"
          )
          bottom_layout = QVBoxLayout(bottom_frame)
          bottom_layout.setContentsMargins(12, 10, 12, 12)
          bottom_layout.setSpacing(6)

          # License pulse row
          lic_row = QHBoxLayout()
          lic_row.setSpacing(8)
          pulse_dot = QLabel("●")
          pulse_dot.setStyleSheet("color: #8B5CF6; font-size: 8px; background: transparent; border: none;")
          lic_row.addWidget(pulse_dot)

          if _is_lifetime:
              lic_text = "PRO · ∞ lifetime"
          else:
              lic_text = f"PRO · {self._license.expires_at.strftime('%d.%m.%Y')}"
          lic_lbl = QLabel(lic_text)
          lic_lbl.setStyleSheet(
              "color: #8B5CF6; font-size: 11px; font-family: monospace;"
              " font-weight: 600; background: transparent; border: none;"
          )
          lic_row.addWidget(lic_lbl)
          lic_row.addStretch()
          bottom_layout.addLayout(lic_row)

          # Social buttons
          social_row = QHBoxLayout()
          social_row.setSpacing(8)
          social_row.addStretch()

          _tg_btn = QPushButton()
          _tg_btn.setFixedSize(30, 30)
          _tg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
          _tg_btn.setToolTip("Telegram поддержка")
          _tg_btn.setIcon(make_icon(TELEGRAM, 18, "#ffffff"))
          _tg_btn.setIconSize(QSize(18, 18))
          _tg_btn.setStyleSheet(
              "QPushButton { background: transparent; border: none; border-radius: 15px; }"
              "QPushButton:hover { background: rgba(42,171,238,0.15); }"
          )
          _tg_btn.clicked.connect(lambda: webbrowser.open("https://t.me/ftpdev_sup"))
          social_row.addWidget(_tg_btn)

          _lolz_btn = QPushButton()
          _lolz_btn.setFixedSize(30, 30)
          _lolz_btn.setCursor(Qt.CursorShape.PointingHandCursor)
          _lolz_btn.setToolTip("Lolzteam")
          _lolz_btn.setIcon(make_icon(LOLZ, 16, "#22C55E"))
          _lolz_btn.setIconSize(QSize(16, 16))
          _lolz_btn.setStyleSheet(
              "QPushButton { background: transparent; border: none; border-radius: 15px; }"
              "QPushButton:hover { background: rgba(34,197,94,0.15); }"
          )
          _lolz_btn.clicked.connect(lambda: webbrowser.open("https://lolz.live/ftpdev"))
          social_row.addWidget(_lolz_btn)
          social_row.addStretch()
          bottom_layout.addLayout(social_row)

          _by_lbl = QLabel("by ftpdev")
          _by_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
          _by_lbl.setStyleSheet(
              "color: rgba(139,92,246,0.40); font-size: 10px;"
              " letter-spacing: 1.2px; background: transparent; border: none; margin-top: 2px;"
          )
          bottom_layout.addWidget(_by_lbl)
          sidebar_layout.addWidget(bottom_frame)

          root.addWidget(sidebar)

          # ── Main content area ─────────────────────────────────────────────
          main_area = QWidget()
          main_area.setStyleSheet("background: transparent;")
          main_layout = QVBoxLayout(main_area)
          main_layout.setContentsMargins(0, 0, 0, 0)
          main_layout.setSpacing(0)

          self._anim_bg = AnimatedBackground(main_area)
          self._anim_bg.lower()

          self._stack = QStackedWidget()
          self._stack.setStyleSheet("background: transparent;")
          self._screens: dict[str, QWidget] = {}

          screen_map = [
              ("dashboard",  DashboardScreen()),
              ("accounts",   AccountsScreen()),
              ("compose",    ComposeScreen()),
              ("recipients", RecipientsScreen()),
              ("sending",    SendingScreen()),
              ("analytics",  AnalyticsScreen()),
              ("inbox",      InboxScreen()),
          ]
          for key, screen in screen_map:
              screen.setStyleSheet("background: transparent;")
              self._stack.addWidget(screen)
              self._screens[key] = screen

          acct_screen: AccountsScreen = self._screens["accounts"]
          sending_screen: SendingScreen = self._screens["sending"]
          compose_screen: ComposeScreen = self._screens["compose"]
          recip_screen = self._screens["recipients"]
          analytics_screen = self._screens["analytics"]
          dashboard_screen = self._screens["dashboard"]
          inbox_screen: InboxScreen = self._screens["inbox"]

          acct_screen.accounts_changed.connect(sending_screen.set_accounts)
          acct_screen.accounts_changed.connect(inbox_screen.set_accounts)
          if acct_screen._accounts:
              sending_screen.set_accounts(acct_screen._accounts)
              inbox_screen.set_accounts(acct_screen._accounts)
          recip_screen.list_ready.connect(sending_screen.set_recipients)
          compose_screen.template_ready.connect(sending_screen.set_template)
          sending_screen.campaign_finished.connect(analytics_screen.on_results)
          sending_screen.campaign_finished.connect(dashboard_screen.update_campaign_results)

          main_layout.addWidget(self._stack)
          root.addWidget(main_area)

          self._navigate("dashboard")

      def resizeEvent(self, event) -> None:
          super().resizeEvent(event)
          if hasattr(self, "_anim_bg"):
              parent = self._anim_bg.parent()
              if parent:
                  self._anim_bg.setGeometry(0, 0, parent.width(), parent.height())

      def closeEvent(self, event) -> None:
          sending_screen = self._screens.get("sending")
          if sending_screen is not None:
              engine = getattr(sending_screen, "_engine", None)
              if engine is not None:
                  try:
                      engine.stop()
                  except Exception:
                      pass
          event.accept()

      def _navigate(self, key: str) -> None:
          if key not in self._screens:
              return
          self._stack.setCurrentWidget(self._screens[key])
          for i, btn in enumerate(self._nav_buttons):
              btn.set_active(self._nav_keys[i] == key)
  