---
  name: cancel-guard
  description: "Правильная отмена asyncio задачи из другого потока (v6). Используй loop.call_soon_threadsafe(task.cancel) вместо прямого task.cancel()."
  ---

  # Cancel Guard — Корректная отмена asyncio из другого потока (v6)

  ## Проблема

  `task.cancel()` вызванный из daemon-потока (не потока asyncio event loop) — НЕ thread-safe.
  Это гонка данных:
  - `CancelledError` может не быть доставлен
  - Рассылка продолжается несмотря на стоп
  - Кнопка «Стоп» внешне работает, но фактически нет

  ## Контекст v6 (Tauri + FastAPI)

  В v6 архитектуре:
  - `SendingEngine.run()` — sync метод, запускается в `threading.Thread` из `server.py`
  - Внутри `run()` создаётся новый asyncio event loop (`asyncio.new_event_loop()`)
  - `run_campaign()` — async корутина внутри этого loop

  Кнопка «Стоп» в React → HTTP POST /api/campaign/stop → server.py → `engine.stop()` — из другого thread!

  ## Правильный паттерн (уже реализован в core/sender.py)

  ```python
  class SendingEngine:
      def __init__(self, ...):
          self._loop: Optional[asyncio.AbstractEventLoop] = None
          self._campaign_task: Optional[asyncio.Task] = None

      def stop(self) -> None:
          self.stop_event.set()
          self._paused = False
          _loop = getattr(self, "_loop", None)
          task = getattr(self, "_campaign_task", None)
          if task and not task.done():
              if _loop and not _loop.is_closed():
                  _loop.call_soon_threadsafe(task.cancel)  # ✅ thread-safe
              else:
                  task.cancel()  # fallback

      async def run_campaign(self, recipients, template):
          self._loop = asyncio.get_running_loop()  # ✅ сохраняем loop
          self._campaign_task = asyncio.current_task()
          try:
              ...
          except asyncio.CancelledError:
              pass
          finally:
              self._campaign_task = None
              self._loop = None  # очищаем
  ```

  ## Почему именно так

  - asyncio event loop полностью однопоточный — все операции с задачами должны вызываться из его потока
  - `call_soon_threadsafe` безопасно планирует вызов `task.cancel()` в нужном потоке
  - В v6 нет Qt — `stop()` вызывается из HTTP-handler thread FastAPI

  ## Антипаттерн
  ```python
  # ❌ НЕ делай: прямой task.cancel() из другого thread
  engine._campaign_task.cancel()  # RACE CONDITION — может не сработать
  ```
  