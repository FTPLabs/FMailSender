---
  name: smtp-pool-guide
  description: Интеграция SMTP Connection Pool в FMailSender — как подключить пул к _send_sync, паттерны использования, troubleshooting. Активируй при работе с core/smtp_pool.py.
  ---

  # SMTP Connection Pool Guide

  ## Что такое пул и зачем он нужен

  Без пула: каждое письмо → TCP connect + TLS handshake + AUTH (0.5-3 сек overhead)
  С пулом: первое письмо → connect+AUTH, следующие → RSET (0.05 сек overhead)

  При 10 000 писем экономия: **~5-15 часов** на соединениях.

  ## Базовое использование

  ```python
  from core.smtp_pool import get_global_pool

  pool = get_global_pool()

  def _send_sync_pooled(account, recipient, template, uniqueize=True):
      from core.sender import _build_message
      msg = _build_message(account, recipient, template, uniqueize=uniqueize)
      
      conn = pool.acquire(account)
      if conn is None:
          return {"success": False, "error": "Не удалось подключиться (AUTH fail)"}
      
      try:
          conn.send_message(msg)  # включает per-провайдер задержку
          return {"success": True, "account": account.email}
      except Exception as e:
          # Соединение испорчено — закрыть, не возвращать в пул
          conn.close()
          conn = None
          return {"success": False, "error": str(e)}
      finally:
          if conn is not None:
              pool.release(conn, account)  # RSET + возврат
  ```

  ## Session limits (когда создаётся новое соединение)

  Пул автоматически отслеживает `sent_count` и создаёт новое соединение при достижении лимита.

  ```
  conn.is_exhausted → sent_count >= session_limit → pool.release() закрывает соединение
  conn.is_stale    → (now - last_used) > 300 сек → pool.release() закрывает соединение
  ```

  ## Troubleshooting

  | Симптом | Причина | Решение |
  |---------|---------|---------|
  | OSError: Connection reset | Сервер разорвал устаревшее соединение | is_stale автоматически обнаружит — reconnect |
  | SMTPServerDisconnected | Превышен session_limit | is_exhausted → reconnect |
  | AUTH fail на acquire | Неверный пароль или заблокирован | вернуть None → ошибка в SendResult |
  | GMX 421 Too many | max_threads > 3 для gmx | снизить до 2-3 |

  ## Закрытие пула при завершении кампании

  ```python
  # По завершении рассылки — закрыть все соединения
  from core.smtp_pool import get_global_pool
  get_global_pool().close_all()
  ```

  ## Ограничения

  - Пул работает ТОЛЬКО с прокси (прямое соединение запрещено)
  - Не использовать для тестирования аккаунтов (_test_smtp_sync не использует пул)
  - Max 2 соединения на аккаунт одновременно (настраивается _max_per_account)
  