"""
Main window: CyberPro sidebar navigation + animated background.
v3.3: CyberPro design — SVG logo, violet/cyan neon sidebar, glass panels.
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QFrame, QStackedWidget, QSizePolicy
)
from PyQt6.QtCore import Qt, QByteArray, QSize, pyqtSignal, QTimer
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtGui import QPixmap, QPainter, QLinearGradient, QColor, QIcon

from gui import icons
from gui.theme import Colors, Spacing, Typography
from gui.screens.screen_dashboard import DashboardScreen
from gui.screens.screen_accounts import AccountsScreen
from gui.screens.screen_recipients import RecipientsScreen
from gui.screens.screen_compose import ComposeScreen
from gui.screens.screen_sending import SendingScreen
from gui.screens.screen_inbox import InboxScreen


LOGO_SVG = b"""<svg width="32" height="32" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
<defs>
  <linearGradient id="lg" x1="0%" y1="0%" x2="100%" y2="100%">
    <stop offset="0%" style="stop-color:#8B5CF6"/>
    <stop offset="100%" style="stop-color:#06B6D4"/>
  </linearGradient>
</defs>
<rect width="32" height="32" rx="8" fill="url(#lg)" opacity="0.20"/>
<path d="M6 10 L16 17 L26 10" stroke="url(#lg)" stroke-width="2" fill="none" stroke-linecap="round"/>
<rect x="6" y="9" width="20" height="14" rx="2" fill="none" stroke="url(#lg)" stroke-width="1.5"/>
</svg>"""


def _render_svg_icon(svg_bytes: bytes, size: int = 32) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(svg_bytes))
    pix = QPixmap(QSize(size, size))
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    renderer.render(p)
    p.end()
    return pix


NAV_ITEMS = [
    ("dashboard",   "Дашборд",     icons.LAYOUT),
    ("accounts",    "Аккаунты",    icons.USERS),
    ("recipients",  "Получатели",  icons.CONTACT),
    ("compose",     "Письмо",      icons.FILE_TEXT),
    ("sending",     "Рассылка",    icons.SEND),
    ("inbox",       "Входящие",    icons.INBOX),
]


class NavButton(QPushButton):
    """Кнопка боковой навигации CyberPro."""

    def __init__(self, key: str, label: str, icon: str, parent=None):
        super().__init__(parent)
        self._key = key
        self._icon_svg = icon
        self.setFixedHeight(46)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setText("  " + label)
        self.setIconSize(QSize(18, 18))
        self._update_style(False)

    def _update_style(self, active: bool) -> None:
        self.setIcon(icons.make_icon(self._icon_svg, 18, "#E8E8FF" if active else "#6666AA"))
        if active:
            self.setStyleSheet(
                "QPushButton {"
                "  background: rgba(139,92,246,0.15);"
                "  border: none;"
                "  border-left: 3px solid #8B5CF6;"
                "  border-radius: 0;"
                "  color: #E8E8FF;"
                "  font-weight: 600;"
                "  font-size: 13px;"
                "  text-align: left;"
                "  padding-left: 21px;"
                "}"
            )
        else:
            self.setStyleSheet(
                "QPushButton {"
                "  background: transparent;"
                "  border: none;"
                "  border-left: 3px solid transparent;"
                "  border-radius: 0;"
                "  color: #6666AA;"
                "  font-weight: 500;"
                "  font-size: 13px;"
                "  text-align: left;"
                "  padding-left: 21px;"
                "}"
                "QPushButton:hover {"
                "  background: rgba(139,92,246,0.07);"
                "  color: #E8E8FF;"
                "}"
            )

    def set_active(self, active: bool) -> None:
        self.setChecked(active)
        self._update_style(active)


class Sidebar(QFrame):
    """CyberPro боковая панель: SVG лого + nav buttons + info снизу."""
    page_requested = pyqtSignal(str)

    def __init__(self, license_info=None, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(220)
        self.setStyleSheet(
            "QFrame#sidebar {"
            "  background-color: rgba(4,4,16,0.90);"
            "  border-right: 1px solid rgba(139,92,246,0.15);"
            "}"
        )
        self._nav_buttons: dict[str, NavButton] = {}
        self._license_info = license_info
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Logo header
        logo_frame = QFrame()
        logo_frame.setFixedHeight(64)
        logo_frame.setStyleSheet(
            "QFrame { border-bottom: 1px solid rgba(139,92,246,0.12); background: transparent; }"
        )
        lf_layout = QHBoxLayout(logo_frame)
        lf_layout.setContentsMargins(16, 0, 16, 0)
        lf_layout.setSpacing(10)

        icon_lbl = QLabel()
        pix = None
        try:
            from core.utils import resource_path
            _logo = QPixmap(resource_path("assets", "images", "fmail_logo.png"))
            if not _logo.isNull():
                pix = _logo.scaled(
                    28, 28,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
        except Exception:
            pix = None
        if pix is None:  # fallback — встроенный SVG
            pix = _render_svg_icon(LOGO_SVG, 28)
        icon_lbl.setPixmap(pix)
        icon_lbl.setFixedSize(28, 28)
        icon_lbl.setStyleSheet("background: transparent; border: none;")
        lf_layout.addWidget(icon_lbl)

        app_name = QLabel("FMail Sender")
        app_name.setStyleSheet(
            "color: #E8E8FF; font-size: 14px; font-weight: 700;"
            " background: transparent; border: none;"
        )
        lf_layout.addWidget(app_name)
        lf_layout.addStretch()
        root.addWidget(logo_frame)

        # Nav buttons
        nav_frame = QWidget()
        nav_frame.setStyleSheet("background: transparent;")
        nav_layout = QVBoxLayout(nav_frame)
        nav_layout.setContentsMargins(0, 12, 0, 12)
        nav_layout.setSpacing(2)
        for key, label, icon in NAV_ITEMS:
            btn = NavButton(key, label, icon)
            btn.clicked.connect(lambda _, k=key: self.page_requested.emit(k))
            nav_layout.addWidget(btn)
            self._nav_buttons[key] = btn
        nav_layout.addStretch()
        root.addWidget(nav_frame)

        root.addStretch()

        # Info bottom
        info_frame = QFrame()
        info_frame.setObjectName("plan_info_frame")
        info_frame.setStyleSheet(
            "QFrame {"
            "  border-top: 1px solid rgba(139,92,246,0.12);"
            "  background: rgba(139,92,246,0.04);"
            "}"
        )
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(16, 12, 16, 14)
        info_layout.setSpacing(4)

        if self._license_info:
            plan = getattr(self._license_info, "plan", "PRO")
            email = getattr(self._license_info, "email", "")
            plan_lbl = QLabel(str(plan).upper())
            plan_lbl.setObjectName("badge_pro")
            plan_lbl.setStyleSheet(
                "color: #8B5CF6; background: rgba(139,92,246,0.12);"
                " border: 1px solid rgba(139,92,246,0.30);"
                " border-radius: 6px; padding: 2px 8px;"
                " font-size: 10px; font-weight: 700;"
            )
            info_layout.addWidget(plan_lbl)
            if email:
                em_lbl = QLabel(email[:28] + "…" if len(email) > 28 else email)
                em_lbl.setStyleSheet(
                    "color: #6666AA; font-size: 11px;"
                    " background: transparent; border: none;"
                )
                info_layout.addWidget(em_lbl)
        else:
            demo_lbl = QLabel("DEMO")
            demo_lbl.setObjectName("demo_badge")
            demo_lbl.setStyleSheet(
                "color: #EF4444; background: rgba(239,68,68,0.12);"
                " border: 1px solid rgba(239,68,68,0.25);"
                " border-radius: 6px; padding: 2px 8px;"
                " font-size: 10px; font-weight: 700;"
            )
            info_layout.addWidget(demo_lbl)
        root.addWidget(info_frame)

    def set_active_page(self, key: str) -> None:
        for k, btn in self._nav_buttons.items():
            btn.set_active(k == key)


class MainWindow(QMainWindow):
    """Главное окно — animated background + sidebar + content stack."""

    _license_invalid_sig = pyqtSignal(str)

    def __init__(self, license_info=None, parent=None):
        super().__init__(parent)
        self._license_info = license_info
        self._license_expired = False
        self._lic_online_counter = 0

        try:
            from core._version import APP_NAME, APP_VERSION
            self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        except Exception:
            self.setWindowTitle("FMail Sender Pro")

        # Иконка окна — логотип приложения
        try:
            from core.utils import resource_path
            _ico = QIcon(resource_path("assets", "images", "fmail_logo.png"))
            if not _ico.isNull():
                self.setWindowIcon(_ico)
        except Exception:
            pass

        self.setMinimumSize(1024, 660)
        self.resize(1280, 780)
        self.setStyleSheet("background-color: " + Colors.BG_BASE + ";")

        # Central widget
        central = QWidget()
        central.setStyleSheet("background: transparent;")
        self.setCentralWidget(central)

        # Animated background
        try:
            from gui.widgets.animated_bg import AnimatedBackground
            self._animated_bg = AnimatedBackground(central)
            self._animated_bg.setGeometry(central.rect())
            self._animated_bg.lower()
        except Exception:
            self._animated_bg = None

        # Main layout: sidebar + content
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._sidebar = Sidebar(license_info)
        self._sidebar.page_requested.connect(self._navigate)
        main_layout.addWidget(self._sidebar)

        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: transparent;")
        main_layout.addWidget(self._stack)

        self._screens: dict[str, QWidget] = {}
        self._build_screens()
        self._navigate("dashboard")

        # Авто-закрытие при истечении/отзыве подписки
        self._license_invalid_sig.connect(self._on_license_invalid)
        self._start_license_watch()

    def _start_license_watch(self) -> None:
        """Каждые 30с проверяет срок подписки; раз в ~30 мин — онлайн-перепроверку."""
        if self._license_info is None:
            return
        self._lic_timer = QTimer(self)
        self._lic_timer.setInterval(30_000)
        self._lic_timer.timeout.connect(self._check_license_expiry)
        self._lic_timer.start()

    def _check_license_expiry(self) -> None:
        if self._license_expired:
            return
        try:
            if self._license_info is not None and self._license_info.is_expired:
                self._on_license_invalid("Срок подписки истёк.")
                return
        except Exception:
            pass
        self._lic_online_counter += 1
        if self._lic_online_counter >= 60:
            self._lic_online_counter = 0
            self._revalidate_license_async()

    def _revalidate_license_async(self) -> None:
        """Фоновая онлайн-перепроверка (отзыв/grace) — результат через сигнал в GUI-поток."""
        import threading

        def _work():
            try:
                from core.license import check_license
                valid, _info, msg = check_license()
            except Exception:
                return
            if not valid:
                self._license_invalid_sig.emit(msg or "Лицензия недействительна.")

        threading.Thread(target=_work, daemon=True).start()

    def _on_license_invalid(self, message: str) -> None:
        if self._license_expired:
            return
        self._license_expired = True
        try:
            self._lic_timer.stop()
        except Exception:
            pass
        from PyQt6.QtWidgets import QMessageBox, QApplication
        QMessageBox.warning(
            self, "Подписка неактивна",
            f"{message}\n\nПриложение будет закрыто. "
            f"Продлите подписку через Telegram-бот и запустите заново.",
        )
        QApplication.quit()

    def _build_screens(self) -> None:
        screens = {
            "dashboard":  DashboardScreen,
            "accounts":   AccountsScreen,
            "recipients": RecipientsScreen,
            "compose":    ComposeScreen,
            "sending":    SendingScreen,
            "inbox":      InboxScreen,
        }
        for key, cls in screens.items():
            try:
                screen = cls()
            except Exception as e:
                screen = QLabel(f"Ошибка загрузки {key}: {e}")
                screen.setStyleSheet("color: #EF4444; padding: 20px;")
            self._screens[key] = screen
            self._stack.addWidget(screen)

        accounts   = self._screens.get("accounts")
        recipients = self._screens.get("recipients")
        compose    = self._screens.get("compose")
        sending    = self._screens.get("sending")
        inbox      = self._screens.get("inbox")
        dashboard  = self._screens.get("dashboard")

        # accounts -> sending + inbox + compose (для автоматического теста доставки)
        if hasattr(accounts, "accounts_changed"):
            if hasattr(sending, "set_accounts"):
                accounts.accounts_changed.connect(sending.set_accounts)
            if hasattr(inbox, "set_accounts"):
                accounts.accounts_changed.connect(inbox.set_accounts)
            if hasattr(compose, "set_accounts"):
                accounts.accounts_changed.connect(compose.set_accounts)

        # recipients -> sending + inbox
        if hasattr(recipients, "list_ready"):
            if hasattr(sending, "set_recipients"):
                recipients.list_ready.connect(sending.set_recipients)
            if hasattr(inbox, "set_recipients"):
                recipients.list_ready.connect(inbox.set_recipients)

        # compose -> sending
        if hasattr(compose, "template_ready") and hasattr(sending, "set_template"):
            compose.template_ready.connect(sending.set_template)

        # sending -> dashboard
        if hasattr(sending, "campaign_finished") and hasattr(dashboard, "update_campaign_results"):
            sending.campaign_finished.connect(dashboard.update_campaign_results)

        # Re-emit: accounts._load() ran in __init__ before signals were wired.
        # Push current state now that all connections exist.
        if hasattr(accounts, "_accounts") and accounts._accounts:
            accounts.accounts_changed.emit(accounts._accounts)

    def _navigate(self, key: str) -> None:
        if key not in self._screens:
            return
        self._stack.setCurrentWidget(self._screens[key])
        self._sidebar.set_active_page(key)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._animated_bg:
            central = self.centralWidget()
            if central:
                self._animated_bg.setGeometry(central.rect())
