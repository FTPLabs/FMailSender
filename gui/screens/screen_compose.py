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
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    _HAS_WEBENGINE = True
except ImportError:
    QWebEngineView = None  # type: ignore
    _HAS_WEBENGINE = False
from PyQt6.QtCore import QUrl

from gui.theme import Colors, Spacing

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
        layout.setContentsMargins(Spacing.SM, 3, Spacing.SM, 3)
        layout.setSpacing(2)
        self.setObjectName("card")
        self.setFixedHeight(40)

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
            b.setFixedSize(26, 26)
            b.setToolTip(tooltip)
            b.clicked.connect(callback)
            if _has_icons and icon_key in _SVG_MAP:
                import gui.icons as _ic
                svg_str = getattr(_ic, _SVG_MAP[icon_key], None)
                if svg_str is None:
                    svg_str = getattr(_ic, "PALETTE", "")
                from PyQt6.QtCore import QSize as _QSize
                b.setIcon(make_icon(svg_str, 14))
                b.setIconSize(_QSize(14, 14))
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
        self.font_size.setFixedWidth(46)
        self.font_size.setFixedHeight(24)
        self.font_size.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.font_size.valueChanged.connect(self._font_size_changed)
        self.font_size.setToolTip("Размер шрифта (пт)")
        layout.addWidget(self.font_size)

        # ── Цвет текста ────────────────────────────────────────────────────
        layout.addWidget(fbtn("Aa", self._text_color, "Цвет текста", "btn_fmt_color", "color"))
        layout.addWidget(sep())

        # ── Выравнивание ─────────────────────────────────────────────────────
        layout.addWidget(fbtn("←", lambda: self._align(Qt.AlignmentFlag.AlignLeft), "По левому краю", icon_key="align_left"))
        layout.addWidget(fbtn("↔", lambda: self._align(Qt.AlignmentFlag.AlignCenter), "По центру", icon_key="align_center"))
        layout.addWidget(fbtn("→", lambda: self._align(Qt.AlignmentFlag.AlignRight), "По правому краю", icon_key="align_right"))
        layout.addWidget(sep())

        # ── Ссылка ──────────────────────────────────────────────────────────────
        layout.addWidget(fbtn("⊕", self._insert_link, "Вставить ссылку (URL)", icon_key="link"))
        layout.addWidget(sep())

        # ── Переменные ───────────────────────────────────────────────────────
        self._vars_combo = QComboBox()
        self._vars_combo.setFixedWidth(148)
        self._vars_combo.setFixedHeight(28)
        self._vars_combo.addItem("∴ Переменная...")
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
        """Открывает диалог выбора цвета с полной русификацией."""
        from PyQt6.QtWidgets import QLabel, QPushButton, QGroupBox
        dialog = QColorDialog(parent=self)
        dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        dialog.setWindowTitle("Выбрать цвет текста")
        _RU = {
            "Basic colors": "Основные цвета", "&Basic colors": "Основные цвета",
            "Custom colors": "Пользовательские", "&Custom colors": "Пользовательские",
            "Pick Screen Color": "Пипетка", "&Pick Screen Color": "Пипетка",
            "Add to Custom Colors": "Добавить", "&Add to Custom Colors": "Добавить",
            "Hue:": "Тон:", "Sat:": "Нас.:", "Val:": "Ярк.:",
            "Red:": "R:", "Green:": "G:", "Blue:": "B:",
            "HTML:": "HEX:", "Alpha channel:": "Прозрачность:",
            "OK": "ОК", "&OK": "ОК", "Cancel": "Отмена", "&Cancel": "Отмена",
        }
        def _ru(w):
            for lbl in w.findChildren(QLabel):
                lbl.setText(_RU.get(lbl.text(), lbl.text()))
            for btn in w.findChildren(QPushButton):
                btn.setText(_RU.get(btn.text(), btn.text()))
            for gb in w.findChildren(QGroupBox):
                gb.setTitle(_RU.get(gb.title(), gb.title()))
        _ru(dialog)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, lambda: _ru(dialog))
        if dialog.exec() == QColorDialog.DialogCode.Accepted:
            color = dialog.selectedColor()
            if color.isValid():
                fmt = QTextCharFormat()
                fmt.setForeground(color)
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
  

