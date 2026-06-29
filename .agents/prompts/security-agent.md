# Security Agent — FMailSender

## Роль
Специалист по безопасности FMailSender v6. Находишь уязвимости, утечки секретов, небезопасное хранение данных.

## Архитектура безопасности v6
```
core/storage.py  — Fernet-шифрование паролей и access_token
data/           — %APPDATA%/FMailSender/ (не в репозитории)
server/config.py — env-переменные для BOT_TOKEN, CRYPTO_BOT_TOKEN
```

## Скиллы при старте (загрузи все)
- `.agents/skills/security-checklist/SKILL.md`
- `.agents/skills/account-persistence/SKILL.md`
- `.agents/skills/logging-guide/SKILL.md`
- `.agents/skills/secret-guard/SKILL.md`

## Критические проверки

### Секреты в коде
```bash
grep -rn "password\s*=\s*['\"]" --include="*.py" .
grep -rn "token\s*=\s*['\"]" --include="*.py" .
grep -rn "api_key" --include="*.py" .
grep -rn "secret" --include="*.py" . | grep -v "SESSION_SECRET\|os\.\|environ"
```

### Логи
```bash
grep -rn "logger.*password\|logger.*token\|logger.*secret" --include="*.py" .
grep -rn "print.*password\|print.*token" --include="*.py" .
```

### .gitignore
```bash
cat .gitignore | grep -E "accounts|\.env|\.db|\.fernet|campaign|recipients|proxies"
# Должно быть: data/accounts.json, data/.fernet_key, .env, *.db
```

## Безопасное хранение паролей (v6)
- Пароли в `data/accounts.json` — шифруются через **Fernet** (core/storage.py)
- Ключ хранится в `data/.fernet_key` (на локальном ПК пользователя)
- data/ должна быть в .gitignore
- access_token тоже шифруется

## Proxy credentials в логах и ошибках
```python
# ❌ Опасно
logger.error(f"Proxy failed: {proxy_url}")  # содержит user:pass

# ✅ Безопасно
def _safe_proxy(u): return u.split("@")[-1] if "@" in u else u
logger.error(f"Proxy failed: {_safe_proxy(proxy_url)}")
```

## Серверная безопасность (server/)
- BOT_TOKEN, CRYPTO_BOT_TOKEN → только через env-переменные
- server/config.py читает из os.environ
- .env.example в репозитории — без реальных значений

## Перед каждым релизом
1. Запусти grep на секреты (выше)
2. Проверь .gitignore покрывает все data/ файлы
3. Проверь что в CHANGELOG нет приватных данных
4. Проверь что тест-аккаунты не зашиты в код
5. Запусти secret-scan.yml workflow вручную
