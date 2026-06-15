---
name: python-syntax-guard
description: Проверяет Python-файлы проекта на синтаксические ошибки, SyntaxError и импортные проблемы перед пушем в GitHub или созданием релиза. Активируй когда: пользователь говорит о краше при запуске приложения, ImportError/SyntaxError в трейсбеке, сборке .exe через PyInstaller, пуше в GitHub. ОБЯЗАТЕЛЬНО использовать перед любым коммитом Python-кода.
---

# Python Syntax Guard

## Когда использовать

- Пользователь сообщает о SyntaxError, ImportError, или краше при запуске
- Перед пушем Python-файлов в GitHub
- Перед сборкой .exe через PyInstaller (pyinstaller build.py)
- После ручного редактирования Python-кода (особенно docstrings и f-string)
- Перед релизом новой версии

## Что проверять

### 1. Синтаксис всех Python-файлов

Запусти проверку синтаксиса для всего проекта:

```bash
# Если python3 доступен
find . -name "*.py" -not -path "./.git/*" -not -path "./venv/*" | \
  xargs -I{} python3 -c "import ast; ast.parse(open('{}').read()); print('OK: {}')" 2>&1

# Через node (универсально в Replit)
node -e "
const {execSync} = require('child_process');
const fs = require('fs');
const glob = require('glob');
// Fallback: показываем файлы для проверки
const files = execSync('find . -name \"*.py\" -not -path \"./.git/*\" 2>/dev/null').toString().trim().split('\n');
console.log('Файлы для проверки:', files.length);
"
```

### 2. Частые паттерны SyntaxError

Ищи эти паттерны в коде перед пушем:

**Docstring слита с кодом (главная ошибка этого проекта):**
```bash
# Ищет docstring на одной строке с кодом — гарантированный SyntaxError
grep -rn '""".*""".*from\|""".*"""\s\+import\|""".*"""\s\+if\|""".*"""\s\+for' --include="*.py" .
```

**Inline импорты без переноса строки:**
```bash
grep -rn '"""\s\+import\|"""\s\+from' --include="*.py" .
```

**f-string с backslash (Python < 3.12):**
```bash
grep -rn "f'.*\\\\" --include="*.py" . | grep -v "#"
```

### 3. Проверка импортов

```bash
# Проверка что все from X import Y разрешаются
grep -rn "^from \.\|^import \." --include="*.py" . | head -30
```

### 4. PyInstaller-специфичные проблемы

Перед сборкой .exe убедись:

- `block_cipher` не передаётся в `PYZ()` и `EXE()` при PyInstaller >= 6.x  
  Ищи: `grep -n "cipher=block_cipher" build.py`
- Все `hiddenimports` перечислены (особенно `gui.screens.*`, `core.*`)
- Нет `import X` внутри функций в часто вызываемых методах

### 5. Circular imports

```bash
# Ищем взаимные импорты между модулями
grep -rn "^from core.sender import\|^from core.spam_checker import" --include="*.py" core/
```

## Алгоритм действий

1. **Получи список изменённых файлов** (через `git diff --name-only` или список коммитов)
2. **Запусти grep-проверки** по паттернам выше на изменённых файлах
3. **Если найдены проблемы** — исправляй до пуша, не после
4. **После пуша** — проверь что GitHub Actions (если есть) завершился без ошибок

## Специфика проекта FMailSender

- Файлы GUI: `gui/screens/*.py` — содержат PyQt6 + docstrings, высокий риск SyntaxError
- Главная точка входа: `main.py` → `gui/app.py` → `gui/screens/screen_compose.py`
- Сборка .exe: `python build.py` (Windows-only, запускается через GitHub Actions на `windows-latest`)
- Серверная часть: `server/bot.py` — aiogram 3.x + FastAPI, запускается через systemd на VPS
- База данных: `server/database.py` — aiosqlite, таблицы создаются в `init_db()` через `CREATE_SQL`

## Примеры частых ошибок и исправлений

### SyntaxError: invalid syntax (docstring + код на одной строке)

**Сломано:**
```python
def _text_color(self):
    """Открывает диалог выбора цвета."""    from PyQt6.QtWidgets import QColorDialog
```

**Исправлено:**
```python
def _text_color(self):
    """Открывает диалог выбора цвета."""
    from PyQt6.QtWidgets import QColorDialog
```

### PyInstaller 6.x: TypeError: EXE() got unexpected argument 'cipher'

**Сломано:**
```python
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(pyz, ..., cipher=block_cipher)
```

**Исправлено:**
```python
pyz = PYZ(a.pure, a.zipped_data)
exe = EXE(pyz, ...)
```

### Hardcoded version in API response

**Сломано:** `"version": "3.0.0"` в `/health` endpoint  
**Исправлено:** `from core._version import APP_VERSION` → `"version": APP_VERSION`
