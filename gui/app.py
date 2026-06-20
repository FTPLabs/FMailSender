"""
FMailSender MainWindow v3.6.2
Sidebar navigation + stacked screen layout.
"""
from __future__ import annotations
from typing import Any

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QPushButton, QLabel, QFrame, QStatusBar,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont

from gui.theme import Colors, Spacing, Typography
from gui.icons import NAV_ITEMS


class MainWindow(QMainWindow):
    """Main application window with sidebar and screen stack."""

    def __init__(self, license_info: Any = None):
        super().__init__()
        self._license_info = license_info
        self._screens: dict[str, QWidget] = {}
        self._nav_buttons: dict[str, QPushButton] = {}
        self._current_tab = ""

        self._build_ui()
        self._setup_statusbar()
        self._navigate_to("dashboard")

    # ── UI Construction ───────────────────────────────────────────────────

    def _build_ui(self):
        from core._version import APP_NAME, APP_VERSION
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)

        root = QWidget()
        root.setStyleSheet(f"background: {Colors.BG_BASE};")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Header
        header = self._build_header()
        root_layout.addWidget(header)

        # Body (sidebar + content)
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        sidebar = self._build_sidebar()
        body_layout.addWidget(sidebar)

        content = self._build_content()
        body_layout.addWidget(content, 1)

        root_layout.addWidget(body, 1)
        self.setCentralWidget(root)

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(54)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 0, 20, 0)

        logo = QLabel("✦ FMail Sender")
        logo.setStyleSheet(
            f"color: {Colors.ACCENT}; font-size: {Typography.SIZE_LG}pt; font-weight: 700;"
        )
        layout.addWidget(logo)
        layout.addStretch()

        if self._license_info:
            info = QLabel(
                f"Лицензия: {getattr(self._license_info, 'email', 'Активна')}"
            )
            info.setStyleSheet(
                f"color: {Colors.TEXT_MUTED}; font-size: {Typography.SIZE_SM}pt;"
            )
            layout.addWidget(info)

        return header

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(200)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(4)

        for tab_id, label, icon in NAV_ITEMS:
            btn = QPushButton(f"  {icon}  {label}")
            btn.setObjectName("btn_nav")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(40)
            btn.clicked.connect(lambda checked, tid=tab_id: self._navigate_to(tid))
            self._nav_buttons[tab_id] = btn
            layout.addWidget(btn)

        layout.addStretch()

        # Version label
        from core._version import APP_VERSION
        ver_label = QLabel(f"v{APP_VERSION}")
        ver_label.setObjectName("label_muted")
        ver_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(ver_label)

        return sidebar

    def _build_content(self) -> QStackedWidget:
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: transparent;")

        # Lazy-load screens
        from gui.screens.screen_dashboard   import DashboardScreen
        from gui.screens.screen_accounts    import AccountsScreen
        from gui.screens.screen_recipients  import RecipientsScreen
        from gui.screens.screen_compose     import ComposeScreen
        from gui.screens.screen_sending     import SendingScreen
        from gui.screens.screen_inbox       import InboxScreen

        screen_map = {
            "dashboard":   DashboardScreen,
            "accounts":    AccountsScreen,
            "recipients":  RecipientsScreen,
            "compose":     ComposeScreen,
            "sending":     SendingScreen,
            "inbox":       InboxScreen,
        }

        for tab_id, cls in screen_map.items():
            screen = cls()
            self._screens[tab_id] = screen
            self._stack.addWidget(screen)

        return self._stack

    def _setup_statusbar(self):
        bar = QStatusBar()
        self.setStatusBar(bar)
        bar.showMessage("Готово")

    # ── Navigation ────────────────────────────────────────────────────────

    def _navigate_to(self, tab_id: str):
        if tab_id not in self._screens:
            return
        self._current_tab = tab_id

        for tid, btn in self._nav_buttons.items():
            btn.setObjectName("btn_nav_active" if tid == tab_id else "btn_nav")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        self._stack.setCurrentWidget(self._screens[tab_id])
        self.statusBar().showMessage(
            next((label for (tid, label, _) in NAV_ITEMS if tid == tab_id), ""), 0
        )
