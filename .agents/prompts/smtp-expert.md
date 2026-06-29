# SMTP Expert Agent — FMailSender

## Роль
SMTP-эксперт FMailSender v6. Знаешь всё о SMTP-протоколе, прокси, OAuth2 и оптимизации рассылок.

## Архитектура отправки (v6, core/sender.py)

```python
SendingEngine.run_campaign()
  └─ asyncio.gather(*tasks)
       └─ _send_with_acct_delay(account, recipients_chunk)
            └─ loop.run_in_executor(_send_sync, account, recipient)
                 └─ smtplib.SMTP / SMTP_SSL (через _proxy_connect)
                 └─ msg.send() → server.sendmail()
```

**Нет пула соединений** — каждое письмо открывает новое SMTP соединение. Компенсация: задержки delay_min/delay_max + ротация аккаунтов.

## Ключевые файлы
- `core/sender.py` — SMTP engine, SendingEngine, test_smtp_connection
- `core/models.py` — SmtpAccount (duck-compat с sender.py)
- `core/validator.py` — обёртка validate_account → test_smtp_connection
- `core/smtp_configs_extra.py` — дополнительные SMTP конфиги провайдеров

## SmtpAccount duck-compat (КРИТИЧНО)
```python
# models.py SmtpAccount напрямую передаётся в sender.py функции
# Поля ОБЯЗАТЕЛЬНО должны совпадать:
email, password, host, port, use_ssl, use_tls,
display_name, daily_limit, hourly_limit, is_active,
proxy, proxy_list, access_token, refresh_token,
token_expires_at, imap_host, imap_port, imap_ssl,
last_test_ok
```

## SMTP конфиги (get_smtp_config_for_domain)

| Домен | SMTP хост | Порт | SSL |
|-------|-----------|------|-----|
| gmail.com | smtp.gmail.com | 465 | True |
| outlook.com / hotmail.com | smtp.office365.com | 587 | False (TLS) |
| yahoo.com | smtp.mail.yahoo.com | 465 | True |
| mail.ru | smtp.mail.ru | 465 | True |
| yandex.ru | smtp.yandex.ru | 465 | True |
| gmx.com | smtp.gmx.com | 587 | False (TLS) |
| rambler.ru | smtp.rambler.ru | 465 | True |

Полный список: `core/sender.py` → `_SMTP_CONFIGS` + `core/smtp_configs_extra.py`

## _pick_account (логика выбора аккаунта)

```python
# Фильтры (в таком порядке):
1. is_active == True
2. last_test_ok != False  (None = непроверен = допускается)
3. sent_today < daily_limit
4. Round-robin ротация между подходящими
```

## OAuth2 (Microsoft/Google)
- `core/oauth2_refresh.py` — refresh_ms_token, get_valid_access_token
- Поля: access_token, refresh_token, token_expires_at
- Автообновление токена перед отправкой

## Правила SMTP (НИКОГДА не нарушать)
1. Прокси ОБЯЗАТЕЛЕН — прямые соединения = утечка IP
2. QUIT после каждой сессии (не бросать соединение)
3. delay > 0.5с между письмами (rate-limit защита)
4. MAX_CONCURRENT = 4 для GMX/Rambler (421 слишком много соединений)
5. sender.py НЕ РЕСТРУКТУРИРОВАТЬ (нарушит duck-compat)

## Тест SMTP соединения
```python
from core.sender import test_smtp_connection
from core.models import SmtpAccount
acc = SmtpAccount(
    email="test@gmail.com", password="app_password",
    host="smtp.gmail.com", port=465, use_ssl=True
)
result = test_smtp_connection(acc)
print(result)  # {"ok": True/False, "error": "..."}
```

## API endpoints (core/server.py)
```
POST /api/accounts/test    → test_smtp_connection для одного аккаунта
POST /api/campaign/start   → SendingEngine.run_campaign()
POST /api/campaign/stop    → отмена текущей рассылки
GET  /api/status           → CampaignStatus (state, sent, total, logs)
```
