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
| [proxy-country-cache](.agents/skills/proxy-country-cache/SKILL.md) | Кэш страны прокси (v4.4.0) |
| [rate-limit-strategy](.agents/skills/rate-limit-strategy/SKILL.md) | MAX_CONCURRENT, Semaphore |
| [debug-network](.agents/skills/debug-network/SKILL.md) | Отладка сетевых проблем |

### GUI и PyQt6
| Скилл | Назначение |
|-------|-----------|
| [gui-inspector](.agents/skills/gui-inspector/SKILL.md) | Инспекция координат и дизайна |
| [pyqt6-threading-guide](.agents/skills/pyqt6-threading-guide/SKILL.md) | QThread паттерны |
| [pyqt6-table-patterns](.agents/skills/pyqt6-table-patterns/SKILL.md) | QTableWidget |
| [gui-ux-principles](.agents/skills/gui-ux-principles/SKILL.md) | UX принципы |
| [gui-status](.agents/skills/gui-status/SKILL.md) | Status bar |
| [memory-management-qt](.agents/skills/memory-management-qt/SKILL.md) | Qt GC и утечки |
| [error-messages-ru](.agents/skills/error-messages-ru/SKILL.md) | Русские ошибки для UI |
| [color-palette](.agents/skills/color-palette/SKILL.md) | CyberPro цветовая система |
| [fps-optimization](.agents/skills/fps-optimization/SKILL.md) | 60 FPS, анимации |

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
| [release-workflow](.agents/skills/release-workflow/SKILL.md) | Полный процесс релиза |
| [changelog-guide](.agents/skills/changelog-guide/SKILL.md) | Как писать CHANGELOG |
| [vps-server-guide](.agents/skills/vps-server-guide/SKILL.md) | Деплой на VPS |

### Мультиагентная система
| Скилл | Назначение |
|-------|-----------|
| [agent-roles](.agents/skills/agent-roles/SKILL.md) | Кто что делает |
| [parallel-agent-guide](.agents/skills/parallel-agent-guide/SKILL.md) | Параллельная работа |

### Защитные guard-скиллы
| Скилл | Активация |
|-------|-----------|
| [gui-style-guard](.agents/skills/gui-style-guard/SKILL.md) | При изменении gui/ |
| [build-guard](.agents/skills/build-guard/SKILL.md) | При сборке EXE |
| [smtp-engine-guard](.agents/skills/smtp-engine-guard/SKILL.md) | При изменении core/sender.py |
| [openai-guard](.agents/skills/openai-guard/SKILL.md) | При изменении core/ai_fixer.py |
| [server-deploy-guard](.agents/skills/server-deploy-guard/SKILL.md) | При изменении server/ |
| [license-server-guard](.agents/skills/license-server-guard/SKILL.md) | При изменении server/bot.py |
| [patch-updater-guard](.agents/skills/patch-updater-guard/SKILL.md) | При изменении updater.py |
| [i18n-guard](.agents/skills/i18n-guard/SKILL.md) | При изменении текстов UI |
| [changelog-guard](.agents/skills/changelog-guard/SKILL.md) | При каждом релизе |

---

## 🤖 Специализированные агенты

Промпты в `.agents/prompts/`. При каждом старте: загрузить нужный промпт → следовать session-boot протоколу.

| Агент | Файл | Специализация | Скиллов |
|-------|------|--------------|---------|
| Architect | [architect.md](.agents/prompts/architect.md) | Архитектура, рефакторинг | 5 |
| GUI Agent | [gui-agent.md](.agents/prompts/gui-agent.md) | PyQt6 UI, дизайн | 6 |
| GUI Inspector | [gui-inspector-agent.md](.agents/prompts/gui-inspector-agent.md) | Проверка координат и CyberPro | 8 |
| SMTP Expert | [smtp-expert.md](.agents/prompts/smtp-expert.md) | SMTP протокол, провайдеры | 7 |
| Proxy Expert | [proxy-expert.md](.agents/prompts/proxy-expert.md) | SOCKS5/HTTP прокси | 6 |
| Code Reviewer | [code-reviewer.md](.agents/prompts/code-reviewer.md) | Code review | 5 |
| Security Agent | [security-agent.md](.agents/prompts/security-agent.md) | Безопасность, секреты | 3 |
| Tester | [tester.md](.agents/prompts/tester.md) | QA, тесты, регрессии | 4 |
| DevOps | [devops-agent.md](.agents/prompts/devops-agent.md) | Сборка, CI/CD, релизы | 4 |
| Debugger | [debugger.md](.agents/prompts/debugger.md) | Отладка сложных проблем | 6 |
| Orchestrator | [orchestrator.md](.agents/prompts/orchestrator.md) | Координация агентов | 2 |
| Cleanup Agent | [cleanup-agent.md](.agents/prompts/cleanup-agent.md) | Удаление мусора, дубликатов | 5 |
| Optimizer Agent | [optimizer-agent.md](.agents/prompts/optimizer-agent.md) | FPS, RAM, startup, EXE | 8 |
| Audit Agent | [audit-agent.md](.agents/prompts/audit-agent.md) | Полный аудит всех систем | 9 |

