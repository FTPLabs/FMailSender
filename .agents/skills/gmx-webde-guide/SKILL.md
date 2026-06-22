---
name: gmx-webde-guide
description: GMX / web.de SMTP специфика — включение SMTP, ошибки 535, лимиты. Активируй при работе с gmx.com/gmx.de/web.de аккаунтами.
---

# GMX / web.de SMTP Guide

## Конфигурация

```python
"gmx.com": {"host": "mail.gmx.net",  "port": 587, "use_ssl": False, "use_tls": True},
"gmx.de":  {"host": "mail.gmx.net",  "port": 587, "use_ssl": False, "use_tls": True},
"gmx.net": {"host": "mail.gmx.net",  "port": 587, "use_ssl": False, "use_tls": True},
"web.de":  {"host": "smtp.web.de",   "port": 587, "use_ssl": False, "use_tls": True},
```

Pattern: `("gmx.", _GMX)` в `_SMTP_DOMAIN_PATTERNS` покрывает gmx.*

## Диагностика (из боевых тестов, июнь 2026)

- **Success rate:** ~60% при включённом SMTP
- **Основная проблема:** SMTP отключён по умолчанию (требует ручного включения)
- **Второстепенная проблема:** Rate limit при MAX_CONCURRENT > 4

## Включение SMTP в GMX

1. Зайти на `gmx.com`
2. Email → Settings (шестерёнка) → POP3 & IMAP
3. Раздел "Send Emails via External Client"
4. Включить: "Send emails via Thunderbird, Outlook or another email client"
5. Сохранить

## Включение SMTP в web.de

1. `web.de` → E-Mail → Einstellungen (Settings)
2. POP3/IMAP-Zugriff → aktivieren

## Частые ошибки

| Ошибка | Причина | Решение |
|--------|---------|---------|
| 535 Authentication failed | SMTP отключён в настройках | Включить SMTP (инструкция выше) |
| 535 Wrong password | Неверный пароль | Проверить/сменить пароль |
| 550 blocked | IP заблокирован | Сменить прокси |
| 421 Too many connections | Rate limit | MAX_CONCURRENT=4 |

## _parse_auth_error (core/sender.py)

```python
if any(s in h for s in ["gmx", "web.de", "t-online"]):
    if "535" in d or "authentication" in d:
        return (
            "Неверный логин/пароль GMX.\n"
            "Причина: SMTP отключён в настройках.\n"
            "Решение: gmx.com → Settings → POP3 & IMAP → Enable SMTP."
        )
    if "550" in d and "blocked" in d:
        return "GMX: аккаунт заблокирован. Войдите на gmx.com и разблокируйте."
```
