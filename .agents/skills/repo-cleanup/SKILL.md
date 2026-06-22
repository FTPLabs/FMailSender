---
name: repo-cleanup
description: Удаление мусора из репозитория — неиспользуемые файлы, кэш, дубликаты, временные файлы. Активируй ДО каждого релиза и по требованию.
---

# Repo Cleanup Skill

## Что удалять БЕЗОПАСНО

### Кэш и компиляция
```
__pycache__/        — Python bytecode кэш (пересоздаётся автоматически)
*.pyc               — скомпилированные .pyc файлы
*.pyo               — оптимизированные .pyc
dist/               — результат сборки PyInstaller
build/              — промежуточные файлы сборки
*.spec.bak          — бэкапы spec файлов
```

### Временные файлы
```
*.tmp
*.bak
*.swp
*.orig
.DS_Store           — macOS метаданные
Thumbs.db           — Windows метаданные
desktop.ini         — Windows
```

### Логи (если не нужны для дебага)
```
*.log               — логи (кроме debug-critical)
logs/*.log
```

### IDE файлы
```
.idea/              — PyCharm (если нет в .gitignore)
.vscode/settings.json — личные настройки VS Code
```

## Что НИКОГДА не удалять
```
data/accounts.json  — аккаунты пользователей (если нет в .gitignore)
.env                — переменные окружения (должен быть в .gitignore!)
i18n/*.qm           — скомпилированные переводы Qt (нужны для EXE)
assets/             — иконки, изображения
core/_version.py    — версия приложения
```

## Дубликаты кода — как найти

```bash
# Найти дублирующиеся функции (одинаковое имя)
grep -rn "^def " --include="*.py" . | sort | awk -F: '{print $NF}' | sort | uniq -d

# Найти import которые не используются в файле
# (требует flake8 или pylint)
python -m flake8 --select=F401 core/ gui/

# Найти файлы > 500 строк (кандидаты на split)
find . -name "*.py" -exec wc -l {} \; | sort -n | awk '$1 > 500 {print}'
```

## Проверка .gitignore
```bash
# Убедись что это есть в .gitignore:
cat .gitignore | grep -E "accounts\.json|\.env|__pycache__|\.pyc|dist/|build/"
```

## Неиспользуемые зависимости
```bash
# Установи pip-check-reqs
pip install pip-check-reqs
pip-extra-reqs . requirements.txt   # зависимости в requirements, но не в коде
pip-missing-reqs . requirements.txt # зависимости в коде, но не в requirements
```

## Мёртвый код
```bash
# Установи vulture
pip install vulture
vulture core/ gui/ --min-confidence 80
```

## После очистки — обязательно
1. Запустить python-syntax-guard
2. Запустить python -m py_compile main.py
3. Убедиться что приложение запускается
