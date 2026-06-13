"""
FMail Sender — Web3 / dApp UI + Glassmorphism Design System v3.0
Primary:  violet   #7C3AED  →  #8B5CF6
Accent:   cyan     #06B6D4  →  #0891B2
BG:       deep space  #050510
Glass panels: rgba(255,255,255,0.04) with backdrop blur simulation
Neon glow effects via box-shadow on key elements
"""
from PyQt6.QtGui import QFontDatabase
from pathlib import Path


class Colors:
    # ── Deep space backgrounds ──────────────────────────
    BG_BASE       = "#050510"
    BG_SURFACE1   = "#0A0A1A"
    BG_SURFACE2   = "#0F0F22"
    BG_SURFACE3   = "#14142E"
    BG_SURFACE4   = "#1A1A3A"
    BG_GLASS      = "rgba(255, 255, 255, 0.04)"
    BG_GLASS2     = "rgba(255, 255, 255, 0.07)"

    # ── Primary – violet neon ──────────────────────────
    ACCENT        = "#8B5CF6"
    ACCENT_HOVER  = "#7C3AED"
    ACCENT_PRESS  = "#6D28D9"
    ACCENT_GLOW   = "rgba(139, 92, 246, 0.35)"

    # ── Secondary – cyan neon ─────────────────────────
    CYAN          = "#06B6D4"
    CYAN_HOVER    = "#0891B2"
    CYAN_GLOW     = "rgba(6, 182, 212, 0.30)"

    # ── Gradient ──────────────────────────────────────
    GRAD_START    = "#7C3AED"
    GRAD_END      = "#06B6D4"
    GRAD_MID      = "#5B21B6"

    # ── Text ──────────────────────────────────────────
    TEXT_PRIMARY   = "#E8E8FF"
    TEXT_SECONDARY = "#8888BB"
    TEXT_MUTED     = "#5555AA"
    TEXT_DISABLED  = "#333366"

    # ── Borders – neon glass ──────────────────────────
    BORDER         = "rgba(139, 92, 246, 0.18)"
    BORDER_FOCUS   = "rgba(139, 92, 246, 0.70)"
    BORDER_HOVER   = "rgba(139, 92, 246, 0.35)"
    BORDER_CYAN    = "rgba(6, 182, 212, 0.25)"

    # ── Semantic ──────────────────────────────────────
    SUCCESS        = "#10B981"
    WARNING        = "#F59E0B"
    ERROR          = "#EF4444"
    INFO           = "#06B6D4"
    SUCCESS_BG     = "rgba(16, 185, 129, 0.10)"
    WARNING_BG     = "rgba(245, 158, 11,  0.10)"
    ERROR_BG       = "rgba(239, 68,  68,  0.10)"

    SCROLLBAR_HANDLE = "rgba(139, 92, 246, 0.25)"


class Radii:
    INPUT  = "8px"
    CARD   = "14px"
    PANEL  = "20px"
    MODAL  = "24px"
    BUTTON = "10px"
    SMALL  = "6px"
    PILL   = "50px"


class Spacing:
    XS = 4; SM = 8; MD = 12; LG = 16; XL = 24; XXL = 32


class Typography:
    FONT_FAMILY    = "Inter"
    SIZE_XS = 11; SIZE_SM = 13; SIZE_MD = 15; SIZE_LG = 20; SIZE_XL = 28
    WEIGHT_REGULAR = 400; WEIGHT_MEDIUM = 500; WEIGHT_BOLD = 700


def load_fonts() -> None:
    fonts_dir = Path(__file__).parent.parent / "assets" / "fonts"
    if not fonts_dir.exists():
        return
    for f in fonts_dir.glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(f))


