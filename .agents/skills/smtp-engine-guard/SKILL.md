---
  name: smtp-engine-guard
  description: Защищает async SMTP движок core/sender.py от race conditions, deadlocks и потери писем. Активируй при изменении core/sender.py, добавлении новых параметров отправки, или при жалобах на зависание/потерю писем.
  ---

  # SMTP Engine Guard — core/sender.py (v6)

  ## Архитектура (v6)
  - `core/sender.py` — sync SendingEngine.run() → asyncio loop → run_campaign()
  - `core/server.py` — запускает engine в daemon thread
  - Прогресс: `engine.on_progress(sent, total, result)` callback
  - Остановка: `engine.stop_event.set()` + `engine._paused = True/False`

  ## Критические инварианты (НЕЛЬЗЯ нарушать)

  ### Thread safety
  ```python
  # ✅ Инкремент счётчика — только через try_increment (atomic)
  account.try_increment()  # returns bool — check before sending

  # ❌ НЕ делай: account.sent_today += 1 напрямую из async task
  ```

  ### asyncio loop — ОБЯЗАТЕЛЬНО
  ```python
  # ✅ Внутри корутины — get_running_loop()
  self._loop = asyncio.get_running_loop()  # в async def run_campaign()

  # ❌ НЕЛЬЗЯ в корутине: asyncio.get_event_loop() — deprecated Python 3.10+
  ```

  ### Async parallelism
  - delay между письмами — ВНУТРИ task wrapper (`_send_with_acct_delay`), не снаружи
  - Каждый получатель — отдельная asyncio.Task
  - Семафор на количество параллельных соединений (`max_threads`)

  ### Остановка (thread-safe cancel)
  ```python
  def stop(self) -> None:
      self.stop_event.set()
      _loop = getattr(self, "_loop", None)
      task = getattr(self, "_campaign_task", None)
      if task and not task.done():
          if _loop and not _loop.is_closed():
              _loop.call_soon_threadsafe(task.cancel)  # ✅ thread-safe
          else:
              task.cancel()
  ```

  ## Типичные ошибки

  | Ошибка | Причина | Исправление |
  |--------|---------|-------------|
  | Письма теряются | delay снаружи task | перенести asyncio.sleep внутрь _send_with_acct_delay |
  | Зависание при стопе | SMTP не закрывается | добавить finally: smtp.quit() |
  | Дублирование отправки | race в try_increment | всегда использовать try_increment |
  | DeprecationWarning asyncio | get_event_loop() в корутине | заменить на get_running_loop() |

  ## Чеклист перед изменением sender.py

  ```bash
  # 1. Нет прямых += без lock/atomic
  grep -n "+= " core/sender.py | grep -v "#"

  # 2. Все asyncio.sleep() внутри task, не снаружи цикла
  grep -n "asyncio.sleep" core/sender.py

  # 3. SMTP соединение закрывается в finally
  grep -A5 "smtplib.SMTP" core/sender.py | grep -E "finally|close|quit"

  # 4. Нет get_event_loop() в корутинах (только get_running_loop)
  grep -n "get_event_loop" core/sender.py
  ```
  