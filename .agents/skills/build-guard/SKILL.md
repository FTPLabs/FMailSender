---
name: build-guard
description: Проверяет готовность проекта к сборке .exe через PyInstaller и к созданию GitHub Release. Активируй перед любым запуском build.py, github push с тегом, или ручным workflow_dispatch. Обнаруживает: bitchin CI/блокеры PyInstaller 6.x, отсутствующие hiddenimports, неверные параметры aiosmtplib, module-level sys.exit(), устаревший datetime.utcnow().
---

# Build Guard — Проверка перед сборкой EXE и релизом

## Когда использовать

- Перед `python build.py` или `pyinstaller FMailSender.spec`
- Перед пушем тега `v*` (триггер GitHub Actions build.yml)
- Перед ручным запуском workflow_dispatch с tag_name
- После любых изменений в `core/`, `gui/`, `main.py`, `build.py`
- Когда EXE падает при запуске с ImportError или ModuleNotFoundError

## Блок 1 — PyInstaller 6.x совместимость

```bash
# PyInstaller >= 6.0 убрал параметр cipher= из PYZ() и EXE()
grep -n "cipher=block_cipher\|cipher=None" build.py FMailSender.spec 2>/dev/null \
  && echo "FAIL: устаревший cipher= параметр — удали его" || echo "OK: cipher= не найден"

# Проверка что block_cipher не передаётся
grep -n "pyz = PYZ\|exe = EXE" build.py | grep -v "#"
```

**Исправление:**
```python
# ❌ PyInstaller < 6.0
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(pyz, ..., cipher=block_cipher)

# ✅ PyInstaller >= 6.0
pyz = PYZ(a.pure, a.zipped_data)
exe = EXE(pyz, ...)
```

## Блок 2 — Критические импорты (module-level sys.exit)

Проверь что ни один `import core.*` не вызывает sys.exit() при отсутствии ENV:

```bash
# Опасный паттерн: _require_env() вызывается на уровне модуля
grep -n "_require_env\|sys.exit" core/license.py | head -20

# ПРАВИЛЬНО: lazy-геттеры вместо module-level вызовов
grep -n "def _get_license_api_url\|def _get_license_verify_url" core/license.py
```

**Ожидаемый результат после фикса v3.3.0:**
- `_get_license_api_url()` и `_get_license_verify_url()` — ленивые функции
- На уровне модуля: только константы, без вызовов _require_env()

## Блок 3 — aiosmtplib >= 3.0 параметры

```bash
# Устаревший параметр start_tls= в конструкторе SMTP() (убран в aiosmtplib 3.0)
grep -n "start_tls=" core/sender.py
# Ожидается: 0 совпадений (исправлено в v3.3.0)

# STARTTLS должен вызываться после connect():
grep -n "starttls()" core/sender.py
# Ожидается: 1 строка: await smtp.starttls()
```

**Правильный паттерн для aiosmtplib >= 3.0:**
```python
# SSL/TLS (порт 465):
smtp = aiosmtplib.SMTP(hostname=host, port=465, use_tls=True, timeout=30)
await smtp.connect()

# STARTTLS (порт 587):
smtp = aiosmtplib.SMTP(hostname=host, port=587, use_tls=False, timeout=30)
await smtp.connect()
await smtp.starttls()  # ← после connect(), не в конструкторе
```

## Блок 4 — datetime.utcnow() (Python 3.12+ deprecation)

```bash
grep -rn "datetime.utcnow()" core/ gui/ main.py 2>/dev/null \
  && echo "WARN: устаревший datetime.utcnow() — замени на datetime.now(timezone.utc)" \
  || echo "OK: utcnow() не используется"
```

**Исправление:**
```python
# ❌ Устаревший (Python 3.12+ выводит DeprecationWarning)
from datetime import datetime
datetime.utcnow()

# ✅ Правильный
from datetime import datetime, timezone
datetime.now(timezone.utc).replace(tzinfo=None)  # для naive datetime сравнений
datetime.now(timezone.utc)  # для aware datetime
```

