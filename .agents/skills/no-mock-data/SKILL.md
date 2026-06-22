---
name: no-mock-data
description: Запрет любых моковых данных в продакшн коде FMailSender. Активируй ВСЕГДА при code review и перед релизом.
---

# No Mock Data Skill — Абсолютный запрет

## Что такое моковые данные (ЗАПРЕЩЕНО)

```python
# ❌ Захардкоженные тестовые аккаунты
TEST_ACCOUNTS = [
    {"email": "test@gmail.com", "password": "test123"},
    {"email": "demo@outlook.com", "password": "demo456"},
]

# ❌ Фиктивные прокси
DEFAULT_PROXIES = ["socks5://1.2.3.4:1080", "http://5.6.7.8:8080"]

# ❌ Захардкоженные API ключи или токены
API_KEY = "sk-test-xxxxxxxxxxxx"
DEMO_TOKEN = "eyJhbGciOiJIUzI1NiJ9..."

# ❌ Заглушки-функции
def send_email(account, msg):
    return True  # TODO: implement

# ❌ Статические демо-данные в UI
def _load_demo_accounts():
    return [{"email": "demo@example.com", "status": "Валидный"}]

# ❌ Фейковые результаты валидации
def validate_smtp(acc):
    return True, "OK (mock)"  # МОКА!
```

## Что допустимо

```python
# ✅ Реальные данные из файла пользователя
def _load_accounts(self) -> list[SmtpAccount]:
    path = DATA_DIR / "accounts.json"
    if not path.exists():
        return []  # пустой список — ОК
    with open(path) as f:
        return [SmtpAccount(**d) for d in json.load(f)]

# ✅ Пустые дефолты без данных
accounts: list[SmtpAccount] = field(default_factory=list)

# ✅ Конфигурации без данных (только структура)
SMTP_CONFIGS = {
    "gmail.com": {"host": "smtp.gmail.com", "port": 465, "use_ssl": True}
    # это конфигурация, не данные
}

# ✅ Тесты с реальными SMTP (помечены @pytest.mark.integration)
@pytest.mark.skipif(not os.getenv("TEST_EMAIL"), reason="No test credentials")
def test_real_smtp():
    ...
```

## Где чаще всего прячутся моки

1. `if __name__ == "__main__":` блоки с тестовыми данными
2. `TODO:` комментарии со заглушками
3. Функции с `pass` или `return True` без реализации
4. Захардкоженные email/proxy строки где угодно
5. `demo_mode` / `test_mode` флаги

## Как проверить

```bash
# Поиск захардкоженных email адресов
grep -rn "@gmail\|@outlook\|@yahoo\|@hotmail" --include="*.py" . | grep -v "#" | grep -v "smtp.gmail"

# Поиск фейковых функций
grep -rn "return True\s*#.*mock\|return True\s*#.*TODO\|return True\s*#.*fake" --include="*.py" .

# Поиск test/demo/mock переменных
grep -rn "TEST_\|DEMO_\|MOCK_\|FAKE_" --include="*.py" . | grep -v "^#"

# Поиск test данных
grep -rn "test123\|password123\|demo456\|example\.com" --include="*.py" .
```

## В тестах

Тесты (`tests/`) — единственное место где допустимы моки, но:
- Используй `unittest.mock.Mock`, `patch` — не хардкод
- Помечай через `@pytest.mark.integration` тесты с реальными данными
- Тесты НЕ попадают в production EXE (исключить из PyInstaller)
