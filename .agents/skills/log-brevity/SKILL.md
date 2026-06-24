---
name: log-brevity
description: "Правила краткости лог-сообщений: коды ошибок, ограничение длины строк, читаемый лог без мусора."
---

# Log Brevity — Краткость лог-сообщений

## Правило

Все строки в лог-виджете (**screen_sending.py**) должны быть:
- Не длиннее **120 символов** — текст обрезается с «...»
- С **кратким кодом ошибки** в начале или конце (например `[E535]`, `[TIMEOUT]`)
- **Без технических stacktrace** — только суть ошибки

## Реализация

```python
# В _flush_log_queue: ограничить длину
if len(_msg) > 120:
    _msg = _msg[:117] + "..."

# В sender.py: краткие коды ошибок в log messages
# 535 = Auth failed
# 550 = User unknown / blacklisted
# 421 = Server temp unavailable
# E001 = Cancel error
# E002 = Proxy blocked
# E003 = Timeout
```

## Шаблоны краткого лога

```
[10:34:12] user@gmail.com → ok                          # отправка OK
[10:34:13] user2@mail.ru: [535] Неверный пароль         # auth error
[10:34:14] user3@yandex.ru: [E002] IP прокси заблокирован  # proxy error
[10:34:15] user4@hotmail.com: [TIMEOUT] Нет ответа 30с  # timeout
```

## Чего избегать

❌ Длинные технические stacktrace в лог-виджете
❌ Повторяющиеся однотипные строки без счётчика
❌ ASCII-блоки из urllib.error, smtplib.SMTPException и т.д.
❌ Proxy IP в каждой строке (перегружает лог)

## Как применить

При добавлении нового сообщения в log_queue:
```python
# Хорошо:
f"[{ts}] E535: {email} — неверный пароль"

# Плохо:
f"[{ts}] SMTPAuthenticationError: (535, b'5.7.8 Username and Password not accepted...')"
```
