---
name: smtp-auth-methods
description: SMTP AUTH методы — PLAIN, LOGIN, XOAUTH2, CRAM-MD5. Активируй при ошибках AUTH, добавлении нового провайдера, отладке аутентификации.
---

# SMTP AUTH Methods

## Поддерживаемые методы

| Метод | Безопасность | Провайдеры |
|-------|-------------|-----------|
| AUTH PLAIN | Base64 (нужен TLS) | Gmail, GMX, большинство |
| AUTH LOGIN | Base64 (нужен TLS) | Outlook, legacy |
| AUTH XOAUTH2 | OAuth2 Bearer | Gmail, Microsoft |
| AUTH CRAM-MD5 | HMAC-MD5 | Старые серверы |

## AUTH PLAIN (стандартный)

```
C: AUTH PLAIN <base64(user\0user\0password)>
S: 235 2.7.0 Authentication successful
```

```python
import base64
# smtplib делает это автоматически при login()
smtp.login(email, password)
```

## AUTH XOAUTH2 (Microsoft/Google OAuth2)

```python
# Формат: base64("user=email\x01auth=Bearer TOKEN\x01\x01")
token_string = f"user={email}\x01auth=Bearer {access_token}\x01\x01"
auth_string = base64.b64encode(token_string.encode()).decode()
smtp.docmd("AUTH", f"XOAUTH2 {auth_string}")
```

## Коды ошибок AUTH

| Код | Значение |
|-----|---------|
| 235 | Authentication successful |
| 334 | Server challenge (CRAM-MD5) |
| 432 | Password transition needed |
| 534 | Auth mechanism not supported |
| 535 | Authentication credentials invalid |
| 538 | Encryption required for auth |

## В _test_smtp_sync (core/sender.py)

```python
# Обычный login
smtp.login(account.email, account.password)

# XOAUTH2 для Outlook
if _is_oauth_acct:
    # refresh token если нужно
    token = await _refresh_ms_oauth_token(account)
    # AUTH XOAUTH2
    _xoauth2_auth(smtp, account.email, token)
```

## Почему 535 не всегда = неверный пароль

- Gmail: нужен App Password (не обычный пароль)
- GMX: SMTP отключён в настройках
- Microsoft: Basic Auth отключён → нужен XOAUTH2
- Rambler: аккаунт заблокирован или пароль устарел

## Отладка AUTH

```python
import smtplib
smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465)
smtp.set_debuglevel(2)  # включить отладочный вывод
smtp.login("user@gmail.com", "app_password")
```
