# FMailSender — AI Agent Instructions

> **ВАЖНО: Прочти этот файл ПЕРВЫМ перед любым действием в репозитории.**
> **При каждом старте сессии: загрузи session-boot скилл и все нужные скиллы. Сообщи о готовности.**

---

## 🚀 Протокол запуска сессии (ОБЯЗАТЕЛЬНО)

```
1. Прочитать AGENTS.md (этот файл)
2. Прочитать .agents/memory/MEMORY.md
3. Загрузить session-boot скилл → определить роль
4. Загрузить скиллы для роли (см. ниже)
5. Сообщить: "✅ [Агент] инициализирован. Загружено скиллов: N. Готов к работе, сэр."
6. На задачу: "Принял задачу, сэр." → [тихая работа] → [отчёт]
```

---

## 🔴 Универсальные скиллы — загружай ВСЕГДА

| Скилл | Назначение |
|-------|-----------|
| [session-boot](.agents/skills/session-boot/SKILL.md) | **ПЕРВЫЙ** — протокол запуска |
| [secret-guard](.agents/skills/secret-guard/SKILL.md) | Безопасность секретов |
| [python-syntax-guard](.agents/skills/python-syntax-guard/SKILL.md) | Синтаксис Python |
| [ponytail](.agents/skills/ponytail/SKILL.md) | Минимальный код |
| [token-economy](.agents/skills/token-economy/SKILL.md) | Экономия токенов |
| [no-mock-data](.agents/skills/no-mock-data/SKILL.md) | Запрет моков |
| [conflict-check](.agents/skills/conflict-check/SKILL.md) | Нет конфликтов скиллов |
| [agent-report](.agents/skills/agent-report/SKILL.md) | Стандарт финального отчёта |

---

## 🟡 Специализированные скиллы — по задаче

### SMTP и Email
| Скилл | Назначение |
|-------|-----------|
| [smtp-error-diagnosis](.agents/skills/smtp-error-diagnosis/SKILL.md) | Коды ошибок SMTP |
| [smtp-port-fallback](.agents/skills/smtp-port-fallback/SKILL.md) | Стратегия портов 465/587/25 |
| [smtp-auth-methods](.agents/skills/smtp-auth-methods/SKILL.md) | AUTH PLAIN/LOGIN/XOAUTH2 |
| [smtp-configs-extended](.agents/skills/smtp-configs-extended/SKILL.md) | Расширенный список провайдеров |
| [smtp-validator](.agents/skills/smtp-validator/SKILL.md) | Логика smtp_validator.py |
| [async-smtp-guide](.agents/skills/async-smtp-guide/SKILL.md) | asyncio SMTP паттерны |
| [rambler-specifics](.agents/skills/rambler-specifics/SKILL.md) | Rambler.ru специфика |
| [gmx-webde-guide](.agents/skills/gmx-webde-guide/SKILL.md) | GMX / web.de специфика |
| [oauth2-microsoft](.agents/skills/oauth2-microsoft/SKILL.md) | Microsoft OAuth2 Outlook |

### Прокси и Сеть
| Скилл | Назначение |
|-------|-----------|
| [socks5-internals](.agents/skills/socks5-internals/SKILL.md) | SOCKS5 raw socket |
| [http-connect-proxy](.agents/skills/http-connect-proxy/SKILL.md) | HTTP CONNECT |
| [proxy-smtp-requirements](.agents/skills/proxy-smtp-requirements/SKILL.md) | Требования к прокси |
| [proxy-country-cache](.agents/skills/proxy-country-cache/SKILL.md) | Кэш страны прокси |
| [rate-limit-strategy](.agents/skills/rate-limit-strategy/SKILL.md) | MAX_CONCURRENT, Semaphore |
| [debug-network](.agents/skills/debug-network/SKILL.md) | Отладка сетевых проблем |

