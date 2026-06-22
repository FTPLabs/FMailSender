---
name: fps-optimization
description: Оптимизация FPS и плавности анимаций в PyQt6 FMailSender. Активируй при жалобах на тормоза UI, при добавлении анимаций, при работе с animated_bg.py.
---

# FPS Optimization — PyQt6

## Цель: 60 FPS в UI

PyQt6 использует QPainter/OpenGL. Целевой показатель: 60 FPS при любой операции.

## Главные враги FPS

### 1. Блокировка главного потока
```python
# ❌ УБИВАЕТ FPS — UI замирает
def on_button_click():
    result = requests.get("https://api.example.com")  # блокирует UI поток
    self.label.setText(result.text)

# ✅ QThread — не блокируем UI поток
class FetchWorker(QThread):
    done = pyqtSignal(str)
    def run(self): 
        result = requests.get("https://api.example.com")
        self.done.emit(result.text)
```

### 2. Перерисовка слишком часто
```python
# ❌ update() при каждом событии — перегрузка QPainter
def mouseMoveEvent(self, e):
    self.cursor_pos = e.pos()
    self.update()  # вызывает paintEvent каждый пиксель

# ✅ Throttle через QTimer (60fps = 16ms интервал)
def __init__(self):
    self._paint_timer = QTimer()
    self._paint_timer.setInterval(16)  # 60 FPS
    self._paint_timer.timeout.connect(self.update)
    self._paint_timer.start()
```

### 3. Тяжёлый paintEvent
```python
# ❌ Сложные расчёты в paintEvent
def paintEvent(self, e):
    painter = QPainter(self)
    for i in range(1000):
        # math.sin, math.cos каждый кадр — ДОРОГО
        x = math.sin(time.time() + i) * 100
        painter.drawEllipse(x, 0, 5, 5)

# ✅ Пре-рендер статичных элементов в QPixmap
def __init__(self):
    self._bg_pixmap = self._render_bg()  # один раз

def _render_bg(self) -> QPixmap:
    px = QPixmap(self.size())
    p = QPainter(px)
    # рисуем статику
    p.end()
    return px

def paintEvent(self, e):
    painter = QPainter(self)
    painter.drawPixmap(0, 0, self._bg_pixmap)  # только копирование
```

### 4. animated_bg.py — оптимизация
```python
# В AnimatedBackground:
# - Ограничь количество частиц: MAX_PARTICLES = 30 (не 100+)
# - FPS cap: 30 FPS достаточно для фона (не 60)
# - Используй setInterval(33)  # 30fps вместо 16ms (60fps)
# - При переходе между экранами: timer.stop() на неактивных экранах
```

## Оптимизация QTableWidget

```python
# Отключить live sort при добавлении строк
self.table.setSortingEnabled(False)
self.table.setUpdatesEnabled(False)
try:
    for row in rows:
        # ... добавление строк
        pass
finally:
    self.table.setSortingEnabled(True)
    self.table.setUpdatesEnabled(True)

# Виртуальная прокрутка для 1000+ строк
# Рассмотреть QAbstractTableModel вместо QTableWidget
```

## CSS/QSS оптимизация

```python
# ❌ setStyleSheet на каждый виджет — парсится каждый раз
for widget in self.buttons:
    widget.setStyleSheet("color: red; background: blue;")

# ✅ Один stylesheet на родителя
self.buttons_container.setStyleSheet("""
    QPushButton { color: red; background: blue; }
""")
```

## Замеры FPS

```python
import time

class FPSCounter:
    def __init__(self):
        self._frames = 0
        self._last = time.monotonic()
    
    def tick(self) -> float:
        self._frames += 1
        now = time.monotonic()
        if now - self._last >= 1.0:
            fps = self._frames / (now - self._last)
            self._frames = 0
            self._last = now
            return fps
        return -1

# В paintEvent:
fps = self._fps_counter.tick()
if fps > 0:
    self.setWindowTitle(f"FPS: {fps:.0f}")  # для отладки
```

## Целевые показатели

| Операция | Цель | Недопустимо |
|----------|------|------------|
| Открытие экрана | < 100ms | > 500ms |
| Анимация фона | 30 FPS | < 15 FPS |
| Прокрутка таблицы | 60 FPS | < 30 FPS |
| Реакция на клик | < 50ms | > 200ms |
| Начало проверки аккаунта | < 100ms | > 1000ms |
