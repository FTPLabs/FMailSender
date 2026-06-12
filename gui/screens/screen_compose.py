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
    QToolBar, QFontComboBox, QSpinBox, QColorDialog, QDialog,
    QFormLayout, QDialogButtonBox, QMessageBox, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
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
        layout.setContentsMargins(Spacing.SM, Spacing.SM, Spacing.SM, Spacing.SM)
        layout.setSpacing(4)
        self.setObjectName("card")

        def btn(label: str, callback, tooltip: str = "") -> QPushButton:
            b = QPushButton(label)
            b.setObjectName("btn_icon")
            b.setFixedSize(32, 32)
            b.setToolTip(tooltip)
            b.clicked.connect(callback)
            return b

        # Жирный
        layout.addWidget(btn("B", self._bold, "Жирный (Ctrl+B)"))
        # Курсив
        layout.addWidget(btn("I", self._italic, "Курсив (Ctrl+I)"))
        # Подчёркнутый
        layout.addWidget(btn("U", self._underline, "Подчёркнутый (Ctrl+U)"))

        # Разделитель
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setFixedWidth(1)
        sep1.setStyleSheet(f"background: {Colors.BORDER};")
        layout.addWidget(sep1)

        # Размер шрифта
        self.font_size = QSpinBox()
        self.font_size.setRange(8, 72)
        self.font_size.setValue(14)
        self.font_size.setFixedWidth(60)
        self.font_size.valueChanged.connect(self._font_size_changed)
        layout.addWidget(self.font_size)

        # Цвет текста
        layout.addWidget(btn("A", self._text_color, "Цвет текста"))

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setFixedWidth(1)
        sep2.setStyleSheet(f"background: {Colors.BORDER};")
        layout.addWidget(sep2)

        # Выравнивание
        layout.addWidget(btn("≡L", lambda: self._align(Qt.AlignmentFlag.AlignLeft), "По левому краю"))
        layout.addWidget(btn("≡C", lambda: self._align(Qt.AlignmentFlag.AlignCenter), "По центру"))
        layout.addWidget(btn("≡R", lambda: self._align(Qt.AlignmentFlag.AlignRight), "По правому краю"))

        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.VLine)
        sep3.setFixedWidth(1)
        sep3.setStyleSheet(f"background: {Colors.BORDER};")
        layout.addWidget(sep3)

        # Ссылка
        layout.addWidget(btn("🔗", self._insert_link, "Вставить ссылку"))

        # Переменные
        vars_combo = QComboBox()
        vars_combo.setFixedWidth(160)
        vars_combo.addItem("Вставить переменную...")
        vars_combo.addItems([
            "{{first_name}}", "{{last_name}}", "{{company}}",
            "{{custom_1}}", "{{custom_2}}", "{{custom_3}}",
            "{{custom_4}}", "{{custom_5}}", "{{email}}"
        ])
        vars_combo.currentTextChanged.connect(self._insert_variable)
        layout.addWidget(vars_combo)

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
        color = QColorDialog.getColor(parent=self)
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

    def _insert_variable(self, text: str):
        if text.startswith("{{"):
            self._editor.textCursor().insertText(text)


