---
name: oauth2-microsoft
description: Microsoft OAuth2 для Outlook/Hotmail — refresh_token, access_token, XOAUTH2 SMTP. Активируй при работе с Outlook аккаунтами, ошибках 5.7.139, OAuth2 flow.
---

# Microsoft OAuth2 — Outlook SMTP

## XOAUTH2 vs Basic Auth

Microsoft отключил Basic Auth (LOGIN/PLAIN) для потребительских аккаунтов в 2023.
Нужен: `AUTH XOAUTH2` + `access_token`

## Токены

| Поле | Назначение | TTL |
|------|-----------|-----|
| `access_token` | Bearer для SMTP AUTH XOAUTH2 | 1 час |
| `refresh_token` | Обновление access_token | Бессрочно (до отзыва) |
| `token_expires_at` | Unix timestamp истечения | — |

## Refresh flow (core/oauth2_refresh.py)

```python
async def refresh_ms_token(account: SmtpAccount) -> bool:
    """Обновляет access_token если истёк. True если успешно."""
    if time.time() < account.token_expires_at - 60:
        return True  # токен ещё валиден
    
    resp = await httpx.AsyncClient().post(
        "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": account.refresh_token,
            "client_id": MS_CLIENT_ID,
            "scope": "https://outlook.office.com/SMTP.Send offline_access"
        }
    )
    if resp.status_code == 200:
        data = resp.json()
        account.access_token = data["access_token"]
        account.token_expires_at = time.time() + data.get("expires_in", 3600)
        return True
    return False
```

## SMTP AUTH XOAUTH2

```python
# В smtplib
token = base64.b64encode(
    f"user={email}\x01auth=Bearer {access_token}\x01\x01".encode()
).decode()
smtp.docmd("AUTH", f"XOAUTH2 {token}")
```

## Импорт аккаунтов (pipe-формат)

```
email@outlook.com|password|refresh_token
```
Парсится в BulkImportWorker: `if _sep == "|" and len(parts) >= 3: acc.refresh_token = parts[2]`

## Проблемы

- **5.7.139**: Basic Auth отключён → нужен OAuth2
- **invalid_grant**: refresh_token истёк/отозван → нужна повторная авторизация
- **AADSTS53003**: Conditional Access блокирует → Enterprise аккаунт с ограничениями