---

## 🗺️ Матрица: Задача → Агент → Скиллы

| Задача | Основной агент | Параллельно |
|--------|---------------|-------------|
| Новая GUI фича | GUI Agent | Code Reviewer |
| SMTP ошибки | SMTP Expert | Debugger |
| Прокси проблемы | Proxy Expert | Debugger |
| Баг в UI | GUI Inspector + Debugger | — |
| Релиз PATCH | DevOps | Security Agent |
| Релиз MINOR/MAJOR | Audit Agent → DevOps | — |
| Рефакторинг | Architect → Code Reviewer | Tester |
| Очистка репо | Cleanup Agent | — |
| Оптимизация | Optimizer Agent | GUI Inspector |
| Полный аудит | Audit Agent | — |

---

## ⚙️ Абсолютные правила (никогда не нарушать)

1. **Секреты не в коде** — secret-guard (приоритет №1)
2. **Синтаксис проверять до push** — python-syntax-guard
3. **CyberPro дизайн** — только Colors.* / Spacing.* — gui-style-guard
4. **Минимальный код** — ponytail (stdlib > зависимость)
5. **Thread safety** — Qt только из UI потока
6. **MAX_CONCURRENT = 4** — не менять!
7. **Нет моковых данных** — no-mock-data
8. **Отчёт в конце задачи** — agent-report (обязательно)
9. **Принял → работа → доложил** — token-economy (без промежуточных сообщений)
10. **Backward compatibility** — новые поля с дефолтами, .get("key", default)

---

## 📁 Структура файлов

```
main.py              — точка входа
core/
  sender.py          — SMTP engine (SmtpAccount, _test_smtp_sync, configs)
  smtp_validator.py  — валидация (_try_smtp_connect, PROXY_BLOCKS_SMTP)
  ai_fixer.py        — OpenAI spam fixer
  spam_checker.py    — спам-скор 0-100
  warmup.py          — прогрев аккаунтов
  bounce.py          — IMAP bounce parser
  updater.py         — auto-updater с patch
  license.py         — JWT лицензии
  _version.py        — APP_VERSION (источник истины для версии)
gui/
  app.py             — MainWindow, sidebar
  theme.py           — Colors, Spacing, Typography (ЕДИНСТВЕННЫЙ источник стилей)
  screens/
    screen_accounts.py — аккаунты, TestWorker, _CountryWorker, _proxy_country_cache
    screen_sender.py   — рассылка
    screen_*.py
  widgets/
    animated_bg.py   — фоновая анимация (ограничь до 30 FPS, MAX_PARTICLES=30)
server/
  bot.py             — Telegram Bot + FastAPI (120k chars — читай offset/limit!)
  database.py        — aiosqlite
  crypto_pay.py      — CryptoBot
  config.py          — env config
i18n/                — Qt Linguist переводы (.ts, .qm)
.agents/
  skills/            — 63 специализированных скилла
  prompts/           — 14 агентных промптов
  memory/            — MEMORY.md (персистентная память)
```

---

## 🔑 GitHub API (вместо git commit)

В Replit main agent git commit запрещён. **Только GitHub REST API:**
1. Токен: `attached_assets/fmmail_*.txt` — regex `/(ghp_[A-Za-z0-9]+)/`
2. Паттерн: create blobs → create tree (base_tree) → create commit → PATCH ref
3. Owner: `FTPLabs`, Repo: `FMailSender`, Branch: `main`
4. Батчи по 8 файлов при создании блобов
5. Детали: `.agents/skills/release-workflow/SKILL.md`

---

## 📊 Известные исправления (v4.4.0)

- `PROXY_BLOCKS_SMTP` только при SOCKS5 General Failure (не таймаут)
- `_proxy_country_cache` — кэш страны прокси, не сбрасывается при _refresh_table
- `MAX_CONCURRENT = 4` (было 10)
- `Semaphore(3)` для ip-api.com
- `_test_workers` очищаются после завершения
