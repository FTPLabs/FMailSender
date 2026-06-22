---
name: proxy-country-cache
description: Паттерны кэширования страны прокси. Активируй при работе с _CountryWorker, _refresh_table, определением флага страны. Предотвращает потерю страны при обновлении таблицы.
---

# Proxy Country Cache

## Проблема без кэша
Каждый `_refresh_table()` сбрасывает ячейку прокси в пустую строку.
`_CountryWorker` запускается снова. Результат приходит в "устаревшую" ячейку после следующего rebuild.

## Реализация (screen_accounts.py)

```python
# Модульный кэш — персистентен на всю сессию
_proxy_country_cache: dict[str, str] = {}

# Семафор — не более 3 запросов к ip-api.com одновременно
_country_api_semaphore = threading.Semaphore(3)
```

## _CountryWorker.run() с кэшем

```python
def run(self):
    cached = _proxy_country_cache.get(self._proxy_url)
    if cached is not None:
        self.result_ready.emit(self._row, cached)
        return
    with _country_api_semaphore:
        flag = self._resolve(self._proxy_url)
    _proxy_country_cache[self._proxy_url] = flag
    self.result_ready.emit(self._row, flag)
```

## _refresh_table с кэшем

```python
_proxy_raw = (acc.proxy or "").strip()
_cached_country = _proxy_country_cache.get(_proxy_raw, "")
if _cached_country and _cached_country != "—":
    _proxy_display = f"{_cached_country} | {_proxy_raw}"
else:
    _proxy_display = _proxy_raw or "—"
# Запускаем воркер ТОЛЬКО если нет в кэше
if _proxy_raw and not _cached_country:
    QTimer.singleShot(100 + row * 80, lambda r=row, p=_proxy_raw: self._fetch_proxy_country(r, p))
```

## Держи ссылку на воркер!

```python
# ❌ НЕПРАВИЛЬНО — GC удалит объект до завершения потока
w = _CountryWorker(row, proxy_url, parent=self)
w.start()

# ✅ ПРАВИЛЬНО — держим в _test_workers
w = _CountryWorker(row, proxy_url, parent=self)
self._test_workers.append(w)
w.start()
```

## ip-api.com лимиты
- Free tier: 45 req/min = ~1.3 req/sec
- Используй Semaphore(3) чтобы не превышать
- Кэш устраняет повторные запросы для тех же прокси
