---
name: cancel-guard
description: "Правильная отмена asyncio задачи из Qt/другого потока. Используй loop.call_soon_threadsafe(task.cancel) вместо прямого task.cancel()."
---

# Cancel Guard — Корректная отмена asyncio из другого потока

## Проблема

`task.cancel()` вызванный из Qt main thread (или любого другого потока, не являющегося
потоком asyncio event loop) — НЕ thread-safe. Это гонка данных:
- `CancelledError` может не быть доставлен
- Рассылка продолжается как ни в чём ни бывало
- Кнопка «Стоп» / «Отменить» внешне работает (UI замирает), но фактически нет

## Правильное исправление

```python
class MyEngine:
    def __init__(self, ...):
        self._loop: Optional[asyncio.AbstractEventLoop] = None  # Шаг 1
        self._campaign_task: Optional[asyncio.Task] = None

    def stop(self) -> None:
        self.stop_event.set()
        _loop = getattr(self, "_loop", None)
        task = getattr(self, "_campaign_task", None)
        if task and not task.done():
            if _loop and not _loop.is_closed():
                _loop.call_soon_threadsafe(task.cancel)  # ✅ thread-safe
            else:
                task.cancel()  # fallback

    async def run_campaign(self, ...):
        self._loop = asyncio.get_event_loop()  # Шаг 2: сохраняем loop
        self._campaign_task = asyncio.current_task()
        ...
        try:
            ...
        except asyncio.CancelledError:
            pass
        finally:
            self._campaign_task = None
            self._loop = None  # Шаг 3: очищаем
```

В GUI (Qt thread):
```python
def run():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    self._engine._loop = loop  # ← сохраняем ДО run_until_complete
    try:
        loop.run_until_complete(self._engine.run_campaign(...))
    finally:
        loop.close()
threading.Thread(target=run, daemon=True).start()
```

## Почему именно так

- asyncio event loop полностью однопоточный — все операции с задачами (cancel,
  создание, await) должны происходить в его потоке.
- `loop.call_soon_threadsafe(fn)` — официальный и единственный правильный способ
  поставить вызов в очередь asyncio loop из другого потока (Python docs: `asyncio.loop.call_soon_threadsafe`).
- Прямой `task.cancel()` из Qt потока — неопределённое поведение (UB), работает
  в части Python runtime реализаций, но ненадёжно.

## Проверить что исправление работает

1. Запустить рассылку на 100+ адресов.
2. Нажать «Стоп» через 3–5 секунд.
3. Рассылка должна прекратиться в течение 1–2 секунд (после завершения текущего батча).
4. В логе должно появиться «Готово: N успешно, M ошибок» с актуальными числами.
