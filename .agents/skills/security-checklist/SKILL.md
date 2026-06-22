---
name: security-checklist
description: Security checklist для FMailSender. Активируй при code review, перед релизом, при работе с паролями/токенами/прокси-кредами.
---

# Security Checklist

## НИКОГДА не делай

- [ ] Не хардкодь пароли, токены, ключи в коде
- [ ] Не логируй пароли, access_token, refresh_token
- [ ] Не отправляй пароли в error messages пользователю
- [ ] Не храни пароли в plaintext в git

## Проверки перед каждым коммитом (secret-guard)

```bash
# Ищем утечки секретов
grep -rn "password\s*=\s*['\"][^'\"]\+['\"]" --include="*.py" .
grep -rn "token\s*=\s*['\"][^'\"]\+['\"]" --include="*.py" .
grep -rn "api_key\s*=\s*['\"]" --include="*.py" .
```

## Хранение паролей

**Текущий подход (data/accounts.json):** пароли в plaintext JSON.
- ⚠️ Приемлемо для desktop app (файл на локальном ПК)
- Файл должен быть в `.gitignore`
- Для production: рассмотри Fernet encryption (уже есть `from cryptography.fernet import Fernet`)

## Proxy credentials

Прокси-строки вида `socks5://user:pass@host:port` содержат пароли.
- НЕ логируй полную строку прокси
- В error messages показывай только `host:port` без креденциалов
- `proxy_url.split("@")[-1]` — безопасная часть

```python
# Безопасное логирование прокси
def _safe_proxy(proxy_url: str) -> str:
    try:
        from urllib.parse import urlparse
        p = urlparse(proxy_url)
        return f"{p.scheme}://{p.hostname}:{p.port}"
    except Exception:
        return "***"
```

## OAuth2 токены

- `access_token` — не логируй, не показывай в UI
- `refresh_token` — критически важен, не логируй
- `token_expires_at` — нейтрально, можно логировать

## SMTP пароли в debug

```python
# ❌ Нельзя
logger.debug(f"AUTH {account.email} {account.password}")

# ✅ Безопасно
logger.debug(f"AUTH {account.email} [*****]")
```

## data/ в .gitignore

```
data/accounts.json
data/global_proxies.json
data/*.db
*.env
.env
```

## SSRF через proxy

При определении страны прокси через ip-api.com — пользователь контролирует proxy_url.
Уже безопасно: используем `urllib.request.ProxyHandler` с ограниченным URL.
Не передавай proxy_url напрямую в shell команды.
