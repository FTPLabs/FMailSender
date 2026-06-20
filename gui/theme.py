"""
FMailSender GUI Theme v3.6.2
Dark CyberPro design: Purple accent #8B5CF6, deep dark background #040410
"""
from __future__ import annotations


class Colors:
    # ── Backgrounds ──────────────────────────────────────────────────────
    BG_BASE     = "#040410"
    BG_SURFACE  = "#0D0D1A"
    BG_SURFACE2 = "#12121F"
    # ── Accent (purple) ──────────────────────────────────────────────────
    ACCENT        = "#8B5CF6"
    ACCENT_HOVER  = "#7C3AED"
    ACCENT_LIGHT  = "#A78BFA"
    ACCENT_DIM    = "rgba(139,92,246,0.12)"
    BORDER_ACCENT = "rgba(139,92,246,0.35)"
    # ── Semantic ─────────────────────────────────────────────────────────
    GREEN  = "#22C55E"
    RED    = "#EF4444"
    AMBER  = "#F59E0B"
    BLUE   = "#3B82F6"
    CYAN   = "#06B6D4"
    # ── Text ─────────────────────────────────────────────────────────────
    TEXT_PRIMARY   = "#E2E8F0"
    TEXT_SECONDARY = "#6666AA"
    TEXT_MUTED     = "rgba(255,255,255,0.38)"
    TEXT_FAINT     = "rgba(255,255,255,0.15)"
    # ── Borders ──────────────────────────────────────────────────────────
    BORDER = "rgba(255,255,255,0.07)"
    FAINT  = "rgba(255,255,255,0.06)"


class Spacing:
    XS  = 4
    SM  = 6
    MD  = 10
    LG  = 14
    XL  = 20
    XXL = 28
    RADIUS_SM = 6
    RADIUS_MD = 8
    RADIUS_LG = 12
    RADIUS_XL = 16


class Typography:
    FAMILY      = "Inter"
    FAMILY_MONO = "Consolas"
    SIZE_XS   = 9
    SIZE_SM   = 10
    SIZE_BASE = 11
    SIZE_MD   = 12
    SIZE_LG   = 13
    SIZE_XL   = 15
    SIZE_2XL  = 20
    SIZE_3XL  = 28


def load_fonts() -> None:
    """Load custom fonts if bundled with the app."""
    pass  # Inter loaded from system or bundled assets


