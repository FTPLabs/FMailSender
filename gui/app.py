"""
Главное приложение: QApplication + MainWindow с sidebar, header и QStackedWidget.
"""
import queue
import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QFrame, QStackedWidget, QSizePolicy,
    QSpacerItem, QStatusBar
)
from PyQt6.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtCore import QByteArray

from gui.theme import get_stylesheet, load_fonts, Colors, Spacing, Typography
from gui.screens.screen_activation import ActivationScreen
from gui.screens.screen_dashboard import DashboardScreen
from gui.screens.screen_accounts import AccountsScreen
from gui.screens.screen_compose import ComposeScreen
from gui.screens.screen_recipients import RecipientsScreen
from gui.screens.screen_sending import SendingScreen
from gui.screens.screen_analytics import AnalyticsScreen
from core.license import LicenseInfo


# ──────────────────────────────────────────────
# SVG иконки для sidebar
# ──────────────────────────────────────────────

ICONS = {
    "dashboard": b'<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="%s" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>',
    "accounts": b'<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="%s" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
    "compose": b'<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="%s" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>',
    "recipients": b'<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="%s" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    "sending": b'<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="%s" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>',
    "analytics": b'<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="%s" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>',
}


def _make_svg_icon(name: str, color: str = Colors.TEXT_SECONDARY) -> QSvgWidget:
    svg_data = ICONS.get(name, b"")
    svg = QSvgWidget()
    svg.load(QByteArray(svg_data.replace(b"%s", color.encode())))
    svg.setFixedSize(20, 20)
    svg.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    return svg


# ──────────────────────────────────────────────
# Sidebar кнопка навигации
# ──────────────────────────────────────────────

class NavButton(QPushButton):
    """Кнопка навигации в sidebar с SVG-иконкой."""

    def __init__(self, label: str, icon_name: str, parent=None):
        super().__init__(parent)
        self._label = label
        self._icon_name = icon_name
        self._is_active = False
        self._collapsed = False

        self.setCheckable(True)
        self.setFixedHeight(44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(10)

        self._icon_widget = _make_svg_icon(icon_name)
        layout.addWidget(self._icon_widget)

        self._label_widget = QLabel(label)
        self._label_widget.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 13px;")
        layout.addWidget(self._label_widget)
        layout.addStretch()

    def set_active(self, active: bool):
        self._is_active = active
        self.setChecked(active)
        color = Colors.ACCENT if active else Colors.TEXT_SECONDARY
        self._label_widget.setStyleSheet(f"color: {color}; font-size: 13px;")
        self._icon_widget.load(QByteArray(
            ICONS.get(self._icon_name, b"").replace(b"%s", color.encode())
        ))

    def set_collapsed(self, collapsed: bool):
        self._collapsed = collapsed
        self._label_widget.setVisible(not collapsed)
        if collapsed:
            self.setFixedWidth(44)
            self.setToolTip(self._label)
        else:
            self.setMinimumWidth(0)
            self.setMaximumWidth(16777215)
            self.setToolTip("")


# ──────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────

class Sidebar(QFrame):
    """Левый навигационный sidebar."""

    nav_changed = pyqtSignal(int)

    NAV_ITEMS = [
        ("Обзор",          "dashboard"),
        ("Аккаунты SMTP",  "accounts"),
        ("Создать письмо", "compose"),
        ("Получатели",     "recipients"),
        ("Рассылка",       "sending"),
        ("Аналитика",      "analytics"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self._collapsed = False
        self._buttons: list[NavButton] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.SM, Spacing.LG, Spacing.SM, Spacing.LG)
        layout.setSpacing(4)

        # Логотип / заголовок
        self._logo_row = QHBoxLayout()
        logo_label = QLabel("ESP")
        logo_label.setStyleSheet(
            f"color: {Colors.ACCENT}; font-size: 18px; font-weight: bold; padding: 8px 6px;"
        )
        self._logo_row.addWidget(logo_label)

        self._app_name = QLabel("Email Sender Pro")
        self._app_name.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 13px; font-weight: 500;")
        self._logo_row.addWidget(self._app_name)
        self._logo_row.addStretch()
        layout.addLayout(self._logo_row)

        # Кнопка коллапса
        self._collapse_btn = QPushButton("◀")
        self._collapse_btn.setObjectName("btn_icon")
        self._collapse_btn.setFixedSize(28, 28)
        self._collapse_btn.clicked.connect(self._toggle_collapse)
        self._logo_row.addWidget(self._collapse_btn)

        layout.addSpacing(Spacing.LG)

        # Навигационные кнопки
        for i, (label, icon_name) in enumerate(self.NAV_ITEMS):
            btn = NavButton(label, icon_name)
            btn.clicked.connect(lambda _, idx=i: self._on_nav_click(idx))
            self._buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        # Планы / лицензия
        self._plan_badge = QLabel("STARTER")
        self._plan_badge.setObjectName("badge_starter")
        self._plan_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._plan_badge)

        self._license_label = QLabel("Лицензия активна")
        self._license_label.setObjectName("label_muted")
        self._license_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._license_label)

        # По умолчанию выбран первый пункт
        if self._buttons:
            self._buttons[0].set_active(True)

    def _on_nav_click(self, index: int):
        for i, btn in enumerate(self._buttons):
            btn.set_active(i == index)
        self.nav_changed.emit(index)

    def _toggle_collapse(self):
        self._collapsed = not self._collapsed
        self._collapse_btn.setText("▶" if self._collapsed else "◀")
        self._app_name.setVisible(not self._collapsed)
        self._plan_badge.setVisible(not self._collapsed)
        self._license_label.setVisible(not self._collapsed)

        for btn in self._buttons:
            btn.set_collapsed(self._collapsed)

        anim = QPropertyAnimation(self, b"minimumWidth")
        anim.setDuration(200)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        if self._collapsed:
            anim.setStartValue(220)
            anim.setEndValue(64)
            self.setMaximumWidth(64)
        else:
            anim.setStartValue(64)
            anim.setEndValue(220)
            self.setMaximumWidth(220)
        anim.start()
        self._anim = anim  # Держим ссылку

    def set_plan(self, plan: str, days_left: int):
        badge_id = {
            "STARTER": "badge_starter",
            "PRO": "badge_pro",
            "UNLIMITED": "badge_unlimited",
        }.get(plan, "badge_starter")
        self._plan_badge.setObjectName(badge_id)
        self._plan_badge.setText(plan)
        self._plan_badge.style().unpolish(self._plan_badge)
        self._plan_badge.style().polish(self._plan_badge)
        self._license_label.setText(f"Осталось: {days_left} дней")

    def navigate_to(self, index: int):
        if 0 <= index < len(self._buttons):
            self._on_nav_click(index)


