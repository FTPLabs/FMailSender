---
name: windows-exe-build
description: Сборка Windows EXE через PyInstaller и GitHub Actions. Активируй при ошибках сборки, добавлении новых зависимостей в EXE, настройке build.py.
---

# Windows EXE Build

## Файлы сборки

```
build.py          — главный скрипт сборки (PyInstaller wrapper)
FMailSender.spec  — PyInstaller spec (если есть)
requirements.txt  — runtime зависимости
requirements-dev.txt — dev/build зависимости
.github/workflows/build-release.yml — CI/CD
```

## GitHub Actions (автоматически)

Триггеры:
1. `git push tags/v*` — создаёт GitHub Release с EXE
2. `workflow_dispatch` — ручной запуск

```yaml
on:
  push:
    tags: ['v*']
  workflow_dispatch:
```

## Локальная сборка (Windows)

```bash
pip install pyinstaller pillow -r requirements.txt
python build.py
# → dist/FMailSender.exe
```

## Версия в EXE

```python
# core/_version.py
APP_VERSION = "4.4.0"
APP_NAME = "FMail Sender"
```
Build workflow читает версию: `from core._version import APP_VERSION`

## Добавление новой зависимости в EXE

1. Добавить в `requirements.txt`
2. Если hidden import — добавить в `build.py` или `.spec`:
   ```python
   hiddenimports=['mymodule', 'mymodule.submodule']
   ```
3. Если data files — добавить в `datas`:
   ```python
   datas=[('data/*.json', 'data'), ('i18n/*.qm', 'i18n')]
   ```

## Релиз-процесс

1. Обновить `core/_version.py` → `APP_VERSION = "X.Y.Z"`
2. Добавить запись в `CHANGELOG.md`
3. Commit + push на main
4. Создать тег `vX.Y.Z` → GitHub Actions запустит сборку
5. EXE появится в GitHub Releases через ~10-15 минут

## Важно: не запускай pnpm dev в репо FMailSender

FMailSender — Python/PyQt6 проект. pnpm/Node.js здесь не используются.
