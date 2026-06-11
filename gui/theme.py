"""
Design system: color tokens, QSS stylesheet. Dark theme with #6366F1 accent.
"""
from PyQt6.QtGui import QFontDatabase
from pathlib import Path


class Colors:
    BG_BASE       = "#0D0D0F"
    BG_SURFACE1   = "#141416"
    BG_SURFACE2   = "#1A1A1E"
    BG_SURFACE3   = "#202024"
    BG_SURFACE4   = "#27272B"
    ACCENT        = "#6366F1"
    ACCENT_HOVER  = "#818CF8"
    ACCENT_PRESS  = "#4F46E5"
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
    SCROLLBAR_HANDLE = "#3F3F46"


class Radii:
    INPUT  = "6px"
    CARD   = "10px"
    PANEL  = "16px"
    MODAL  = "24px"
    BUTTON = "8px"
    SMALL  = "4px"


class Spacing:
    XS = 4; SM = 8; MD = 12; LG = 16; XL = 24; XXL = 32


class Typography:
    FONT_FAMILY    = "Inter"
    SIZE_XS = 11; SIZE_SM = 13; SIZE_MD = 15; SIZE_LG = 20; SIZE_XL = 28
    WEIGHT_REGULAR = 400; WEIGHT_MEDIUM = 500; WEIGHT_BOLD = 700


def load_fonts() -> None:
    """Load Inter font from assets/fonts if directory exists."""
    fonts_dir = Path(__file__).parent.parent / "assets" / "fonts"
    if not fonts_dir.exists():
        return
    for f in fonts_dir.glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(f))