# ──────────────────────────────────────────────
# Основной экран
# ──────────────────────────────────────────────

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

        save_template_btn = QPushButton("Сохранить шаблон")
        save_template_btn.clicked.connect(self._save_template)
        header_row.addWidget(save_template_btn)

        load_template_btn = QPushButton("Загрузить шаблон")
        load_template_btn.clicked.connect(self._load_template)
        header_row.addWidget(load_template_btn)

        layout.addLayout(header_row)

        # ── A/B тестирование ─────────────────────
        ab_row = QHBoxLayout()
        ab_label = QLabel("Варианты (A/B тест):")
        ab_label.setObjectName("label_muted")
        ab_row.addWidget(ab_label)

        self.ab_tabs = QTabWidget()
        self.ab_tabs.setMaximumHeight(30)
        self.ab_tabs.addTab(QWidget(), "Вариант A")
        ab_row.addWidget(self.ab_tabs, 1)

        add_variant_btn = QPushButton("+ Вариант")
        add_variant_btn.clicked.connect(self._add_ab_variant)
        ab_row.addWidget(add_variant_btn)

        layout.addLayout(ab_row)

        # ── Тема письма ──────────────────────────
        subject_row = QHBoxLayout()
        subject_label = QLabel("Тема:")
        subject_label.setFixedWidth(80)
        subject_row.addWidget(subject_label)

        self.subject_input = QLineEdit()
        self.subject_input.setPlaceholderText("Тема письма — поддерживает {{first_name}}")
        self.subject_input.textChanged.connect(self._on_content_changed)
        subject_row.addWidget(self.subject_input)

        layout.addLayout(subject_row)

        # ── Разделитель: редактор / превью ───────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Левая часть — редактор
        editor_widget = QWidget()
        editor_layout = QVBoxLayout(editor_widget)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(Spacing.SM)

        # Вкладки редакторов
        editor_tabs = QTabWidget()

        # Rich text редактор
        rich_tab = QWidget()
        rich_layout = QVBoxLayout(rich_tab)
        rich_layout.setContentsMargins(0, 0, 0, 0)
        rich_layout.setSpacing(4)

        self.rich_editor = QTextEdit()
        self.rich_editor.setPlaceholderText(
            "Введите текст письма...\n\nИспользуйте переменные: {{first_name}}, {{company}} и т.д."
        )
        self.rich_editor.textChanged.connect(self._on_content_changed)

        self.formatting_toolbar = FormattingToolbar(self.rich_editor)
        rich_layout.addWidget(self.formatting_toolbar)
        rich_layout.addWidget(self.rich_editor)
        editor_tabs.addTab(rich_tab, "Визуальный редактор")

        # HTML редактор
        self.html_editor = QTextEdit()
        self.html_editor.setFont(QFont("Courier New", 12))
        self.html_editor.setPlaceholderText("<!-- HTML-код письма -->")
        self.html_highlighter = HtmlHighlighter(self.html_editor.document())
        self.html_editor.textChanged.connect(self._on_html_changed)
        editor_tabs.addTab(self.html_editor, "HTML")

        editor_layout.addWidget(editor_tabs)

        # Вложения
        attachments_card = QFrame()
        attachments_card.setObjectName("card")
        att_layout = QVBoxLayout(attachments_card)
        att_layout.setSpacing(Spacing.SM)

        att_header = QHBoxLayout()
        att_title = QLabel("Вложения")
        att_title.setObjectName("label_muted")
        att_header.addWidget(att_title)
        att_header.addStretch()

        add_att_btn = QPushButton("+ Добавить файл")
        add_att_btn.clicked.connect(self._add_attachment)
        att_header.addWidget(add_att_btn)
        att_layout.addLayout(att_header)

        self.attachments_list = QListWidget()
        self.attachments_list.setMaximumHeight(80)
        att_layout.addWidget(self.attachments_list)

        editor_layout.addWidget(attachments_card)
        splitter.addWidget(editor_widget)

        # Правая часть — превью
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(Spacing.SM)

        preview_header = QHBoxLayout()
        preview_title = QLabel("Предпросмотр")
        preview_title.setObjectName("label_muted")
        preview_header.addWidget(preview_title)
        preview_header.addStretch()

        refresh_btn = QPushButton("↻")
        refresh_btn.setObjectName("btn_icon")
        refresh_btn.setFixedSize(28, 28)
        refresh_btn.clicked.connect(self._update_preview)
        preview_header.addWidget(refresh_btn)
        preview_layout.addLayout(preview_header)

        if _HAS_WEBENGINE:
            self.preview = QWebEngineView()
        else:
            from PyQt6.QtWidgets import QTextBrowser
            self.preview = QTextBrowser()
            self.preview.setOpenExternalLinks(True)
        self.preview.setMinimumWidth(360)
        preview_layout.addWidget(self.preview)

        splitter.addWidget(preview_widget)
        splitter.setSizes([600, 400])
        layout.addWidget(splitter, 1)

        # ── Кнопка готовности ────────────────────
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()

        self.spam_check_btn = QPushButton("Проверить спам-балл")
        self.spam_check_btn.clicked.connect(self._check_spam)
        bottom_row.addWidget(self.spam_check_btn)

        self.use_template_btn = QPushButton("Использовать шаблон →")
        self.use_template_btn.setObjectName("btn_primary")
        self.use_template_btn.clicked.connect(self._emit_template)
        bottom_row.addWidget(self.use_template_btn)

        layout.addLayout(bottom_row)

    def _on_content_changed(self):
        """Запускает дебаунс-таймер для обновления превью."""
        self._preview_timer.start()

    def _on_html_changed(self):
        """Синхронизирует HTML-редактор с rich редактором."""
        html = self.html_editor.toPlainText()
        self._preview_timer.start()

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
                QMessageBox.warning(self, "Файл слишком большой",
                                    f"{Path(path).name} превышает лимит 25MB")
                continue
            if path not in self._attachments:
                self._attachments.append(path)
                item = QListWidgetItem(f"{Path(path).name} ({size_mb:.1f}MB)")
                self.attachments_list.addItem(item)

    def _add_ab_variant(self):
        if len(self._ab_variants) >= 5:
            QMessageBox.information(self, "Лимит", "Максимум 5 вариантов A/B теста")
            return
        self._ab_variants.append({"subject": "", "body": ""})
        letter = chr(ord('A') + len(self._ab_variants) - 1)
        self.ab_tabs.addTab(QWidget(), f"Вариант {letter}")

    def _check_spam(self):
        """Проверяет спам-балл. FIX: запуск в QThread во избежание зависания UI."""
        from core.spam_checker import SpamChecker
        from PyQt6.QtWidgets import (
            QDialog, QLabel, QVBoxLayout, QProgressBar,
            QHBoxLayout, QDialogButtonBox, QScrollArea, QWidget,
        )
        from PyQt6.QtCore import QThread, pyqtSignal

        subject = self.subject_input.text().strip()
        body_html = self.html_editor.toPlainText() or self.rich_editor.toHtml()

        if not subject and not body_html.strip():
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Нет данных", "Введите тему и текст письма перед проверкой")
            return

        # Run spam check in background thread to avoid UI freeze
        class _Worker(QThread):
            done = pyqtSignal(object)
            error = pyqtSignal(str)

            def __init__(self, subj, html):
                super().__init__()
                self._subject = subj
                self._html = html

            def run(self):
                try:
                    checker = SpamChecker()
                    self.done.emit(checker.check(subject=self._subject, body_html=self._html))
                except Exception as exc:
                    self.error.emit(str(exc))

        self._spam_worker = _Worker(subject, body_html)
        self.spam_check_btn.setEnabled(False)
        self.spam_check_btn.setText("Проверяю...")

        def _on_done(result):
            self.spam_check_btn.setEnabled(True)
            self.spam_check_btn.setText("Проверить спам-балл")
            self._show_spam_dialog(result)

        def _on_error(msg):
            self.spam_check_btn.setEnabled(True)
            self.spam_check_btn.setText("Проверить спам-балл")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Ошибка проверки", f"Не удалось проверить спам-балл:\n{msg}")

        self._spam_worker.done.connect(_on_done)
        self._spam_worker.error.connect(_on_error)
        self._spam_worker.start()

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

        # Категории
        categories = getattr(result, "categories", {})
        for cat, cat_score in categories.items():
            if cat_score > 0:
                row = QHBoxLayout()
                row.addWidget(QLabel(cat))
                row.addStretch()
                row.addWidget(QLabel(str(score)))
                layout.addLayout(row)

        # Проблемы
        if result.issues:
            issues_label = QLabel("Проблемы:")
            issues_label.setObjectName("label_subtitle")
            layout.addWidget(issues_label)
            for issue in result.issues[:5]:
                lbl = QLabel(f"• {issue}")
                lbl.setStyleSheet(f"color: {Colors.ERROR};")
                lbl.setWordWrap(True)
                layout.addWidget(lbl)

        # Рекомендации
        if result.suggestions:
            sugg_label = QLabel("Рекомендации:")
            sugg_label.setObjectName("label_subtitle")
            layout.addWidget(sugg_label)
            for s in result.suggestions[:3]:
                lbl = QLabel(f"• {s}")
                lbl.setStyleSheet(f"color: {Colors.SUCCESS};")
                lbl.setWordWrap(True)
                layout.addWidget(lbl)

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
        TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
        name, ok = self._ask_template_name()
        if not ok or not name:
            return
        path = TEMPLATES_DIR / f"{name}.json"
        import json
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "subject": self.subject_input.text(),
                "body_html": self.html_editor.toPlainText() or self.rich_editor.toHtml(),
            }, f, ensure_ascii=False, indent=2)

    def _load_template(self):
        TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getOpenFileName(
            self, "Загрузить шаблон", str(TEMPLATES_DIR), "JSON files (*.json)"
        )
        if path:
            import json
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.subject_input.setText(data.get("subject", ""))
            self.html_editor.setPlainText(data.get("body_html", ""))
            self._update_preview()

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
