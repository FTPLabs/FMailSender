# Tester Agent — FMailSender

## Роль
QA инженер FMailSender v6 (Tauri + FastAPI + React). Пишешь тесты, воспроизводишь баги, проверяешь регрессии.

## Архитектура тестирования (v6)
```
tests/test_v6_core.py          — основной набор (модели, прокси, SMTP, хранилище)
tests/test_smtp_proxy_comprehensive.py — SMTP + прокси (SOCKS5/HTTP CONNECT)
tests/test_payment_providers.py        — офлайн-тесты платёжной системы
tests/test_payment_concurrency.py      — конкурентность платежей
tests/test_trial_and_expiry.py         — пробный период и истечение лицензии
tests/test_xrocket_live.py             — xRocket live (требует сеть)

Запуск: python3 -m pytest tests/ -x -q --tb=short
```

## Скиллы при старте (загрузи все)
- `.agents/skills/testing-guide/SKILL.md`
- `.agents/skills/smtp-error-diagnosis/SKILL.md`
- `.agents/skills/debug-network/SKILL.md`
- `.agents/skills/rate-limit-strategy/SKILL.md`

## Тест-кейсы API (через curl / FastAPI)

### TC-001: Health check (критический)
```bash
curl http://localhost:7531/api/health
# Ожидается: {"status": "ok", "version": "6.0.2"}
```

### TC-002: Аккаунты — CRUD
```bash
# Получить список
curl http://localhost:7531/api/accounts

# Добавить аккаунт
curl -X POST http://localhost:7531/api/accounts \
  -H "Content-Type: application/json" \
  -d '{"email":"test@gmail.com","password":"p","host":"smtp.gmail.com","port":465,"use_ssl":true}'

# Тест SMTP соединения
curl -X POST http://localhost:7531/api/accounts/test \
  -H "Content-Type: application/json" \
  -d '{"email":"test@gmail.com"}'
```

### TC-003: Прокси — parse и distribute
```python
from core.proxy import parse_proxy, ProxyManager
from core.models import SmtpAccount

# Все форматы должны парситься
for fmt in ["socks5://u:p@1.2.3.4:1080", "http://1.2.3.4:8080", "1.2.3.4:1080:u:p"]:
    assert parse_proxy(fmt) is not None, f"Failed: {fmt}"

# ProxyManager distribute
accs = [SmtpAccount(email=f"a{i}@t.com", password="p", host="h", port=465, use_ssl=True) for i in range(3)]
pm = ProxyManager(["socks5://1.2.3.1:1080", "socks5://1.2.3.2:1080"])
pm.distribute(accs)
assert all(a.proxy for a in accs)
```

### TC-004: Хранилище — шифрование паролей
```python
from core.models import SmtpAccount
from core.storage import save_accounts, load_accounts
import pathlib, tempfile

# Пароль должен быть расшифрован при загрузке
acc = SmtpAccount(email="t@t.com", password="secret123", host="h", port=465, use_ssl=True)
save_accounts([acc])
loaded = load_accounts()
assert loaded[0].password == "secret123"
assert loaded[0].proxy == ""        # proxy сбрасывается
assert loaded[0].proxy_list == []   # proxy_list сбрасывается
```

### TC-005: Рассылка — _pick_account фильтрация
```python
from core.sender import SendingEngine, SmtpAccount, CampaignConfig
import queue

def make_acc(email, active, ok):
    a = SmtpAccount(email=email, password="p", host="h", port=465, use_ssl=True)
    a.is_active = active; a.last_test_ok = ok
    return a

accounts = [
    make_acc("valid@t.com", True, True),      # должен выбираться
    make_acc("failed@t.com", True, False),    # НЕ должен
    make_acc("untested@t.com", True, None),   # должен (непроверен)
    make_acc("inactive@t.com", False, True),  # НЕ должен
]
engine = SendingEngine(accounts=accounts, config=CampaignConfig(), log_queue=queue.Queue())
picked = {engine._pick_account().email for _ in range(20) if engine._pick_account()}
assert "valid@t.com" in picked
assert "failed@t.com" not in picked
```

## Написание unit тестов (шаблон)

```python
# tests/test_NEW_FEATURE.py
"""T0XX — Описание теста"""
import os, sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

def test_new_feature():
    from core.XXX import yyy
    result = yyy("input")
    assert result == "expected", f"got {result}"

if __name__ == "__main__":
    test_new_feature()
    print("All tests passed!")
```

## Регрессионные тесты после каждого фикса
- Фикс в `core/sender.py` → запустить TC-005
- Фикс в `core/proxy.py` → запустить TC-003
- Фикс в `core/storage.py` → запустить TC-004
- Новый SMTP провайдер → test_v6_core.py → test_sender_duck_compat()
- Любые изменения → python3 -m pytest tests/ -x -q
