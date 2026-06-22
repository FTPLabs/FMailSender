"""
Экран 3: Создание письма.
Rich-text редактор, HTML-редактор с подсветкой, live preview, A/B тесты, вложения.
"""
import os
import re
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit, QTabWidget, QSplitter, QFrame,
    QComboBox, QFileDialog, QListWidget, QListWidgetItem,
    QToolBar, QFontComboBox, QSpinBox, QAbstractSpinBox, QColorDialog, QDialog,
    QFormLayout, QDialogButtonBox, QMessageBox, QScrollArea, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize, QThread
from PyQt6.QtGui import (
    QTextCharFormat, QFont, QColor, QSyntaxHighlighter,
    QTextDocument, QKeySequence, QIcon, QAction, QTextCursor
)
import os as _os
import tempfile as _tempfile
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    _HAS_WEBENGINE = True
except ImportError:
    QWebEngineView = None  # type: ignore
    _HAS_WEBENGINE = False
from PyQt6.QtCore import QUrl

from gui.theme import Colors, Spacing
from gui import icons

TEMPLATES_DIR = Path("data/templates")

# ──────────────────────────────────────────────
# HTML Syntax Highlighter
# ──────────────────────────────────────────────

class HtmlHighlighter(QSyntaxHighlighter):
    """Подсветка синтаксиса HTML."""

    def __init__(self, document: QTextDocument):
        super().__init__(document)
        self._rules = []

        def _fmt(color: str, bold: bool = False) -> QTextCharFormat:
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            if bold:
                f.setFontWeight(QFont.Weight.Bold)
            return f

        # Теги
        tag_fmt = _fmt("#818CF8", bold=True)
        self._rules.append((re.compile(r"<[/!]?[a-zA-Z][a-zA-Z0-9]*"), tag_fmt))
        self._rules.append((re.compile(r">"), tag_fmt))

        # Атрибуты
        attr_fmt = _fmt("#34D399")
        self._rules.append((re.compile(r'\b[a-zA-Z-]+='), attr_fmt))

        # Строки в кавычках
        str_fmt = _fmt("#FCD34D")
        self._rules.append((re.compile(r'"[^"]*"'), str_fmt))
        self._rules.append((re.compile(r"'[^']*'"), str_fmt))

        # Комментарии
        comment_fmt = _fmt("#6B7280")
        self._rules.append((re.compile(r"<!--.*?-->", re.DOTALL), comment_fmt))

        # Переменные шаблона
        var_fmt = _fmt("#F97316", bold=True)
        self._rules.append((re.compile(r"\{\{[^}]+\}\}"), var_fmt))

    def highlightBlock(self, text: str):
        for pattern, fmt in self._rules:
            for m in pattern.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)


# ──────────────────────────────────────────────
# Панель форматирования
# ──────────────────────────────────────────────