### React / Tauri UI (v6 архитектура)
| Скилл | Назначение |
|-------|-----------|
| [error-messages-ru](.agents/skills/error-messages-ru/SKILL.md) | Русские тексты ошибок для UI |
| [color-palette](.agents/skills/color-palette/SKILL.md) | Цветовая система (theme.ts) |
| [tauri-fastapi](.agents/skills/tauri-fastapi/SKILL.md) | Tauri + Python sidecar |

### Качество и Безопасность
| Скилл | Назначение |
|-------|-----------|
| [security-checklist](.agents/skills/security-checklist/SKILL.md) | Чеклист безопасности |
| [code-review-guide](.agents/skills/code-review-guide/SKILL.md) | Чеклист code review |
| [logging-guide](.agents/skills/logging-guide/SKILL.md) | Что/как логировать |
| [testing-guide](.agents/skills/testing-guide/SKILL.md) | Тест-кейсы и pytest |
| [performance-guide](.agents/skills/performance-guide/SKILL.md) | Оптимизация производительности |

### Оптимизация и Очистка
| Скилл | Назначение |
|-------|-----------|
| [repo-cleanup](.agents/skills/repo-cleanup/SKILL.md) | Удаление мусора из репо |
| [app-optimization](.agents/skills/app-optimization/SKILL.md) | Startup, IO, SMTP throughput |
| [size-reduction](.agents/skills/size-reduction/SKILL.md) | Размер EXE и RAM |
| [full-system-audit](.agents/skills/full-system-audit/SKILL.md) | Полный аудит перед релизом |

### Аккаунты и Данные
| Скилл | Назначение |
|-------|-----------|
| [account-persistence](.agents/skills/account-persistence/SKILL.md) | Сохранение/загрузка аккаунтов |
| [inbox-bypass-prompts](.agents/skills/inbox-bypass-prompts/SKILL.md) | Обход спам-фильтров |
| [reply-monitor](.agents/skills/reply-monitor/SKILL.md) | Мониторинг ответов IMAP |
| [spam-score-pro](.agents/skills/spam-score-pro/SKILL.md) | SpamAssassin спам-скор |
| [html-generator](.agents/skills/html-generator/SKILL.md) | Генерация HTML писем |

### Сборка и Релизы
| Скилл | Назначение |
|-------|-----------|
| [windows-exe-build](.agents/skills/windows-exe-build/SKILL.md) | PyInstaller EXE |
| [pyinstaller-spec](.agents/skills/pyinstaller-spec/SKILL.md) | spec файл, hidden imports |
| [build-guard](.agents/skills/build-guard/SKILL.md) | Чеклист перед сборкой |
| [changelog-guard](.agents/skills/changelog-guard/SKILL.md) | Как писать CHANGELOG |

### Мультиагентная система
| Скилл | Назначение |
|-------|-----------|
| [agent-roles](.agents/skills/agent-roles/SKILL.md) | Кто что делает |

### Защитные guard-скиллы
| Скилл | Активация |
|-------|-----------|
| [build-guard](.agents/skills/build-guard/SKILL.md) | При сборке EXE |
| [smtp-engine-guard](.agents/skills/smtp-engine-guard/SKILL.md) | При изменении core/sender.py |
| [license-server-guard](.agents/skills/license-server-guard/SKILL.md) | При изменении server/ |
| [cancel-guard](.agents/skills/cancel-guard/SKILL.md) | При остановке рассылки |
| [patch-updater-guard](.agents/skills/patch-updater-guard/SKILL.md) | При изменении обновлений |
| [session-only-data](.agents/skills/session-only-data/SKILL.md) | Сессионные данные (прокси) |
| [openai-guard](.agents/skills/openai-guard/SKILL.md) | При вызовах OpenAI API |

---

## 🤖 Агентные роли и промпты

