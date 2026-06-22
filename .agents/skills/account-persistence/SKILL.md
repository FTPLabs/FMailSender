---
name: account-persistence
description: SmtpAccount dataclass — поля, хранение, загрузка из JSON. Активируй при добавлении новых полей к аккаунту, исправлении ошибок загрузки/сохранения.
---

# Account Persistence

## SmtpAccount dataclass (core/sender.py)

```python
@dataclass
class SmtpAccount:
    email: str
    password: str
    host: str
    port: int = 465
    use_ssl: bool = True
    use_tls: bool = False
    display_name: str = ""
    daily_limit: int = 500
    hourly_limit: int = 50
    is_active: bool = True
    proxy: str = ""                   # текущий прокси (строка)
    oauth_token: str = ""             # legacy field
    access_token: str = ""            # OAuth2 Bearer token
    refresh_token: str = ""           # OAuth2 refresh token
    token_expires_at: float = 0.0
    imap_host: str = ""
    imap_port: int = 993
    imap_ssl: bool = True
    last_test_ok: Optional[bool] = None
    last_test_msg: str = ""
```

Дополнительные поля (динамически через setattr):
- `proxy_list: list[str]` — все прокси аккаунта
- `proxy_rotation_random: bool` — случайная ротация
- `reply_to: str` — Reply-To адрес
- `sent_today: int`, `sent_this_hour: int` — счётчики

## Функции хранения (gui/screens/screen_accounts.py)

```python
from gui.screens.screen_accounts import save_accounts, load_accounts

accounts = load_accounts()   # → list[SmtpAccount]
save_accounts(accounts)      # сохранить в data/accounts.json
```

## Формат JSON (data/accounts.json)

```json
[
  {
    "email": "user@gmail.com",
    "password": "app_password",
    "host": "smtp.gmail.com",
    "port": 465,
    "use_ssl": true,
    "proxy": "socks5://user:pass@1.2.3.4:1080",
    "proxy_list": ["socks5://user:pass@1.2.3.4:1080"],
    "last_test_ok": true,
    "last_test_msg": "OK via proxy"
  }
]
```

## Добавление нового поля

1. Добавить в `SmtpAccount` dataclass с дефолтом
2. Добавить в `save_accounts` — `d["new_field"] = acc.new_field`
3. Добавить в `load_accounts` — `acc.new_field = d.get("new_field", default)`
4. Обновить `AccountDialog._fill()` и `get_account()`
5. Не ломай backward compatibility — всегда `.get("field", default)`

## Глобальный пул прокси

```python
save_global_proxies(proxies: list[str])  # data/global_proxies.json
load_global_proxies() -> list[str]
distribute_proxies(accounts, proxies)    # round-robin назначение
```
