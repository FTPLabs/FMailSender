---
  name: build-guard
  description: Проверяет готовность проекта к сборке .exe через PyInstaller и к созданию GitHub Release. Активируй перед любым запуском build.py, push с тегом, или workflow_dispatch. Документирует patch-систему обновлений.
  ---

  # Build Guard — Проверка перед сборкой EXE и релизом

  ## Когда использовать

  - Перед `python build.py` или `pyinstaller FMailSender.spec`
  - Перед пушем тега `v*` (триггер build.yml)
  - После изменений в `core/`, `gui/`, `main.py`, `build.py`
  - Когда EXE падает при запуске с ImportError/ModuleNotFoundError

  ---

  ## Блок 1 — PyInstaller 6.x совместимость

  ```bash
  grep -n "cipher=block_cipher" build.py && echo "FAIL: устаревший cipher= — удали" || echo "OK"
  ```

  **Исправление:**
  ```python
  # ❌ PyInstaller < 6.0
  pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
  # ✅ PyInstaller >= 6.0
  pyz = PYZ(a.pure, a.zipped_data)
  ```

  ---

  ## Блок 2 — aiosmtplib >= 3.0

  ```bash
  grep -n "start_tls=" core/sender.py && echo "FAIL: убран в aiosmtplib 3.0" || echo "OK"
  ```

  **Правильный паттерн:**
  ```python
  # SSL (порт 465):
  smtp = aiosmtplib.SMTP(hostname=host, port=465, use_tls=True, timeout=30)
  await smtp.connect()
  # STARTTLS (порт 587):
  smtp = aiosmtplib.SMTP(hostname=host, port=587, use_tls=False, timeout=30)
  await smtp.connect()
  await smtp.starttls()
  ```

  ---

  ## Блок 3 — datetime.utcnow() deprecated

  ```bash
  grep -rn "datetime.utcnow()" core/ gui/ main.py && echo "WARN: замени на datetime.now(timezone.utc)" || echo "OK"
  ```

  ---

  ## Блок 4 — hiddenimports полнота

  ```bash
  python3 -c "
  import os
  screens = ['gui.screens.' + f[:-3] for f in os.listdir('gui/screens') if f.endswith('.py') and f != '__init__.py']
  cores = ['core.' + f[:-3] for f in os.listdir('core') if f.endswith('.py') and f != '__init__.py']
  bp = open('build.py').read()
  missing = [m for m in screens + cores if m not in bp]
  print('MISSING:', missing) if missing else print('OK: все модули в hiddenimports')
  "
  ```

  ---

  ## Блок 5 — Синтаксис (AST)

  ```bash
  python3 -c "
  import ast, os
  errors = []
  for root, dirs, files in os.walk('.'):
      dirs[:] = [d for d in dirs if d not in ('.git','__pycache__','venv','build','dist')]
      for f in files:
          if f.endswith('.py'):
              path = os.path.join(root, f)
              try: ast.parse(open(path).read())
              except SyntaxError as e: errors.append(f'{path}:{e.lineno}: {e.msg}')
  [print(e) for e in errors] or print('OK: синтаксических ошибок нет')
  raise SystemExit(1) if errors else None
  "
  ```

  ---

  ## Блок 6 — Patch-система (v2.0+)

  Начиная с v3.4.2 FMailSender поддерживает **patch-обновления**:

  ### Как работает
  1. `main.py` при старте добавляет `_patches/` в `sys.path[0]`
  2. Каждый релиз содержит `patch_manifest_vX.Y.Z.json` с SHA-256 изменённых .py
  3. Клиент скачивает только изменённые файлы (~КБ вместо ~МБ полного EXE)
  4. Файлы помещаются в `_patches/core/...`, `_patches/gui/...` рядом с EXE
  5. При следующем запуске Python загружает их вместо встроенных

  ### Генерация патча (CI/CD делает автоматически)
  ```bash
  python make_patch.py v3.4.1 v3.4.2
  # → dist/patch_manifest_v3.4.2.json
  ```

  ### Структура манифеста
  ```json
  {
    "version": "3.4.2",
    "base_version": "3.4.1",
    "files": [
      {
        "path": "core/updater.py",
        "sha256": "abc123...",
        "url": "https://raw.githubusercontent.com/FTPLabs/FMailSender/v3.4.2/core/updater.py",
        "size": 8192
      }
    ]
  }
  ```

  ### Проверка _patches injection в main.py
  ```bash
  grep -n "_patch_dir\|_patches" main.py || echo "WARN: patch loader не найден в main.py"
  ```

  ### Очистка патчей (сброс к состоянию EXE)
  ```python
  from core.updater import clear_patches
  clear_patches()
  ```

  ---

  ## Полный pre-build чеклист

  ```bash
  echo "=== Build Guard v2.0 ==="

  # 1. Синтаксис
  python3 -c "import ast,os; [ast.parse(open(os.path.join(r,f)).read()) for r,d,fs in os.walk('.') for f in fs if f.endswith('.py') and '.git' not in r and '__pycache__' not in r]" && echo "1. Syntax OK" || echo "1. SYNTAX ERROR"

  # 2. PyInstaller 6.x
  ! grep -q "cipher=block_cipher" build.py && echo "2. PyInstaller 6.x OK" || echo "2. FAIL: cipher="

  # 3. aiosmtplib
  ! grep -q "start_tls=" core/sender.py && echo "3. aiosmtplib OK" || echo "3. FAIL: start_tls="

  # 4. datetime
  ! grep -rq "datetime.utcnow()" core/ && echo "4. datetime OK" || echo "4. WARN: utcnow()"

  # 5. patch loader
  grep -q "_patch_dir" main.py && echo "5. Patch loader OK" || echo "5. WARN: patch loader нет"

  # 6. Версия
  python3 -c "from core._version import APP_VERSION; print(f'6. Version: {APP_VERSION}')"

  echo "=== Done ==="
  ```

  ---

  ## Дерево артефактов релиза

  ```
  dist/
  ├── FMailSender.exe               ← полный EXE (всегда)
  ├── FMailSender_v3.4.2.exe        ← копия с тегом в имени
  └── patch_manifest_v3.4.2.json   ← только изменённые файлы
  ```

  ---

  ## После сборки — smoke test

  ```bash
  ./dist/FMailSender.exe --check
  # Ожидается: "FMailSender v3.4.2 — startup check OK" и exit 0
  ```

  ## Создание релиза

  ```bash
  git tag v3.4.2
  git push origin v3.4.2
  # GitHub Actions сам соберёт EXE, прогонит 6 gate'ов и создаст Release
  ```
  