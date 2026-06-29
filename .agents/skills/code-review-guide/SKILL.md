---
  name: code-review-guide
  description: Чеклист code review для FMailSender v6 (Tauri+React+FastAPI). Активируй при проверке PR, после написания крупных фич, перед релизом.
  ---

  # Code Review Guide — FMailSender v6

  ## 1. Python / FastAPI (core/)

  ### Thread Safety
  - [ ] Нет блокирующих вызовов в async-функциях FastAPI без run_in_executor
  - [ ] Все обновления _campaign_status через _status_lock (threading.Lock)
  - [ ] SendingEngine.run() запускается в daemon thread, не в asyncio loop

  ### Memory Management
  - [ ] Завершённые engine-потоки не держат ссылки на_accounts/_recipients
  - [ ] Нет утечек asyncio задач (gather, создавать задачи через asyncio.gather)

  ### Error Handling
  - [ ] Все сетевые операции в try/except
  - [ ] SMTP таймаут: 15-30с; HTTP API таймаут: 5-10с
  - [ ] Ошибки понятны пользователю (русский текст, без трейсбэков)
  - [ ] except Exception: pass → ЗАПРЕЩЁН (всегда логируй: logger.warning/error)

  ### Security
  - [ ] Нет секретов в коде (см. secret-guard)
  - [ ] Пароли не логируются (ни частично)
  - [ ] Proxy credentials не в error messages
  - [ ] uvicorn только на 127.0.0.1 (никогда 0.0.0.0)

  ### Code Quality (ponytail)
  - [ ] Минимальный код — нет дублирования
  - [ ] Новые зависимости обоснованы (stdlib предпочтительна)
  - [ ] Функции до ~50 строк, файлы до ~800 строк

  ### Backward Compatibility
  - [ ] Новые поля SmtpAccount с дефолтами
  - [ ] .get("field", default) при чтении JSON
  - [ ] Старые форматы данных по-прежнему читаются

  ## 2. React / TypeScript (ui/)

  ### Build (КРИТИЧНО для Tauri)
  - [ ] vite.config.ts имеет base: './' (без этого WebView2 не загрузит ресурсы)
  - [ ] Все API-вызовы через ui/src/api.ts (не прямой fetch)
  - [ ] Никаких жёстких URL — только относительные или localhost:7531

  ### Type Safety
  - [ ] Нет any (кроме обоснованных исключений)
  - [ ] Все пропсы типизированы
  - [ ] API-ответы не кастуются без проверки

  ### UI
  - [ ] Цвета только через theme.ts (не хардкодить hex)
  - [ ] Ошибки показываются пользователю (не только console.error)
  - [ ] Loading-состояния есть у всех async-операций

  ## 3. Rust / Tauri (src-tauri/)

  ### Sidecar
  - [ ] fmail-core-x86_64-pc-windows-msvc.exe — имя бинаря правильное
  - [ ] bundle.externalBin: ["binaries/fmail-core"] в tauri.conf.json
  - [ ] beforeBuildCommand: "" или "cd ../ui && npm run build" (не "cd ui")

  ### Иконки
  - [ ] src-tauri/icons/ существует или генерируется в CI: tauri icon assets/images/fmail_logo.png

  ## 4. CI/CD (.github/workflows/)

  ### release.yml
  - [ ] Repo → PUBLIC в начале (Step 0), PRIVATE в конце (always:)
  - [ ] PAT_TOKEN задан в GitHub Secrets
  - [ ] upx=False в fmail-core.spec (UPX не установлен в CI)
  - [ ] Версия синхронизируется в: tauri.conf.json, Cargo.toml, core/_version.py, ui/src/version.ts
  - [ ] Exe валидируется по размеру (> 5 МБ) перед публикацией

  ### toggle_and_build.py
  - [ ] WORKFLOW = "release.yml" (не "build.yml"!)
  - [ ] GITHUB_TOKEN имеет права: repo + admin:repo (для смены видимости)

  ### PyInstaller spec (fmail-core.spec)
  - [ ] PYZ() без cipher= (PyInstaller >= 6.0)
  - [ ] upx=False
  - [ ] console=False
  - [ ] Все hidden imports присутствуют (uvicorn, fastapi, email.mime.*, multipart)

  ### aiosmtplib 3.x
  - [ ] Нет start_tls= параметра (удалён в aiosmtplib 3.0)
  - [ ] STARTTLS: smtp.connect() → await smtp.starttls() (отдельный вызов)

  ## Rate limits
  - [ ] MAX_CONCURRENT = 4 (не менять на большее)
  - [ ] ip-api.com через Semaphore(3) и кэш (proxy-country-cache skill)

  ## Перед merge / release
  - [ ] core/_version.py обновлена
  - [ ] CHANGELOG.md обновлён
  - [ ] Все тесты проходят: python -m pytest tests/ -x -q
  - [ ] Python синтаксис: python -m py_compile main.py core/*.py
  - [ ] TypeScript: cd ui && npx tsc --noEmit
  