## Блок 5 — hiddenimports полнота

```bash
# Все gui.screens.* должны быть в hiddenimports build.py
python3 -c "
import os
screens = [f'gui.screens.{f[:-3]}' for f in os.listdir('gui/screens') if f.endswith('.py') and f != '__init__.py']
buildpy = open('build.py').read()
missing = [s for s in screens if s not in buildpy]
if missing:
    print('MISSING hiddenimports:', missing)
else:
    print('OK: все gui.screens.* в hiddenimports')
"

# Аналогично для core.*
python3 -c "
import os
cores = [f'core.{f[:-3]}' for f in os.listdir('core') if f.endswith('.py') and f != '__init__.py']
buildpy = open('build.py').read()
missing = [s for s in cores if s not in buildpy]
if missing:
    print('MISSING core hiddenimports:', missing)
else:
    print('OK: все core.* в hiddenimports')
"
```

## Блок 6 — Синтаксис перед сборкой

```bash
python3 -c "
import ast, os
errors = []
for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__', 'venv', 'build', 'dist')]
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            try:
                ast.parse(open(path).read())
            except SyntaxError as e:
                errors.append(f'SYNTAX ERROR {path}:{e.lineno}: {e.msg}')
if errors:
    for e in errors: print(e)
    raise SystemExit(1)
else:
    print('OK: синтаксических ошибок не найдено')
"
```

## Блок 7 — hourly counter корректность (отправитель)

```bash
# Баг: sent_this_hour = 0 для всех аккаунтов при старте кампании
grep -n "sent_this_hour = 0" core/sender.py
# В v3.3.0 должен быть IF с проверкой >= 3600

grep -A3 "sent_this_hour = 0" core/sender.py
# Ожидается: if _now - _acct._hour_reset >= 3600:
```

## Полный pre-build чеклист

Запускай по порядку перед каждым тегом/релизом:

```bash
echo "=== Build Guard Check v3.3.0 ==="

# 1. Синтаксис
python3 -c "import ast,os; [ast.parse(open(os.path.join(r,f)).read()) for r,d,fs in os.walk('.') for f in fs if f.endswith('.py') and '.git' not in r and '__pycache__' not in r]" && echo "1. Syntax OK" || echo "1. SYNTAX ERROR"

# 2. cipher= устарел
! grep -q "cipher=block_cipher" build.py && echo "2. PyInstaller 6.x OK" || echo "2. FAIL: cipher= в build.py"

# 3. aiosmtplib start_tls
! grep -q "start_tls=" core/sender.py && echo "3. aiosmtplib OK" || echo "3. FAIL: start_tls= найден"

# 4. utcnow
! grep -rq "datetime.utcnow()" core/ && echo "4. datetime OK" || echo "4. FAIL: utcnow() найден"

# 5. lazy license URLs
grep -q "_get_license_api_url\|_get_license_verify_url" core/license.py && echo "5. License lazy OK" || echo "5. FAIL: module-level _require_env"

# 6. версия
python3 -c "from core._version import APP_VERSION; print(f'6. Version: {APP_VERSION}')"

echo "=== Done ==="
```

## После сборки — smoke test

GitHub Actions выполняет `FMailSender.exe --check` — убедись что main.py обрабатывает этот флаг:

```python
# main.py должен содержать:
if "--check" in sys.argv:
    from core._version import APP_NAME, APP_VERSION
    print(f"{APP_NAME} v{APP_VERSION} — startup check OK")
    sys.exit(0)
```

```bash
grep -n "\-\-check" main.py || echo "WARN: --check флаг не реализован в main.py"
```

## Создание релиза (после успешной сборки)

```bash
# Тег и push (триггерит GitHub Actions build.yml автоматически)
git tag v3.3.0
git push origin v3.3.0

# Или через workflow_dispatch (без тега):
# GitHub → Actions → Release FMailSender .exe → Run workflow → tag: v3.3.0
```
