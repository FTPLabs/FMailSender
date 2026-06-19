---
  name: pyqt6-patterns
  description: PyQt6 паттерны для FMailSender — thread safety, сигналы, стилизация, кастомные виджеты. Активируй при изменении gui/ или создании новых экранов/виджетов.
  ---

  # PyQt6 Patterns — FMailSender GUI

  ## Золотое правило: UI обновляется ТОЛЬКО из главного потока

  ```python
  # ✅ Правильно — через сигнал
  class WorkerThread(QThread):
      result = pyqtSignal(str)
      def run(self):
          data = do_work()
          self.result.emit(data)  # UI обновится в главном потоке

  # ❌ Нельзя — прямой вызов из потока = CRASH
  threading.Thread(target=lambda: self.label.setText("done")).start()
  ```

  ## CyberPro дизайн-паттерны (из gui/theme.py)

  ```python
  from gui.theme import Colors, Spacing, Typography

  # Стеклянная карточка
  frame.setStyleSheet("""
      background: rgba(255,255,255,0.025);
      border: 1px solid rgba(139,92,246,0.12);
      border-radius: 12px;
  """)

  # Кнопка с акцентом
  btn.setStyleSheet(f"""
      QPushButton {{
          background: {Colors.ACCENT};
          color: white;
          border-radius: {Spacing.RADIUS_MD}px;
          padding: {Spacing.SM}px {Spacing.MD}px;
      }}
      QPushButton:hover {{ background: {Colors.ACCENT_HOVER}; }}
  """)
  ```

  ## Добавление нового экрана

  1. Создай `gui/screens/screen_<name>.py` → наследуй от `QWidget`
  2. Добавь в `gui/app.py` → `_add_screen()`
  3. Добавь кнопку в sidebar с иконкой из `gui/icons.py`
  4. Используй `Colors`, `Spacing`, `Typography` из theme.py

  ## Кастомные виджеты с анимацией

  ```python
  class MyWidget(QWidget):
      def paintEvent(self, e):
          painter = QPainter(self)
          painter.setRenderHint(QPainter.RenderHint.Antialiasing)
          # рисуй через painter, не через stylesheet
          painter.end()
  ```

  ## Чеклист нового экрана

  - [ ] Нет прямых вызовов UI из потоков
  - [ ] Цвета только из `Colors` (не хардкод hex)
  - [ ] Отступы из `Spacing` (не хардкод px)
  - [ ] Публичные методы: `update_data()` или `refresh()`
  