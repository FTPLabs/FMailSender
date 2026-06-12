"""
  Main window: sidebar navigation, header, QStackedWidget with all screens.
  v2.6.0: Added animated particle background to the main content area.
  """
  from PyQt6.QtWidgets import (
      QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
      QLabel, QPushButton, QFrame, QStackedWidget
  )
  from PyQt6.QtCore import Qt, QByteArray
  from PyQt6.QtSvgWidgets import QSvgWidget

  from gui.theme import Colors, Spacing, Typography
  from gui.screens.screen_dashboard import DashboardScreen
  from gui.screens.screen_accounts import AccountsScreen
  from gui.screens.screen_compose import ComposeScreen
  from gui.screens.screen_recipients import RecipientsScreen
  from gui.screens.screen_sending import SendingScreen
  from gui.screens.screen_analytics import AnalyticsScreen
  from gui.widgets.animated_bg import AnimatedBackground
  from core.license import LicenseInfo
  from core._version import APP_NAME


  ICONS: dict[str, bytes] = {
      "dashboard":  b'<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="COLOR" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>',
      "accounts":   b'<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="COLOR" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
      "compose":    b'<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="COLOR" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>',
      "recipients": b'<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="COLOR" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
      "sending":    b'<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="COLOR" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>',
      "analytics":  b'<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="COLOR" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>',
  }

  LOGO_SVG = b"""<svg width="28" height="28" viewBox="0 0 28 28" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="lg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#7C3AED"/>
      <stop offset="100%" style="stop-color:#06B6D4"/>
    </linearGradient>
  </defs>
  <rect width="28" height="28" rx="7" fill="url(#lg)" opacity="0.15"/>
  <rect x="1" y="1" width="26" height="26" rx="6" fill="none" stroke="url(#lg)" stroke-width="1.5"/>
  <path d="M5 10 L14 16 L23 10" stroke="#8B5CF6" stroke-width="2" fill="none" stroke-linecap="round"/>
  <rect x="5" y="8" width="18" height="12" rx="2" fill="none" stroke="#06B6D4" stroke-width="1.5"/>
  </svg>"""


  def _make_svg_icon(name: str, color: str = Colors.TEXT_SECONDARY) -> QSvgWidget:
      svg_data = ICONS.get(name, b"")
      colored = svg_data.replace(b"COLOR", color.encode("utf-8"))
      svg = QSvgWidget()
      svg.load(QByteArray(colored))
      svg.setFixedSize(20, 20)
      return svg


  class SidebarButton(QPushButton):
      def __init__(self, icon_name: str, label: str, parent=None):
          super().__init__(parent)
          self._icon_name = icon_name
          self._active = False
          layout = QHBoxLayout(self)
          layout.setContentsMargins(14, 0, 14, 0)
          layout.setSpacing(10)
          self._icon_widget = _make_svg_icon(icon_name, Colors.TEXT_SECONDARY)
          layout.addWidget(self._icon_widget)
          self._text_label = QLabel(label)
          self._text_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
          layout.addWidget(self._text_label)
          layout.addStretch()
          self.setFixedHeight(40)

      def set_active(self, active: bool):
          self._active = active
          color = Colors.ACCENT if active else Colors.TEXT_SECONDARY
          colored = ICONS.get(self._icon_name, b"").replace(b"COLOR", color.encode("utf-8"))
          self._icon_widget.load(QByteArray(colored))
          self._text_label.setStyleSheet(f"color: {color};")
          self.setProperty("active", "true" if active else "false")
          self.style().unpolish(self)
          self.style().polish(self)


  class MainWindow(QMainWindow):
      def __init__(self, license_info: LicenseInfo):
          super().__init__()
          self._license = license_info
          self.setWindowTitle(APP_NAME)
          self.setMinimumSize(1100, 680)
          self.resize(1280, 780)
          self._setup_ui()

      def _setup_ui(self):
          central = QWidget()
          self.setCentralWidget(central)
          root = QHBoxLayout(central)
          root.setContentsMargins(0, 0, 0, 0)
          root.setSpacing(0)

          # ── Sidebar ────────────────────────────────────────────────────────
          sidebar = QFrame()
          sidebar.setObjectName("sidebar")
          sidebar_layout = QVBoxLayout(sidebar)
          sidebar_layout.setContentsMargins(8, 16, 8, 16)
          sidebar_layout.setSpacing(2)

          logo_row = QHBoxLayout()
          logo_row.setContentsMargins(8, 0, 8, 12)
          logo_svg = QSvgWidget()
          logo_svg.load(QByteArray(LOGO_SVG))
          logo_svg.setFixedSize(28, 28)
          logo_row.addWidget(logo_svg)
          logo_title = QLabel(APP_NAME)
          logo_title.setStyleSheet(
              f"font-size:14px;font-weight:bold;"
              f"background: transparent;"
              f"color: {Colors.TEXT_PRIMARY};"
          )
          logo_row.addWidget(logo_title)
          logo_row.addStretch()
          sidebar_layout.addLayout(logo_row)

          if getattr(self._license, "is_demo", False):
              badge = QLabel("DEMO")
              badge.setObjectName("demo_badge")
              badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
              sidebar_layout.addWidget(badge)

          sidebar_layout.addSpacing(8)

          nav_items = [
              ("dashboard",  "Обзор"),
              ("accounts",   "Аккаунты"),
              ("compose",    "Письмо"),
              ("recipients", "Получатели"),
              ("sending",    "Рассылка"),
              ("analytics",  "Аналитика"),
          ]
          self._nav_buttons: list[SidebarButton] = []
          self._nav_keys: list[str] = []
          for icon, label in nav_items:
              btn = SidebarButton(icon, label)
              btn.clicked.connect(lambda checked, i=icon: self._navigate(i))
              sidebar_layout.addWidget(btn)
              self._nav_buttons.append(btn)
              self._nav_keys.append(icon)

          sidebar_layout.addStretch()

          plan_lbl = QLabel(self._license.plan)
          plan_lbl.setObjectName("plan_badge")
          plan_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
          sidebar_layout.addWidget(plan_lbl)
          root.addWidget(sidebar)

          # ── Main area (content + animated background) ──────────────────────
          main_area = QWidget()
          main_layout = QVBoxLayout(main_area)
          main_layout.setContentsMargins(0, 0, 0, 0)
          main_layout.setSpacing(0)

          # Animated background — transparent to mouse events, sits behind all children
          self._anim_bg = AnimatedBackground(main_area)
          self._anim_bg.lower()   # push behind everything else

          header = QFrame()
          header.setObjectName("header")
          header.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
          header_layout = QHBoxLayout(header)
          self.page_title = QLabel("Обзор")
          self.page_title.setStyleSheet(
              f"font-size:15px;font-weight:600;color:{Colors.TEXT_PRIMARY};"
          )
          header_layout.addWidget(self.page_title)
          header_layout.addStretch()
          expiry_lbl = QLabel(
              f"Лицензия до: {self._license.expires_at.strftime('%d.%m.%Y')}"
          )
          expiry_lbl.setObjectName("label_muted")
          header_layout.addWidget(expiry_lbl)
          main_layout.addWidget(header)

          self._stack = QStackedWidget()
          self._screens: dict[str, QWidget] = {}

          screen_map = [
              ("dashboard",  DashboardScreen()),
              ("accounts",   AccountsScreen()),
              ("compose",    ComposeScreen()),
              ("recipients", RecipientsScreen()),
              ("sending",    SendingScreen()),
              ("analytics",  AnalyticsScreen()),
          ]
          for key, screen in screen_map:
              self._stack.addWidget(screen)
              self._screens[key] = screen

          acct_screen: AccountsScreen = self._screens["accounts"]
          sending_screen: SendingScreen = self._screens["sending"]
          compose_screen: ComposeScreen = self._screens["compose"]
          recip_screen = self._screens["recipients"]
          analytics_screen = self._screens["analytics"]
          dashboard_screen = self._screens["dashboard"]

          acct_screen.accounts_changed.connect(sending_screen.set_accounts)
          recip_screen.list_ready.connect(sending_screen.set_recipients)
          compose_screen.template_ready.connect(sending_screen.set_template)
          sending_screen.campaign_finished.connect(analytics_screen.on_results)
          sending_screen.campaign_finished.connect(dashboard_screen.update_campaign_results)

          main_layout.addWidget(self._stack)
          root.addWidget(main_area)

          self._navigate("dashboard")

      def _navigate(self, key: str):
          labels = {
              "dashboard": "Обзор", "accounts": "Аккаунты",
              "compose": "Письмо", "recipients": "Получатели",
              "sending": "Рассылка", "analytics": "Аналитика",
          }
          if key not in self._screens:
              return
          self._stack.setCurrentWidget(self._screens[key])
          self.page_title.setText(labels.get(key, key))
          for i, btn in enumerate(self._nav_buttons):
              btn.set_active(self._nav_keys[i] == key)
  