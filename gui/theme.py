"""
FMail Sender Pro — CyberPro Design System v3.3
Style: киберпанк #040410 BG, violet/cyan neon, 3 animated orbs, aurora sweep
Primary:  violet   #7C3AED -> #8B5CF6
Accent:   cyan     #06B6D4
BG:       deep black  #040410
"""
from PyQt6.QtGui import QFontDatabase
from pathlib import Path


class Colors:
    # Deep black backgrounds (CyberPro)
    BG_BASE       = "#040410"
    BG_SURFACE1   = "#08080F"
    BG_SURFACE2   = "#0C0C1A"
    BG_SURFACE3   = "#101020"
    BG_SURFACE4   = "#14142A"
    BG_GLASS      = "rgba(255, 255, 255, 0.03)"
    BG_GLASS2     = "rgba(255, 255, 255, 0.06)"

    # Primary violet neon
    ACCENT        = "#8B5CF6"
    ACCENT_HOVER  = "#7C3AED"
    ACCENT_PRESS  = "#6D28D9"
    ACCENT_GLOW   = "rgba(139, 92, 246, 0.35)"
    ACCENT_DIM    = "rgba(139, 92, 246, 0.12)"

    # Secondary cyan neon
    CYAN          = "#06B6D4"
    CYAN_HOVER    = "#0891B2"
    CYAN_GLOW     = "rgba(6, 182, 212, 0.25)"
    CYAN_DIM      = "rgba(6, 182, 212, 0.10)"

    # Gradient
    GRAD_START    = "#7C3AED"
    GRAD_END      = "#06B6D4"
    GRAD_MID      = "#5B21B6"

    # Text
    TEXT_PRIMARY   = "#E8E8FF"
    TEXT_SECONDARY = "#6666AA"
    TEXT_MUTED     = "#33335A"
    TEXT_DISABLED  = "#22224A"

    # Borders violet glass
    BORDER         = "rgba(139, 92, 246, 0.12)"
    BORDER_FOCUS   = "rgba(139, 92, 246, 0.65)"
    BORDER_HOVER   = "rgba(139, 92, 246, 0.30)"
    BORDER_CYAN    = "rgba(6, 182, 212, 0.20)"
    BORDER_WHITE   = "rgba(255, 255, 255, 0.06)"

    # Semantic
    SUCCESS        = "#10B981"
    WARNING        = "#F59E0B"
    ERROR          = "#EF4444"
    INFO           = "#06B6D4"
    SUCCESS_BG     = "rgba(16, 185, 129, 0.10)"
    WARNING_BG     = "rgba(245, 158, 11,  0.10)"
    ERROR_BG       = "rgba(239, 68,  68,  0.10)"

    SCROLLBAR_HANDLE = "rgba(139, 92, 246, 0.20)"

    # Orb colors (for AnimatedBackground)
    ORB1_COLOR     = (139, 92, 246)
    ORB2_COLOR     = (6, 182, 212)
    ORB3_COLOR     = (91, 33, 182)


class Radii:
    INPUT  = "8px"
    CARD   = "12px"
    PANEL  = "16px"
    MODAL  = "20px"
    BUTTON = "8px"
    SMALL  = "6px"
    PILL   = "50px"


class Spacing:
    XS = 4; SM = 8; MD = 12; LG = 16; XL = 24; XXL = 32


class Typography:
    FONT_FAMILY    = "Inter"
    FONT_HEADING   = "Inter"
    SIZE_XS = 11; SIZE_SM = 13; SIZE_MD = 15; SIZE_LG = 20; SIZE_XL = 28
    WEIGHT_REGULAR = 400; WEIGHT_MEDIUM = 500; WEIGHT_SEMIBOLD = 600; WEIGHT_BOLD = 700


def load_fonts() -> None:
    fonts_dir = Path(__file__).parent.parent / "assets" / "fonts"
    if not fonts_dir.exists():
        return
    for ext in ("*.ttf", "*.otf"):
        for fpath in fonts_dir.glob(ext):
            QFontDatabase.addApplicationFont(str(fpath))


def _c(name: str) -> str:
    """Helper — return Colors attribute by name string."""
    return getattr(Colors, name)


