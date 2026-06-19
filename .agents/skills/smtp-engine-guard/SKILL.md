---
  name: smtp-engine-guard
  description: Защищает async SMTP движок core/sender.py от race conditions, deadlocks и потери писем. Активируй при изменении core/sender.py, добавлении новых параметров отправки, или при жалобах на зависание/потерю писем.
  ---

  # SMTP Engine Guard — core/sender.py

  ## Критические инварианты (НЕЛЬЗЯ нарушать)

  ### Thread safety
  ```python
  # ✅ Инкремент счётчика — только через try_increment (atomic)
  # ❌ НЕ делай: self.sent_count += 1 напрямую из async task
  ```

  ### Async parallelism
  - delay между письмами — ВНУТРИ task wrapper, не снаружи
  - Каждый аккаунт — отдельная asyncio.Task
  - Семафор на количество параллельных соединений

  ### Ротация аккаунтов
  - Аккаунт блокируется после `max_errors` ошибок подряд
  - Временная блокировка (cooldown) — не постоянная
  - Blacklist получателей проверяется ДО создания соединения

  ## Чеклист перед изменением sender.py

  ```bash
  # 1. Нет прямых self.field += N без lock/atomic
  grep -n "+= " core/sender.py | grep -v "#"

  # 2. Все asyncio.sleep() внутри task, не снаружи цикла
  grep -n "asyncio.sleep" core/sender.py

  # 3. SMTP соединение закрывается в finally
  grep -A5 "smtplib.SMTP" core/sender.py | grep -E "finally|close|quit"
  ```

  ## Сигналы прогресса в PyQt6

  ```python
  # ✅ Правильно — сигнал из потока в UI
  self.progress_signal.emit(sent, total, current_email)

  # ❌ Нельзя — прямой вызов QLabel из async thread
  self.label.setText("...")  # CRASH в PyQt6
  ```

  ## Типичные ошибки в этом проекте

  | Ошибка | Причина | Исправление |
  |--------|---------|-------------|
  | Письма теряются | delay снаружи task | перенести asyncio.sleep внутрь |
  | Зависание при стопе | SMTP не закрывается | добавить finally: smtp.quit() |
  | Дублирование отправки | race в try_increment | всегда использовать try_increment |
  