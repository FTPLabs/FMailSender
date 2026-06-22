---
name: pyqt6-table-patterns
description: QTableWidget паттерны для FMailSender — создание, обновление ячеек, цвета, tooltip, избегание rebuild. Активируй при работе с таблицами аккаунтов, прокси, получателей.
---

# QTableWidget Patterns

## Таблица аккаунтов (3 колонки)

| # | Имя | Тип | Ключевые атрибуты |
|---|-----|-----|-------------------|
| 0 | Email | строка | toolTip = хост:порт, лимиты |
| 1 | Статус | цветной текст | SUCCESS/ERROR/TEXT_MUTED |
| 2 | Прокси | строка + флаг | toolTip = raw proxy url |

## Создание строки

```python
row = self.table.rowCount()
self.table.insertRow(row)
self.table.setRowHeight(row, 32)

item = QTableWidgetItem("текст")
item.setForeground(QColor(Colors.SUCCESS))
item.setToolTip("подробности")
item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
self.table.setItem(row, col, item)
```

## Обновление ячейки БЕЗ пересоздания таблицы

```python
# Дешевле чем _refresh_table() — не трогай другие ячейки
item = self.table.item(row, 1)
if item:
    item.setText("Валидный")
    item.setForeground(QColor(Colors.SUCCESS))
    item.setToolTip(full_message)
```

## Когда НЕЛЬЗЯ делать _refresh_table()

В `on_result` каждого тестового воркера — вызывает cascade rebuild и теряет:
- Страну прокси (если нет кэша)
- Scroll position
- Selection state

**Предпочитай:** точечное обновление ячейки item.setText() вместо полного rebuild.

## Колонка прокси с флагом

```python
# В _refresh_table: берём из кэша
cached = _proxy_country_cache.get(proxy_raw, "")
display = f"{cached} | {proxy_raw}" if cached and cached != "—" else proxy_raw
item = QTableWidgetItem(display)
item.setToolTip(proxy_raw)  # raw url в tooltip

# В on_country: обновляем без rebuild
item = self.table.item(row, 2)
if item:
    base = item.toolTip() or proxy_raw
    item.setText(f"{flag} | {base}")
```

## Цвета (из Colors в theme.py)

```python
Colors.SUCCESS  = "#10B981"  # зелёный — валидный
Colors.ERROR    = "#EF4444"  # красный — ошибка
Colors.WARNING  = "#F59E0B"  # жёлтый — предупреждение
Colors.TEXT_MUTED = "#6666AA"  # серый — не проверено
"#6C8EBF"  # голубой — прокси URL
"#6666AA"  # фиолетовый — в очереди
```

## Запрет редактирования всей таблицы

```python
self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
```