def global_stylesheet() -> str:
    c = Colors
    r = Radii
    t = Typography
    return f"""
/* Base */
QWidget {{
    background-color: transparent;
    color: {c.TEXT_PRIMARY};
    font-family: {t.FONT_FAMILY};
    font-size: {t.SIZE_SM}px;
    outline: none;
}}
QMainWindow, QDialog {{
    background-color: {c.BG_BASE};
}}
/* Scrollbars */
QScrollBar:vertical {{
    background: transparent; width: 4px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {c.SCROLLBAR_HANDLE}; border-radius: 2px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {c.ACCENT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
QScrollBar:horizontal {{ background: transparent; height: 4px; }}
QScrollBar::handle:horizontal {{ background: {c.SCROLLBAR_HANDLE}; border-radius: 2px; }}
/* Buttons */
QPushButton {{
    background-color: {c.BG_GLASS};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER};
    border-radius: {r.BUTTON};
    padding: 7px 16px;
    font-size: {t.SIZE_SM}px;
    font-weight: {t.WEIGHT_MEDIUM};
}}
QPushButton:hover {{
    background-color: {c.ACCENT_DIM};
    border-color: {c.BORDER_HOVER};
    color: white;
}}
QPushButton:pressed {{
    background-color: rgba(109, 40, 217, 0.25);
    border-color: {c.ACCENT_PRESS};
}}
QPushButton:disabled {{ color: {c.TEXT_MUTED}; border-color: {c.BORDER}; background: transparent; }}
QPushButton[accent="true"] {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {c.ACCENT_HOVER}, stop:1 {c.CYAN});
    border: none; color: white; font-weight: {t.WEIGHT_SEMIBOLD};
}}
QPushButton[accent="true"]:hover {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {c.ACCENT}, stop:1 {c.CYAN_HOVER});
}}
/* Inputs */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {c.BG_GLASS};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER};
    border-radius: {r.INPUT};
    padding: 6px 10px;
    selection-background-color: {c.ACCENT_DIM};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {c.BORDER_FOCUS}; background-color: {c.BG_GLASS2};
}}
/* Combobox */
QComboBox {{
    background-color: {c.BG_GLASS}; color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER}; border-radius: {r.INPUT}; padding: 5px 10px;
}}
QComboBox:focus, QComboBox:on {{ border-color: {c.BORDER_FOCUS}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{ image: none; width: 0; }}
QComboBox QAbstractItemView {{
    background-color: {c.BG_SURFACE2}; color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER}; border-radius: {r.INPUT};
    selection-background-color: {c.ACCENT_DIM}; outline: none;
}}
/* SpinBox */
QSpinBox, QDoubleSpinBox {{
    background-color: {c.BG_GLASS}; color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER}; border-radius: {r.INPUT}; padding: 5px 8px;
}}
QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {c.BORDER_FOCUS}; }}
/* Tables */
QTableWidget, QTableView {{
    background-color: transparent; color: {c.TEXT_PRIMARY};
    gridline-color: {c.BORDER}; border: 1px solid {c.BORDER};
    border-radius: {r.CARD}; outline: none;
}}
QHeaderView::section {{
    background-color: {c.BG_SURFACE1}; color: {c.TEXT_SECONDARY};
    border: none; border-bottom: 1px solid {c.BORDER};
    padding: 6px 10px; font-size: 11px;
    font-weight: {t.WEIGHT_SEMIBOLD}; text-transform: uppercase; letter-spacing: 0.06em;
}}
QTableWidget::item {{ padding: 6px 10px; border-bottom: 1px solid {c.BORDER}; }}
QTableWidget::item:selected {{ background-color: {c.ACCENT_DIM}; color: white; }}
/* Checkbox */
QCheckBox {{ color: {c.TEXT_PRIMARY}; spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {c.BORDER_HOVER}; border-radius: 4px; background: {c.BG_GLASS};
}}
QCheckBox::indicator:checked {{ background: {c.ACCENT}; border-color: {c.ACCENT}; }}
/* Tabs */
QTabBar::tab {{
    background: transparent; color: {c.TEXT_SECONDARY};
    border: none; border-bottom: 2px solid transparent;
    padding: 8px 18px; font-size: {t.SIZE_SM}px; font-weight: {t.WEIGHT_MEDIUM};
}}
QTabBar::tab:selected {{ color: {c.TEXT_PRIMARY}; border-bottom: 2px solid {c.ACCENT}; }}
QTabBar::tab:hover:!selected {{ color: {c.TEXT_PRIMARY}; }}
QTabWidget::pane {{ border: 1px solid {c.BORDER}; border-radius: {r.CARD}; background: transparent; }}
/* ProgressBar */
QProgressBar {{ background-color: {c.BG_SURFACE2}; border: none; border-radius: 3px; height: 4px; color: transparent; }}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {c.ACCENT}, stop:1 {c.CYAN});
    border-radius: 3px;
}}
/* Labels */
QLabel {{ background: transparent; color: {c.TEXT_PRIMARY}; }}
/* Tooltip */
QToolTip {{
    background-color: {c.BG_SURFACE2}; color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER}; border-radius: {r.SMALL}; padding: 5px 8px;
}}
/* Splitter */
QSplitter::handle {{ background: {c.BORDER}; width: 1px; height: 1px; }}
/* Card/Panel frames */
QFrame[role="card"] {{ background-color: {c.BG_GLASS}; border: 1px solid {c.BORDER}; border-radius: {r.CARD}; }}
QFrame[role="panel"] {{ background-color: {c.BG_SURFACE1}; border: 1px solid {c.BORDER}; border-radius: {r.PANEL}; }}
"""