"""
Main window: sidebar navigation, header, QStackedWidget with all screens.
v2.6.0: Added animated particle background to the main content area.
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QFrame, QStackedWidget
)
from PyQt6.QtCore import Qt, QByteArray, pyqtSignal
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtGui import QPixmap, QPainter

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


ICONS: dict[str, bytes] = {
    "dashboard":  b'<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="COLOR" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>',
    "accounts":   b'<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="COLOR" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
    "compose":    b'<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="COLOR" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>',
    "recipients": b'<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="COLOR" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    "sending":    b'<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="COLOR" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>',
    "analytics":  b'<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="COLOR" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>',
    "inbox":      b'<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="COLOR" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/></svg>',
}



def _svg_to_pixmap(svg_bytes: bytes, size: int = 20) -> QPixmap:
    """Render SVG bytes into a transparent QPixmap — works correctly inside any layout."""
    renderer = QSvgRenderer(QByteArray(svg_bytes))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    return pixmap


def _make_svg_icon(name: str, color: str = Colors.TEXT_SECONDARY) -> QLabel:
    """Return a QLabel with the SVG icon rendered as a pixmap (transparent background)."""
    svg_data = ICONS.get(name, b"")
    colored = svg_data.replace(b"COLOR", color.encode("utf-8"))
    lbl = QLabel()
    lbl.setFixedSize(20, 20)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    lbl.setStyleSheet("background: transparent; border: none;")
    lbl.setPixmap(_svg_to_pixmap(colored))
    return lbl


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
        self._text_label.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self._text_label)
        layout.addStretch()
        self.setFixedHeight(40)

    def set_active(self, active: bool):
        self._active = active
        color = Colors.ACCENT if active else Colors.TEXT_SECONDARY
        svg_data = ICONS.get(self._icon_name, b"")
        colored = svg_data.replace(b"COLOR", color.encode("utf-8"))
        self._icon_widget.setPixmap(_svg_to_pixmap(colored))
        self._text_label.setStyleSheet(f"color: {color}; background: transparent; border: none;")
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)


class MainWindow(QMainWindow):
    _update_available = pyqtSignal(dict)  # thread-safe

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

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(8, 16, 8, 16)
        sidebar_layout.setSpacing(2)

        logo_row = QHBoxLayout()
        logo_row.setContentsMargins(8, 0, 8, 12)
        logo_title = QLabel(APP_NAME)
        logo_title.setStyleSheet(
            f"font-size:15px;font-weight:700;letter-spacing:0.8px;"
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
            ("inbox",      "Ответы"),
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

        _is_lifetime = self._license.plan.upper() in ("LIFETIME", "LIFE", "LTD", "LIFELONG")
        _plan_frame = QFrame()
        _plan_frame.setObjectName("plan_info_frame")
        _plan_fl = QVBoxLayout(_plan_frame)
        _plan_fl.setContentsMargins(10, 10, 10, 10)
        _plan_fl.setSpacing(6)

        if not _is_lifetime:
            expiry_lbl = QLabel(f"до {self._license.expires_at.strftime('%d.%m.%Y')}")
            expiry_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            expiry_lbl.setStyleSheet(
                "color: rgba(139,92,246,0.65); font-size: 10px;"
                " font-weight: 400; letter-spacing: 0.5px;"
                " background: transparent; padding: 0;"
            )
            _plan_fl.addWidget(expiry_lbl)

        plan_lbl = QLabel(("\u221e  " if _is_lifetime else "") + self._license.plan.lower())
        plan_lbl.setObjectName("plan_badge")
        plan_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _plan_fl.addWidget(plan_lbl)

        # Премиум: иконки Telegram и Lolz с ссылками
        _social_row = QHBoxLayout()
        _social_row.setContentsMargins(0, 2, 0, 0)
        _social_row.setSpacing(6)
        _social_row.addStretch()

        # Иконки через Unicode — надёжнее SVG на всех платформах
        _tg_icon_lbl = QLabel("\u2708")   # ✈ самолётик — символ Telegram
        _tg_icon_lbl.setFixedSize(18, 18)
        _tg_icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _tg_icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        _tg_icon_lbl.setStyleSheet(
            "color: rgba(139,92,246,0.75); font-size: 12px;"
            " background: transparent; border: none;"
        )
        _tg_icon_lbl.setToolTip("Поддержка в Telegram")
        _tg_icon_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        _social_row.addWidget(_tg_icon_lbl)

        _lolz_icon_lbl = QLabel("L")   # Lolz — буква в кружке через CSS
        _lolz_icon_lbl.setFixedSize(18, 18)
        _lolz_icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _lolz_icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        _lolz_icon_lbl.setStyleSheet(
            "color: rgba(139,92,246,0.75); font-size: 10px; font-weight: 700;"
            " background: transparent;"
            " border: 1.5px solid rgba(139,92,246,0.55);"
            " border-radius: 9px;"
        )
        _lolz_icon_lbl.setToolTip("Профиль на Lolz")
        _lolz_icon_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        _social_row.addWidget(_lolz_icon_lbl)

        dev_lbl = QLabel('<a href="https://t.me/ftpdev_sup" style="color:rgba(139,92,246,0.5);text-decoration:none;font-size:10px;">@ftpdev_sup</a>')
        dev_lbl.setOpenExternalLinks(True)
        dev_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dev_lbl.setStyleSheet("font-size: 10px; background: transparent; padding: 0;")
        _social_row.addWidget(dev_lbl)
        _social_row.addStretch()
        _plan_fl.addLayout(_social_row)

        sidebar_layout.addWidget(_plan_frame)
        root.addWidget(sidebar)

        # Main area with animated background
        main_area = QWidget()
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Animated background sits behind everything else
        self._anim_bg = AnimatedBackground(main_area)
        self._anim_bg.lower()

        header = QFrame()
        header.setObjectName("header")
        header_layout = QHBoxLayout(header)
        self.page_title = QLabel("Обзор")
        self.page_title.setStyleSheet(
            f"font-size:15px;font-weight:600;color:{Colors.TEXT_PRIMARY};"
        )
        header_layout.addWidget(self.page_title)
        header_layout.addStretch()
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
            ("inbox",      InboxScreen()),
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

        inbox_screen: InboxScreen = self._screens["inbox"]
        acct_screen.accounts_changed.connect(sending_screen.set_accounts)
        acct_screen.accounts_changed.connect(inbox_screen.set_accounts)
        if acct_screen._accounts:
            sending_screen.set_accounts(acct_screen._accounts)
        recip_screen.list_ready.connect(sending_screen.set_recipients)
        compose_screen.template_ready.connect(sending_screen.set_template)
        sending_screen.campaign_finished.connect(analytics_screen.on_results)
        sending_screen.campaign_finished.connect(dashboard_screen.update_campaign_results)

        main_layout.addWidget(self._stack)
        root.addWidget(main_area)

        self._navigate("dashboard")

    def closeEvent(self, event):
        """При закрытии окна — останавливаем рассылку и завершаем процесс."""
        sending_screen = self._screens.get("sending")
        if sending_screen is not None:
            engine = getattr(sending_screen, "_engine", None)
            if engine is not None:
                try:
                    engine.stop()
                except Exception:
                    pass
        event.accept()
        import os
        os._exit(0)

    def _navigate(self, key: str):
        labels = {
            "dashboard": "Обзор", "accounts": "Аккаунты",
            "compose": "Письмо", "recipients": "Получатели",
            "sending": "Рассылка", "analytics": "Аналитика",
            "inbox": "Ответы",
        }
        if key not in self._screens:
            return
        self._stack.setCurrentWidget(self._screens[key])
        self.page_title.setText(labels.get(key, key))
        for i, btn in enumerate(self._nav_buttons):
            btn.set_active(self._nav_keys[i] == key)