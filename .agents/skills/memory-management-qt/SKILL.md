---
name: memory-management-qt
description: Qt/PyQt6 memory management — parent-child ownership, GC prevention, утечки памяти. Активируй при отладке утечек, крэшей после долгой работы, проблем с GC.
---

# Memory Management in PyQt6

## Qt Parent-Child Ownership

```python
# Qt удаляет дочерние объекты при удалении родителя
w = QWidget(parent=self)   # Qt удалит w при удалении self
w = QWidget()              # Python GC управляет временем жизни
```

## Проблема: Python GC vs Qt lifecycle

```python
# ❌ ОПАСНО: GC может удалить w пока поток ещё работает
def start_work(self):
    w = MyWorker()
    w.start()
    # w выходит из scope → GC кандидат → крэш в run()

# ✅ БЕЗОПАСНО вариант 1: parent=self
def start_work(self):
    w = MyWorker(parent=self)  # Qt держит ссылку
    w.start()

# ✅ БЕЗОПАСНО вариант 2: список
def start_work(self):
    w = MyWorker()
    self._workers.append(w)   # Python держит ссылку
    w.start()
```

## Очистка завершённых воркеров

```python
# Вызывай после каждого on_result
def _cleanup(self):
    self._workers = [w for w in self._workers if w.isRunning()]

# Или в on_result через QTimer
def on_result(ok, msg):
    ...
    QTimer.singleShot(0, self._cleanup)  # после обработки сигнала
```

## Сигналы и GC

```python
# ❌ Лямбда держит ссылку на self — может создать циклическую ссылку
w.done.connect(lambda ok, msg: self._on_done(ok, msg, row=row))

# ✅ Используй default arguments для захвата значений
@pyqtSlot(bool, str)
def on_done(ok, msg, r=row):
    self._on_done(ok, msg, r)
w.done.connect(on_done)
```

## Диалоги — exec() vs show()

```python
# exec() — блокирующий, автоматически удаляется после закрытия
dlg = MyDialog(parent=self)
if dlg.exec() == QDialog.DialogCode.Accepted:
    data = dlg.get_data()

# show() — неблокирующий, держи ссылку!
self._dlg = MyDialog(parent=self)  # self._dlg предотвращает GC
self._dlg.show()
```

## QTableWidget items

QTableWidgetItem принадлежит таблице после `setItem()`.
Не держи внешние ссылки на items — после `setRowCount(0)` они удаляются Qt.

```python
# После setRowCount(0) все items удалены — не используй старые ссылки
self.table.setRowCount(0)
# item = self.table.item(0, 0)  # → None, не старый объект
```

## Утечка: _test_workers без очистки

```python
# ❌ БЫЛ: список только растёт
self._test_workers.append(w)
# После 100 аккаунтов: 100 мёртвых QThread в памяти

# ✅ ИСПРАВЛЕНО v4.4.0: очищаем завершённые
self._test_workers = [x for x in self._test_workers if x.isRunning()]
```
