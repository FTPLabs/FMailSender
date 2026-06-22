---
name: rambler-specifics
description: Rambler Mail SMTP специфика — настройки, ошибки, ограничения. Активируй при работе с rambler.ru / lenta.ru / championat.com аккаунтами.
---

# Rambler SMTP Specifics

## Конфигурация

```python
"rambler.ru":    {"host": "smtp.rambler.ru", "port": 465, "use_ssl": True},
"lenta.ru":      {"host": "smtp.rambler.ru", "port": 465, "use_ssl": True},
"championat.com":{"host": "smtp.rambler.ru", "port": 465, "use_ssl": True},
```

## Диагностика (из боевых тестов, июнь 2026)

- **Success rate:** 100% при рабочем пароле + residential прокси
- **Основная проблема:** устаревший пароль или заблокированный аккаунт
- **ВАЖНО:** Datacenter-прокси (FoxyProxy и т.п.) БЛОКИРУЮТ SMTP → нужен residential

## Частые ошибки

| Ошибка | Причина | Решение |
|--------|---------|---------|
| 535 Invalid login/password | Устаревший пароль | Сменить на rambler.ru |
| 535 Invalid login/password | Аккаунт заблокирован | Разблокировать через сайт |
| Too many login attempts | Rate limit | Подождать 5-10 минут |
| Connection timeout | Datacenter прокси | Сменить на residential |

## _parse_auth_error (core/sender.py)

```python
if "rambler" in h or "lenta" in h or "championat" in h:
    if "invalid login" in d or "535" in d:
        return (
            "Неверный логин/пароль Rambler.\n"
            "Причина: пароль устарел или аккаунт заблокирован.\n"
            "Решение: зайдите на rambler.ru → Настройки → Безопасность → смените пароль."
        )
    if "too many" in d or "rate" in d:
        return "Rambler: слишком много попыток. Подождите 5-10 минут."
```

## Смена пароля Rambler

1. Зайти на `rambler.ru`
2. Настройки → Безопасность → Изменить пароль
3. Использовать новый пароль в FMailSender

## Прокси для Rambler

Rambler блокирует datacenter IP на SMTP уровне.
Нужен:
- Residential прокси (Bright Data, Oxylabs, Smartproxy)
- SSH-туннель через VPS с российским IP
- Мобильные прокси (4G/LTE)