def get_stylesheet() -> str:
    C = Colors
    S = Spacing
    T = Typography
    return f"""
/* ── Base ───────────────────────────────────────────────────────────────── */
QWidget {{
    background: {C.BG_BASE};
    color: {C.TEXT_PRIMARY};
    font-family: '{T.FAMILY}', 'Segoe UI', 'Arial', sans-serif;
    font-size: {T.SIZE_BASE}pt;
    outline: none;
}}
QMainWindow {{
    background: {C.BG_BASE};
}}
QDialog {{
    background: {C.BG_SURFACE};
}}

/* ── Scrollbars ─────────────────────────────────────────────────────────── */
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: rgba(139,92,246,0.35);
    border-radius: 3px;
    min-height: 24px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 6px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: rgba(139,92,246,0.35);
    border-radius: 3px;
    min-width: 24px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── Inputs ─────────────────────────────────────────────────────────────── */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background: {C.BG_SURFACE};
    color: {C.TEXT_PRIMARY};
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: {S.RADIUS_MD}px;
    padding: 7px 12px;
    selection-background-color: rgba(139,92,246,0.35);
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid rgba(139,92,246,0.55);
    background: {C.BG_SURFACE};
}}
QLineEdit:disabled, QTextEdit:disabled {{
    color: rgba(255,255,255,0.25);
}}

/* ── SpinBox ────────────────────────────────────────────────────────────── */
QSpinBox, QDoubleSpinBox {{
    background: {C.BG_SURFACE};
    color: {C.TEXT_PRIMARY};
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: {S.RADIUS_MD}px;
    padding: 6px 10px;
}}
QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid rgba(139,92,246,0.55);
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background: rgba(255,255,255,0.06);
    border: none;
    width: 18px;
    border-radius: 3px;
}}

/* ── ComboBox ───────────────────────────────────────────────────────────── */
QComboBox {{
    background: {C.BG_SURFACE};
    color: {C.TEXT_PRIMARY};
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: {S.RADIUS_MD}px;
    padding: 6px 10px;
}}
QComboBox:focus {{ border: 1px solid rgba(139,92,246,0.55); }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{ width: 10px; height: 10px; }}
QComboBox QAbstractItemView {{
    background: {C.BG_SURFACE};
    color: {C.TEXT_PRIMARY};
    border: 1px solid rgba(139,92,246,0.25);
    selection-background-color: rgba(139,92,246,0.18);
    selection-color: {C.TEXT_PRIMARY};
    outline: none;
}}

/* ── Buttons (named via objectName) ─────────────────────────────────────── */
QPushButton {{
    background: rgba(255,255,255,0.06);
    color: {C.TEXT_PRIMARY};
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: {S.RADIUS_MD}px;
    padding: 7px 14px;
}}
QPushButton:hover {{
    background: rgba(255,255,255,0.10);
    border: 1px solid rgba(255,255,255,0.12);
}}
QPushButton:pressed {{
    background: rgba(255,255,255,0.06);
}}
QPushButton:disabled {{
    color: rgba(255,255,255,0.25);
    border: 1px solid rgba(255,255,255,0.05);
}}
QPushButton[objectName="btn_primary"] {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {C.ACCENT_HOVER}, stop:1 {C.ACCENT_LIGHT});
    color: white;
    border: none;
    font-weight: 600;
    padding: 8px 20px;
}}
QPushButton[objectName="btn_primary"]:hover {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #6D28D9, stop:1 {C.ACCENT});
}}
QPushButton[objectName="btn_primary"]:disabled {{
    background: rgba(139,92,246,0.25);
    color: rgba(255,255,255,0.4);
}}
QPushButton[objectName="btn_secondary"] {{
    background: rgba(139,92,246,0.12);
    color: {C.ACCENT_LIGHT};
    border: 1px solid rgba(139,92,246,0.28);
    padding: 8px 20px;
}}
QPushButton[objectName="btn_secondary"]:hover {{
    background: rgba(139,92,246,0.22);
    border: 1px solid rgba(139,92,246,0.4);
}}
QPushButton[objectName="btn_danger"] {{
    background: rgba(239,68,68,0.10);
    color: {C.RED};
    border: 1px solid rgba(239,68,68,0.28);
    padding: 8px 20px;
}}
QPushButton[objectName="btn_danger"]:hover {{
    background: rgba(239,68,68,0.20);
}}
QPushButton[objectName="btn_success"] {{
    background: rgba(34,197,94,0.10);
    color: {C.GREEN};
    border: 1px solid rgba(34,197,94,0.28);
    padding: 8px 20px;
}}
QPushButton[objectName="btn_success"]:hover {{
    background: rgba(34,197,94,0.20);
}}
QPushButton[objectName="btn_icon"] {{
    background: transparent;
    border: 1px solid rgba(255,255,255,0.08);
    padding: 6px 10px;
    color: {C.TEXT_MUTED};
}}
QPushButton[objectName="btn_icon"]:hover {{
    background: rgba(255,255,255,0.06);
    color: {C.TEXT_PRIMARY};
    border: 1px solid rgba(255,255,255,0.14);
}}
QPushButton[objectName="btn_nav"] {{
    background: transparent;
    border: 1px solid transparent;
    text-align: left;
    padding: 9px 14px;
    border-radius: {S.RADIUS_LG}px;
    color: {C.TEXT_MUTED};
    font-size: {T.SIZE_BASE}pt;
}}
QPushButton[objectName="btn_nav"]:hover {{
    background: rgba(255,255,255,0.04);
    color: {C.TEXT_PRIMARY};
}}
QPushButton[objectName="btn_nav_active"] {{
    background: rgba(139,92,246,0.12);
    border: 1px solid rgba(139,92,246,0.35);
    color: {C.ACCENT};
    text-align: left;
    padding: 9px 14px;
    border-radius: {S.RADIUS_LG}px;
    font-size: {T.SIZE_BASE}pt;
    font-weight: 600;
}}

/* ── Cards ──────────────────────────────────────────────────────────────── */
QFrame[objectName="card"] {{
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(139,92,246,0.12);
    border-radius: {S.RADIUS_LG}px;
}}
QFrame[objectName="kpi_card"] {{
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(139,92,246,0.22);
    border-radius: {S.RADIUS_LG}px;
}}
QFrame[objectName="sidebar"] {{
    background: {C.BG_SURFACE};
    border: none;
    border-right: 1px solid rgba(255,255,255,0.07);
}}
QFrame[objectName="header"] {{
    background: {C.BG_SURFACE};
    border: none;
    border-bottom: 1px solid rgba(255,255,255,0.07);
}}

/* ── Table ──────────────────────────────────────────────────────────────── */
QTableWidget {{
    background: transparent;
    border: none;
    gridline-color: rgba(255,255,255,0.05);
    selection-background-color: rgba(139,92,246,0.12);
    selection-color: {C.TEXT_PRIMARY};
    alternate-background-color: rgba(255,255,255,0.015);
}}
QTableWidget::item {{
    padding: 8px 12px;
    border-bottom: 1px solid rgba(255,255,255,0.04);
}}
QTableWidget::item:selected {{
    background: rgba(139,92,246,0.12);
    color: {C.TEXT_PRIMARY};
}}
QHeaderView::section {{
    background: {C.BG_SURFACE};
    color: rgba(255,255,255,0.38);
    border: none;
    border-bottom: 1px solid rgba(255,255,255,0.07);
    padding: 8px 12px;
    font-size: {T.SIZE_XS}pt;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

/* ── Tabs ───────────────────────────────────────────────────────────────── */
QTabWidget::pane {{
    border: none;
    background: transparent;
}}
QTabBar::tab {{
    background: transparent;
    color: rgba(255,255,255,0.38);
    padding: 8px 18px;
    border: none;
    border-bottom: 2px solid transparent;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    color: {C.ACCENT_LIGHT};
    border-bottom: 2px solid {C.ACCENT};
}}
QTabBar::tab:hover:!selected {{
    color: rgba(255,255,255,0.65);
}}

/* ── CheckBox / RadioButton ─────────────────────────────────────────────── */
QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 4px;
    background: {C.BG_SURFACE};
}}
QCheckBox::indicator:checked {{
    background: {C.ACCENT};
    border: 1px solid {C.ACCENT};
}}
QCheckBox::indicator:hover {{
    border: 1px solid rgba(139,92,246,0.5);
}}
QRadioButton::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 7px;
    background: {C.BG_SURFACE};
}}
QRadioButton::indicator:checked {{
    background: {C.ACCENT};
    border: 2px solid {C.BG_SURFACE};
    outline: 1px solid {C.ACCENT};
}}

/* ── ProgressBar ────────────────────────────────────────────────────────── */
QProgressBar {{
    background: rgba(255,255,255,0.06);
    border: none;
    border-radius: 99px;
    height: 6px;
    text-align: center;
    color: transparent;
    max-height: 6px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #7C3AED, stop:1 #A78BFA);
    border-radius: 99px;
}}

/* ── Slider ─────────────────────────────────────────────────────────────── */
QSlider::groove:horizontal {{
    background: rgba(255,255,255,0.08);
    height: 4px;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {C.ACCENT};
    width: 14px;
    height: 14px;
    border-radius: 7px;
    margin: -5px 0;
}}
QSlider::sub-page:horizontal {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #7C3AED,stop:1 #A78BFA);
    border-radius: 2px;
}}

/* ── ToolTip ─────────────────────────────────────────────────────────────── */
QToolTip {{
    background: {C.BG_SURFACE};
    color: {C.TEXT_PRIMARY};
    border: 1px solid rgba(139,92,246,0.3);
    border-radius: 6px;
    padding: 5px 10px;
}}

/* ── Label aliases ───────────────────────────────────────────────────────── */
QLabel[objectName="section_header"] {{
    color: {C.TEXT_PRIMARY};
    font-size: {T.SIZE_XL}pt;
    font-weight: 600;
}}
QLabel[objectName="label_muted"] {{
    color: rgba(255,255,255,0.38);
    font-size: {T.SIZE_SM}pt;
}}
QLabel[objectName="label_kpi_title"] {{
    color: rgba(255,255,255,0.38);
    font-size: {T.SIZE_XS}pt;
    font-weight: 600;
    letter-spacing: 1px;
}}
QLabel[objectName="label_kpi_value"] {{
    color: {C.ACCENT_LIGHT};
    font-size: {T.SIZE_2XL}pt;
    font-weight: 700;
}}
QLabel[objectName="label_green"] {{
    color: {C.GREEN};
    font-weight: 600;
}}
QLabel[objectName="label_red"] {{
    color: {C.RED};
    font-weight: 600;
}}
QLabel[objectName="label_amber"] {{
    color: {C.AMBER};
    font-weight: 600;
}}

/* ── Separator ───────────────────────────────────────────────────────────── */
QFrame[frameShape="4"], QFrame[frameShape="5"] {{
    color: rgba(255,255,255,0.07);
    background: rgba(255,255,255,0.07);
    border: none;
    max-height: 1px;
}}

/* ── StatusBar ───────────────────────────────────────────────────────────── */
QStatusBar {{
    background: {C.BG_SURFACE};
    color: rgba(255,255,255,0.38);
    border-top: 1px solid rgba(255,255,255,0.07);
    font-size: {T.SIZE_XS}pt;
}}
"""