| Агент | Промпт | Специализация | Скиллов |
|-------|--------|--------------|---------|
| Architect | [architect.md](.agents/prompts/architect.md) | Архитектура, рефакторинг | 6 |
| SMTP Expert | [smtp-expert.md](.agents/prompts/smtp-expert.md) | SMTP, аутентификация | 9 |
| Proxy Expert | [proxy-expert.md](.agents/prompts/proxy-expert.md) | SOCKS5/HTTP прокси | 6 |
| Code Reviewer | [code-reviewer.md](.agents/prompts/code-reviewer.md) | Code review | 5 |
| Security Agent | [security-agent.md](.agents/prompts/security-agent.md) | Безопасность, секреты | 3 |
| Tester | [tester.md](.agents/prompts/tester.md) | QA, тесты, регрессии | 4 |
| DevOps | [devops-agent.md](.agents/prompts/devops-agent.md) | Сборка, CI/CD, релизы | 4 |
| Debugger | [debugger.md](.agents/prompts/debugger.md) | Отладка сложных проблем | 6 |
| Orchestrator | [orchestrator.md](.agents/prompts/orchestrator.md) | Координация агентов | 2 |
| Cleanup Agent | [cleanup-agent.md](.agents/prompts/cleanup-agent.md) | Удаление мусора, дубликатов | 5 |
| Optimizer Agent | [optimizer-agent.md](.agents/prompts/optimizer-agent.md) | RAM, startup, EXE size | 8 |
| Audit Agent | [audit-agent.md](.agents/prompts/audit-agent.md) | Полный аудит всех систем | 9 |

---

## 🗺️ Матрица: Задача → Агент → Скиллы

| Задача | Основной агент | Параллельно |
|--------|---------------|-------------|
| Новая UI фича (React) | Architect | Code Reviewer |
| SMTP ошибки | SMTP Expert | Debugger |
| Прокси проблемы | Proxy Expert | Debugger |
| Баг в UI (React/Tauri) | Debugger | — |
| Релиз PATCH | DevOps | Security Agent |
| Релиз MINOR/MAJOR | Audit Agent → DevOps | — |
| Рефакторинг | Architect → Code Reviewer | Tester |
| Очистка репо | Cleanup Agent | — |
| Оптимизация | Optimizer Agent | — |
| Полный аудит | Audit Agent | — |

---

## ⚙️ Абсолютные правила (никогда не нарушать)

1. **Секреты не в коде** — secret-guard (приоритет №1)
2. **Синтаксис проверять до push** — python-syntax-guard
3. **Дизайн через theme.ts** — только цвета из tailwind.config.js / theme.ts
4. **Минимальный код** — ponytail (stdlib > зависимость)
5. **Thread safety** — SendingEngine только из потока; React — только из UI
6. **MAX_CONCURRENT = 4** — не менять!
7. **Нет моковых данных** — no-mock-data
8. **Отчёт в конце задачи** — agent-report (обязательно)
9. **Принял → работа → доложил** — token-economy (без промежуточных сообщений)
10. **Backward compatibility** — новые поля с дефолтами, .get("key", default)

---

## 📁 Структура файлов v6 (Tauri + Python + React)

