---
  name: async-smtp-guide
  description: asyncio SMTP паттерны в FMailSender — aiosmtplib, event loop в потоках, connection pool, test_smtp_connection. Активируй при работе с async SMTP, отладке event loop ошибок.
  ---

  # Async SMTP Guide

  ## test_smtp_connection (gui/screens/screen_accounts.py)

  ```python
  async def test_smtp_connection(account: SmtpAccount) -> tuple[bool, str]:
      """Async обёртка над _test_smtp_sync."""
      loop = asyncio.get_event_loop()
      return await loop.run_in_executor(None, _test_smtp_sync, account)
  ```

  ## TestWorker — запуск в отдельном потоке

  ```python
  class TestWorker(QThread):
      result_ready = pyqtSignal(bool, str)

      def run(self):
          loop = asyncio.new_event_loop()  # НОВЫЙ loop — не шарить!
          asyncio.set_event_loop(loop)
          try:
              ok, msg = loop.run_until_complete(test_smtp_connection(self._account))
          finally:
              loop.close()
          self.result_ready.emit(ok, msg)
  ```

  ## _test_smtp_sync (core/sender.py)

  Синхронная функция с многоуровневым fallback:
  1. Основная конфигурация + cert verify
  2. Та же конфигурация без cert verify (self-signed SSL)
  3. Если прокси: только 465/587 через прокси (no port scan)
  4. Если нет прокси: ЗАПРЕЩЕНО — возвращает ошибку

  ```python
  TIMEOUT = 5  # секунд на каждую попытку — быстрый fail
  ```

  ## Connection Pool (v5.0+) — для реальной отправки

  **Не для тестирования аккаунтов — только для кампаний!**

  ```python
  from core.smtp_pool import get_global_pool

  pool = get_global_pool()

  # Взять соединение (создаётся при первом использовании)
  conn = pool.acquire(account)
  if conn is None:
      # AUTH ошибка — аккаунт недоступен
      return SendResult(success=False, error="AUTH fail")

  try:
      conn.send_message(msg)  # включает per-провайдер delay
      return SendResult(success=True)
  except Exception as e:
      conn.close()
      conn = None
      return SendResult(success=False, error=str(e))
  finally:
      if conn is not None:
          pool.release(conn, account)  # RSET и возврат в пул
  ```

  ## aiosmtplib vs smtplib

  - **smtplib** — в `_test_smtp_sync` (тест) и `_send_sync` (кампании через прокси)
  - **smtplib + pool** — в `SmtpConnection` (smtp_pool.py) для переиспользования
  - **aiosmtplib** — DEAD CODE в `_send_aiosmtp()` (только для no-proxy режима, отключён)

  Для тестирования соединения: `smtplib` проще и надёжнее через raw socket.
  Для кампаний: `smtplib` через пул (`smtp_pool.py`).

  ## Event loop в многопоточном коде

  ```python
  # ❌ НЕЛЬЗЯ: шарить event loop между потоками
  self._loop = asyncio.get_event_loop()
  threading.Thread(target=lambda: self._loop.run_until_complete(coro())).start()

  # ✅ Каждый поток создаёт свой loop
  def _worker_thread():
      loop = asyncio.new_event_loop()
      asyncio.set_event_loop(loop)
      try:
          loop.run_until_complete(coro())
      finally:
          loop.close()
  ```

  ## SSL Context для SMTP

  ```python
  import ssl
  ctx_strict = ssl.create_default_context()
  ctx_nocheck = ssl.create_default_context()
  ctx_nocheck.check_hostname = False
  ctx_nocheck.verify_mode = ssl.CERT_NONE
  ```
  