class SpamCheckWorker(QThread):
    """Воркер для асинхронной проверки спам-балла в отдельном потоке."""
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, subject: str, html: str, parent=None):
        super().__init__(parent)
        self.subject = subject
        self.html = html

    def run(self):
        try:
            from core.spam_checker import SpamChecker
            checker = SpamChecker()
            result = checker.check(self.subject, self.html)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


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

          self.use_template_btn = QPushButton("Использовать →")
          self.use_template_btn.setObjectName("btn_primary")
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
          self.editor_tabs.addTab(rich_tab, "✏️ Редактор")

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
          refresh_btn = QPushButton("↻  Обновить")
          refresh_btn.setObjectName("btn_secondary")
          refresh_btn.clicked.connect(self._update_preview)
          prev_header.addWidget(refresh_btn)
          preview_layout.addLayout(prev_header)

          if _HAS_WEBENGINE:
              self.preview = QWebEngineView()
          else:
              from PyQt6.QtWidgets import QTextBrowser
              self.preview = QTextBrowser()
              self.preview.setOpenExternalLinks(True)
          preview_layout.addWidget(self.preview, 1)
          self.editor_tabs.addTab(preview_container, "👁 Предпросмотр")

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

          self.spam_check_btn = QPushButton("Проверить спам-балл")
          self.spam_check_btn.clicked.connect(self._check_spam)
          bottom_row.addWidget(self.spam_check_btn)

          layout.addLayout(bottom_row)

  
    def _on_content_changed(self):
        """Запускает дебаунс-таймер для обновления превью."""
        self._preview_timer.start()

    def _on_html_changed(self):
        """Синхронизирует HTML-редактор с rich редактором."""
        html = self.html_editor.toPlainText()
        self._preview_timer.start()


    def _on_tab_changed(self, index: int):
        """Обновляет предпросмотр при переключении на вкладку предпросмотра."""
        if index == 2:
            self._update_preview()

    def _update_preview(self):
        """Обновляет HTML-превью."""
        html = self.html_editor.toPlainText()
        if not html.strip():
            html = self.rich_editor.toHtml()

        # Оборачиваем в базовый HTML если нет тегов html/body
        if "<html" not in html.lower():
            html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{ font-family: Arial, sans-serif; font-size: 14px; 
       line-height: 1.6; color: #333; margin: 20px; }}
a {{ color: #6366F1; }}
</style>
</head>
<body>{html}</body>
</html>"""

        if self.preview is not None:
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

    def _check_spam(self):
        """Run spam check in background thread to avoid UI freeze."""
        self.spam_check_btn.setEnabled(False)
        self.spam_check_btn.setText("⏳ Проверка...")
        subject = self.subject_input.text().strip()
        html = self.html_editor.toPlainText().strip() or self.rich_editor.toHtml()
        if not subject and not html:
            self.spam_check_btn.setEnabled(True)
            self.spam_check_btn.setText("Проверить спам-балл")
            QMessageBox.warning(self, "Предупреждение", "Заполните тему и тело письма перед проверкой.")
            return
        worker = SpamCheckWorker(subject, html, self)
        worker.finished.connect(self._on_spam_result)
        worker.error.connect(self._on_spam_error)
        worker.finished.connect(worker.deleteLater)
        worker.error.connect(worker.deleteLater)
        self._spam_worker = worker
        worker.start()

    def _on_spam_result(self, result):
        self.spam_check_btn.setEnabled(True)
        self.spam_check_btn.setText("Проверить спам-балл")
        self._show_spam_dialog_ai(result)

    def _show_spam_dialog_ai(self, result):
        score = getattr(result, 'score', 0)
        verdict = getattr(result, 'verdict', '\u2014')
        issues = getattr(result, 'issues', [])
        warnings = getattr(result, 'warnings', [])
        passed = getattr(result, 'passed', [])

        if score < 20:
            grade_color = "#22C55E"
        elif score < 50:
            grade_color = "#F59E0B"
        else:
            grade_color = "#EF4444"

        dlg = QDialog(self)
        dlg.setWindowTitle("\u0410\u043d\u0430\u043b\u0438\u0437 \u0441\u043f\u0430\u043c-\u0431\u0430\u043b\u043b\u0430")
        dlg.setMinimumWidth(520)
        dlg.setMinimumHeight(460)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        lay.setSpacing(Spacing.MD)

        score_lbl = QLabel(f"<span style='font-size:18px;font-weight:bold;color:{grade_color}'>\u0421\u043f\u0430\u043c-\u0431\u0430\u043b\u043b: {score}/100</span> &nbsp; {verdict}")
        score_lbl.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(score_lbl)

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(score)
        bar.setFixedHeight(10)
        bar.setStyleSheet(f"QProgressBar::chunk{{background:{grade_color};border-radius:4px;}}QProgressBar{{border-radius:4px;background:rgba(255,255,255,0.08);}}")
        lay.addWidget(bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(220)
        inner = QWidget()
        inner_lay = QVBoxLayout(inner)
        inner_lay.setSpacing(4)
        if issues:
            inner_lay.addWidget(QLabel("<b>\U0001f6ab \u041f\u0440\u043e\u0431\u043b\u0435\u043c\u044b:</b>"))
            for i in issues:
                l = QLabel(f"  \u2022 {i}")
                l.setWordWrap(True)
                l.setStyleSheet(f"color: {Colors.ERROR};")
                inner_lay.addWidget(l)
        if warnings:
            inner_lay.addWidget(QLabel("<b>\u26a0\ufe0f \u041f\u0440\u0435\u0434\u0443\u043f\u0440\u0435\u0436\u0434\u0435\u043d\u0438\u044f:</b>"))
            for w in warnings:
                l = QLabel(f"  \u2022 {w}")
                l.setWordWrap(True)
                l.setStyleSheet(f"color: {Colors.WARNING};")
                inner_lay.addWidget(l)
        if passed:
            inner_lay.addWidget(QLabel("<b>\u2705 \u041f\u0440\u043e\u0439\u0434\u0435\u043d\u043e:</b>"))
            for p in passed[:6]:
                l = QLabel(f"  \u2022 {p}")
                l.setWordWrap(True)
                inner_lay.addWidget(l)
        inner_lay.addStretch()
        scroll.setWidget(inner)
        lay.addWidget(scroll)

        btn_row = QHBoxLayout()
        ai_btn = QPushButton("\u2728 \u0418\u0441\u043f\u0440\u0430\u0432\u0438\u0442\u044c \u0441 \u0418\u0418")
        ai_btn.setObjectName("btn_primary")
        close_btn = QPushButton("\u0417\u0430\u043a\u0440\u044b\u0442\u044c")
        close_btn.setObjectName("btn_secondary")
        close_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(ai_btn)
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        def _run_ai_fix():
            from core.ai_fixer import AiSpamFixer
            from PyQt6.QtWidgets import QInputDialog
            fixer = AiSpamFixer()
            if not fixer.has_key:
                key, ok = QInputDialog.getText(
                    dlg, "OpenAI API Key",
                    "\u0412\u0432\u0435\u0434\u0438\u0442\u0435 OpenAI API \u043a\u043b\u044e\u0447 (sk-...):",
                    QLineEdit.EchoMode.Password,
                )
                if not ok or not key.strip():
                    return
                import os
                os.environ["OPENAI_API_KEY"] = key.strip()
                fixer = AiSpamFixer(api_key=key.strip())

            ai_btn.setEnabled(False)
            ai_btn.setText("\u2728 \u0418\u0441\u043f\u0440\u0430\u0432\u043b\u044f\u044e...")

            class _AiFixWorker(QThread):
                done = pyqtSignal(object)
                err = pyqtSignal(str)
                def __init__(self, fixer, subj, html, iss, warns):
                    super().__init__()
                    self._f = fixer; self._s = subj; self._h = html
                    self._i = iss; self._w = warns
                def run(self):
                    try:
                        self.done.emit(self._f.fix_email(self._s, self._h, self._i, self._w))
                    except Exception as e:
                        self.err.emit(str(e))

            worker = _AiFixWorker(
                fixer,
                self.subject_input.text(),
                self.html_editor.toPlainText() or self.rich_editor.toHtml(),
                issues, warnings,
            )
            def on_done(fix_result):
                ai_btn.setEnabled(True)
                ai_btn.setText("\u2728 \u0418\u0441\u043f\u0440\u0430\u0432\u0438\u0442\u044c \u0441 \u0418\u0418")
                reply = QMessageBox.question(
                    dlg,
                    "\u0418\u0418-\u0438\u0441\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u0435 \u0433\u043e\u0442\u043e\u0432\u043e",
                    f"\u0418\u0418 \u0438\u0441\u043f\u0440\u0430\u0432\u0438\u043b \u043f\u0438\u0441\u044c\u043c\u043e.\n\n{fix_result.explanation}\n\n\u041f\u0440\u0438\u043c\u0435\u043d\u0438\u0442\u044c?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self.subject_input.setText(fix_result.subject)
                    self.html_editor.setPlainText(fix_result.body_html)
                    dlg.accept()
            def on_err(msg):
                ai_btn.setEnabled(True)
                ai_btn.setText("\u2728 \u0418\u0441\u043f\u0440\u0430\u0432\u0438\u0442\u044c \u0441 \u0418\u0418")
                QMessageBox.warning(dlg, "\u041e\u0448\u0438\u0431\u043a\u0430 \u0418\u0418", msg)
            worker.done.connect(on_done)
            worker.err.connect(on_err)
            worker.done.connect(worker.deleteLater)
            worker.err.connect(worker.deleteLater)
            self._ai_fix_worker = worker
            worker.start()

        ai_btn.clicked.connect(_run_ai_fix)
        dlg.exec()
    def _on_spam_error(self, error: str):
        self.spam_check_btn.setEnabled(True)
        self.spam_check_btn.setText("Проверить спам-балл")
        QMessageBox.warning(self, "Ошибка проверки", f"Не удалось проверить:\n{error}")


    def _show_spam_dialog(self, result):
      """Показывает диалог результата проверки спам-балла."""
      from PyQt6.QtWidgets import (
          QDialog, QLabel, QVBoxLayout, QProgressBar,
          QHBoxLayout, QDialogButtonBox, QScrollArea, QWidget,
      )

      # FIX: grade_color не всегда присутствует в SpamCheckResult
      score = getattr(result, "score", 0)
      grade = getattr(result, "grade", "")
      if hasattr(result, "grade_color"):
          grade_color = result.grade_color
      elif score < 30:
          grade_color = "#22C55E"
      elif score < 60:
          grade_color = "#F59E0B"
      else:
          grade_color = "#EF4444"

      dialog = QDialog(self)
      dialog.setWindowTitle("Проверка спам-балла")
      dialog.setMinimumWidth(480)
      dialog.setMinimumHeight(400)
      layout = QVBoxLayout(dialog)
      layout.setSpacing(Spacing.LG)
      layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)

      # Общий балл
      score_label = QLabel(f"Спам-балл: {score}/100" + (f" — {grade}" if grade else ""))
      score_label.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {grade_color};")
      layout.addWidget(score_label)

      bar = QProgressBar()
      bar.setRange(0, 100)
      bar.setValue(score)
      bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {grade_color}; }}")
      layout.addWidget(bar)

      # Прокручиваемая область с деталями
      scroll = QScrollArea()
      scroll.setWidgetResizable(True)
      inner = QWidget()
      inner_layout = QVBoxLayout(inner)
      inner_layout.setSpacing(Spacing.SM)

      # Спам-слова из details (SpamCheckResult не имеет поля categories)
      details = getattr(result, "details", {})
      spam_words_found = details.get("spam_words_found", [])
      if spam_words_found:
          row = QHBoxLayout()
          row.addWidget(QLabel("Найдено спам-слов:"))
          row.addStretch()
          row.addWidget(QLabel(str(len(spam_words_found))))
          inner_layout.addLayout(row)

      # Проблемы
      if result.issues:
          issues_label = QLabel("Проблемы:")
          issues_label.setObjectName("label_subtitle")
          inner_layout.addWidget(issues_label)
          for issue in result.issues[:5]:
              lbl = QLabel(f"• {issue}")
              lbl.setStyleSheet(f"color: {Colors.ERROR};")
              lbl.setWordWrap(True)
              inner_layout.addWidget(lbl)

      # Рекомендации
      if result.warnings:
          sugg_label = QLabel("Рекомендации:")
          sugg_label.setObjectName("label_subtitle")
          inner_layout.addWidget(sugg_label)
          for s in result.warnings[:3]:
              lbl = QLabel(f"• {s}")
              lbl.setStyleSheet(f"color: {Colors.WARNING};")
              lbl.setWordWrap(True)
              inner_layout.addWidget(lbl)

      inner_layout.addStretch()
      scroll.setWidget(inner)
      layout.addWidget(scroll, 1)

      close_btn = QPushButton("Закрыть")
      close_btn.setObjectName("btn_primary")
      close_btn.clicked.connect(dialog.accept)
      layout.addWidget(close_btn)

      dialog.exec()

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
