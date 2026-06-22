---
name: async-smtp-guide
description: asyncio SMTP паттерны в FMailSender — aiosmtplib, event loop в потоках, test_smtp_connection. Активируй при работе с async SMTP, отладке event loop ошибок.
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

## aiosmtplib vs smtplib

- **smtplib** — в `_test_smtp_sync` и `_make_smtp` в `sender.py` (через proxy-socket)
- **aiosmtplib** — в async отправке `send_email_async()` (batch sending)

Для тестирования соединения: `smtplib` проще и надёжнее через raw socket.

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
