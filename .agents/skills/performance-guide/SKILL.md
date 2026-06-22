---
name: performance-guide
description: Оптимизация производительности FMailSender — загрузка таблиц, batch SMTP, память, профилирование. Активируй при зависаниях, медленном запуске, утечках памяти.
---

# Performance Guide

## Проблемы и решения

### _refresh_table() слишком часто вызывается

```python
# ❌ Плохо: rebuild при каждом результате (100 аккаунтов = 100 rebuilds)
def on_result(ok, msg):
    self._accounts[r].last_test_ok = ok
    self._refresh_table()  # ДОРОГО

# ✅ Хорошо: точечное обновление ячейки
def on_result(ok, msg):
    self._accounts[r].last_test_ok = ok
    item = self.table.item(r, 1)
    if item:
        item.setText("Валидный" if ok else "Ошибка")
        item.setForeground(QColor(Colors.SUCCESS if ok else Colors.ERROR))
    # _refresh_table только в конце всех тестов
```

### QTableWidget с 1000+ строками

```python
# Отключи updates во время batch insert
self.table.setUpdatesEnabled(False)
try:
    for row_data in data:
        # ... insertRow, setItem ...
        pass
finally:
    self.table.setUpdatesEnabled(True)
```

### Много воркеров — pool вместо spawn

```python
# ❌ Создаём новый QThread для каждого аккаунта
for acc in accounts:
    w = TestWorker(acc)
    w.start()

# ✅ Батчевый запуск с MAX_CONCURRENT
MAX_CONCURRENT = 4
running = [0]
queue = list(range(len(accounts)))

def _start_next():
    while queue and running[0] < MAX_CONCURRENT:
        row = queue.pop(0)
        start_worker(row)  # managing running[0] in callback
```

### _CountryWorker — кэш устраняет повторные запросы

```python
# ip-api.com: 45 req/min
# Для 100 аккаунтов без кэша = 100 запросов = rate limit
# С кэшем: один запрос на уникальный прокси

_proxy_country_cache: dict[str, str] = {}  # [proxy_url] = "🇷🇺 Russia"
```

### asyncio overhead

Создание нового event loop для каждого TestWorker — небольшой overhead.
При 100 аккаунтах: 100 loops × ~0.1ms = 10ms — приемлемо.
Не оптимизируй преждевременно.

### Профилирование

```python
import cProfile, pstats
profiler = cProfile.Profile()
profiler.enable()

# ... код для профилирования ...

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)
```

## Memory budget (ориентировочно)

- SmtpAccount: ~2KB
- 1000 аккаунтов: ~2MB
- QTableWidget row: ~5KB
- 1000 строк таблицы: ~5MB
- QThread (idle): ~1MB
- 4 активных воркера: ~4MB

Общий бюджет: ~15-20MB — комфортно для desktop.
