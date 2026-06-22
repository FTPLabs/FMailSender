---
name: smtp-port-fallback
description: Стратегия перебора SMTP-портов и fallback с прокси на direct. Активируй при ошибках "Проверено N портов" или добавлении нового провайдера.
---

# SMTP Port Fallback Strategy

## Стандартные SMTP-порты

| Порт | Протокол | Провайдеры |
|------|----------|-----------|
| 465 | SSL/TLS | Gmail, Rambler, Yahoo, GMX |
| 587 | STARTTLS | Outlook, GMX, web.de, большинство |
| 25 | Открытый | Только сервер-к-серверу (ISP блокируют) |
| 2525 | STARTTLS | Альтернатива 587 (редко) |

## Fallback в smtp_validator.py

```
Основная конфигурация (port из cfg)
    ↓ PROXY_BLOCKS_SMTP (SOCKS5 General Failure)
Fallback 1: тот же хост, порт 465 SSL
    ↓ снова PROXY_BLOCKS_SMTP
Fallback 2: тот же хост, порт 587 STARTTLS
    ↓ снова PROXY_BLOCKS_SMTP
Fallback 3: прямое соединение (без прокси) порт 465
    ↓ снова ошибка
Fallback 4: прямое соединение порт 587
    ↓ провал
CONN_ERROR — "Не удалось подключиться через N портов"
```

## ВАЖНО: таймаут ≠ PROXY_BLOCKS_SMTP

```python
# v4.4.0+: только явный SOCKS5 General Failure → PROXY_BLOCKS_SMTP
_SOCKS5_BLOCK_SIGNALS = ("general failure", "socks5 error", "not allowed by ruleset")
if any(x in error_msg.lower() for x in _SOCKS5_BLOCK_SIGNALS):
    raise ConnectionError(f"PROXY_BLOCKS_SMTP:...")
# Таймаут, refused → pre-check игнорируется, соединение продолжается
```

## Конфиг провайдеров (core/sender.py _SMTP_CONFIGS)

```python
"gmail.com":  {"host": "smtp.gmail.com",   "port": 465, "use_ssl": True},
"rambler.ru": {"host": "smtp.rambler.ru",  "port": 465, "use_ssl": True},
"gmx.com":    {"host": "mail.gmx.net",     "port": 587, "use_ssl": False, "use_tls": True},
"web.de":     {"host": "smtp.web.de",      "port": 587, "use_ssl": False, "use_tls": True},
"outlook.com":{"host": "smtp.office365.com","port":587, "use_ssl": False, "use_tls": True},
```

## Добавление нового провайдера

1. Добавить в `_SMTP_CONFIGS` в `core/sender.py`
2. Добавить в `smtp_configs_extra.py` если это маловероятный домен
3. Добавить обработку ошибок в `_parse_auth_error()`
4. Обновить CHANGELOG.md