class FormattingToolbar(QFrame):
    """Панель форматирования для rich-text редактора."""

    def __init__(self, editor: QTextEdit, parent=None):
        super().__init__(parent)
        self._editor = editor
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(Spacing.SM, 4, Spacing.SM, 4)
        layout.setSpacing(2)
        self.setObjectName("card")
        self.setFixedHeight(48)

        try:
            from gui.icons import make_icon, BOLD, ITALIC, UNDERLINE, ALIGN_LEFT, ALIGN_CENTER, ALIGN_RIGHT, LINK, PALETTE
            _has_icons = True
        except ImportError:
            _has_icons = False

        def fbtn(label: str, callback, tooltip: str = "", obj: str = "btn_fmt", icon_key: str = "") -> QPushButton:
            _SVG_MAP = {"bold": "BOLD", "italic": "ITALIC", "underline": "UNDERLINE",
                        "align_left": "ALIGN_LEFT", "align_center": "ALIGN_CENTER",
                        "align_right": "ALIGN_RIGHT", "link": "LINK", "color": "PALETTE"}
            b = QPushButton()
            b.setObjectName(obj)
            b.setFixedSize(30, 30)
            b.setToolTip(tooltip)
            b.clicked.connect(callback)
            if _has_icons and icon_key in _SVG_MAP:
                import gui.icons as _ic
                svg_str = getattr(_ic, _SVG_MAP[icon_key], None)
                if svg_str is None:
                    svg_str = getattr(_ic, "PALETTE", "")
                from PyQt6.QtCore import QSize as _QSize
                b.setIcon(make_icon(svg_str, 16))
                b.setIconSize(_QSize(16, 16))
            else:
                b.setText(label)
            return b

        def sep() -> QFrame:
            s = QFrame()
            s.setFrameShape(QFrame.Shape.VLine)
            s.setFixedWidth(1)
            s.setMaximumHeight(22)
            s.setStyleSheet(f"background: {Colors.BORDER}; margin: 0 2px;")
            return s

        # ── Форматирование текста ─────────────────────────────────────────
        layout.addWidget(fbtn("B", self._bold, "Жирный (Ctrl+B)", "btn_fmt_bold", "bold"))
        layout.addWidget(fbtn("I", self._italic, "Курсив (Ctrl+I)", "btn_fmt_italic", "italic"))
        layout.addWidget(fbtn("U", self._underline, "Подчёркнутый (Ctrl+U)", "btn_fmt_underline", "underline"))
        layout.addWidget(sep())

        # ── Размер шрифта ──────────────────────────────────────────────────
        self.font_size = QSpinBox()
        self.font_size.setRange(8, 72)
        self.font_size.setValue(14)
        self.font_size.setFixedWidth(58)
        self.font_size.setFixedHeight(28)
        self.font_size.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.font_size.valueChanged.connect(self._font_size_changed)
        self.font_size.setToolTip("Размер шрифта (пт)")
        layout.addWidget(self.font_size)

        # ── Цвет текста ────────────────────────────────────────────────────
        layout.addWidget(fbtn("Aa", self._text_color, "Цвет текста", "btn_fmt_color", "color"))
        layout.addWidget(sep())

        # ── Выравнивание ─────────────────────────────────────────────────────
        layout.addWidget(fbtn("", lambda: self._align(Qt.AlignmentFlag.AlignLeft), "По левому краю", icon_key="align_left"))
        layout.addWidget(fbtn("", lambda: self._align(Qt.AlignmentFlag.AlignCenter), "По центру", icon_key="align_center"))
        layout.addWidget(fbtn("", lambda: self._align(Qt.AlignmentFlag.AlignRight), "По правому краю", icon_key="align_right"))
        layout.addWidget(sep())

        # ── Ссылка ──────────────────────────────────────────────────────────────
        layout.addWidget(fbtn("", self._insert_link, "Вставить ссылку (URL)", icon_key="link"))
        layout.addWidget(sep())

        # ── Переменные ───────────────────────────────────────────────────────
        self._vars_combo = QComboBox()
        self._vars_combo.setFixedWidth(162)
        self._vars_combo.setFixedHeight(30)
        self._vars_combo.addItem("Переменная...")
        self._vars_combo.addItems([
            "{{first_name}}", "{{last_name}}", "{{company}}",
            "{{custom_1}}", "{{custom_2}}", "{{custom_3}}",
            "{{custom_4}}", "{{custom_5}}", "{{email}}"
        ])
        self._vars_combo.currentIndexChanged.connect(self._insert_variable)
        layout.addWidget(self._vars_combo)

        layout.addStretch()

    def _bold(self):
        fmt = QTextCharFormat()
        cursor = self._editor.textCursor()
        current_weight = cursor.charFormat().fontWeight()
        fmt.setFontWeight(
            QFont.Weight.Normal if current_weight == QFont.Weight.Bold else QFont.Weight.Bold
        )
        cursor.mergeCharFormat(fmt)

    def _italic(self):
        fmt = QTextCharFormat()
        cursor = self._editor.textCursor()
        fmt.setFontItalic(not cursor.charFormat().fontItalic())
        cursor.mergeCharFormat(fmt)

    def _underline(self):
        fmt = QTextCharFormat()
        cursor = self._editor.textCursor()
        fmt.setFontUnderline(not cursor.charFormat().fontUnderline())
        cursor.mergeCharFormat(fmt)

    def _font_size_changed(self, size: int):
        fmt = QTextCharFormat()
        fmt.setFontPointSize(float(size))
        self._editor.textCursor().mergeCharFormat(fmt)

    def _text_color(self):
        """Premium цветовой пикер — сетка 24 preset + custom кнопка."""
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton,
            QLabel, QFrame, QLineEdit
        )
        from PyQt6.QtGui import QColor
        from PyQt6.QtCore import Qt

        _PRESETS = [
            # Тёмные
            "#000000", "#1F2937", "#374151", "#6B7280",
            # Светлые / нейтральные
            "#FFFFFF", "#F9FAFB", "#E5E7EB", "#D1D5DB",
            # Красные / оранжевые
            "#EF4444", "#F97316", "#F59E0B", "#EAB308",
            # Зелёные
            "#22C55E", "#10B981", "#14B8A6", "#06B6D4",
            # Синие / фиолетовые
            "#3B82F6", "#6366F1", "#8B5CF6", "#A855F7",
            # Розовые / акценты
            "#EC4899", "#F43F5E", "#7C3AED", "#0EA5E9",
        ]

        dialog = QDialog(self._editor.window() if self._editor.window() else None)
        dialog.setWindowTitle("Цвет текста")
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        dialog.setFixedSize(276, 200)
        dialog.setStyleSheet(
            "QDialog { background: #0F0F22; border: 1px solid rgba(139,92,246,0.3); border-radius: 12px; }"
            "QPushButton#color_swatch { border-radius: 4px; border: 1px solid rgba(255,255,255,0.12); }"
            "QPushButton#color_swatch:hover { border: 2px solid rgba(139,92,246,0.9); }"
            "QLabel { color: #8888BB; font-size: 11px; background: transparent; }"
            "QLineEdit { background: rgba(255,255,255,0.06); border: 1px solid rgba(139,92,246,0.25);"
            "            border-radius: 6px; color: #E8E8FF; font-size: 12px; padding: 3px 8px; }"
            "QPushButton#btn_custom { background: rgba(139,92,246,0.15); color: #A78BFA;"
            "  border: 1px solid rgba(139,92,246,0.35); border-radius: 6px; font-size: 11px; }"
            "QPushButton#btn_custom:hover { background: rgba(139,92,246,0.28); }"
        )

        lay = QVBoxLayout(dialog)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        hdr = QLabel("Выберите цвет текста")
        hdr.setStyleSheet("color: #E8E8FF; font-size: 12px; font-weight: 600;")
        lay.addWidget(hdr)

        grid = QGridLayout()
        grid.setSpacing(5)
        _chosen_color = [None]

        def _pick(hex_color):
            _chosen_color[0] = QColor(hex_color)
            dialog.accept()

        for i, hex_c in enumerate(_PRESETS):
            btn = QPushButton()
            btn.setObjectName("color_swatch")
            btn.setFixedSize(26, 26)
            btn.setStyleSheet(
                f"QPushButton#color_swatch {{ background-color: {hex_c}; }}"
                f"QPushButton#color_swatch:hover {{ border: 2px solid rgba(255,255,255,0.9); }}"            )
            btn.setToolTip(hex_c)
            btn.clicked.connect(lambda _=False, c=hex_c: _pick(c))
            grid.addWidget(btn, i // 6, i % 6)

        lay.addLayout(grid)

        # HEX-ввод + custom picker
        hex_row = QHBoxLayout()
        hex_row.setSpacing(6)
        hex_input = QLineEdit()
        hex_input.setPlaceholderText("#RRGGBB")
        hex_input.setFixedHeight(28)
        hex_row.addWidget(hex_input)

        custom_btn = QPushButton("Своя")
        custom_btn.setObjectName("btn_custom")
        custom_btn.setFixedHeight(28)
        custom_btn.setIcon(icons.make_icon(icons.PALETTE, 16))
        custom_btn.setIconSize(QSize(16, 16))
        def _open_custom():
            std = QColorDialog.getColor(Qt.GlobalColor.white, dialog, "Цвет текста")
            if std.isValid():
                hex_input.setText(std.name())
                _chosen_color[0] = std
                dialog.accept()
        custom_btn.clicked.connect(_open_custom)
        hex_row.addWidget(custom_btn)
        lay.addLayout(hex_row)

        def _apply_hex():
            text = hex_input.text().strip()
            if not text.startswith("#"):
                text = "#" + text
            c = QColor(text)
            if c.isValid():
                _chosen_color[0] = c
                dialog.accept()
        hex_input.returnPressed.connect(_apply_hex)

        dialog.exec()

        if _chosen_color[0] and _chosen_color[0].isValid():
            fmt = QTextCharFormat()
            fmt.setForeground(_chosen_color[0])
            self._editor.textCursor().mergeCharFormat(fmt)
  
    def _align(self, alignment):
        self._editor.setAlignment(alignment)

    def _insert_link(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Вставить ссылку")
        layout = QFormLayout(dialog)
        url_input = QLineEdit()
        url_input.setPlaceholderText("https://example.com")
        text_input = QLineEdit()
        text_input.setPlaceholderText("Текст ссылки")
        layout.addRow("URL:", url_input)
        layout.addRow("Текст:", text_input)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            url = url_input.text().strip()
            text = text_input.text().strip() or url
            if url:
                cursor = self._editor.textCursor()
                cursor.insertHtml(f'<a href="{url}">{text}</a>')

    def _insert_variable(self, index: int):
        """Вставляет выбранную переменную и сбрасывает комбо на placeholder.
        Принимает index (currentIndexChanged), что позволяет вставить одну
        переменную несколько раз подряд.
        """
        if index <= 0:
            return
        text = self._vars_combo.itemText(index)
        if text.startswith("{{") and text.endswith("}}"):
            self._editor.textCursor().insertText(text)
            self._editor.setFocus()
        # Сбрасываем обратно на placeholder, не вызывая рекурсию
        self._vars_combo.blockSignals(True)
        self._vars_combo.setCurrentIndex(0)
        self._vars_combo.blockSignals(False)
  

class ComposeScreen(QWidget):
    """Экран создания письма."""

    template_ready = pyqtSignal(object)  # EmailTemplate

    def __init__(self, parent=None):
        super().__init__(parent)
        self._attachments: list[str] = []
        self._ab_variants: list[dict] = [{"subject": "", "body": ""}]
        self._current_variant = 0
        self._preview_timer = QTimer()
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(800)
        self._preview_timer.timeout.connect(self._update_preview)
        self._spam_worker = None  # Keep reference to prevent GC
        self._syncing = False      # защита от рекурсивных сигналов (crash-guard)
        self._accounts: list = []  # SMTP-аккаунты для автоматического теста доставки
        self._setup_ui()

    def _setup_ui(self):
          layout = QVBoxLayout(self)
          layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
          layout.setSpacing(Spacing.LG)

          # ── Заголовок ────────────────────────────
          header_row = QHBoxLayout()
          title = QLabel("Создание письма")
          title.setObjectName("section_header")
          header_row.addWidget(title)
          header_row.addStretch()

          save_btn = QPushButton("Сохранить шаблон")
          save_btn.setObjectName("btn_secondary")
          save_btn.clicked.connect(self._save_template)
          header_row.addWidget(save_btn)

          load_btn = QPushButton("Загрузить шаблон")
          load_btn.setObjectName("btn_secondary")
          load_btn.clicked.connect(self._load_template)
          header_row.addWidget(load_btn)

          self.use_template_btn = QPushButton("Использовать")
          self.use_template_btn.setObjectName("btn_primary")
          self.use_template_btn.setIcon(icons.make_icon(icons.ARROW_RIGHT, 16))
          self.use_template_btn.setIconSize(QSize(16, 16))
          self.use_template_btn.clicked.connect(self._emit_template)
          header_row.addWidget(self.use_template_btn)
          layout.addLayout(header_row)

          # ── Тема письма ──────────────────────────
          subject_card = QFrame()
          subject_card.setObjectName("card")
          subject_layout = QHBoxLayout(subject_card)
          subject_layout.setContentsMargins(Spacing.MD, Spacing.SM, Spacing.MD, Spacing.SM)

          subject_lbl = QLabel("Тема:")
          subject_lbl.setFixedWidth(50)
          subject_layout.addWidget(subject_lbl)

          self.subject_input = QLineEdit()
          self.subject_input.setPlaceholderText(
              "Тема письма — поддерживает {{first_name}}, {{last_name}}, {{company}}"
          )
          self.subject_input.textChanged.connect(self._on_content_changed)
          subject_layout.addWidget(self.subject_input)
          layout.addWidget(subject_card)

          # ── Редактор с вкладками ─────────────────
          self.editor_tabs = QTabWidget()

          # Вкладка 1: визуальный редактор
          rich_tab = QWidget()
          rich_layout = QVBoxLayout(rich_tab)
          rich_layout.setContentsMargins(0, Spacing.SM, 0, 0)
          rich_layout.setSpacing(Spacing.SM)

          self.rich_editor = QTextEdit()
          self.rich_editor.setPlaceholderText(
              "Введите текст письма...\n\n"
              "Персонализация: {{first_name}}, {{last_name}}, {{company}}, {{email}}"
          )
          self.rich_editor.textChanged.connect(self._on_content_changed)
          self.rich_editor.setMinimumHeight(300)

          self.formatting_toolbar = FormattingToolbar(self.rich_editor)
          rich_layout.addWidget(self.formatting_toolbar)
          rich_layout.addWidget(self.rich_editor, 1)
          self.editor_tabs.addTab(rich_tab, icons.make_icon(icons.EDIT), "Редактор")

          # Вкладка 2: HTML-код
          self.html_editor = QTextEdit()
          self.html_editor.setFont(QFont("Courier New", 12))
          self.html_editor.setPlaceholderText("<!-- HTML-код письма -->")
          self.html_highlighter = HtmlHighlighter(self.html_editor.document())
          self.html_editor.textChanged.connect(self._on_html_changed)
          self.editor_tabs.addTab(self.html_editor, "</> HTML")

          # Вкладка 3: предпросмотр
          preview_container = QWidget()
          preview_layout = QVBoxLayout(preview_container)
          preview_layout.setContentsMargins(0, Spacing.SM, 0, 0)
          preview_layout.setSpacing(Spacing.XS)

          prev_header = QHBoxLayout()
          prev_lbl = QLabel("Предпросмотр письма")
          prev_lbl.setObjectName("label_muted")
          prev_header.addWidget(prev_lbl)
          prev_header.addStretch()
          refresh_btn = QPushButton("Обновить")
          refresh_btn.setObjectName("btn_secondary")
          refresh_btn.setIcon(icons.make_icon(icons.REFRESH, 16))
          refresh_btn.setIconSize(QSize(16, 16))
          refresh_btn.clicked.connect(self._update_preview)
          prev_header.addWidget(refresh_btn)
          preview_layout.addLayout(prev_header)

          if _HAS_WEBENGINE:
              self.preview = QWebEngineView()
              try:
                  from PyQt6.QtWebEngineCore import QWebEngineSettings, QWebEngineProfile
                  # Применяем к профилю И к view — в ряде версий PyQt6-WebEngine
                  # настройки только на view игнорируются (особенно на Windows).
                  for _so in [
                      QWebEngineProfile.defaultProfile().settings(),
                      self.preview.settings(),
                  ]:
                      _so.setAttribute(
                          QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
                      _so.setAttribute(
                          QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
                      _so.setAttribute(
                          QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
              except Exception:
                  pass
              self._preview_tmp: str = ""
          else:
              from PyQt6.QtWidgets import QTextBrowser
              self.preview = QTextBrowser()
              self.preview.setOpenExternalLinks(True)
              self._preview_tmp = ""
          preview_layout.addWidget(self.preview, 1)
          self.editor_tabs.addTab(preview_container, icons.make_icon(icons.EYE), "Предпросмотр")

          self.editor_tabs.currentChanged.connect(self._on_tab_changed)
          layout.addWidget(self.editor_tabs, 1)

          # ── Нижняя панель ─────────────────────────
          bottom_row = QHBoxLayout()
          bottom_row.setSpacing(Spacing.SM)

          self.attach_btn = QPushButton("+ Вложение")
          self.attach_btn.setObjectName("btn_secondary")
          self.attach_btn.clicked.connect(self._add_attachment)
          bottom_row.addWidget(self.attach_btn)

          self.attach_label = QLabel("Вложений нет")
          self.attach_label.setObjectName("label_muted")
          bottom_row.addWidget(self.attach_label)

          bottom_row.addStretch()

          self.uniqueize_btn = QPushButton("Уникализировать")
          self.uniqueize_btn.setObjectName("btn_secondary")
          self.uniqueize_btn.setIcon(icons.make_icon(icons.ZAP, 16))
          self.uniqueize_btn.setToolTip("Уникализация для «Входящих»: spintax, безопасные отпечатки, ИИ-перефразировка")
          self.uniqueize_btn.clicked.connect(self._uniqueize)
          bottom_row.addWidget(self.uniqueize_btn)

          self.delivery_test_btn = QPushButton("Тест доставки")
          self.delivery_test_btn.setObjectName("btn_secondary")
          self.delivery_test_btn.setIcon(icons.make_icon(icons.SEARCH, 16))
          self.delivery_test_btn.setToolTip("Проверить: письмо попадёт во Входящие или Спам?")
          self.delivery_test_btn.clicked.connect(self._test_delivery)
          bottom_row.addWidget(self.delivery_test_btn)

          layout.addLayout(bottom_row)

  
    def _on_content_changed(self):
        """Запускает дебаунс-таймер для обновления превью."""
        self._preview_timer.start()

    def _on_html_changed(self):
        """Запускает таймер обновления превью; игнорирует программные setPlainText."""
        if self._syncing:
            return
        self._preview_timer.start()


    def _on_tab_changed(self, index: int):
        """Обновляет предпросмотр при переключении на вкладку предпросмотра."""
        if index == 2:
            self._update_preview()

    def _update_preview(self):
        """Обновляет HTML-превью так, чтобы он совпадал с браузером/почтовым клиентом."""
        html = self.html_editor.toPlainText()
        if not html.strip():
            html = self.rich_editor.toHtml()

        # Полный документ оставляем как есть (точный рендер). Фрагмент — оборачиваем
        # в минимальную корректную обёртку: сброс отступов, charset+viewport,
        # адаптивные картинки. Никакого лишнего body-margin, который «кривил» вид.
        low = html.lower()
        is_full_doc = ("<html" in low) or ("<!doctype" in low) or ("<body" in low)
        if not is_full_doc:
            html = (
                "<!DOCTYPE html>\n<html><head>"
                '<meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1">'
                "<style>"
                "html,body{margin:0;padding:0;background:#ffffff;}"
                "body{font-family:-apple-system,'Segoe UI',Roboto,Arial,sans-serif;"
                "font-size:14px;line-height:1.5;color:#1a1a1a;-webkit-font-smoothing:antialiased;}"
                "img{max-width:100%;height:auto;}"
                "a{color:#6366F1;}"
                "</style></head><body>" + html + "</body></html>"
            )

        if self.preview is not None:
            if _HAS_WEBENGINE and isinstance(self.preview, QWebEngineView):
                # Записываем HTML во временный файл и загружаем через file:// URL.
                # Это надёжнее, чем setHtml(): при загрузке через file://
                # LocalContentCanAccessRemoteUrls=True реально разрешает CDN-картинки.
                # При setHtml(data:, ...) origin="null" — Chromium часто блокирует remote
                # даже с установленным флагом, особенно на Windows.
                try:
                    if not self._preview_tmp:
                        _fd, self._preview_tmp = _tempfile.mkstemp(
                            suffix=".html", prefix="fmail_preview_"
                        )
                        _os.close(_fd)
                    with open(self._preview_tmp, "w", encoding="utf-8") as _f:
                        _f.write(html)
                    self.preview.load(QUrl.fromLocalFile(self._preview_tmp))
                except Exception:
                    # fallback на setHtml если не удалось записать temp-файл
                    self.preview.setHtml(html, QUrl("https://fmail.shop/"))
            else:
                # QTextBrowser: поддерживает только локальные ресурсы
                self.preview.setHtml(html)
    def _add_attachment(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Добавить вложение", "", "Все файлы (*.*)"
        )
        for path in paths:
            size_mb = os.path.getsize(path) / (1024 * 1024)
            if size_mb > 25:
                QMessageBox.warning(
                    self, "Файл слишком большой",
                    f"{Path(path).name} превышает лимит 25 МБ"
                )
                continue
            if path not in self._attachments:
                self._attachments.append(path)
        count = len(self._attachments)
        self.attach_label.setText(
            "Вложений нет" if count == 0 else
            f"Вложений: {count}"
        )

    def _add_ab_variant(self):
        if len(self._ab_variants) >= 5:
            QMessageBox.information(self, "Лимит", "Максимум 5 вариантов A/B теста")
            return
        self._ab_variants.append({"subject": "", "body": ""})
        letter = chr(ord('A') + len(self._ab_variants) - 1)
        # ab_tabs removed — A/B variant UI not yet implemented

    def _uniqueize(self):
        """Диалог выбора техник уникализации + применение."""
        from core.uniqueizer import ALL_TECHNIQUES, TECHNIQUE_LABELS, DEFAULT_TECHNIQUES, apply_all, ai_rephrase

        html = self.html_editor.toPlainText().strip()
        if not html:
            html = self.rich_editor.toHtml()
        if not html.strip():
            QMessageBox.warning(self, "Уникализация", "Сначала напишите письмо в редакторе.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Уникализация письма")
        dlg.setMinimumWidth(540)
        dlg.setMinimumHeight(580)
        # Явно применяем тему — QDialog на Windows не всегда наследует app stylesheet
        from PyQt6.QtWidgets import QApplication as _QAppRef
        _qapp = _QAppRef.instance()
        if _qapp:
            dlg.setStyleSheet(_qapp.styleSheet())
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        lay.setSpacing(Spacing.MD)

        title_lbl = QLabel("<b>Выберите техники уникализации</b>")
        title_lbl.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(title_lbl)

        info_lbl = QLabel(
            "Каждое письмо получит уникальный fingerprint — спам-фильтры не смогут\n"
            "определить, что отправляется одно и то же письмо всем получателям."
        )
        info_lbl.setObjectName("label_muted")
        info_lbl.setWordWrap(True)
        lay.addWidget(info_lbl)

        from PyQt6.QtWidgets import QCheckBox
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(260)
        inner = QWidget()
        inner_lay = QVBoxLayout(inner)
        inner_lay.setSpacing(4)

        checkboxes = {}
        for tech in ALL_TECHNIQUES:
            label = TECHNIQUE_LABELS.get(tech, tech)
            cb = QCheckBox(label)
            cb.setChecked(tech in DEFAULT_TECHNIQUES)
            checkboxes[tech] = cb
            inner_lay.addWidget(cb)

        sel_row = QHBoxLayout()
        sel_all = QPushButton("Выбрать все")
        sel_all.setObjectName("btn_secondary")
        sel_none = QPushButton("Снять все")
        sel_none.setObjectName("btn_secondary")
        sel_all.clicked.connect(lambda: [cb.setChecked(True) for cb in checkboxes.values()])
        sel_none.clicked.connect(lambda: [cb.setChecked(False) for cb in checkboxes.values()])
        sel_row.addWidget(sel_all)
        sel_row.addWidget(sel_none)
        sel_row.addStretch()
        inner_lay.addLayout(sel_row)
        inner_lay.addStretch()
        scroll.setWidget(inner)
        lay.addWidget(scroll)

        ai_frame = QFrame()
        ai_frame.setObjectName("card")
        ai_fl = QVBoxLayout(ai_frame)
        ai_fl.setContentsMargins(Spacing.MD, Spacing.SM, Spacing.MD, Spacing.SM)
        ai_fl.setSpacing(Spacing.XS)
        ai_fl.addWidget(QLabel("<b>ИИ-перефразировка текста</b>"))
        ai_note = QLabel(
            "Groq (бесплатно, быстрый): console.groq.com\n"
            "Together.ai ($25 на старте): api.together.ai\n"
            "OpenRouter (free models): openrouter.ai\n"
            "OpenAI gpt-4o-mini (платно, лучшее качество): platform.openai.com"
        )
        ai_note.setObjectName("label_muted")
        ai_note.setWordWrap(True)
        ai_fl.addWidget(ai_note)
        ai_row = QHBoxLayout()
        from PyQt6.QtWidgets import QComboBox as _QCB
        ai_prov = _QCB()
        ai_prov.addItems(["groq", "together", "openrouter", "openai"])
        ai_prov.setFixedWidth(120)
        ai_row.addWidget(QLabel("Провайдер:"))
        ai_row.addWidget(ai_prov)
        ai_key = QLineEdit()
        ai_key.setPlaceholderText("API ключ (gsk_... / sk-or-... / sk-...)")
        ai_key.setEchoMode(QLineEdit.EchoMode.Password)
        ai_row.addWidget(ai_key, 1)
        ai_fl.addLayout(ai_row)
        from PyQt6.QtWidgets import QCheckBox as _QCBx
        ai_cb = _QCBx("Применить AI-перефразировку")
        ai_cb.setChecked(False)
        ai_fl.addWidget(ai_cb)
        lay.addWidget(ai_frame)

        btn_row = QHBoxLayout()
        apply_btn = QPushButton("Применить")
        apply_btn.setObjectName("btn_primary")
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setObjectName("btn_secondary")
        cancel_btn.clicked.connect(dlg.reject)
        btn_row.addWidget(apply_btn)
        btn_row.addWidget(cancel_btn)
        lay.addLayout(btn_row)

        result_holder = [None]

        def _do_apply():
            selected = [t for t, cb in checkboxes.items() if cb.isChecked()]
            if not selected and not ai_cb.isChecked():
                QMessageBox.warning(dlg, "Уникализация", "Выберите хотя бы одну технику.")
                return
            apply_btn.setEnabled(False)
            apply_btn.setText("Применяю...")
            dlg.setEnabled(False)
            subject = self.subject_input.text()
            import threading

            def _worker():
                new_html, new_subj = apply_all(html, subject, selected or None)
                if ai_cb.isChecked():
                    key = ai_key.text().strip()
                    prov = ai_prov.currentText()
                    if key:
                        new_html, _ = ai_rephrase(new_html, key, prov)
                result_holder[0] = (new_html, new_subj)

            t = threading.Thread(target=_worker, daemon=True)
            t.start()

            def _poll():
                if t.is_alive():
                    QTimer.singleShot(300, _poll)
                else:
                    dlg.accept()
            QTimer.singleShot(300, _poll)

        apply_btn.clicked.connect(_do_apply)
        dlg.exec()

        if result_holder[0] is not None:
            new_html, new_subj = result_holder[0]
            self._syncing = True
            try:
                self.html_editor.setPlainText(new_html)
            finally:
                self._syncing = False
            if new_subj:
                self.subject_input.setText(new_subj)
            self.editor_tabs.setCurrentIndex(1)
            self._update_preview()
            cnt = len([t for t, cb in checkboxes.items() if cb.isChecked()])
            QMessageBox.information(
                self, "Готово",
                f"Применено техник: {cnt}\nКаждое письмо теперь уникально!"
            )

    def set_accounts(self, accounts: list) -> None:
        """Получает список SMTP-аккаунтов от AccountsScreen для автоотправки теста."""
        self._accounts = list(accounts)

    def _test_delivery(self):
        """Тест доставляемости через mail-tester.com — с автоматической отправкой."""
        from core.inbox_tester import generate_test_address, fetch_result, open_result_browser
        import threading

        test_email, result_url, uid = generate_test_address()

        dlg = QDialog(self)
        dlg.setWindowTitle("Тест доставки — inbox vs spam")
        dlg.setMinimumWidth(540)
        # Явно применяем тему
        from PyQt6.QtWidgets import QApplication as _QAppD
        _qappd = _QAppD.instance()
        if _qappd:
            dlg.setStyleSheet(_qappd.styleSheet())
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        lay.setSpacing(Spacing.MD)

        # ── Тестовый адрес ──────────────────────────────────
        addr_lbl = QLabel("<b>Тестовый адрес mail-tester.com:</b>")
        addr_lbl.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(addr_lbl)

        email_row = QHBoxLayout()
        email_input = QLineEdit(test_email)
        email_input.setReadOnly(True)
        email_input.setStyleSheet("font-weight:bold;font-size:13px;")
        email_row.addWidget(email_input, 1)
        copy_btn = QPushButton("Копировать")
        copy_btn.setObjectName("btn_secondary")
        copy_btn.setFixedWidth(90)
        def _copy():
            from PyQt6.QtWidgets import QApplication as _QA
            _QA.clipboard().setText(test_email)
            copy_btn.setIcon(icons.make_icon(icons.CHECK, 16))
            copy_btn.setIconSize(QSize(16, 16))
            copy_btn.setText("")
            def _reset_copy():
                copy_btn.setIcon(QIcon())
                copy_btn.setText("Копировать")
            QTimer.singleShot(1800, _reset_copy)
        copy_btn.clicked.connect(_copy)
        email_row.addWidget(copy_btn)
        lay.addLayout(email_row)

        # ── Реальный тест размещения (Входящие vs Спам) ─────
        from core.inbox_tester import run_delivery_test as _run_delivery
        real_frame = QFrame()
        real_frame.setObjectName("card")
        rfl = QVBoxLayout(real_frame)
        rfl.setContentsMargins(Spacing.MD, Spacing.SM, Spacing.MD, Spacing.SM)
        rfl.setSpacing(Spacing.XS)
        rhdr = QLabel("<b>Реальный тест: Входящие vs Спам</b>")
        rhdr.setTextFormat(Qt.TextFormat.RichText)
        rfl.addWidget(rhdr)
        rinfo = QLabel(
            "Отправляет помеченное письмо между вашими аккаунтами и определяет "
            "папку (Входящие/Спам) через IMAP по каждому получателю."
        )
        rinfo.setWordWrap(True)
        rinfo.setObjectName("label_muted")
        rfl.addWidget(rinfo)
        real_status = QLabel("")
        real_status.setWordWrap(True)
        real_status.setStyleSheet("font-size:12px;")
        real_results = QLabel("")
        real_results.setTextFormat(Qt.TextFormat.RichText)
        real_results.setWordWrap(True)

        _valid_accs = [a for a in self._accounts if a.is_active and getattr(a, "last_test_ok", False)]
        if len(_valid_accs) >= 2:
            from PyQt6.QtWidgets import QComboBox as _QCB3
            srow = QHBoxLayout()
            srow.addWidget(QLabel("Отправитель:"))
            sender_combo = _QCB3()
            for a in _valid_accs:
                sender_combo.addItem(getattr(a, "email", str(a)))
            srow.addWidget(sender_combo, 1)
            rfl.addLayout(srow)

            run_real_btn = QPushButton("Запустить реальный тест")
            run_real_btn.setObjectName("btn_primary")
            run_real_btn.setIcon(icons.make_icon(icons.ZAP, 16))
            run_real_btn.setIconSize(QSize(16, 16))
            rfl.addWidget(run_real_btn)
            rfl.addWidget(real_status)
            rfl.addWidget(real_results)

            def _run_real():
                si = sender_combo.currentIndex()
                sender = _valid_accs[si]
                seeds = [a for i, a in enumerate(_valid_accs) if i != si]
                subj = self.subject_input.text() or "Тест доставки"
                html_body = self.html_editor.toPlainText().strip() or self.rich_editor.toHtml()
                run_real_btn.setEnabled(False)
                run_real_btn.setText("Идёт тест…")
                real_results.setText("")
                real_status.setText(
                    "Отправка и опрос IMAP… это может занять до 2 минут."
                )
                res_ref: list = [None]

                def _real_worker():
                    try:
                        res_ref[0] = _run_delivery(
                            sender, seeds, subj, html_body, timeout=120
                        )
                    except Exception as exc:
                        res_ref[0] = {"error": str(exc)}

                tt = threading.Thread(target=_real_worker, daemon=True)
                tt.start()

                _labels = {
                    "inbox": "<span style='color:#10B981'>Входящие</span>",
                    "spam": "<span style='color:#EF4444'>Спам</span>",
                    "not_found": "<span style='color:#F59E0B'>Не найдено</span>",
                    "pending": "…",
                }

                def _poll_real():
                    if tt.is_alive():
                        QTimer.singleShot(500, _poll_real)
                        return
                    run_real_btn.setEnabled(True)
                    run_real_btn.setText("Запустить снова")
                    data = res_ref[0] or {}
                    if data.get("error"):
                        real_status.setText(
                            f"<span style='color:#EF4444'>Ошибка:</span> {data['error']}"
                        )
                        return
                    rows = []
                    for addr, info in (data.get("results") or {}).items():
                        pl = info.get("placement", "")
                        if not info.get("sent"):
                            cell = (
                                "<span style='color:#EF4444'>Не отправлено</span>"
                                + (f" ({info.get('send_error','')})" if info.get("send_error") else "")
                            )
                        elif isinstance(pl, str) and pl.startswith("error:"):
                            cell = f"<span style='color:#EF4444'>Ошибка IMAP</span> ({pl[6:]})"
                        else:
                            cell = _labels.get(pl, pl)
                        rows.append(f"<code>{addr}</code> — {cell}")
                    real_status.setText("Готово.")
                    real_results.setText("<br>".join(rows) or "Нет seed-аккаунтов.")

                QTimer.singleShot(500, _poll_real)

            run_real_btn.clicked.connect(_run_real)
        else:
            need_lbl = QLabel(
                "Для реального теста нужно ≥2 аккаунта (отправитель + получатель-seed). "
                "Ниже — оценка балла через mail-tester.com."
            )
            need_lbl.setWordWrap(True)
            need_lbl.setObjectName("label_muted")
            rfl.addWidget(need_lbl)
        lay.addWidget(real_frame)

        # ── Автоотправка (только валидные/активные аккаунты) ─
        _send_accs = [a for a in self._accounts if a.is_active and getattr(a, "last_test_ok", False)]
        if not _send_accs and self._accounts:
            # Аккаунты есть, но не проверены — разрешаем использовать все активные
            _send_accs = [a for a in self._accounts if a.is_active]
        if _send_accs:
            acc = _send_accs[0]
            host = getattr(acc, "smtp_host", getattr(acc, "host", "?"))
            login = getattr(acc, "username", getattr(acc, "email", "?"))
            auto_frame = QFrame()
            auto_frame.setObjectName("card")
            auto_fl = QVBoxLayout(auto_frame)
            auto_fl.setContentsMargins(Spacing.MD, Spacing.SM, Spacing.MD, Spacing.SM)
            auto_fl.setSpacing(Spacing.XS)
            auto_hdr = QLabel(f"<b>Автоматическая отправка</b> через <code>{host}</code> ({login})")
            auto_hdr.setTextFormat(Qt.TextFormat.RichText)
            auto_fl.addWidget(auto_hdr)

            # Выбор аккаунта если их несколько
            acc_combo = None
            if len(_send_accs) > 1:
                from PyQt6.QtWidgets import QComboBox as _QCB2
                acc_row = QHBoxLayout()
                acc_row.addWidget(QLabel("Аккаунт:"))
                acc_combo = _QCB2()
                for a in _send_accs:
                    lbl = getattr(a, "username", getattr(a, "email", str(a)))
                    acc_combo.addItem(lbl)
                acc_row.addWidget(acc_combo, 1)
                auto_fl.addLayout(acc_row)

            send_btn = QPushButton("Отправить тест автоматически")
            send_btn.setObjectName("btn_primary")
            send_btn.setIcon(icons.make_icon(icons.ZAP, 16))
            send_btn.setIconSize(QSize(16, 16))
            auto_fl.addWidget(send_btn)
            lay.addWidget(auto_frame)

            def _auto_send():
                idx = acc_combo.currentIndex() if acc_combo else 0
                sel = _send_accs[idx]
                s_host = getattr(sel, "smtp_host", getattr(sel, "host", ""))
                s_port = int(getattr(sel, "smtp_port", getattr(sel, "port", 587)))
                s_user = getattr(sel, "username", getattr(sel, "email", ""))
                s_pass = getattr(sel, "password", "")
                s_tls  = getattr(sel, "use_tls", getattr(sel, "tls", True))
                s_from = getattr(sel, "from_email", s_user)

                send_btn.setEnabled(False)
                send_btn.setText("Отправляю...")
                status_lbl.setText("Соединение с SMTP-сервером...")
                send_result: list = [None]

                def _send_worker():
                    try:
                        import smtplib, ssl as _ssl, socket as _socket, struct as _struct
                        from email.mime.multipart import MIMEMultipart
                        from email.mime.text import MIMEText as _MIMEText
                        msg = MIMEMultipart("alternative")
                        msg["Subject"] = self.subject_input.text() or "Тест доставки"
                        msg["From"] = s_from
                        msg["To"] = test_email
                        html_body = self.html_editor.toPlainText().strip() or self.rich_editor.toHtml()
                        msg.attach(_MIMEText(html_body, "html", "utf-8"))
                        ctx = _ssl.create_default_context()
                        # ── Прокси (SOCKS5) — если задан на аккаунте ─────────────
                        proxy_url = (getattr(sel, "proxy", "") or "").strip()
                        if proxy_url:
                            import urllib.parse as _up
                            if "://" not in proxy_url:
                                proxy_url = "socks5://" + proxy_url
                            pp = _up.urlparse(proxy_url)
                            ph, pp_port = pp.hostname or "", pp.port or 1080
                            pu, ppw = pp.username or "", pp.password or ""

                            def _socks5_raw(conn_host, conn_port):
                                sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
                                sock.settimeout(20)
                                sock.connect((ph, pp_port))
                                if pu:
                                    sock.sendall(b"\x05\x02\x00\x02")
                                else:
                                    sock.sendall(b"\x05\x01\x00")
                                r = sock.recv(2)
                                if len(r) < 2 or r[0] != 5:
                                    raise Exception("Не SOCKS5 сервер")
                                if r[1] == 0xFF:
                                    raise Exception("SOCKS5 не принял метод аутентификации")
                                if r[1] == 2:
                                    un, pw = pu.encode(), ppw.encode()
                                    sock.sendall(b"\x01" + bytes([len(un)]) + un + bytes([len(pw)]) + pw)
                                    a = sock.recv(2)
                                    if len(a) < 2 or a[1] != 0:
                                        raise Exception("SOCKS5: неверный логин/пароль")
                                tb = conn_host.encode()
                                sock.sendall(b"\x05\x01\x00\x03" + bytes([len(tb)]) + tb + _struct.pack(">H", conn_port))
                                hdr = sock.recv(10)
                                if len(hdr) < 2 or hdr[1] != 0:
                                    raise Exception(f"SOCKS5 CONNECT отклонён: код {hdr[1] if len(hdr)>1 else '?'}")
                                return sock

                            if s_port == 465:
                                raw_sock = _socks5_raw(s_host, s_port)
                                ssl_sock = ctx.wrap_socket(raw_sock, server_hostname=s_host)
                                srv = smtplib.SMTP(s_host, s_port)
                                srv.sock = ssl_sock
                                srv._tls_established = True
                            else:
                                raw_sock = _socks5_raw(s_host, s_port)
                                srv = smtplib.SMTP(s_host, s_port)
                                srv.sock = raw_sock
                                srv._tls_established = False
                                if s_tls:
                                    srv.starttls(context=ctx)
                            srv.login(s_user, s_pass)
                            srv.sendmail(s_from, [test_email], msg.as_string())
                            try:
                                srv.quit()
                            except Exception:
                                pass
                        elif s_port == 465:
                            with smtplib.SMTP_SSL(s_host, s_port, context=ctx, timeout=20) as srv:
                                srv.login(s_user, s_pass)
                                srv.sendmail(s_from, [test_email], msg.as_string())
                        else:
                            with smtplib.SMTP(s_host, s_port, timeout=20) as srv:
                                if s_tls:
                                    srv.starttls(context=ctx)
                                srv.login(s_user, s_pass)
                                srv.sendmail(s_from, [test_email], msg.as_string())
                        send_result[0] = True
                    except Exception as exc:
                        send_result[0] = str(exc)

                t = threading.Thread(target=_send_worker, daemon=True)
                t.start()

                def _poll_send():
                    if t.is_alive():
                        QTimer.singleShot(300, _poll_send)
                    else:
                        send_btn.setEnabled(True)
                        send_btn.setText("Отправить тест автоматически")
                        if send_result[0] is True:
                            status_lbl.setText(
                                "<span style=\"color:#10B981\">Письмо отправлено!</span> "
                                "Подождите 30–60 сек и нажмите «Проверить»."
                            )
                            check_btn.setEnabled(True)
                        else:
                            status_lbl.setText(f"<span style=\"color:#EF4444\">Ошибка отправки:</span> {send_result[0]}")

                QTimer.singleShot(300, _poll_send)

            send_btn.clicked.connect(_auto_send)
        else:
            # Нет аккаунтов — ручная инструкция
            hint = QLabel(
                "Добавьте SMTP-аккаунт во вкладке <b>Аккаунты</b> для автоматической отправки.<br>"
                "Пока можно скопировать адрес и отправить письмо вручную."
            )
            hint.setTextFormat(Qt.TextFormat.RichText)
            hint.setWordWrap(True)
            hint.setObjectName("label_muted")
            lay.addWidget(hint)

        # ── Статус и прогресс ────────────────────────────────
        status_lbl = QLabel("Ожидание отправки...")
        status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_lbl.setWordWrap(True)
        status_lbl.setStyleSheet("font-size:13px;padding:10px;")
        lay.addWidget(status_lbl)

        bar = QProgressBar()
        bar.setRange(0, 10)
        bar.setValue(0)
        bar.setFixedHeight(10)
        bar.setVisible(False)
        lay.addWidget(bar)

        # ── Кнопки ──────────────────────────────────────────
        btn_row = QHBoxLayout()
        check_btn = QPushButton("Проверить результат")
        check_btn.setObjectName("btn_primary")
        check_btn.setIcon(icons.make_icon(icons.SEARCH, 16))
        check_btn.setIconSize(QSize(16, 16))
        check_btn.setEnabled(not bool(self._accounts))  # если нет аккаунтов — доступна сразу
        browser_btn = QPushButton("Открыть в браузере")
        browser_btn.setObjectName("btn_secondary")
        close_btn = QPushButton("Закрыть")
        close_btn.setObjectName("btn_secondary")
        close_btn.clicked.connect(dlg.accept)
        browser_btn.clicked.connect(lambda: open_result_browser(uid))
        btn_row.addWidget(check_btn)
        btn_row.addWidget(browser_btn)
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        def _check():
            check_btn.setEnabled(False)
            check_btn.setText("Проверяю...")
            status_lbl.setText("Запрашиваем результат mail-tester.com...")
            result_ref: list = [None]

            def _fetch_worker():
                result_ref[0] = fetch_result(uid, timeout=25)

            t2 = threading.Thread(target=_fetch_worker, daemon=True)
            t2.start()

            def _poll():
                if t2.is_alive():
                    QTimer.singleShot(500, _poll)
                else:
                    r = result_ref[0] or {}
                    check_btn.setEnabled(True)
                    check_btn.setText("Проверить снова")
                    if r.get("error"):
                        status_lbl.setText(f"<span style=\"color:#EF4444\">Ошибка:</span> {r['error']}")
                        bar.setVisible(False)
                    else:
                        status_lbl.setText(r.get("inbox_status", "Нет данных"))
                        score = r.get("score")
                        if score is not None:
                            bar.setValue(int(round(score)))
                            bar.setVisible(True)
                        else:
                            bar.setVisible(False)
            QTimer.singleShot(500, _poll)

        check_btn.clicked.connect(_check)
        dlg.exec()

    def _emit_template(self):
      from core.sender import EmailTemplate
      subject = self.subject_input.text().strip()
      if not subject:
          QMessageBox.warning(self, "Нет темы", "Введите тему письма")
          return

      body_html = self.html_editor.toPlainText().strip()
      if not body_html:
          body_html = self.rich_editor.toHtml()

      template = EmailTemplate(
          subject=subject,
          body_html=body_html,
          attachments=list(self._attachments),
      )
      self.template_ready.emit(template)

    def _save_template(self):
          """Сохраняет шаблон — имя через QInputDialog."""
          TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
          from PyQt6.QtWidgets import QInputDialog
          default = self.subject_input.text()[:40].strip().replace("/", "_") or "шаблон"
          name, ok = QInputDialog.getText(self, "Сохранить шаблон", "Имя шаблона:", text=default)
          if not ok or not name.strip():
              return
          import json as _json
          path = TEMPLATES_DIR / f"{name.strip()}.json"
          with open(path, "w", encoding="utf-8") as f:
              _json.dump({
                  "subject": self.subject_input.text(),
                  "body_html": self.html_editor.toPlainText() or self.rich_editor.toHtml(),
              }, f, ensure_ascii=False, indent=2)
  
    def _load_template(self):
          """Загружает шаблон (JSON/HTML) без лишних диалогов подтверждения."""
          TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
          path, _ = QFileDialog.getOpenFileName(
              self, "Загрузить шаблон", str(TEMPLATES_DIR),
              "JSON шаблоны (*.json);;HTML файлы (*.html *.htm);;Все файлы (*)"
          )
          if not path:
              return
          import json as _json
          try:
              if path.lower().endswith((".html", ".htm")):
                  self.html_editor.setPlainText(
                      Path(path).read_text(encoding="utf-8", errors="replace")
                  )
              else:
                  with open(path, "r", encoding="utf-8") as f:
                      data = _json.load(f)
                  self.subject_input.setText(data.get("subject", ""))
                  self.html_editor.setPlainText(data.get("body_html", ""))
              self._update_preview()
          except Exception as e:
              QMessageBox.warning(self, "Ошибка загрузки", str(e))
  
    def _ask_template_name(self):
      from PyQt6.QtWidgets import QInputDialog
      return QInputDialog.getText(self, "Название шаблона", "Введите имя шаблона:")

    def get_template(self):
        from core.sender import EmailTemplate
        return EmailTemplate(
            subject=self.subject_input.text(),
            body_html=self.html_editor.toPlainText() or self.rich_editor.toHtml(),
            attachments=list(self._attachments),
        )