def get_stylesheet() -> str:
    c = Colors
    r = Radii
    return f"""
QMainWindow, QDialog, QWidget {{
    background-color: {c.BG_BASE};
    color: {c.TEXT_PRIMARY};
    font-family: "Inter", "Segoe UI", "Arial", sans-serif;
    font-size: {Typography.SIZE_SM}px;
}}
QStackedWidget {{ background-color: {c.BG_BASE}; }}

#sidebar {{
    background-color: {c.BG_SURFACE1};
    border-right: 1px solid {c.BORDER};
    min-width: 220px; max-width: 220px;
}}
#sidebar QPushButton {{
    background: transparent; color: {c.TEXT_SECONDARY};
    border: none; border-radius: {r.SMALL};
    padding: 10px 14px; text-align: left;
    font-size: {Typography.SIZE_SM}px; font-weight: {Typography.WEIGHT_MEDIUM};
    min-height: 36px;
}}
#sidebar QPushButton:hover {{ background-color: {c.BG_SURFACE3}; color: {c.TEXT_PRIMARY}; }}
#sidebar QPushButton[active="true"] {{
    background-color: rgba(99,102,241,0.15);
    color: {c.ACCENT};
    border-left: 3px solid {c.ACCENT};
    padding-left: 11px;
}}
#sidebar #plan_badge {{
    background-color: rgba(99,102,241,0.12); color: {c.ACCENT};
    border-radius: {r.SMALL}; padding: 3px 8px;
    font-size: {Typography.SIZE_XS}px; font-weight: {Typography.WEIGHT_BOLD};
}}

#header {{
    background-color: {c.BG_SURFACE1};
    border-bottom: 1px solid {c.BORDER};
    min-height: 56px; max-height: 56px;
    padding: 0 {Spacing.LG}px;
}}

QLabel#section_header {{
    font-size: {Typography.SIZE_LG}px;
    font-weight: {Typography.WEIGHT_BOLD};
    color: {c.TEXT_PRIMARY};
    padding-bottom: 4px;
}}

QPushButton {{
    background-color: {c.BG_SURFACE3}; color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER}; border-radius: {r.BUTTON};
    padding: 8px 16px; font-size: {Typography.SIZE_SM}px;
    font-weight: {Typography.WEIGHT_MEDIUM}; min-height: 32px;
}}
QPushButton:hover  {{ background-color: {c.BG_SURFACE4}; border-color: {c.BORDER_HOVER}; }}
QPushButton:pressed {{ background-color: {c.BG_SURFACE2}; }}
QPushButton:disabled {{ color: {c.TEXT_DISABLED}; border-color: {c.BORDER}; background-color: {c.BG_SURFACE2}; }}
QPushButton#btn_primary {{ background-color: {c.ACCENT}; color: white; border: none; font-weight: {Typography.WEIGHT_MEDIUM}; }}
QPushButton#btn_primary:hover   {{ background-color: {c.ACCENT_HOVER}; }}
QPushButton#btn_primary:pressed {{ background-color: {c.ACCENT_PRESS}; }}
QPushButton#btn_danger  {{ background-color: transparent; color: {c.ERROR}; border: 1px solid {c.ERROR}; }}
QPushButton#btn_danger:hover {{ background-color: {c.ERROR_BG}; }}
QPushButton#btn_success {{ background-color: {c.SUCCESS}; color: white; border: none; }}
QPushButton#btn_success:hover {{ background-color: #16a34a; }}
QPushButton#btn_icon {{
    background-color: transparent; border: none;
    padding: 6px; border-radius: {r.SMALL}; min-height: 0;
}}
QPushButton#btn_icon:hover {{ background-color: {c.BG_SURFACE3}; }}

QFrame#activation_container {{
    background-color: {c.BG_SURFACE1};
    border: 1px solid {c.BORDER};
    border-radius: {r.PANEL};
}}

QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {c.BG_SURFACE2}; color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER}; border-radius: {r.INPUT};
    padding: 8px 12px; font-size: {Typography.SIZE_SM}px;
    selection-background-color: rgba(99,102,241,0.3);
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {c.ACCENT}; background-color: {c.BG_SURFACE1};
}}
QLineEdit:hover, QTextEdit:hover {{ border-color: {c.BORDER_HOVER}; }}
QLineEdit[valid="true"]  {{ border-color: {c.SUCCESS}; }}
QLineEdit[valid="false"] {{ border-color: {c.ERROR}; }}

QComboBox {{
    background-color: {c.BG_SURFACE2}; color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER}; border-radius: {r.INPUT};
    padding: 7px 12px; font-size: {Typography.SIZE_SM}px; min-height: 32px;
}}
QComboBox:hover {{ border-color: {c.BORDER_HOVER}; }}
QComboBox:focus {{ border-color: {c.ACCENT}; }}
QComboBox::drop-down {{ border: none; padding-right: 8px; }}
QComboBox::down-arrow {{ image: none; width: 0; }}
QComboBox QAbstractItemView {{
    background-color: {c.BG_SURFACE2}; color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER}; border-radius: {r.INPUT};
    selection-background-color: rgba(99,102,241,0.2); outline: none;
}}

QSpinBox, QDoubleSpinBox {{
    background-color: {c.BG_SURFACE2}; color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER}; border-radius: {r.INPUT};
    padding: 6px 10px; min-height: 30px;
}}
QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {c.ACCENT}; }}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background-color: {c.BG_SURFACE3}; border: none; width: 18px;
}}

QSlider::groove:horizontal {{ height: 4px; background: {c.BG_SURFACE4}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    background: {c.ACCENT}; border: 2px solid {c.ACCENT};
    width: 16px; height: 16px; border-radius: 8px; margin: -6px 0;
}}
QSlider::handle:horizontal:hover {{ background: {c.ACCENT_HOVER}; border-color: {c.ACCENT_HOVER}; }}
QSlider::sub-page:horizontal {{ background: {c.ACCENT}; border-radius: 2px; }}

QProgressBar {{
    background-color: {c.BG_SURFACE3}; border: none;
    border-radius: {r.SMALL}; height: 6px; color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {c.ACCENT},stop:1 {c.ACCENT_HOVER});
    border-radius: {r.SMALL};
}}
QProgressBar#activation_bar {{ height: 8px; border-radius: 4px; }}

QTableWidget, QTableView {{
    background-color: {c.BG_SURFACE1}; color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER}; border-radius: {r.CARD};
    gridline-color: {c.BORDER};
    selection-background-color: rgba(99,102,241,0.15); outline: none;
}}
QTableWidget::item, QTableView::item {{ padding: 10px 12px; border: none; }}
QTableWidget::item:selected, QTableView::item:selected {{
    background-color: rgba(99,102,241,0.15); color: {c.TEXT_PRIMARY};
}}
QHeaderView::section {{
    background-color: {c.BG_SURFACE2}; color: {c.TEXT_SECONDARY};
    border: none; border-bottom: 1px solid {c.BORDER};
    padding: 10px 12px; font-size: {Typography.SIZE_XS}px;
    font-weight: {Typography.WEIGHT_MEDIUM}; text-transform: uppercase;
    letter-spacing: 0.5px;
}}
QHeaderView::section:hover {{ background-color: {c.BG_SURFACE3}; color: {c.TEXT_PRIMARY}; }}

QListWidget {{
    background-color: {c.BG_SURFACE1}; color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER}; border-radius: {r.CARD}; outline: none;
}}
QListWidget::item {{ padding: 8px 12px; border-radius: {r.SMALL}; }}
QListWidget::item:hover {{ background-color: {c.BG_SURFACE3}; }}
QListWidget::item:selected {{ background-color: rgba(99,102,241,0.15); color: {c.ACCENT}; }}

QFrame#card {{
    background-color: {c.BG_SURFACE1};
    border: 1px solid {c.BORDER}; border-radius: {r.CARD};
}}
QFrame#kpi_card {{
    background-color: {c.BG_SURFACE1};
    border: 1px solid {c.BORDER}; border-radius: {r.CARD};
    min-width: 130px;
}}
QFrame#kpi_card:hover {{ border-color: {c.BORDER_HOVER}; background-color: {c.BG_SURFACE2}; }}

QLabel {{ color: {c.TEXT_PRIMARY}; background: transparent; }}
QLabel#label_title {{ font-size: {Typography.SIZE_XL}px; font-weight: {Typography.WEIGHT_BOLD}; }}
QLabel#label_subtitle {{ font-size: {Typography.SIZE_MD}px; font-weight: {Typography.WEIGHT_MEDIUM}; color: {c.TEXT_SECONDARY}; }}
QLabel#label_muted {{ font-size: {Typography.SIZE_XS}px; color: {c.TEXT_MUTED}; }}
QLabel#label_kpi_value {{ font-size: {Typography.SIZE_XL}px; font-weight: {Typography.WEIGHT_BOLD}; }}
QLabel#label_kpi_title {{
    font-size: {Typography.SIZE_XS}px; font-weight: {Typography.WEIGHT_MEDIUM};
    color: {c.TEXT_MUTED}; text-transform: uppercase; letter-spacing: 0.5px;
}}
QLabel#label_accent {{ color: {c.ACCENT}; font-weight: {Typography.WEIGHT_MEDIUM}; }}
QLabel#label_success {{ color: {c.SUCCESS}; }}
QLabel#label_error   {{ color: {c.ERROR}; }}
QLabel#label_warning {{ color: {c.WARNING}; }}
QLabel#demo_badge {{
    background-color: rgba(245,158,11,0.15); color: {c.WARNING};
    border: 1px solid rgba(245,158,11,0.3);
    border-radius: {r.SMALL}; padding: 2px 10px;
    font-size: {Typography.SIZE_XS}px; font-weight: {Typography.WEIGHT_BOLD};
}}

QTabWidget::pane {{
    border: 1px solid {c.BORDER}; border-radius: {r.CARD};
    background-color: {c.BG_SURFACE1}; top: -1px;
}}
QTabBar::tab {{
    background: transparent; color: {c.TEXT_MUTED};
    border: none; border-bottom: 2px solid transparent;
    padding: 8px 16px; font-size: {Typography.SIZE_SM}px; font-weight: {Typography.WEIGHT_MEDIUM};
}}
QTabBar::tab:hover {{ color: {c.TEXT_PRIMARY}; }}
QTabBar::tab:selected {{ color: {c.ACCENT}; border-bottom: 2px solid {c.ACCENT}; }}

QGroupBox {{
    background-color: {c.BG_SURFACE1}; border: 1px solid {c.BORDER};
    border-radius: {r.CARD}; margin-top: 12px; padding: 12px;
    font-size: {Typography.SIZE_SM}px; font-weight: {Typography.WEIGHT_MEDIUM}; color: {c.TEXT_SECONDARY};
}}
QGroupBox::title {{
    subcontrol-origin: margin; subcontrol-position: top left;
    left: 12px; top: -2px; padding: 0 6px;
    color: {c.TEXT_SECONDARY}; background-color: {c.BG_SURFACE1};
}}

QCheckBox {{ color: {c.TEXT_PRIMARY}; spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border: 1px solid {c.BORDER};
    border-radius: 3px; background-color: {c.BG_SURFACE2};
}}
QCheckBox::indicator:hover {{ border-color: {c.ACCENT}; }}
QCheckBox::indicator:checked {{ background-color: {c.ACCENT}; border-color: {c.ACCENT}; }}

QScrollBar:vertical {{ background: {c.BG_SURFACE1}; width: 8px; border: none; }}
QScrollBar::handle:vertical {{
    background: {c.SCROLLBAR_HANDLE}; border-radius: 4px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {c.BORDER_HOVER}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; border: none; }}
QScrollBar:horizontal {{ background: {c.BG_SURFACE1}; height: 8px; border: none; }}
QScrollBar::handle:horizontal {{
    background: {c.SCROLLBAR_HANDLE}; border-radius: 4px; min-width: 30px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; border: none; }}

QDialog {{ background-color: {c.BG_SURFACE1}; }}
QDialogButtonBox QPushButton {{ min-width: 80px; }}
QDateTimeEdit {{
    background-color: {c.BG_SURFACE2}; color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER}; border-radius: {r.INPUT}; padding: 6px 10px;
}}
QDateTimeEdit:focus {{ border-color: {c.ACCENT}; }}
QStatusBar {{
    background-color: {c.BG_SURFACE1}; color: {c.TEXT_MUTED};
    border-top: 1px solid {c.BORDER}; font-size: {Typography.SIZE_XS}px;
}}
QToolTip {{
    background-color: {c.BG_SURFACE3}; color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER}; border-radius: {r.SMALL};
    padding: 4px 8px; font-size: {Typography.SIZE_XS}px;
}}
"""
