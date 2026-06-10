"""
Дизайн-система: токены, палитра, полный QSS stylesheet.
Тёмная тема с акцентом #6366F1 (electric indigo).
"""
from PyQt6.QtGui import QColor, QFont, QFontDatabase
from PyQt6.QtCore import Qt
from pathlib import Path

# ──────────────────────────────────────────────
# Токены дизайн-системы
# ──────────────────────────────────────────────

class Colors:
    BG_BASE       = "#0D0D0F"
    BG_SURFACE1   = "#141416"
    BG_SURFACE2   = "#1A1A1E"
    BG_SURFACE3   = "#202024"
    BG_SURFACE4   = "#27272B"

    ACCENT        = "#6366F1"
    ACCENT_HOVER  = "#818CF8"
    ACCENT_PRESS  = "#4F46E5"
    ACCENT_GLOW   = "rgba(99, 102, 241, 0.25)"
    ACCENT_GLOW2  = "rgba(99, 102, 241, 0.10)"

    TEXT_PRIMARY   = "#F4F4F5"
    TEXT_SECONDARY = "#A1A1AA"
    TEXT_MUTED     = "#71717A"
    TEXT_DISABLED  = "#52525B"

    BORDER         = "#2A2A2E"
    BORDER_FOCUS   = "#6366F1"
    BORDER_HOVER   = "#3F3F46"

    SUCCESS        = "#22C55E"
    WARNING        = "#F59E0B"
    ERROR          = "#EF4444"
    INFO           = "#3B82F6"

    SUCCESS_BG     = "rgba(34, 197, 94, 0.10)"
    WARNING_BG     = "rgba(245, 158, 11, 0.10)"
    ERROR_BG       = "rgba(239, 68, 68, 0.10)"

    SCROLLBAR      = "#2A2A2E"
    SCROLLBAR_HANDLE = "#3F3F46"


class Radii:
    INPUT  = "6px"
    CARD   = "10px"
    PANEL  = "16px"
    MODAL  = "24px"
    BUTTON = "8px"
    SMALL  = "4px"


class Spacing:
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 24
    XXL = 32


class Typography:
    FONT_FAMILY = "Inter"
    SIZE_XS  = 11
    SIZE_SM  = 13
    SIZE_MD  = 15
    SIZE_LG  = 20
    SIZE_XL  = 28

    WEIGHT_REGULAR = 400
    WEIGHT_MEDIUM  = 500
    WEIGHT_BOLD    = 700


def load_fonts() -> None:
    """Загружает шрифт Inter из директории assets."""
    fonts_dir = Path(__file__).parent.parent / "assets" / "fonts"
    for font_file in fonts_dir.glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(font_file))


# ──────────────────────────────────────────────
# Полный QSS stylesheet
# ──────────────────────────────────────────────

