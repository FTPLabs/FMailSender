---
name: gui-ux-principles
description: UX принципы для FMailSender GUI. Активируй при дизайне новых экранов, добавлении кнопок/диалогов, улучшении пользовательского опыта.
---

# GUI UX Principles — FMailSender

## CyberPro дизайн-система

```python
# gui/theme.py — источник истины
BG         = "#040410"   # основной фон
BG_CARD    = "#0A0A1A"   # карточки/панели
ACCENT     = "#8B5CF6"   # фиолетовый акцент (кнопки, active)
CYAN       = "#06B6D4"   # голубой (info, icons)
SUCCESS    = "#10B981"   # зелёный (валидный)
ERROR      = "#EF4444"   # красный (ошибка)
WARNING    = "#F59E0B"   # жёлтый (предупреждение)
TEXT       = "#E2E8F0"   # основной текст
TEXT_MUTED = "#6B7280"   # второстепенный
```

## Принципы

### Мгновенная обратная связь
- Кнопка "Проверить" → статус "Проверка..." сразу (не ждать результата)
- Loading индикатор при любой операции > 0.5с
- Прогресс-бар при batch операциях

### Неблокирующий UI
- Все сетевые операции — в QThread
- `QApplication.processEvents()` только для очень коротких блокировок
- Кнопка "Отмена" всегда доступна при длительных операциях

### Информативные ошибки
```
❌ Плохо: "Ошибка подключения"
✅ Хорошо: "GMX: SMTP отключён в настройках. Зайдите gmx.com → Settings → IMAP → включить SMTP"
```

### Контекстные кнопки
- Показывать "Удалить (3)" только если выбраны строки
- `setVisible(has_selection)` — прячь неактуальные кнопки

## Диалоги

```python
# Подтверждение деструктивных действий
if QMessageBox.question(self, "Удалить?",
    f"Удалить {n} аккаунтов?",
    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
) != QMessageBox.StandardButton.Yes:
    return

# Прогресс-диалог для batch операций
progress = QProgressDialog("Импорт...", "Отмена", 0, total, self)
progress.setWindowModality(Qt.WindowModality.WindowModal)
```

## Таблицы

- Row height: 32px (минимум)
- Alternating row colors: `setAlternatingRowColors(True)`
- No grid: `setShowGrid(False)`
- Double-click → редактирование: `doubleClicked.connect(self._edit)`
- Tooltip с деталями на каждой ячейке

## Status bar

Всегда показывать:
`"Всего: N | Валидных: X | Невалидных: Y | Не проверено: Z | Готово к рассылке: W"`