def get_stylesheet() -> str:
    c = Colors
    r = Radii
    return f"""
/* ═══ Global ═══════════════════════════════════════════════════════════ */
QMainWindow, QDialog, QWidget {{
    background-color: {c.BG_BASE};
    color: {c.TEXT_PRIMARY};
    font-family: "Inter", "Segoe UI", "Arial", sans-serif;
    font-size: {Typography.SIZE_SM}px;
}}
QStackedWidget {{ background-color: {c.BG_BASE}; }}

/* ═══ Sidebar — glass panel ═════════════════════════════════════════════ */
#sidebar {{
    background-color: {c.BG_SURFACE1};
    border-right: 1px solid {c.BORDER};
    min-width: 220px; max-width: 220px;
}}
#sidebar QPushButton {{
    background: transparent;
    color: {c.TEXT_SECONDARY};
    border: none;
    border-radius: {r.SMALL};
    padding: 10px 14px;
    text-align: left;
    font-size: {Typography.SIZE_SM}px;
    font-weight: {Typography.WEIGHT_MEDIUM};
    min-height: 38px;
}}
#sidebar QPushButton:hover {{
    background-color: {c.BG_GLASS2};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER};
}}
#sidebar QPushButton[active="true"] {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(139,92,246,0.20), stop:1 rgba(6,182,212,0.08));
    color: {c.ACCENT};
    border-left: 2px solid {c.ACCENT};
    border-radius: 0px;
    padding-left: 12px;
}}

/* ═══ Header ════════════════════════════════════════════════════════════ */
#header {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {c.BG_SURFACE1}, stop:1 {c.BG_BASE});
    border-bottom: 1px solid {c.BORDER};
    min-height: 56px; max-height: 56px;
    padding: 0 24px;
}}

/* ═══ Buttons ═══════════════════════════════════════════════════════════ */
QPushButton {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {c.GRAD_START}, stop:1 {c.GRAD_END});
    color: {c.TEXT_PRIMARY};
    border: none;
    border-radius: {r.BUTTON};
    padding: 8px 18px;
    font-weight: {Typography.WEIGHT_MEDIUM};
    font-size: {Typography.SIZE_SM}px;
}}
QPushButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {c.ACCENT}, stop:1 {c.CYAN});
}}
QPushButton:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {c.ACCENT_PRESS}, stop:1 {c.CYAN_HOVER});
}}
QPushButton:disabled {{
    background: {c.BG_SURFACE3};
    color: {c.TEXT_DISABLED};
    border: 1px solid {c.BORDER};
}}
QPushButton#btn_primary {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {c.GRAD_START}, stop:1 {c.GRAD_END});
    font-weight: {Typography.WEIGHT_BOLD};
}}
QPushButton#btn_secondary, QPushButton#btn_icon {{
    background: {c.BG_GLASS};
    padding: 4px;
    min-width: 0px;
    color: {c.TEXT_SECONDARY};
    border: 1px solid {c.BORDER};
}}
QPushButton#btn_secondary:hover, QPushButton#btn_icon:hover {{
    background: {c.BG_GLASS2};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER_HOVER};
}}
QPushButton#btn_danger {{
    background: rgba(239, 68, 68, 0.12);
    color: {c.ERROR};
    border: 1px solid rgba(239, 68, 68, 0.28);
}}
QPushButton#btn_danger:hover {{
    background: rgba(239, 68, 68, 0.22);
}}

/* ═══ Glass card panels ══════════════════════════════════════════════════ */
QFrame#card {{
    background: {c.BG_GLASS};
    border: 1px solid {c.BORDER};
    border-radius: {r.CARD};
}}
QFrame#kpi_card {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(139,92,246,0.10), stop:1 rgba(6,182,212,0.04));
    border: 1px solid {c.BORDER};
    border-radius: {r.CARD};
}}
QFrame#panel {{
    background: {c.BG_SURFACE1};
    border: 1px solid {c.BORDER};
    border-radius: {r.PANEL};
}}
QFrame#sidebar {{
    background-color: {c.BG_SURFACE1};
    border-right: 1px solid {c.BORDER};
}}

/* ═══ Inputs ════════════════════════════════════════════════════════════ */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {c.BG_GLASS};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER};
    border-radius: {r.INPUT};
    padding: 7px 12px;
    selection-background-color: rgba(139, 92, 246, 0.40);
}}
QTextEdit, QPlainTextEdit {{
    background: {c.BG_SURFACE2};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER};
    border-radius: {r.INPUT};
    padding: 7px 12px;
    selection-background-color: rgba(139, 92, 246, 0.40);
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {c.BORDER_FOCUS};
    background: {c.BG_GLASS2};
}}
QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {c.BORDER_FOCUS};
    background: {c.BG_SURFACE3};
}}
QLineEdit:disabled {{ color: {c.TEXT_DISABLED}; }}
QComboBox::drop-down {{ border: none; width: 24px; background: transparent; }}
  QComboBox::down-arrow {{ width: 10px; height: 10px; }}
QComboBox QAbstractItemView {{
    background: {c.BG_SURFACE2};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER};
    selection-background-color: rgba(139, 92, 246, 0.25);
    outline: none;
}}

/* ═══ Labels ════════════════════════════════════════════════════════════ */
QLabel#section_header {{
    font-size: {Typography.SIZE_LG}px;
    font-weight: {Typography.WEIGHT_BOLD};
    color: {c.TEXT_PRIMARY};
}}
QLabel#label_muted  {{
    color: {c.TEXT_MUTED};
    font-size: {Typography.SIZE_XS}px;
}}
QLabel#label_subtitle {{
    color: {c.TEXT_SECONDARY};
    font-size: {Typography.SIZE_SM}px;
    font-weight: {Typography.WEIGHT_MEDIUM};
}}
QLabel#label_kpi_title {{
    color: {c.TEXT_MUTED};
    font-size: {Typography.SIZE_XS}px;
    font-weight: {Typography.WEIGHT_MEDIUM};
    letter-spacing: 1px;
}}
QLabel#label_kpi_value {{
    font-size: 26px;
    font-weight: {Typography.WEIGHT_BOLD};
    color: {c.TEXT_PRIMARY};
}}
QLabel#demo_badge {{
    background: rgba(6,182,212,0.12);
    color: {c.CYAN};
    border: 1px solid {c.BORDER_CYAN};
    border-radius: {r.PILL};
    padding: 2px 10px;
    font-size: {Typography.SIZE_XS}px;
    font-weight: {Typography.WEIGHT_BOLD};
    letter-spacing: 1px;
}}
QLabel#plan_badge {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(124,58,237,0.25), stop:1 rgba(6,182,212,0.15));
    color: {c.ACCENT};
    border: 1px solid {c.BORDER};
    border-radius: {r.PILL};
    padding: 3px 12px;
    font-size: {Typography.SIZE_XS}px;
    font-weight: {Typography.WEIGHT_BOLD};
}}
QLabel#label_title {{
    font-size: {Typography.SIZE_XL}px;
    font-weight: {Typography.WEIGHT_BOLD};
    color: {c.TEXT_PRIMARY};
}}

/* ═══ Progress bar — neon gradient ══════════════════════════════════════ */
QProgressBar {{
    background: {c.BG_SURFACE3};
    border: 1px solid {c.BORDER};
    border-radius: {r.SMALL};
    height: 6px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {c.GRAD_START}, stop:0.5 #9333EA, stop:1 {c.GRAD_END});
    border-radius: {r.SMALL};
}}

/* ═══ Tables ════════════════════════════════════════════════════════════ */
QTableWidget {{
    background: {c.BG_SURFACE1};
    color: {c.TEXT_PRIMARY};
    gridline-color: {c.BORDER};
    border: 1px solid {c.BORDER};
    border-radius: {r.CARD};
    alternate-background-color: {c.BG_GLASS};
    selection-background-color: rgba(139, 92, 246, 0.18);
    outline: none;
}}
QTableWidget::item:selected {{ color: {c.TEXT_PRIMARY}; }}
QHeaderView::section {{
    background: {c.BG_GLASS};
    color: {c.TEXT_MUTED};
    border: none;
    border-bottom: 1px solid {c.BORDER};
    padding: 8px 10px;
    font-size: {Typography.SIZE_XS}px;
    font-weight: {Typography.WEIGHT_BOLD};
    letter-spacing: 0.8px;
    text-transform: uppercase;
}}

/* ═══ Tabs ═══════════════════════════════════════════════════════════════ */
QTabWidget::pane {{
    background: {c.BG_SURFACE2};
    border: 1px solid {c.BORDER};
    border-radius: {r.CARD};
}}
QTabBar::tab {{
    background: transparent;
    color: {c.TEXT_SECONDARY};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 8px 20px;
    font-weight: {Typography.WEIGHT_MEDIUM};
}}
QTabBar::tab:selected {{
    color: {c.ACCENT};
    border-bottom: 2px solid {c.ACCENT};
}}
QTabBar::tab:hover {{ color: {c.TEXT_PRIMARY}; }}

/* ═══ Scrollbars ════════════════════════════════════════════════════════ */
QScrollBar:vertical {{
    background: transparent; width: 6px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {c.SCROLLBAR_HANDLE};
    border-radius: 3px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {c.BORDER_HOVER};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent; height: 6px; margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {c.SCROLLBAR_HANDLE};
    border-radius: 3px; min-width: 30px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ═══ Checkboxes ════════════════════════════════════════════════════════ */
QCheckBox {{
    spacing: 8px;
    color: {c.TEXT_SECONDARY};
    font-size: {Typography.SIZE_SM}px;
}}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {c.BORDER};
    border-radius: {r.SMALL};
    background: {c.BG_GLASS};
}}
QCheckBox::indicator:checked {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {c.GRAD_START}, stop:1 {c.GRAD_END});
    border-color: {c.ACCENT};
}}
QCheckBox::indicator:hover {{ border-color: {c.ACCENT}; }}

/* ═══ Slider ════════════════════════════════════════════════════════════ */
QSlider::groove:horizontal {{
    height: 4px;
    background: {c.BG_SURFACE4};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {c.ACCENT}, stop:1 {c.CYAN});
    border: 2px solid {c.BG_BASE};
    width: 14px; height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::sub-page:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {c.GRAD_START}, stop:1 {c.GRAD_END});
    border-radius: 2px;
}}

/* ═══ GroupBox ══════════════════════════════════════════════════════════ */
QGroupBox {{
    color: {c.TEXT_MUTED};
    border: 1px solid {c.BORDER};
    border-radius: {r.CARD};
    margin-top: 8px;
    padding-top: 8px;
    font-size: {Typography.SIZE_XS}px;
    font-weight: {Typography.WEIGHT_BOLD};
    letter-spacing: 0.5px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px; top: -1px;
    padding: 0 6px;
    background-color: {c.BG_BASE};
    color: {c.TEXT_MUTED};
}}

/* ═══ ListWidget ════════════════════════════════════════════════════════ */
QListWidget {{
    background: {c.BG_SURFACE1};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER};
    border-radius: {r.CARD};
    alternate-background-color: {c.BG_GLASS};
    outline: none;
}}
QListWidget::item:selected {{
    background: rgba(139, 92, 246, 0.20);
    color: {c.TEXT_PRIMARY};
}}
QListWidget::item:hover {{
    background: {c.BG_GLASS};
}}

/* ═══ DateTimeEdit ══════════════════════════════════════════════════════ */
QDateTimeEdit {{
    background: {c.BG_GLASS};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER};
    border-radius: {r.INPUT};
    padding: 6px 10px;
}}
QDateTimeEdit:focus {{ border-color: {c.BORDER_FOCUS}; }}
QDateTimeEdit::up-button, QDateTimeEdit::down-button {{
    background: transparent; border: none; width: 16px;
}}

/* ═══ Splitter ══════════════════════════════════════════════════════════ */
QSplitter::handle {{ background: {c.BORDER}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}

/* ═══ Tooltip ═══════════════════════════════════════════════════════════ */
QToolTip {{
    background: {c.BG_SURFACE3};
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER_HOVER};
    border-radius: {r.SMALL};
    padding: 4px 8px;
    font-size: {Typography.SIZE_XS}px;
}}

/* ═══ MessageBox ════════════════════════════════════════════════════════ */
QMessageBox {{ background: {c.BG_SURFACE2}; }}
QMessageBox QLabel {{ color: {c.TEXT_PRIMARY}; }}

/* ═══ Activation screen ═════════════════════════════════════════════════ */
#activation_container {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(124,58,237,0.08), stop:1 rgba(6,182,212,0.04));
    border: 1px solid {c.BORDER};
    border-radius: {r.MODAL};
}}
QLineEdit#key_input {{
    font-size: {Typography.SIZE_MD}px;
    letter-spacing: 2px;
    padding: 10px 14px;
    border-radius: {r.CARD};
    border: 1px solid {c.BORDER};
    background: {c.BG_GLASS};
}}
QLineEdit#key_input:focus {{
    border-color: {c.BORDER_FOCUS};
    background: {c.BG_GLASS2};
}}
QPushButton#btn_activate {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {c.GRAD_START}, stop:1 {c.GRAD_END});
    font-size: {Typography.SIZE_MD}px;
    font-weight: {Typography.WEIGHT_BOLD};
    padding: 12px 24px;
    border-radius: {r.CARD};
    min-width: 200px;
}}
QPushButton#btn_activate:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {c.ACCENT}, stop:1 {c.CYAN});
}}

/* ═══ SpinBox — hide default OS arrow buttons (no black squares) ═══════ */
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    width: 0px;
    height: 0px;
    border: none;
    background: transparent;
}}
"""
