---
  name: full-system-audit
  description: Полный аудит всех систем FMailSender v6 (Tauri + FastAPI + React) перед мажорным релизом. Активируй перед MAJOR/MINOR релизами и по явному запросу "полная проверка".
  ---

  # Full System Audit — v6 (Tauri + FastAPI + React)

  ## Порядок аудита (строго последовательно)

  ### Фаза 1: Безопасность (security-agent)
  - [ ] Нет секретов в коде (secret-guard scan)
  - [ ] Пароли не логируются
  - [ ] data/ в .gitignore (accounts.json, .fernet_key)
  - [ ] server/.env в .gitignore
  - [ ] SSL/TLS включён для всех SMTP подключений
  - [ ] Нет моковых данных (no-mock-data scan)

  ### Фаза 2: Качество кода Python (code-reviewer)
  - [ ] `python -m py_compile core/*.py` — 0 ошибок
  - [ ] `python -m py_compile server/*.py` — 0 ошибок
  - [ ] Нет `asyncio.get_event_loop()` внутри корутин (нужен `get_running_loop()`)
  - [ ] Thread safety: все `sent_today` инкременты через `try_increment()`
  - [ ] Все новые SmtpAccount поля с дефолтами
  - [ ] `.get("key", default)` при чтении JSON

  ### Фаза 3: UI/React (v6 — НЕ PyQt6)
  - [ ] `pnpm --filter @workspace/ui run typecheck` — 0 ошибок
  - [ ] api.ts покрывает все эндпоинты server.py
  - [ ] StatusContext polling не вызывает memory leak
  - [ ] Все страницы подключены к реальному API (нет моков)
  - [ ] Animations/framer-motion работают без лагов

  ### Фаза 4: SMTP (smtp-expert)
  - [ ] Все основные провайдеры в _SMTP_CONFIGS (sender.py)
  - [ ] _parse_auth_error — понятные сообщения на русском
  - [ ] PROXY_BLOCKS_SMTP только при SOCKS5 General Failure
  - [ ] Таймауты заданы везде (SMTP: 15-30с)
  - [ ] get_running_loop() везде в корутинах (не get_event_loop)

  ### Фаза 5: Прокси (proxy-expert)
  - [ ] validate_proxy работает (core/proxy.py)
  - [ ] ProxyManager round-robin ротация
  - [ ] POST /api/proxies/check возвращает правильные статусы
  - [ ] POST /api/proxies/distribute правильно распределяет

  ### Фаза 6: Производительность (optimizer-agent)
  - [ ] core startup (main.py) < 3 секунд
  - [ ] EXE < 80 MB (size-reduction skill)
  - [ ] RAM < 200 MB при 1000 аккаунтов
  - [ ] Нет утечек памяти daemon threads

  ### Фаза 7: Очистка (cleanup-agent)
  - [ ] Нет __pycache__ в репо
  - [ ] Нет .pyc файлов
  - [ ] Нет PyQt6 импортов (v5 мусор)
  - [ ] CHANGELOG.md обновлён
  - [ ] core/_version.py обновлён
  - [ ] .gitignore защищает data/

  ### Фаза 8: Сборка (devops-agent)
  - [ ] `ui/vite.config.ts` содержит `base: './'` (обязательно для Tauri WebView)
  - [ ] `fmail-core.spec` актуален (PyInstaller)
  - [ ] GitHub Actions release.yml — все шаги зелёные
  - [ ] VPS deплой bot.py успешен

  ## Формат отчёта аудита

  ```
  ## Полный аудит v[VERSION] — [DATE]

  ### ✅ Пройдено
  • Безопасность: 6/6 проверок OK
  • Python: 8/8 проверок OK
  • React/UI: 5/5 проверок OK
  ...

  ### ⚠️ Предупреждения
  • [список незначительных проблем]

  ### ❌ Блокеры (релиз запрещён)
  • [список критических проблем]

  ### Итог: [ГОТОВ К РЕЛИЗУ / ТРЕБУЕТ ИСПРАВЛЕНИЙ]
  ```
  