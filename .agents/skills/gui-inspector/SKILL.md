---
name: gui-inspector
description: Инспекция GUI — координаты виджетов, выравнивание, отступы, перекрытия, пропорции. Активируй при любом изменении gui/ и перед релизом.
---

# GUI Inspector Skill

## Что проверять при изменении UI

### 1. Координаты и выравнивание
```python
# ❌ Абсолютные координаты — ЗАПРЕЩЕНО
widget.setGeometry(10, 50, 200, 30)
widget.move(150, 75)

# ✅ Layout-based позиционирование — ВСЕГДА
layout = QVBoxLayout()
layout.addWidget(widget)
```

**Почему:** Абсолютные координаты ломаются при разных DPI и разрешениях экрана.

### 2. Отступы через Spacing константы
```python
# ❌ Хардкодинг — ЗАПРЕЩЕНО
layout.setContentsMargins(10, 10, 10, 10)
layout.setSpacing(8)

# ✅ Только Spacing.* из gui/theme.py
from gui.theme import Spacing
layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
layout.setSpacing(Spacing.MD)
```

### 3. Минимальные размеры
```python
# Все кнопки — минимальная высота 36px
btn.setMinimumHeight(36)

# Поля ввода — минимальная высота 34px  
edit.setMinimumHeight(34)

# Строки таблицы — минимальная высота 32px
table.verticalHeader().setDefaultSectionSize(32)
```

### 4. Stretch и SizePolicy
```python
# Поле ввода должно растягиваться
edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

# Кнопка — фиксированная или минимальная ширина
btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
```

### 5. Перекрытия виджетов
Проверь: нет ли виджетов, которые рисуются поверх друг друга.
```python
# Тест: сделай все виджеты полупрозрачно-красными и проверь перекрытия
widget.setStyleSheet("background: rgba(255, 0, 0, 50);")
```

### 6. Скроллинг при малом окне
Все списки и таблицы должны иметь scroll:
```python
table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
```

## Чеклист GUI Inspector

- [ ] Нет абсолютных координат (setGeometry, move)
- [ ] Все отступы через Spacing.*
- [ ] Все цвета через Colors.*
- [ ] Минимальные размеры заданы
- [ ] SizePolicy настроен правильно
- [ ] Скроллинг на всех больших списках
- [ ] При resize окна UI не ломается
- [ ] Нет виджетов за границами окна
- [ ] Все тексты читабельны (не обрезаны)
- [ ] Tooltips на всех интерактивных элементах

## Тест DPI-независимости
```python
# Запустить с разными DPI масштабами
# 100% (1920x1080) — стандарт
# 125% (2560x1440) — HiDPI
# 150% (3840x2160) — 4K
# Проверить что UI не ломается
```

## Анимации — не замедляй UI
```python
# Максимальная длительность анимации: 300ms
# Иначе UI ощущается медленным
anim = QPropertyAnimation(widget, b"pos")
anim.setDuration(250)  # не более 300ms
```

## CyberPro Design соответствие
- Фон основной: `#040410` (Colors.BG)
- Карточки: `#0A0A1A` (Colors.BG_CARD)
- Акцент: `#8B5CF6` (Colors.ACCENT)
- Нет других цветов кроме определённых в Colors.*
