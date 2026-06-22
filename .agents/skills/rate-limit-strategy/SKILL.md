---
name: rate-limit-strategy
description: Стратегия rate limiting в FMailSender. Активируй при: ошибках 421 Too many connections, зависании при Проверить все, проблемах с ip-api.com.
---

# Rate Limiting Strategy

## SMTP Сервера

| Провайдер | Max concurrent | Рекомендуемый delay |
|-----------|---------------|-------------------|
| GMX | 2-3 | 2-3 сек между попытками |
| Rambler | 3-5 | 1-2 сек |
| Yahoo | 2 | 3 сек |
| Gmail | 5 | 0.5 сек |
| Outlook | 3 | 1 сек |

**Глобальное правило:** `MAX_CONCURRENT = 4` в `_test_all()`

```python
MAX_CONCURRENT = 4  # НЕ менять на большее — 421 у GMX/Rambler
```

## ip-api.com

- Лимит: 45 req/min
- Защита: `threading.Semaphore(3)` в `_CountryWorker`
- Кэш: `_proxy_country_cache` — один запрос на прокси за сессию

## ProxyCheckWorker (диалог проверки прокси)

```python
# Из ProxyCheckWorker — семафор для параллельных проверок
_MAX_PROXY_CHECKERS = 10  # прокси без SMTP, можно больше
```

## Паттерн батчевой обработки

```python
MAX_CONCURRENT = 4
queue = list(range(total))
running = [0]

def _start_next():
    while queue and running[0] < MAX_CONCURRENT:
        if self._test_cancel_event.is_set():
            break
        row = queue.pop(0)
        w = TestWorker(acc)
        running[0] += 1
        def on_done(ok, msg):
            running[0] -= 1
            _start_next()  # освободился слот — запускаем следующий
        w.result_ready.connect(on_done)
        w.start()

_start_next()
```

## Ошибка 421 в логах = нужно снизить MAX_CONCURRENT
