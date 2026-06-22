---
name: logging-guide
description: Logging паттерны в FMailSender — где логировать, как, что запрещено. Активируй при добавлении логов, отладке проблем в production.
---

# Logging Guide

## Правила

1. **Никаких `print()`** в production коде
2. **Никаких `console.log`** (это Python, не JS)
3. **Пароли и токены НЕ логируются никогда**
4. **Уровни:** DEBUG (детали), INFO (события), WARNING (проблемы), ERROR (ошибки)

## Инициализация

```python
import logging
logger = logging.getLogger(__name__)
# Не настраивай handlers здесь — это делает main.py
```

## Уровни логирования

```python
logger.debug("Детали: proxy=%s port=%d", _safe_proxy(proxy), port)
logger.info("Аккаунт %s подключён через прокси", email)
logger.warning("Rate limit от %s, замедление", host)
logger.error("Ошибка подключения к %s: %s", host, error)
logger.exception("Неожиданное исключение")  # включает traceback
```

## Что логировать

✅ МОЖНО:
- SMTP хост и порт
- Код ошибки SMTP (535, 421 и т.д.)
- Email адрес (без пароля)
- Прокси (только host:port, без credentials)
- Время операции

❌ НЕЛЬЗЯ:
- Пароли (`account.password`)
- Access token, refresh token
- Полную прокси-строку с credentials
- Приватные ключи

## _safe_proxy helper

```python
def _safe_proxy(proxy_url: str) -> str:
    try:
        p = urllib.parse.urlparse(proxy_url)
        return f"{p.scheme}://{p.hostname}:{p.port}"
    except Exception:
        return "***proxy***"
```

## Настройка в main.py

```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("logs/fmailsender.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
```

## GUI — не используй logger напрямую

В GUI потоках не вызывай logger — он потокобезопасен, но записи могут перемешаться.
Лучше emit сигнал и логируй в main thread:
```python
# Worker
self.log_message.emit(f"Подключён {email}")
# Main thread
def _on_log(msg): logger.info(msg)
```