# ──────────────────────────────────────────────
# Header
# ──────────────────────────────────────────────

class Header(QFrame):
    """Верхний заголовок: статус SMTP, язык."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("header")
        self._smtp_connected = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(Spacing.XL, 0, Spacing.XL, 0)
        layout.setSpacing(Spacing.MD)

        self.page_title = QLabel("Обзор")
        self.page_title.setStyleSheet(
            f"font-size: 15px; font-weight: 500; color: {Colors.TEXT_PRIMARY};"
        )
        layout.addWidget(self.page_title)
        layout.addStretch()

        # Статус SMTP
        smtp_row = QHBoxLayout()
        smtp_row.setSpacing(6)

        self._smtp_dot = QLabel("●")
        self._smtp_dot.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 10px;")
        smtp_row.addWidget(self._smtp_dot)

        self._smtp_label = QLabel("SMTP: не подключён")
        self._smtp_label.setObjectName("label_muted")
        smtp_row.addWidget(self._smtp_label)

        layout.addLayout(smtp_row)

        # Разделитель
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background: {Colors.BORDER};")
        layout.addWidget(sep)

        # Версия
        ver_label = QLabel("v1.0.0")
        ver_label.setObjectName("label_muted")
        layout.addWidget(ver_label)

    def set_smtp_status(self, connected: bool, count: int = 0):
        self._smtp_connected = connected
        if connected:
            self._smtp_dot.setStyleSheet(f"color: {Colors.SUCCESS}; font-size: 10px;")
            self._smtp_label.setText(f"SMTP: {count} аккаунт{'ов' if count != 1 else ''}")
        else:
            self._smtp_dot.setStyleSheet(f"color: {Colors.ERROR}; font-size: 10px;")
            self._smtp_label.setText("SMTP: не подключён")

    PAGE_TITLES = ["Обзор", "Аккаунты SMTP", "Создать письмо",
                   "Получатели", "Рассылка", "Аналитика"]

    def set_page(self, index: int):
        if 0 <= index < len(self.PAGE_TITLES):
            self.page_title.setText(self.PAGE_TITLES[index])


# ──────────────────────────────────────────────
# MainWindow
# ──────────────────────────────────────────────

class MainWindow(QMainWindow):
    """Основное окно приложения."""

    def __init__(self, license_info: LicenseInfo = None):
        super().__init__()
        self._license = license_info
        self._setup_window()
        self._setup_ui()
        self._connect_signals()

        if license_info:
            self.sidebar.set_plan(license_info.plan, license_info.days_left)
            # Обновляем лимит потоков
            self.sending_screen.threads_slider.setMaximum(
                min(license_info.max_threads, 50)
            )

    def _setup_window(self):
        self.setWindowTitle("Email Sender Pro")
        self.setMinimumSize(1200, 760)
        self.resize(1400, 860)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header
        self.header = Header()
        main_layout.addWidget(self.header)

        # Body: sidebar + content
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.sidebar = Sidebar()
        body.addWidget(self.sidebar)

        # Контент
        content_frame = QFrame()
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        self.dashboard_screen = DashboardScreen()
        self.accounts_screen = AccountsScreen()
        self.compose_screen = ComposeScreen()
        self.recipients_screen = RecipientsScreen()
        self.sending_screen = SendingScreen()
        self.analytics_screen = AnalyticsScreen()

        for screen in [
            self.dashboard_screen, self.accounts_screen, self.compose_screen,
            self.recipients_screen, self.sending_screen, self.analytics_screen
        ]:
            self.stack.addWidget(screen)

        content_layout.addWidget(self.stack)
        body.addWidget(content_frame, 1)

        body_widget = QWidget()
        body_widget.setLayout(body)
        main_layout.addWidget(body_widget, 1)

        # Statusbar
        statusbar = QStatusBar()
        statusbar.showMessage("Email Sender Pro готов к работе")
        self.setStatusBar(statusbar)
        self._statusbar = statusbar

    def _connect_signals(self):
        self.sidebar.nav_changed.connect(self._on_nav_changed)
        self.accounts_screen.accounts_changed.connect(self._on_accounts_changed)
        self.compose_screen.template_ready.connect(self._on_template_ready)
        self.recipients_screen.list_ready.connect(self._on_recipients_ready)
        self.sending_screen.campaign_started.connect(lambda: self._statusbar.showMessage("Рассылка запущена..."))
        self.sending_screen.campaign_finished.connect(self._on_campaign_finished)

    def _on_nav_changed(self, index: int):
        self.stack.setCurrentIndex(index)
        self.header.set_page(index)

    def _on_accounts_changed(self, accounts):
        self.sending_screen.set_accounts(accounts)
        active = sum(1 for a in accounts if a.is_active)
        self.header.set_smtp_status(active > 0, active)

    def _on_template_ready(self, template):
        self.sending_screen.set_template(template)
        self._statusbar.showMessage("Шаблон письма сохранён — переходите к рассылке")
        self.sidebar.navigate_to(4)  # Экран рассылки

    def _on_recipients_ready(self, recipients):
        self.sending_screen.set_recipients(recipients)
        self._statusbar.showMessage(f"Загружено получателей: {len(recipients)}")
        self.sidebar.navigate_to(4)

    def _on_campaign_finished(self, results):
        self.analytics_screen.update_results(results)
        success = sum(1 for r in results if r.success)
        self._statusbar.showMessage(
            f"Кампания завершена: {success}/{len(results)} писем отправлено успешно"
        )
        self.dashboard_screen.update_stats({
            "sent_today": len(results),
            "success": success,
            "errors": len(results) - success,
            "queued": 0,
        })


# ──────────────────────────────────────────────
# Точка входа GUI
# ──────────────────────────────────────────────

def create_app(license_info: LicenseInfo = None) -> tuple[QApplication, MainWindow]:
    """Создаёт и настраивает QApplication + MainWindow."""
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Email Sender Pro")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("EmailSenderPro")

    load_fonts()
    app.setStyleSheet(get_stylesheet())

    # Принудительно Inter если доступен
    font = QFont("Inter")
    font.setPointSize(Typography.SIZE_SM)
    app.setFont(font)

    window = MainWindow(license_info)
    return app, window
