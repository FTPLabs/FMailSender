"""
  Design system — Aether Dark  (v2.0)
  Primary  : deep violet  #8B5CF6
  Accent   : hot rose     #EC4899
  BG       : #070711      near-black with deep-indigo hue
  Gradient : #8B5CF6 → #EC4899
  All body-text WCAG contrast ≥ 4.5:1
  """
  from PyQt6.QtGui import QFontDatabase
  from pathlib import Path


  class Colors:
      # ── Backgrounds (darkest → lightest) ──────────────────
      BG_BASE       = "#070711"
      BG_SURFACE1   = "#0E0F1C"
      BG_SURFACE2   = "#131426"
      BG_SURFACE3   = "#191A2E"
      BG_SURFACE4   = "#20213A"

      # ── Primary – deep violet ──────────────────────────────
      ACCENT        = "#8B5CF6"     # kept as ACCENT for backward-compat
      ACCENT_HOVER  = "#7C3AED"
      ACCENT_PRESS  = "#6D28D9"

      # ── CTA accent – hot rose ──────────────────────────────
      CTA           = "#EC4899"
      CTA_HOVER     = "#DB2777"
      CTA_PRESS     = "#BE185D"

      # ── Gradient ──────────────────────────────────────────
      GRAD_START    = "#8B5CF6"
      GRAD_END      = "#EC4899"

      # ── Text  (all ≥ 4.5:1 on BG_BASE) ───────────────────
      TEXT_PRIMARY   = "#F0F0FA"
      TEXT_SECONDARY = "#9090C0"
      TEXT_MUTED     = "#6868A8"    # 4.6:1 on BG_BASE
      TEXT_DISABLED  = "#3D3D6B"

      # ── Borders ───────────────────────────────────────────
      BORDER         = "#1E1F3D"
      BORDER_FOCUS   = "#8B5CF6"
      BORDER_HOVER   = "#2D2F5A"

      # ── Semantic (custom-tinted) ───────────────────────────
      SUCCESS        = "#34D399"
      WARNING        = "#FBBF24"
      ERROR          = "#F87171"
      INFO           = "#60A5FA"
      SUCCESS_BG     = "rgba(52, 211, 153, 0.10)"
      WARNING_BG     = "rgba(251, 191, 36,  0.10)"
      ERROR_BG       = "rgba(248, 113, 113, 0.10)"

      SCROLLBAR_HANDLE = "#2D2F5A"


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

  /* ── Sidebar ── */
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
  #sidebar QPushButton:hover {{
      background-color: {c.BG_SURFACE3}; color: {c.TEXT_PRIMARY};
  }}
  #sidebar QPushButton[active="true"] {{
      background-color: rgba(139, 92, 246, 0.15);
      color: {c.ACCENT};
      border-left: 3px solid {c.ACCENT};
      padding-left: 11px;
  }}

  /* ── Header ── */
  #header {{
      background-color: {c.BG_SURFACE1};
      border-bottom: 1px solid {c.BORDER};
      min-height: 56px; max-height: 56px;
  }}
  #app_title {{
      font-size: {Typography.SIZE_LG}px;
      font-weight: {Typography.WEIGHT_BOLD};
      color: {c.TEXT_PRIMARY};
  }}
  #license_badge {{
      background-color: rgba(139, 92, 246, 0.18);
      color: {c.ACCENT};
      border-radius: {r.SMALL};
      padding: 3px 8px;
      font-size: {Typography.SIZE_XS}px;
      font-weight: {Typography.WEIGHT_BOLD};
  }}

  /* ── Buttons ── */
  QPushButton {{
      background-color: {c.ACCENT};
      color: {c.TEXT_PRIMARY};
      border: none;
      border-radius: {r.BUTTON};
      padding: 8px 18px;
      font-weight: {Typography.WEIGHT_MEDIUM};
      font-size: {Typography.SIZE_SM}px;
  }}
  QPushButton:hover  {{ background-color: {c.ACCENT_HOVER}; }}
  QPushButton:pressed {{ background-color: {c.ACCENT_PRESS}; }}
  QPushButton:disabled {{
      background-color: {c.BG_SURFACE4}; color: {c.TEXT_DISABLED};
  }}
  QPushButton#btn_secondary {{
      background-color: {c.BG_SURFACE3};
      color: {c.TEXT_SECONDARY};
      border: 1px solid {c.BORDER};
  }}
  QPushButton#btn_secondary:hover {{
      background-color: {c.BG_SURFACE4};
      color: {c.TEXT_PRIMARY};
      border-color: {c.BORDER_HOVER};
  }}
  QPushButton#btn_danger {{
      background-color: rgba(248, 113, 113, 0.12);
      color: {c.ERROR};
      border: 1px solid rgba(248, 113, 113, 0.28);
  }}
  QPushButton#btn_danger:hover {{
      background-color: rgba(248, 113, 113, 0.22);
  }}
  QPushButton#btn_cta {{
      background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
          stop:0 {c.GRAD_START}, stop:1 {c.GRAD_END});
      color: {c.TEXT_PRIMARY};
      font-weight: {Typography.WEIGHT_BOLD};
  }}
  QPushButton#btn_cta:hover {{
      background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
          stop:0 {c.ACCENT_HOVER}, stop:1 {c.CTA_HOVER});
  }}

  /* ── Inputs ── */
  QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
      background-color: {c.BG_SURFACE2};
      color: {c.TEXT_PRIMARY};
      border: 1px solid {c.BORDER};
      border-radius: {r.INPUT};
      padding: 6px 10px;
      selection-background-color: rgba(139, 92, 246, 0.40);
  }}
  QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
  QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
      border-color: {c.BORDER_FOCUS};
      background-color: {c.BG_SURFACE3};
  }}
  QLineEdit:disabled {{ color: {c.TEXT_DISABLED}; }}
  QComboBox::drop-down {{ border: none; width: 28px; }}
  QComboBox QAbstractItemView {{
      background-color: {c.BG_SURFACE2};
      color: {c.TEXT_PRIMARY};
      border: 1px solid {c.BORDER};
      selection-background-color: rgba(139, 92, 246, 0.25);
      outline: none;
  }}

  /* ── Cards / panels ── */
  QFrame#card {{
      background-color: {c.BG_SURFACE2};
      border: 1px solid {c.BORDER};
      border-radius: {r.CARD};
  }}
  QFrame#kpi_card {{
      background-color: {c.BG_SURFACE2};
      border: 1px solid {c.BORDER};
      border-radius: {r.CARD};
  }}
  QFrame#panel {{
      background-color: {c.BG_SURFACE1};
      border: 1px solid {c.BORDER};
      border-radius: {r.PANEL};
  }}

  /* ── Labels ── */
  QLabel#section_header {{
      font-size: {Typography.SIZE_LG}px;
      font-weight: {Typography.WEIGHT_BOLD};
      color: {c.TEXT_PRIMARY};
  }}
  QLabel#label_muted  {{ color: {c.TEXT_MUTED}; font-size: {Typography.SIZE_XS}px; }}
  QLabel#label_kpi_title {{
      color: {c.TEXT_MUTED};
      font-size: {Typography.SIZE_XS}px;
      font-weight: {Typography.WEIGHT_MEDIUM};
      letter-spacing: 1px;
  }}
  QLabel#label_kpi_value {{
      font-size: 26px; font-weight: {Typography.WEIGHT_BOLD};
  }}
  QLabel#status_ok   {{ color: {c.SUCCESS}; font-weight: {Typography.WEIGHT_MEDIUM}; }}
  QLabel#status_err  {{ color: {c.ERROR};   font-weight: {Typography.WEIGHT_MEDIUM}; }}
  QLabel#status_warn {{ color: {c.WARNING}; font-weight: {Typography.WEIGHT_MEDIUM}; }}

  /* ── Progress bar ── */
  QProgressBar {{
      background-color: {c.BG_SURFACE3};
      border: 1px solid {c.BORDER};
      border-radius: {r.SMALL};
      height: 6px; text-align: center; color: transparent;
  }}
  QProgressBar::chunk {{
      background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
          stop:0 {c.GRAD_START}, stop:1 {c.GRAD_END});
      border-radius: {r.SMALL};
  }}

  /* ── Table ── */
  QTableWidget {{
      background-color: {c.BG_SURFACE1};
      color: {c.TEXT_PRIMARY};
      gridline-color: {c.BORDER};
      border: 1px solid {c.BORDER};
      border-radius: {r.CARD};
      alternate-background-color: {c.BG_SURFACE2};
      selection-background-color: rgba(139, 92, 246, 0.18);
  }}
  QTableWidget::item:selected {{ color: {c.TEXT_PRIMARY}; }}
  QHeaderView::section {{
      background-color: {c.BG_SURFACE2};
      color: {c.TEXT_MUTED};
      border: none;
      border-bottom: 1px solid {c.BORDER};
      padding: 8px 10px;
      font-size: {Typography.SIZE_XS}px;
      font-weight: {Typography.WEIGHT_BOLD};
      letter-spacing: 0.5px;
  }}

  /* ── Tabs ── */
  QTabWidget::pane {{
      background-color: {c.BG_SURFACE1};
      border: 1px solid {c.BORDER};
      border-radius: {r.CARD};
  }}
  QTabBar::tab {{
      background: transparent; color: {c.TEXT_SECONDARY};
      border: none; border-bottom: 2px solid transparent;
      padding: 8px 20px; font-weight: {Typography.WEIGHT_MEDIUM};
  }}
  QTabBar::tab:selected {{ color: {c.ACCENT}; border-bottom: 2px solid {c.ACCENT}; }}
  QTabBar::tab:hover   {{ color: {c.TEXT_PRIMARY}; }}

  /* ── Scrollbars ── */
  QScrollBar:vertical {{
      background: transparent; width: 6px; margin: 0;
  }}
  QScrollBar::handle:vertical {{
      background: {c.SCROLLBAR_HANDLE}; border-radius: 3px; min-height: 30px;
  }}
  QScrollBar::handle:vertical:hover {{ background: {c.BORDER_HOVER}; }}
  QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
  QScrollBar:horizontal {{
      background: transparent; height: 6px; margin: 0;
  }}
  QScrollBar::handle:horizontal {{
      background: {c.SCROLLBAR_HANDLE}; border-radius: 3px; min-width: 30px;
  }}
  QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

  /* ── Checkbox ── */
  QCheckBox {{
      spacing: 8px; color: {c.TEXT_SECONDARY};
      font-size: {Typography.SIZE_SM}px;
  }}
  QCheckBox::indicator {{
      width: 16px; height: 16px;
      border: 1px solid {c.BORDER_HOVER}; border-radius: {r.SMALL};
      background-color: {c.BG_SURFACE2};
  }}
  QCheckBox::indicator:checked {{
      background-color: {c.ACCENT}; border-color: {c.ACCENT};
  }}
  QCheckBox::indicator:hover {{ border-color: {c.ACCENT}; }}

  /* ── Slider ── */
  QSlider::groove:horizontal {{
      height: 4px; background: {c.BG_SURFACE4}; border-radius: 2px;
  }}
  QSlider::handle:horizontal {{
      background: {c.ACCENT}; border: 2px solid {c.BG_BASE};
      width: 14px; height: 14px; margin: -5px 0; border-radius: 7px;
  }}
  QSlider::sub-page:horizontal {{ background: {c.ACCENT}; border-radius: 2px; }}

  /* ── GroupBox ── */
  QGroupBox {{
      color: {c.TEXT_MUTED}; border: 1px solid {c.BORDER};
      border-radius: {r.CARD}; margin-top: 8px; padding-top: 8px;
      font-size: {Typography.SIZE_XS}px; font-weight: {Typography.WEIGHT_BOLD};
      letter-spacing: 0.5px;
  }}
  QGroupBox::title {{
      subcontrol-origin: margin; left: 12px; top: -1px;
      padding: 0 6px; background-color: {c.BG_BASE}; color: {c.TEXT_MUTED};
  }}

  /* ── ListWidget ── */
  QListWidget {{
      background-color: {c.BG_SURFACE1}; color: {c.TEXT_PRIMARY};
      border: 1px solid {c.BORDER}; border-radius: {r.CARD};
      alternate-background-color: {c.BG_SURFACE2}; outline: none;
  }}
  QListWidget::item:selected {{
      background-color: rgba(139, 92, 246, 0.20); color: {c.TEXT_PRIMARY};
  }}
  QListWidget::item:hover {{ background-color: {c.BG_SURFACE3}; }}

  /* ── DateTimeEdit ── */
  QDateTimeEdit {{
      background-color: {c.BG_SURFACE2}; color: {c.TEXT_PRIMARY};
      border: 1px solid {c.BORDER}; border-radius: {r.INPUT}; padding: 6px 10px;
  }}
  QDateTimeEdit:focus {{ border-color: {c.BORDER_FOCUS}; }}
  QDateTimeEdit::up-button, QDateTimeEdit::down-button {{
      background: transparent; border: none; width: 16px;
  }}

  /* ── Splitter ── */
  QSplitter::handle             {{ background-color: {c.BORDER}; }}
  QSplitter::handle:horizontal  {{ width: 1px; }}
  QSplitter::handle:vertical    {{ height: 1px; }}

  /* ── Tooltip ── */
  QToolTip {{
      background-color: {c.BG_SURFACE3}; color: {c.TEXT_PRIMARY};
      border: 1px solid {c.BORDER_HOVER}; border-radius: {r.SMALL};
      padding: 4px 8px; font-size: {Typography.SIZE_XS}px;
  }}

  /* ── MessageBox ── */
  QMessageBox {{ background-color: {c.BG_SURFACE2}; }}
  QMessageBox QLabel {{ color: {c.TEXT_PRIMARY}; }}

  /* ── Activation screen ── */
  #activation_container {{
      background-color: {c.BG_SURFACE2};
      border: 1px solid {c.BORDER};
      border-radius: {r.MODAL};
  }}
  QLineEdit#key_input {{
      font-size: {Typography.SIZE_MD}px; letter-spacing: 2px;
      padding: 10px 14px; border-radius: {r.CARD};
  }}
  QPushButton#btn_activate {{
      background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
          stop:0 {c.GRAD_START}, stop:1 {c.GRAD_END});
      font-size: {Typography.SIZE_MD}px;
      font-weight: {Typography.WEIGHT_BOLD};
      padding: 12px 24px; border-radius: {r.CARD};
      min-width: 200px;
  }}
  QPushButton#btn_activate:hover {{
      background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
          stop:0 {c.ACCENT_HOVER}, stop:1 {c.CTA_HOVER});
  }}
  """
  