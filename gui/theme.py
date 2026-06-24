"""
FMail Sender Pro — CyberPro Design System v3.3
Style: #040410 BG, violet #8B5CF6 / cyan #06B6D4, 3 animated orbs, aurora.
Includes get_stylesheet() — применяется через app.setStyleSheet() в main.py.
"""
from PyQt6.QtGui import QFontDatabase
from pathlib import Path


class Colors:
    # Backgrounds
    BG_BASE       = "#040410"
    BG_SURFACE1   = "#08080F"
    BG_SURFACE2   = "#0C0C1A"
    BG_SURFACE3   = "#101020"
    BG_SURFACE4   = "#14142A"
    BG_GLASS      = "rgba(255, 255, 255, 0.03)"
    BG_GLASS2     = "rgba(255, 255, 255, 0.06)"
    # Violet
    ACCENT        = "#8B5CF6"
    ACCENT_HOVER  = "#7C3AED"
    ACCENT_PRESS  = "#6D28D9"
    ACCENT_GLOW   = "rgba(139, 92, 246, 0.35)"
    ACCENT_DIM    = "rgba(139, 92, 246, 0.12)"
    # Cyan
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
    # Borders
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
    # Orb colors for AnimatedBackground
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


def get_stylesheet() -> str:
    """Main stylesheet — applied via app.setStyleSheet() in main.py.
    Covers: base widgets, objectName aliases used across all screens.
    """
    c = Colors
    r = Radii
    t = Typography
    return f"""
/* === BASE =========================================================== */
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

/* === SCROLLBARS ===================================================== */
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
QScrollBar::handle:horizontal {{
    background: {c.SCROLLBAR_HANDLE}; border-radius: 2px;
}}

/* === BUTTONS ======================================================== */
QPushButton {{
    background-color: rgba(255,255,255,0.03);
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
    background-color: rgba(109, 40, 217, 0.22);
    border-color: {c.ACCENT_PRESS};
}}
QPushButton:disabled {{
    color: {c.TEXT_MUTED}; border-color: {c.BORDER}; background: transparent;
}}
/* Accent primary button */
QPushButton[objectName="btn_primary"] {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {c.ACCENT_HOVER}, stop:1 {c.CYAN});
    border: none; color: white; font-weight: {t.WEIGHT_SEMIBOLD};
}}
QPushButton[objectName="btn_primary"]:hover {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {c.ACCENT}, stop:1 {c.CYAN_HOVER});
}}
QPushButton[objectName="btn_primary"]:disabled {{
    background: {c.BG_SURFACE2}; color: {c.TEXT_MUTED}; border: 1px solid {c.BORDER};
}}
/* Secondary button */
QPushButton[objectName="btn_secondary"] {{
    background: {c.ACCENT_DIM};
    border: 1px solid {c.BORDER_HOVER};
    color: {c.ACCENT};
}}
QPushButton[objectName="btn_secondary"]:hover {{
    background: rgba(139,92,246,0.20);
    color: white;
}}
/* Icon button */
QPushButton[objectName="btn_icon"] {{
    background: rgba(255,255,255,0.03);
    border: 1px solid {c.BORDER};
    padding: 5px 10px;
}}
QPushButton[objectName="btn_icon"]:hover {{
    background: {c.ACCENT_DIM}; border-color: {c.BORDER_HOVER};
}}
/* Danger button */
QPushButton[objectName="btn_danger"] {{
    background: rgba(239,68,68,0.10);
    border: 1px solid rgba(239,68,68,0.25);
    color: {c.ERROR};
}}
QPushButton[objectName="btn_danger"]:hover {{
    background: rgba(239,68,68,0.20); color: white;
}}

/* === INPUTS ========================================================= */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: rgba(255,255,255,0.03);
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER};
    border-radius: {r.INPUT};
    padding: 6px 10px;
    selection-background-color: {c.ACCENT_DIM};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {c.BORDER_FOCUS};
    background-color: rgba(255,255,255,0.05);
}}

/* === COMBOBOX ======================================================= */
QComboBox {{
    background-color: rgba(255,255,255,0.03);
    color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER};
    border-radius: {r.INPUT}; padding: 5px 10px;
}}
QComboBox:focus, QComboBox:on {{ border-color: {c.BORDER_FOCUS}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{ image: none; width: 0; }}
QComboBox QAbstractItemView {{
    background-color: {c.BG_SURFACE2}; color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER}; border-radius: {r.INPUT};
    selection-background-color: {c.ACCENT_DIM}; outline: none;
}}

/* === SPINBOX ======================================================== */
QSpinBox, QDoubleSpinBox {{
    background-color: rgba(255,255,255,0.03); color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER}; border-radius: {r.INPUT}; padding: 5px 8px;
}}
QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {c.BORDER_FOCUS}; }}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background: {c.ACCENT_DIM}; border: none; width: 18px;
}}

/* === TABLES ========================================================= */
/* FIX: explicit BG prevents Windows dark-mode system palette from
   overriding alternating row colours (transparent leaks system palette). */
QTableWidget, QTableView {{
    background-color: {c.BG_BASE}; color: {c.TEXT_PRIMARY};
    alternate-background-color: {c.BG_SURFACE1};
    gridline-color: transparent; border: 1px solid {c.BORDER};
    border-radius: {r.CARD}; outline: none;
}}
QHeaderView::section {{
    background-color: {c.BG_SURFACE1}; color: {c.TEXT_SECONDARY};
    border: none; border-bottom: 1px solid {c.BORDER};
    padding: 11px 14px; font-size: 11px;
    font-weight: {t.WEIGHT_SEMIBOLD}; letter-spacing: 0.05em;
}}
QTableWidget::item {{ background-color: transparent; padding: 12px 14px; border-bottom: 1px solid rgba(139,92,246,0.05); }}
QTableWidget::item:selected {{ background-color: {c.ACCENT_DIM}; color: white; }}
QTableWidget::item:hover {{ background-color: rgba(255,255,255,0.03); }}

/* === LIST =========================================================== */
/* FIX: same as tables — explicit BG to prevent Windows dark-mode interference. */
QListWidget {{
    background-color: {c.BG_BASE}; color: {c.TEXT_PRIMARY};
    alternate-background-color: {c.BG_SURFACE1};
    border: 1px solid {c.BORDER}; border-radius: {r.CARD}; outline: none;
}}
QListWidget::item {{ background-color: transparent; padding: 11px 14px; border-bottom: 1px solid rgba(139,92,246,0.05); }}
QListWidget::item:selected {{ background-color: {c.ACCENT_DIM}; color: white; }}
QListWidget::item:hover {{ background-color: rgba(255,255,255,0.03); }}

/* === CHECKBOX ======================================================= */
QCheckBox {{ color: {c.TEXT_PRIMARY}; spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {c.BORDER_HOVER}; border-radius: 4px;
    background: rgba(255,255,255,0.03);
}}
QCheckBox::indicator:checked {{ background: {c.ACCENT}; border-color: {c.ACCENT}; }}
QCheckBox::indicator:unchecked:hover {{ border-color: {c.ACCENT}; }}
  /* === DIALOGS (popup styling) ========================================= */
  /* Диалоговые окна — фон поверхности, не чёрный */
  QDialog {{
      background-color: {c.BG_BASE};
  }}
  QDialog QFrame[objectName="card"] {{
      background: {c.BG_SURFACE2};
      border: 1px solid {c.BORDER};
      border-radius: {r.CARD};
  }}
  QDialog QLabel {{
      background: transparent;
      color: {c.TEXT_PRIMARY};
  }}
  QDialog QLabel[objectName="label_muted"] {{
      color: {c.TEXT_MUTED};
  }}
  /* Чекбоксы в диалогах — видимый текст */
  QDialog QCheckBox {{
      background: transparent;
      color: {c.TEXT_PRIMARY};
      spacing: 8px;
      padding: 3px 0;
      font-size: {t.SIZE_SM}px;
  }}
  QDialog QCheckBox::indicator {{
      width: 16px; height: 16px;
      border: 1px solid {c.BORDER_HOVER};
      border-radius: 4px;
      background: rgba(255,255,255,0.04);
  }}
  QDialog QCheckBox::indicator:checked {{
      background: {c.ACCENT};
      border-color: {c.ACCENT};
      image: none;
  }}
  QDialog QCheckBox::indicator:hover {{
      border-color: {c.ACCENT};
      background: {c.ACCENT_DIM};
  }}
  /* ScrollArea в диалогах */
  QDialog QScrollArea {{
      background: {c.BG_SURFACE2};
      border: 1px solid {c.BORDER};
      border-radius: {r.CARD};
  }}
  QDialog QScrollArea > QWidget > QWidget {{
      background: transparent;
  }}
  /* Кнопки в диалогах */
  QDialogButtonBox QPushButton {{
      min-width: 80px;
  }}

  

/* === TABS =========================================================== */
QTabBar::tab {{
    background: transparent; color: {c.TEXT_SECONDARY};
    border: none; border-bottom: 2px solid transparent;
    padding: 8px 18px; font-size: {t.SIZE_SM}px; font-weight: {t.WEIGHT_MEDIUM};
}}
QTabBar::tab:selected {{
    color: {c.TEXT_PRIMARY}; border-bottom: 2px solid {c.ACCENT};
}}
QTabBar::tab:hover:!selected {{ color: {c.TEXT_PRIMARY}; }}
QTabWidget::pane {{
    border: 1px solid {c.BORDER}; border-radius: {r.CARD}; background: transparent;
}}

/* === PROGRESS BAR =================================================== */
QProgressBar {{
    background-color: {c.BG_SURFACE2}; border: none;
    border-radius: 3px; height: 6px; color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {c.ACCENT}, stop:1 {c.CYAN});
    border-radius: 3px;
}}
QProgressBar[objectName="progress_flat"]::chunk {{
    background: {c.ACCENT}; border-radius: 2px;
}}

/* === GROUPBOX ======================================================= */
QGroupBox {{
    color: {c.TEXT_SECONDARY};
    border: 1px solid {c.BORDER};
    border-radius: {r.CARD};
    margin-top: 8px;
    padding-top: 12px;
    font-size: 11px; font-weight: {t.WEIGHT_SEMIBOLD};
}}
QGroupBox::title {{
    subcontrol-origin: margin; subcontrol-position: top left;
    padding: 0 6px; left: 10px;
    color: {c.TEXT_SECONDARY}; letter-spacing: 0.06em;
}}

/* === SLIDER ========================================================= */
QSlider::groove:horizontal {{
    height: 4px; background: {c.BG_SURFACE3}; border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 14px; height: 14px; margin: -5px 0;
    background: {c.ACCENT}; border-radius: 7px;
    border: 2px solid {c.BG_BASE};
}}
QSlider::sub-page:horizontal {{
    background: {c.ACCENT}; border-radius: 2px;
}}

/* === DATE/TIME EDIT ================================================= */
QDateTimeEdit {{
    background: rgba(255,255,255,0.03); color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER}; border-radius: {r.INPUT}; padding: 5px 8px;
}}
QDateTimeEdit:focus {{ border-color: {c.BORDER_FOCUS}; }}
QDateTimeEdit::drop-down {{ border: none; width: 20px; }}
QCalendarWidget {{
    background-color: {c.BG_SURFACE2}; color: {c.TEXT_PRIMARY};
}}

/* === MISC =========================================================== */
QLabel {{ background: transparent; color: {c.TEXT_PRIMARY}; }}
QToolTip {{
    background-color: {c.BG_SURFACE2}; color: {c.TEXT_PRIMARY};
    border: 1px solid {c.BORDER}; border-radius: {r.SMALL}; padding: 5px 8px;
}}
QSplitter::handle {{ background: {c.BORDER}; width: 1px; height: 1px; }}
QFrame {{ background: transparent; }}

/* === OBJECTNAME ALIASES (used across all screens) =================== */

/* -- Cards -- */
QFrame[objectName="card"] {{
    background-color: rgba(255,255,255,0.025);
    border: 1px solid rgba(139,92,246,0.12);
    border-radius: 12px;
}}
QFrame[objectName="kpi_card"] {{
    background-color: rgba(255,255,255,0.025);
    border: 1px solid rgba(139,92,246,0.14);
    border-radius: 12px;
}}
QFrame[objectName="card_inner"] {{
    background-color: rgba(255,255,255,0.015);
    border: 1px solid rgba(139,92,246,0.08);
    border-radius: 8px;
}}

/* -- Labels -- */
QLabel[objectName="section_header"] {{
    color: {c.TEXT_PRIMARY};
    font-size: 18px; font-weight: 700;
    background: transparent;
}}
QLabel[objectName="label_subtitle"] {{
    color: {c.TEXT_PRIMARY};
    font-size: 14px; font-weight: 600;
    background: transparent;
}}
QLabel[objectName="label_muted"] {{
    color: {c.TEXT_SECONDARY};
    font-size: 12px;
    background: transparent;
}}
QLabel[objectName="label_kpi_title"] {{
    color: {c.TEXT_SECONDARY};
    font-size: 11px; font-weight: 600;
    letter-spacing: 0.08em;
    background: transparent;
    text-transform: uppercase;
}}
QLabel[objectName="label_kpi_value"] {{
    color: {c.ACCENT};
    font-size: 28px; font-weight: 700;
    font-family: monospace;
    background: transparent;
}}
QLabel[objectName="label_error"] {{
    color: {c.ERROR}; font-size: 12px; background: transparent;
}}
QLabel[objectName="label_success"] {{
    color: {c.SUCCESS}; font-size: 12px; background: transparent;
}}

/* -- Status badges -- */
QLabel[objectName="badge_pro"] {{
    background: {c.ACCENT_DIM};
    color: {c.ACCENT};
    border: 1px solid {c.BORDER_HOVER};
    border-radius: 8px; padding: 2px 8px;
    font-size: 10px; font-weight: 700; font-family: monospace;
}}
QLabel[objectName="demo_badge"] {{
    background: rgba(239,68,68,0.15);
    color: {c.ERROR};
    border: 1px solid rgba(239,68,68,0.30);
    border-radius: 6px; padding: 3px 8px;
    font-size: 11px; font-weight: 700;
}}

/* -- Sidebar -- */
QFrame[objectName="plan_info_frame"] {{
    background: rgba(139,92,246,0.05);
    border-top: 1px solid rgba(139,92,246,0.12);
    border-radius: 0;
}}

/* -- Sending screen specifics -- */
QFrame[objectName="status_card"] {{
    background: rgba(255,255,255,0.02);
    border: 1px solid {c.BORDER};
    border-radius: {r.CARD};
}}

/* -- Header bar -- */
QFrame[objectName="header"] {{
    background-color: rgba(4,4,16,0.80);
    border-bottom: 1px solid rgba(139,92,246,0.10);
    min-height: 52px; max-height: 52px;
}}

/* -- Sidebar frame -- */
QFrame[objectName="sidebar"] {{
    background-color: rgba(4,4,16,0.85);
    border-right: 1px solid rgba(139,92,246,0.12);
}}
"""


# Alias for backward compatibility
global_stylesheet = get_stylesheet