---
name: error-messages-ru
description: Написание понятных ошибок на русском для пользователей FMailSender. Активируй при написании error messages, улучшении пользовательского опыта, переводе технических ошибок.
---

# Error Messages (Russian UX)

## Принципы

1. **Понятно** — без технических терминов (не "SOCKS5 General Failure", а "прокси не поддерживает SMTP")
2. **Actionable** — что сделать пользователю
3. **Конкретно** — какой провайдер, какой порт, что именно не работает
4. **Коротко** — первая строка = суть, остальное в tooltip

## Шаблоны

### Ошибка подключения
```
# ❌ Плохо
"Connection error: [Errno 111] Connection refused"

# ✅ Хорошо  
"Прокси не может подключиться к {host}:{port}.\n"
"Причина: прокси блокирует SMTP-порты.\n"
"Решение: используйте residential или SMTP-dedicated прокси."
```

### Ошибка авторизации
```
# ❌ Плохо
"535 5.7.8 Error: authentication failed"

# ✅ Хорошо
"GMX: неверный пароль или SMTP отключён.\n"
"Решение: gmx.com → Settings → POP3 & IMAP → Enable SMTP."
```

### Timeout
```
# ❌ Плохо
"TimeoutError after 30s"

# ✅ Хорошо
"Таймаут подключения к {host}:{port} через прокси.\n"
"Прокси может быть медленным или недоступным.\n"
"Попробуйте другой прокси."
```

## Функции форматирования

```python
# core/sender.py
def _parse_auth_error(host: str, smtp_code: int, detail: str) -> str:
    """Возвращает человекочитаемое сообщение по провайдеру."""
    # Добавляй новые провайдеры сюда
```

## Формат в таблице аккаунтов

- **Короткий текст** в ячейке (до 55 символов)
- **Полная ошибка** в tooltip (setToolTip)
- Цвет: ERROR (#EF4444) для ошибки, SUCCESS (#10B981) для ОК

```python
first_line = error_msg.split('\n')[0]
status_item.setText(first_line[:55])
status_item.setToolTip(error_msg)
```

## Словарь терминов (технический → пользовательский)

| Технический | Для пользователя |
|-------------|-----------------|
| SOCKS5 General Failure | прокси блокирует SMTP-порты |
| AUTH_FAIL 535 | неверный пароль или нужен App Password |
| Connection refused | порт закрыт или прокси неверный |
| Timeout | медленный прокси или сервер недоступен |
| PROXY_BLOCKS_SMTP | прокси не поддерживает SMTP |
| SSL certificate error | проблема с SSL сертификатом сервера |