def get_stylesheet() -> str:
    c = Colors
    r = Radii
    return f"""
/* ═══════════════════════════════════════
   BASE & WINDOW
═══════════════════════════════════════ */
QMainWindow, QDialog, QWidget {{
    background-color: {c.BG_BASE};
    color: {c.TEXT_PRIMARY};
    font-family: "Inter", "Segoe UI", sans-serif;
    font-size: {Typography.SIZE_SM}px;
}}

QStackedWidget {{
    background-color: {c.BG_BASE};
}}

/* ═══════════════════════════════════════
   SIDEBAR
═══════════════════════════════════════ */
#sidebar {{
    background-color: {c.BG_SURFACE1};
    border-right: 1px solid {c.BORDER};
    min-width: 220px;
    max-width: 220px;
}}

#sidebar.collapsed {{
    min-width: 64px;
    max-width: 64px;
}}

#sidebar QPushButton {{
    background-color: transparent;
    color: {c.TEXT_SECONDARY};
    border: none;
    border-radius: {r.SMALL};
    padding: 10px 14px;
    text-align: left;
    font-size: {Typography.SIZE_SM}px;
    font-weight: {Typography.WEIGHT_MEDIUM};
}}

#sidebar QPushButton:hover {{
    background-color: {c.BG_SURFACE3};
    color: {c.TEXT_PRIMARY};
}}

#sidebar QPushButton:checked, #sidebar QPushButton.active {{
    background-color: rgba(99, 102, 241, 0.15);
    color: {c.ACCENT};
    border-left: 2px solid {c.ACCENT};
}}

#sidebar #plan_badge {{
    background-color: rgba(99, 102, 241, 0.12);
    color: {c.ACCENT};
    border-radius: {r.SMALL};
    padding: 3px 8px;
    font-size: {Typography.SIZE_XS}px;
    font-weight: {Typography.WEIGHT_BOLD};
    letter-spacing: 0.5px;
}}

/* ═══════════════════════════════════════
   HEADER
═══════════════════════════════════════ */
#header {{
    background-color: {c.BG_SURFACE1};
    border-bottom: 1px solid {c.BORDER};
    min-height: 56px;
    max-height: 56px;
    padding: 0 {Spacing.LG}px;
}}

#smtp_status_dot {{
    width: 8px;
    height: 8px;
    border-radius: 4px;
}}
#smtp_status_dot.connected {{ background-color: {c.SUCCESS}; }}
#smtp_status_dot.disconnected {{ background-color: {c.ERROR}; }}

/* ═══════════════════════════════════════
   BUTTONS
═══════════════════════════════════════ */
QPushButton {{
    background-color: {c.BG_SURFACE3};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER};
    border-radius: {r.BUTTON};
    padding: 8px 16px;
    font-size: {Typography.SIZE_SM}px;
    font-weight: {Typography.WEIGHT_MEDIUM};
}}

QPushButton:hover {{
    background-color: {c.BG_SURFACE4};
    border-color: {c.BORDER_HOVER};
}}

QPushButton:pressed {{
    background-color: {c.BG_SURFACE2};
}}

QPushButton:disabled {{
    color: {c.TEXT_DISABLED};
    border-color: {c.BORDER};
    background-color: {c.BG_SURFACE2};
}}

QPushButton#btn_primary {{
    background-color: {c.ACCENT};
    color: white;
    border: none;
    font-weight: {Typography.WEIGHT_MEDIUM};
}}

QPushButton#btn_primary:hover {{
    background-color: {c.ACCENT_HOVER};
}}

QPushButton#btn_primary:pressed {{
    background-color: {c.ACCENT_PRESS};
}}

QPushButton#btn_danger {{
    background-color: transparent;
    color: {c.ERROR};
    border: 1px solid {c.ERROR};
}}

QPushButton#btn_danger:hover {{
    background-color: {c.ERROR_BG};
}}

QPushButton#btn_success {{
    background-color: {c.SUCCESS};
    color: white;
    border: none;
}}

QPushButton#btn_icon {{
    background-color: transparent;
    border: none;
    padding: 6px;
    border-radius: {r.SMALL};
}}

QPushButton#btn_icon:hover {{
    background-color: {c.BG_SURFACE3};
}}

/* ═══════════════════════════════════════
   INPUTS
═══════════════════════════════════════ */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {c.BG_SURFACE2};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER};
    border-radius: {r.INPUT};
    padding: 8px 12px;
    font-size: {Typography.SIZE_SM}px;
    selection-background-color: rgba(99, 102, 241, 0.3);
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {c.ACCENT};
    background-color: {c.BG_SURFACE1};
    outline: none;
}}

QLineEdit:hover, QTextEdit:hover {{
    border-color: {c.BORDER_HOVER};
}}

QLineEdit.valid {{
    border-color: {c.SUCCESS};
}}
QLineEdit.invalid {{
    border-color: {c.ERROR};
}}

QLineEdit[placeholderText] {{
    color: {c.TEXT_MUTED};
}}

/* ═══════════════════════════════════════
   COMBOBOX
═══════════════════════════════════════ */
QComboBox {{
    background-color: {c.BG_SURFACE2};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER};
    border-radius: {r.INPUT};
    padding: 8px 12px;
    font-size: {Typography.SIZE_SM}px;
}}

QComboBox:hover {{
    border-color: {c.BORDER_HOVER};
}}

QComboBox:focus {{
    border-color: {c.ACCENT};
}}

QComboBox::drop-down {{
    border: none;
    padding-right: 8px;
}}

QComboBox::down-arrow {{
    image: none;
    width: 12px;
    height: 12px;
}}

QComboBox QAbstractItemView {{
    background-color: {c.BG_SURFACE2};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER};
    border-radius: {r.INPUT};
    selection-background-color: rgba(99, 102, 241, 0.2);
    outline: none;
}}

/* ═══════════════════════════════════════
   SPINBOX / SLIDER
═══════════════════════════════════════ */
QSpinBox, QDoubleSpinBox {{
    background-color: {c.BG_SURFACE2};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER};
    border-radius: {r.INPUT};
    padding: 6px 10px;
}}

QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {c.ACCENT};
}}

QSlider::groove:horizontal {{
    height: 4px;
    background-color: {c.BG_SURFACE4};
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background-color: {c.ACCENT};
    border: 2px solid {c.ACCENT};
    width: 16px;
    height: 16px;
    border-radius: 8px;
    margin: -6px 0;
}}

QSlider::handle:horizontal:hover {{
    background-color: {c.ACCENT_HOVER};
    border-color: {c.ACCENT_HOVER};
}}

QSlider::sub-page:horizontal {{
    background-color: {c.ACCENT};
    border-radius: 2px;
}}

/* ═══════════════════════════════════════
   PROGRESS BAR
═══════════════════════════════════════ */
QProgressBar {{
    background-color: {c.BG_SURFACE3};
    border: none;
    border-radius: {r.SMALL};
    height: 6px;
    text-align: center;
    color: transparent;
}}

QProgressBar::chunk {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 {c.ACCENT},
        stop:1 {c.ACCENT_HOVER}
    );
    border-radius: {r.SMALL};
}}

QProgressBar#activation_bar {{
    height: 8px;
    border-radius: 4px;
}}

/* ═══════════════════════════════════════
   TABLES
═══════════════════════════════════════ */
QTableWidget, QTableView {{
    background-color: {c.BG_SURFACE1};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER};
    border-radius: {r.CARD};
    gridline-color: {c.BORDER};
    selection-background-color: rgba(99, 102, 241, 0.15);
    outline: none;
}}

QTableWidget::item, QTableView::item {{
    padding: 10px 12px;
    border: none;
}}

QTableWidget::item:selected, QTableView::item:selected {{
    background-color: rgba(99, 102, 241, 0.15);
    color: {c.TEXT_PRIMARY};
}}

QHeaderView::section {{
    background-color: {c.BG_SURFACE2};
    color: {c.TEXT_SECONDARY};
    border: none;
    border-bottom: 1px solid {c.BORDER};
    padding: 10px 12px;
    font-size: {Typography.SIZE_XS}px;
    font-weight: {Typography.WEIGHT_MEDIUM};
    letter-spacing: 0.5px;
    text-transform: uppercase;
}}

QHeaderView::section:hover {{
    background-color: {c.BG_SURFACE3};
    color: {c.TEXT_PRIMARY};
}}

/* ═══════════════════════════════════════
   LIST WIDGETS
═══════════════════════════════════════ */
QListWidget {{
    background-color: {c.BG_SURFACE1};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER};
    border-radius: {r.CARD};
    outline: none;
}}

QListWidget::item {{
    padding: 8px 12px;
    border-radius: {r.SMALL};
}}

QListWidget::item:hover {{
    background-color: {c.BG_SURFACE3};
}}

QListWidget::item:selected {{
    background-color: rgba(99, 102, 241, 0.15);
    color: {c.ACCENT};
}}

/* ═══════════════════════════════════════
   CARDS (custom QFrame)
═══════════════════════════════════════ */
QFrame#card {{
    background-color: {c.BG_SURFACE1};
    border: 1px solid {c.BORDER};
    border-radius: {r.CARD};
    padding: {Spacing.LG}px;
}}

QFrame#card_accent {{
    background-color: {c.BG_SURFACE1};
    border: 1px solid {c.ACCENT};
    border-radius: {r.CARD};
}}

QFrame#kpi_card {{
    background-color: {c.BG_SURFACE1};
    border: 1px solid {c.BORDER};
    border-radius: {r.CARD};
    padding: {Spacing.LG}px;
    min-width: 160px;
}}

QFrame#kpi_card:hover {{
    border-color: {c.BORDER_HOVER};
    background-color: {c.BG_SURFACE2};
}}

/* ═══════════════════════════════════════
   LABELS
═══════════════════════════════════════ */
QLabel {{
    color: {c.TEXT_PRIMARY};
    background: transparent;
}}

QLabel#label_title {{
    font-size: {Typography.SIZE_XL}px;
    font-weight: {Typography.WEIGHT_BOLD};
    color: {c.TEXT_PRIMARY};
}}

QLabel#label_subtitle {{
    font-size: {Typography.SIZE_MD}px;
    font-weight: {Typography.WEIGHT_MEDIUM};
    color: {c.TEXT_SECONDARY};
}}

QLabel#label_muted {{
    font-size: {Typography.SIZE_XS}px;
    color: {c.TEXT_MUTED};
}}

QLabel#label_kpi_value {{
    font-size: {Typography.SIZE_XL}px;
    font-weight: {Typography.WEIGHT_BOLD};
    color: {c.TEXT_PRIMARY};
}}

QLabel#label_kpi_title {{
    font-size: {Typography.SIZE_XS}px;
    font-weight: {Typography.WEIGHT_MEDIUM};
    color: {c.TEXT_MUTED};
    letter-spacing: 0.5px;
    text-transform: uppercase;
}}

QLabel#label_accent {{
    color: {c.ACCENT};
    font-weight: {Typography.WEIGHT_MEDIUM};
}}

QLabel#label_success {{
    color: {c.SUCCESS};
}}

QLabel#label_error {{
    color: {c.ERROR};
}}

QLabel#label_warning {{
    color: {c.WARNING};
}}

QLabel#section_header {{
    font-size: {Typography.SIZE_LG}px;
    font-weight: {Typography.WEIGHT_BOLD};
    color: {c.TEXT_PRIMARY};
    padding-bottom: {Spacing.SM}px;
}}

/* ═══════════════════════════════════════
   TABS
═══════════════════════════════════════ */
QTabWidget::pane {{
    background-color: {c.BG_SURFACE1};
    border: 1px solid {c.BORDER};
    border-radius: {r.CARD};
    padding: {Spacing.LG}px;
}}

QTabBar::tab {{
    background-color: transparent;
    color: {c.TEXT_SECONDARY};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 10px 20px;
    font-size: {Typography.SIZE_SM}px;
    font-weight: {Typography.WEIGHT_MEDIUM};
}}

QTabBar::tab:hover {{
    color: {c.TEXT_PRIMARY};
    border-bottom-color: {c.BORDER_HOVER};
}}

QTabBar::tab:selected {{
    color: {c.ACCENT};
    border-bottom-color: {c.ACCENT};
}}

/* ═══════════════════════════════════════
   SCROLLBARS
═══════════════════════════════════════ */
QScrollBar:vertical {{
    background-color: transparent;
    width: 6px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background-color: {c.SCROLLBAR_HANDLE};
    border-radius: 3px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {c.TEXT_MUTED};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
    background: none;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 6px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background-color: {c.SCROLLBAR_HANDLE};
    border-radius: 3px;
    min-width: 30px;
}}

/* ═══════════════════════════════════════
   CHECKBOXES & RADIO
═══════════════════════════════════════ */
QCheckBox {{
    color: {c.TEXT_PRIMARY};
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {c.BORDER};
    border-radius: {r.SMALL};
    background-color: {c.BG_SURFACE2};
}}

QCheckBox::indicator:hover {{
    border-color: {c.ACCENT};
}}

QCheckBox::indicator:checked {{
    background-color: {c.ACCENT};
    border-color: {c.ACCENT};
}}

QRadioButton {{
    color: {c.TEXT_PRIMARY};
    spacing: 8px;
}}

QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {c.BORDER};
    border-radius: 8px;
    background-color: {c.BG_SURFACE2};
}}

QRadioButton::indicator:checked {{
    background-color: {c.ACCENT};
    border-color: {c.ACCENT};
}}

/* ═══════════════════════════════════════
   TOOLTIP
═══════════════════════════════════════ */
QToolTip {{
    background-color: {c.BG_SURFACE3};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER};
    border-radius: {r.SMALL};
    padding: 6px 10px;
    font-size: {Typography.SIZE_XS}px;
}}

/* ═══════════════════════════════════════
   MENU
═══════════════════════════════════════ */
QMenu {{
    background-color: {c.BG_SURFACE2};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER};
    border-radius: {r.CARD};
    padding: 4px;
}}

QMenu::item {{
    padding: 8px 16px;
    border-radius: {r.SMALL};
}}

QMenu::item:selected {{
    background-color: rgba(99, 102, 241, 0.15);
    color: {c.TEXT_PRIMARY};
}}

QMenu::separator {{
    height: 1px;
    background-color: {c.BORDER};
    margin: 4px 8px;
}}

/* ═══════════════════════════════════════
   STATUSBAR
═══════════════════════════════════════ */
QStatusBar {{
    background-color: {c.BG_SURFACE1};
    color: {c.TEXT_MUTED};
    border-top: 1px solid {c.BORDER};
    font-size: {Typography.SIZE_XS}px;
    padding: 0 {Spacing.LG}px;
}}

/* ═══════════════════════════════════════
   ACTIVATION SCREEN SPECIFIC
═══════════════════════════════════════ */
#activation_container {{
    background-color: {c.BG_SURFACE1};
    border: 1px solid {c.BORDER};
    border-radius: {r.MODAL};
    padding: {Spacing.XXL}px;
    max-width: 480px;
}}

#hwid_display {{
    background-color: {c.BG_SURFACE2};
    border: 1px solid {c.BORDER};
    border-radius: {r.CARD};
    padding: 12px 16px;
    font-family: "Courier New", monospace;
    font-size: {Typography.SIZE_SM}px;
    color: {c.TEXT_SECONDARY};
    letter-spacing: 1px;
}}

/* ═══════════════════════════════════════
   BADGE
═══════════════════════════════════════ */
QLabel#badge_starter {{
    background-color: rgba(113, 113, 122, 0.2);
    color: {c.TEXT_SECONDARY};
    border-radius: {r.SMALL};
    padding: 2px 8px;
    font-size: {Typography.SIZE_XS}px;
    font-weight: {Typography.WEIGHT_BOLD};
}}

QLabel#badge_pro {{
    background-color: rgba(99, 102, 241, 0.15);
    color: {c.ACCENT};
    border-radius: {r.SMALL};
    padding: 2px 8px;
    font-size: {Typography.SIZE_XS}px;
    font-weight: {Typography.WEIGHT_BOLD};
}}

QLabel#badge_unlimited {{
    background-color: rgba(34, 197, 94, 0.15);
    color: {c.SUCCESS};
    border-radius: {r.SMALL};
    padding: 2px 8px;
    font-size: {Typography.SIZE_XS}px;
    font-weight: {Typography.WEIGHT_BOLD};
}}

/* ═══════════════════════════════════════
   SPLITTER
═══════════════════════════════════════ */
QSplitter::handle {{
    background-color: {c.BORDER};
    width: 1px;
}}

/* ═══════════════════════════════════════
   DATE/TIME EDIT
═══════════════════════════════════════ */
QDateTimeEdit {{
    background-color: {c.BG_SURFACE2};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER};
    border-radius: {r.INPUT};
    padding: 7px 12px;
    font-size: {Typography.SIZE_SM}px;
}}

QDateTimeEdit:focus {{
    border-color: {c.ACCENT};
}}

QCalendarWidget {{
    background-color: {c.BG_SURFACE2};
    color: {c.TEXT_PRIMARY};
}}

QCalendarWidget QTableView {{
    background-color: {c.BG_SURFACE2};
    selection-background-color: {c.ACCENT};
    border: none;
}}
"""
