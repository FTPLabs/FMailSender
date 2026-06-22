---
name: pyqt6-threading-guide
description: PyQt6 threading — QThread, memory management, GC prevention, signal cleanup. Активируй при создании background workers, исправлении зависания UI, утечек памяти.
---

# PyQt6 Threading Guide

## Правило №1: UI только из главного потока

```python
# ✅ Через сигнал — безопасно
class Worker(QThread):
    done = pyqtSignal(str)
    def run(self):
        result = heavy_work()
        self.done.emit(result)

# ❌ Прямой вызов из потока = крэш или race condition
threading.Thread(target=lambda: label.setText("done")).start()
```

## GC Prevention — держи ссылку на QThread

```python
# ❌ GC удалит w до завершения потока
def start_work(self):
    w = Worker()
    w.done.connect(self.on_done)
    w.start()
    # w уходит из стека → Python GC удаляет → сегфолт

# ✅ Храни в self или в списке
def start_work(self):
    w = Worker(parent=self)  # parent=self даёт Qt-владение
    self._workers.append(w)
    w.done.connect(self._on_done)
    w.start()

# Очищай завершённые
def _cleanup_workers(self):
    self._workers = [w for w in self._workers if w.isRunning()]
```

## Отмена длительной операции

```python
class Worker(QThread):
    def __init__(self):
        super().__init__()
        self._cancel = threading.Event()

    def cancel(self):
        self._cancel.set()

    def run(self):
        for item in big_list:
            if self._cancel.is_set():
                break
            process(item)
```

## QTimer для отложенного старта

```python
# Запуск воркеров с задержкой чтобы UI успел обновиться
for row, proxy in enumerate(proxies):
    QTimer.singleShot(100 + row * 80, lambda r=row, p=proxy:
        self._fetch_country(r, p))
```
Увеличь множитель (50→80мс) если много строк — даёт время UI перерисоваться.

## asyncio + QThread

```python
class AsyncWorker(QThread):
    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(my_coroutine())
        finally:
            loop.close()
```
Создавай НОВЫЙ event loop в каждом потоке — не шари глобальный.

## Список воркеров — паттерн FMailSender

```python
self._test_workers: list[QThread] = []

# Добавить
self._test_workers.append(w)

# Очистить завершённые (вызывать после каждого on_result)
self._test_workers = [x for x in self._test_workers if x.isRunning()]

# Отменить все
def _cancel_all(self):
    self._cancel_event.set()
    for w in self._test_workers:
        if w.isRunning():
            w.quit()
    self._test_workers.clear()
```
