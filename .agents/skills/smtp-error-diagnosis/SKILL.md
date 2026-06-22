---
name: smtp-error-diagnosis
description: Диагностика SMTP-ошибок по провайдерам. Активируй когда видишь AUTH_FAIL, CONN_ERROR, TIMEOUT или пользователь жалуется на ошибки при проверке аккаунтов.
---

# SMTP Error Diagnosis

## Коды ошибок FMailSender

| Код внутри | SMTP код | Причина |
|-----------|----------|---------|
| AUTH_FAIL | 535 | Неверный пароль или нет App Password |
| CONN_ERROR | — | Прокси/сеть блокирует соединение |
| TIMEOUT | — | Прокси медленный или хост не отвечает |
| PROXY_BLOCKS_SMTP | — | SOCKS5 General Failure на SMTP-порту |
| CERT_ERROR | — | SSL сертификат невалиден |

## По провайдерам

### Gmail (smtp.gmail.com:465)
- **534 / application-specific** → Нужен App Password (2FA включена)
- **535** → Неверный пароль или не App Password
- **Fix:** myaccount.google.com → Security → App Passwords

### Microsoft/Outlook (smtp.office365.com:587)
- **5.7.139 basic auth disabled** → Включить SMTP AUTH в M365 Admin
- **535 5.7.3** → Нужен App Password
- **Fix:** account.microsoft.com → Security → App Passwords

### Rambler (smtp.rambler.ru:465)
- **535 Invalid login** → Пароль устарел, аккаунт заблокирован
- **Fix:** rambler.ru → Settings → Security → Change password
- **Success rate:** 100% при рабочем пароле и residential прокси

### GMX / web.de (mail.gmx.net:587, smtp.web.de:587)
- **535 auth failed** → SMTP отключён в настройках
- **Fix:** gmx.com → Email → Settings → POP3 & IMAP → Enable SMTP
- **Success rate:** ~60% (40% отключили SMTP или Auth 535)

### Yahoo (smtp.mail.yahoo.com:465)
- **535** → Нужен App Password
- **Fix:** security.yahoo.com → Manage App Passwords

## Универсальные

- **421** → Rate limit: слишком много одновременных соединений → снизить MAX_CONCURRENT до 4
- **550 blocked** → IP заблокирован → сменить прокси (нужен residential)
- **Connection refused** → Неверный порт или firewall → проверить порт и прокси
- **Timeout** → Прокси медленный или хост не отвечает → увеличить timeout или сменить прокси

## Функция _parse_auth_error (core/sender.py)
Возвращает человекочитаемое сообщение по хосту + коду + деталям.
Всегда обновляй её при добавлении нового провайдера.
