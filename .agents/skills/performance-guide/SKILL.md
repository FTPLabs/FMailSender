---
  name: performance-guide
  description: Оптимизация производительности FMailSender — пул соединений, чекпоинты, rate limiting для рассылок 10-15к писем.
  ---

  # Performance Guide — Рассылки 10-15к писем

  ## Ключевые компоненты (v5.0+)

  ### 1. SMTP Connection Pool (core/smtp_pool.py)

  **Проблема:** каждое письмо = новый TCP+TLS handshake+AUTH (0.5-3 сек)
  **Решение:** переиспользование соединения (RSET между письмами)

  ```python
  from core.smtp_pool import get_global_pool

  pool = get_global_pool()
  conn = pool.acquire(account)
  try:
      conn.send_message(msg)
  finally:
      pool.release(conn, account)
  ```

  **Прирост:** 5-10x быстрее, меньше AUTH-ошибок, меньше rate-limit'ов.

  ### 2. Checkpoint System (core/send_checkpoint.py)

  **Проблема:** при крэше на 8000-м письме вся работа теряется
  **Решение:** сохранение прогресса каждые 25 писем

  ```python
  from core.send_checkpoint import CheckpointManager

  mgr = CheckpointManager("campaign-2024-01", total=len(recipients))
  sent_set = mgr.get_sent_set() if mgr.is_resumable() else set()
  recipients = [r for r in all_recipients if r.email not in sent_set]
  # ... после отправки:
  mgr.record_sent(email)  # flush каждые 25
  ```

  ## Лимиты сессий по провайдерам

  | Провайдер | Писем/сессия | Задержка | Max parallel |
  |-----------|-------------|----------|--------------|
  | Gmail | 400 | 0.3с | 5 |
  | Outlook | 200 | 0.5с | 3 |
  | Yahoo | 100 | 1.0с | 2 |
  | Rambler | 150 | 0.5с | 3-5 |
  | Mail.ru | 200 | 0.3с | 5 |
  | GMX | 100 | 1.0с | 2-3 |
  | Yandex | 200 | 0.3с | 5 |

  ## Оптимальная конфигурация для 10-15к писем

  ```python
  config = SendConfig(
      max_threads=8,           # параллельных задач
      delay_between=0.3,       # глобальная задержка
      pause_after_n=500,       # пауза каждые 500 писем
      pause_duration_sec=30,   # 30 сек паузы (антибан)
      rotate_accounts=True,    # ротация аккаунтов
      uniqueize=True,          # уникализация тела письма
  )
  ```

  ## Расчёт скорости

  - 1 аккаунт, задержка 0.5с = ~7200 писем/час
  - 5 аккаунтов, задержка 0.5с = ~36000 писем/час (ограничено rate-limit'ами)
  - Реальная цифра при 10 аккаунтах = 5000-8000 писем/час

  ## Чеклист перед рассылкой 10к+

  - [ ] Аккаунты проверены (зелёная галочка)
  - [ ] Прокси валидны для каждого аккаунта
  - [ ] Тестовое письмо прошло спам-проверку
  - [ ] Уникализация включена
  - [ ] pause_after_n = 500, pause_duration_sec = 30
  - [ ] Bounce-монитор настроен (core/bounce.py)
  - [ ] Warmup завершён (если новые аккаунты)

  ## SMTP-сессия: как работает переиспользование

  ```
  CONNECT → TLS → AUTH         (1 раз на сессию, ~1-3 сек)
    MAIL FROM / RCPT TO / DATA  (письмо 1)
    RSET                         (сброс без переподключения)
    MAIL FROM / RCPT TO / DATA  (письмо 2)
    ...
  QUIT → CONNECT → TLS → AUTH  (новая сессия после лимита)
  ```
  