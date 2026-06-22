---
name: debug-network
description: Отладка сетевых и прокси проблем в FMailSender. Активируй при неожиданных CONN_ERROR, proxy-related крэшах, SMTP connection debugging.
---

# Network Debugging Guide

## Диагностика прокси

```bash
# Тест SOCKS5 прокси на SMTP порт
curl --proxy socks5h://user:pass@proxy:port smtp://smtp.gmail.com:465 --connect-timeout 10 -v

# Тест HTTP прокси
curl --proxy http://user:pass@proxy:port smtp://smtp.gmail.com:465 --connect-timeout 10

# Результат "220 smtp.gmail.com ESMTP" = работает
# "cannot complete SOCKS5 (1)" = General Failure = PROXY_BLOCKS_SMTP
# "Recv failure" = timeout или сеть недоступна
```

```python
# Python быстропроверка прокси (stdlib)
import socket, struct

s = socket.socket()
s.settimeout(10)
s.connect(("proxy_host", proxy_port))

# SOCKS5 greeting
s.sendall(b"\x05\x01\x00")  # без аутентификации
resp = s.recv(2)
if resp == b"\x05\x00":
    print("SOCKS5 OK — no auth")
elif resp == b"\x05\x02":
    print("SOCKS5 OK — auth required")
elif resp == b"\x05\xff":
    print("SOCKS5 rejected all auth methods")
```

## Диагностика SMTP без прокси

```bash
# Прямое подключение (SSL)
openssl s_client -connect smtp.gmail.com:465 -quiet
# Ответ "220 ..." = ОК; timeout = порт закрыт/firewall

# Прямое подключение (STARTTLS)
openssl s_client -connect smtp.office365.com:587 -starttls smtp
```

## Python — minimal SMTP test

```python
import smtplib, ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# SSL on port 465
with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx, timeout=10) as s:
    s.login("user@gmail.com", "app_password")
    print("OK")
```

## Общие проблемы и решения

| Симптом | Причина | Решение |
|---------|---------|---------|
| PROXY_BLOCKS_SMTP | Прокси блокирует SMTP-порты | Residential/SMTP прокси |
| 535 AUTH FAIL | Неверный пароль или нет App Password | App Password |
| 421 Too many connections | MAX_CONCURRENT слишком высокий | MAX_CONCURRENT = 4 |
| Timeout на pre-check | Медленный прокси | Не классифицировать как PROXY_BLOCKS (v4.4.0+) |
| Пустые флаги стран | ip-api.com rate limit | Semaphore(3) + кэш |
| Страна пропадает | Нет кэша, _refresh_table сбрасывает | _proxy_country_cache (v4.4.0+) |

## Логирование сетевых ошибок

```python
except Exception as e:
    logger.debug(
        "SMTP connection failed: host=%s port=%d proxy=%s error=%s",
        host, port, _safe_proxy(proxy_url), type(e).__name__
    )
```