```
main.py              — точка входа: uvicorn на :7531
core/
  server.py          — FastAPI: все эндпоинты (/api/*)
  models.py          — SmtpAccount, Recipient, CampaignConfig, CampaignStatus
  sender.py          — SMTP движок (SendingEngine, test_smtp_connection)
  storage.py         — Fernet-зашифрованное хранилище (data/*.json)
  proxy.py           — ProxyManager: parse/rotate/check SOCKS5+HTTP
  oauth2_refresh.py  — Microsoft OAuth2 refresh_token
  spam_checker.py    — спам-скор 0-100
  warmup.py          — прогрев аккаунтов
  bounce.py          — IMAP bounce parser
  html_generator.py  — генерация HTML писем
  uniqueizer.py      — anti-spam obfuscation (Spintax, Unicode, HTML randomize)
  inbox_tester.py    — inbox delivery testing
  reply_monitor.py   — IMAP reply monitoring
  send_checkpoint.py — checkpoint/resume for campaigns
  _version.py        — APP_VERSION (источник истины для Python)
  _ensure_imports.py — PyInstaller import guard
ui/src/
  version.ts         — FRONTEND_VERSION (источник истины для JS; обновляется CI)
  api.ts             — HTTP клиент (все запросы к :7531 здесь)
  App.tsx            — React Router + Layout wrapper
  theme.ts           — design tokens (цвета, типографика)
  components/
    Layout.tsx       — Sidebar + main area
    StartupOverlay.tsx — startup screen + stale-cache guard
  contexts/
    StatusContext.tsx — SSE/polling real-time статус
  pages/
    Dashboard.tsx    — статистика
    Accounts.tsx     — SMTP аккаунты
    Recipients.tsx   — получатели
    Compose.tsx      — редактор письма
    Sending.tsx      — управление рассылкой
    Proxies.tsx      — прокси
    Inbox.tsx        — входящие / bounce
src-tauri/
  src/main.rs        — Rust shell: kill old core, spawn new, WebView2
  tauri.conf.json    — конфиг окна, sidecar, CSP
  Cargo.toml         — Rust зависимости
server/
  bot.py             — Telegram Bot + FastAPI (лицензии, платежи)
  database.py        — aiosqlite
  config.py          — env config
  crypto_pay.py, lzt_pay.py, xrocket_pay.py — платёжные провайдеры
.agents/
  skills/            — специализированные скиллы
  prompts/           — агентные промпты
  memory/            — MEMORY.md (персистентная память)
```

---

## 🔑 GitHub API (вместо git commit)

В Replit main agent git commit запрещён. **Только GitHub REST API:**
1. Токен: `attached_assets/fmmail_*.txt` — regex `/(ghp_[A-Za-z0-9]+)/`
2. Паттерн: create blobs → create tree (base_tree) → create commit → PATCH ref
3. Owner: `FTPLabs`, Repo: `FMailSender`, Branch: `main`
4. Батчи по 8 файлов при создании блобов
5. Детали: `.agents/skills/github-push/SKILL.md`

---

## 📊 Известные исправления и архитектурные решения

### v6.0.6 (текущая)
- `kill_existing_core()` — двухэтапный kill: сначала по порту 7531 (PowerShell
  `Get-NetTCPConnection`), затем по имени процесса. Решает upgrade-сценарий где
  старый fmail-core.exe держит порт и Tauri подключается к старой версии.
- `initBaseUrl()` в api.ts — пробует 127.0.0.1 и localhost; берёт первый
  рабочий. Решает проблему с VPN-клиентами блокирующими 127.0.0.1.
- `FRONTEND_VERSION` в ui/src/version.ts — StartupOverlay сравнивает с
  backend version; при несовпадении (stale WebView2 cache) → принудительный
  window.location.reload().
- CSP в tauri.conf.json — блокирует WebView2 от внешних соединений:
  `connect-src http://127.0.0.1:7531 http://localhost:7531`. Предотвращает
  утечку реального IP через browser-side requests.
- Google Fonts CDN удалён из index.html — загрузка с fonts.googleapis.com
  выдавала реальный IP пользователя при каждом запуске, минуя VPN/прокси.
  Заменено на системные шрифты (Segoe UI / system-ui).

### v6.0.5
- `asyncio.get_running_loop()` — внутри корутин всегда `get_running_loop()`,
  не `get_event_loop()` (deprecated Python 3.10+)
- duck-compat models↔sender — models.SmtpAccount обязан иметь _lock,
  _day_reset, _hour_reset в __post_init__
- `data/` в .gitignore — критично, иначе зашифрованные пароли попадут в репо

### v6.0.x (общее)
- `PROXY_BLOCKS_SMTP` только при SOCKS5 General Failure (не таймаут)
- `MAX_CONCURRENT = 4` (было 10) — разумный параллелизм без блокировок
- `Semaphore(3)` для ip-api.com rate limit
