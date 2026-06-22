# FMailSender — AI Agent Instructions

> **ВАЖНО: Прочти этот файл ПЕРВЫМ перед любым действием в репозитории.**

## Обязательные скиллы — активируй при старте сессии

Все скиллы в `.agents/skills/`. Загружай полный SKILL.md каждого:

### 🔴 ВСЕГДА (при любой работе)
| Скилл | Когда активен |
|-------|---------------|
| [secret-guard](.agents/skills/secret-guard/SKILL.md) | **ВСЕГДА** — перед любым push/commit |
| [python-syntax-guard](.agents/skills/python-syntax-guard/SKILL.md) | **ВСЕГДА** — при редактировании .py |
| [ponytail](.agents/skills/ponytail/SKILL.md) | **ВСЕГДА** — пиши минимальный код |

### 🟡 При работе с конкретными модулями
| Скилл | Когда активен |
|-------|---------------|
| [gui-style-guard](.agents/skills/gui-style-guard/SKILL.md) | При изменении gui/ или theme.py |
| [build-guard](.agents/skills/build-guard/SKILL.md) | При сборке EXE или релизе |
| [smtp-engine-guard](.agents/skills/smtp-engine-guard/SKILL.md) | При изменении core/sender.py |
| [openai-guard](.agents/skills/openai-guard/SKILL.md) | При изменении core/ai_fixer.py |
| [pyqt6-patterns](.agents/skills/pyqt6-patterns/SKILL.md) | При изменении gui/ |
| [server-deploy-guard](.agents/skills/server-deploy-guard/SKILL.md) | При изменении server/ |
| [license-server-guard](.agents/skills/license-server-guard/SKILL.md) | При изменении server/database.py, server/bot.py |
| [patch-updater-guard](.agents/skills/patch-updater-guard/SKILL.md) | При изменении core/updater.py, make_patch.py |
| [i18n-guard](.agents/skills/i18n-guard/SKILL.md) | При изменении текстов в UI |
| [changelog-guard](.agents/skills/changelog-guard/SKILL.md) | При каждом релизе |

## Специализированные скиллы (по области)

### SMTP и Email
| Скилл | Назначение |
|-------|-----------|
| [smtp-error-diagnosis](.agents/skills/smtp-error-diagnosis/SKILL.md) | Коды ошибок SMTP, диагностика |
| [smtp-port-fallback](.agents/skills/smtp-port-fallback/SKILL.md) | Стратегия перебора портов 465/587/25 |
| [smtp-auth-methods](.agents/skills/smtp-auth-methods/SKILL.md) | AUTH PLAIN/LOGIN/XOAUTH2/CRAM-MD5 |
| [smtp-configs-extended](.agents/skills/smtp-configs-extended/SKILL.md) | Расширенный список SMTP конфигов |
| [smtp-validator](.agents/skills/smtp-validator/SKILL.md) | Логика smtp_validator.py |
| [async-smtp-guide](.agents/skills/async-smtp-guide/SKILL.md) | asyncio SMTP паттерны |
| [rambler-specifics](.agents/skills/rambler-specifics/SKILL.md) | Rambler.ru / lenta.ru / championat.com |
| [gmx-webde-guide](.agents/skills/gmx-webde-guide/SKILL.md) | GMX.com / gmx.de / web.de специфика |
| [oauth2-microsoft](.agents/skills/oauth2-microsoft/SKILL.md) | Microsoft OAuth2 для Outlook/Hotmail |

### Прокси и Сеть
| Скилл | Назначение |
|-------|-----------|
| [socks5-internals](.agents/skills/socks5-internals/SKILL.md) | SOCKS5 протокол, raw socket |
| [http-connect-proxy](.agents/skills/http-connect-proxy/SKILL.md) | HTTP CONNECT туннелирование |
| [proxy-smtp-requirements](.agents/skills/proxy-smtp-requirements/SKILL.md) | Требования к прокси для SMTP |
| [proxy-country-cache](.agents/skills/proxy-country-cache/SKILL.md) | Кэш страны/флага прокси (v4.4.0) |
| [rate-limit-strategy](.agents/skills/rate-limit-strategy/SKILL.md) | MAX_CONCURRENT, Semaphore, rate limits |
| [debug-network](.agents/skills/debug-network/SKILL.md) | Отладка сетевых проблем |

### GUI и PyQt6
| Скилл | Назначение |
|-------|-----------|
| [pyqt6-threading-guide](.agents/skills/pyqt6-threading-guide/SKILL.md) | QThread паттерны, thread safety |
| [pyqt6-table-patterns](.agents/skills/pyqt6-table-patterns/SKILL.md) | QTableWidget паттерны |
| [gui-ux-principles](.agents/skills/gui-ux-principles/SKILL.md) | UX принципы, диалоги, обратная связь |
| [gui-status](.agents/skills/gui-status/SKILL.md) | Status bar, статусные иконки |
| [memory-management-qt](.agents/skills/memory-management-qt/SKILL.md) | Qt parent-child, GC, утечки памяти |
| [error-messages-ru](.agents/skills/error-messages-ru/SKILL.md) | Понятные ошибки на русском для UI |
| [color-palette](.agents/skills/color-palette/SKILL.md) | CyberPro цветовая палитра |

### Аккаунты и Данные
| Скилл | Назначение |
|-------|-----------|
| [account-persistence](.agents/skills/account-persistence/SKILL.md) | Сохранение/загрузка аккаунтов JSON |
| [inbox-bypass-prompts](.agents/skills/inbox-bypass-prompts/SKILL.md) | Промпты для обхода спам-фильтров |
| [reply-monitor](.agents/skills/reply-monitor/SKILL.md) | Мониторинг ответов IMAP |
| [spam-score-pro](.agents/skills/spam-score-pro/SKILL.md) | SpamAssassin-совместимый спам-скор |
| [html-generator](.agents/skills/html-generator/SKILL.md) | Генерация HTML писем |

### Безопасность и Качество
| Скилл | Назначение |
|-------|-----------|
| [security-checklist](.agents/skills/security-checklist/SKILL.md) | Чеклист безопасности перед релизом |
| [code-review-guide](.agents/skills/code-review-guide/SKILL.md) | Чеклист code review |
| [logging-guide](.agents/skills/logging-guide/SKILL.md) | Что/как логировать, запреты |
| [testing-guide](.agents/skills/testing-guide/SKILL.md) | Тест-кейсы, unit тесты, pytest |
| [performance-guide](.agents/skills/performance-guide/SKILL.md) | Оптимизация, профилирование |

### Сборка и Релизы
| Скилл | Назначение |
|-------|-----------|
| [windows-exe-build](.agents/skills/windows-exe-build/SKILL.md) | PyInstaller EXE сборка |
| [pyinstaller-spec](.agents/skills/pyinstaller-spec/SKILL.md) | spec файл, hidden imports, data files |
| [release-workflow](.agents/skills/release-workflow/SKILL.md) | Полный процесс релиза через GitHub API |
| [changelog-guide](.agents/skills/changelog-guide/SKILL.md) | Как писать CHANGELOG.md |
| [vps-server-guide](.agents/skills/vps-server-guide/SKILL.md) | Деплой server/ на VPS, бот |

### Мультиагентная работа
| Скилл | Назначение |
|-------|-----------|
| [agent-roles](.agents/skills/agent-roles/SKILL.md) | Кто что делает, какой агент когда |
| [parallel-agent-guide](.agents/skills/parallel-agent-guide/SKILL.md) | Параллельная работа агентов |

## Специализированные агенты

Все агентные промпты в `.agents/prompts/`:

| Агент | Файл | Специализация |
|-------|------|--------------|
| Architect | [architect.md](.agents/prompts/architect.md) | Архитектурные решения, рефакторинг |
| GUI Agent | [gui-agent.md](.agents/prompts/gui-agent.md) | PyQt6 UI, дизайн, виджеты |
| SMTP Expert | [smtp-expert.md](.agents/prompts/smtp-expert.md) | SMTP протокол, провайдеры, ошибки |
| Proxy Expert | [proxy-expert.md](.agents/prompts/proxy-expert.md) | SOCKS5/HTTP прокси, страны |
| Code Reviewer | [code-reviewer.md](.agents/prompts/code-reviewer.md) | Code review, качество кода |
| Security Agent | [security-agent.md](.agents/prompts/security-agent.md) | Безопасность, поиск секретов |
| Tester | [tester.md](.agents/prompts/tester.md) | QA, тест-кейсы, pytest |
| DevOps | [devops-agent.md](.agents/prompts/devops-agent.md) | Сборка EXE, CI/CD, релизы |
| Debugger | [debugger.md](.agents/prompts/debugger.md) | Отладка сложных проблем |
| Orchestrator | [orchestrator.md](.agents/prompts/orchestrator.md) | Координация всех агентов |

## Стек проекта

- **GUI:** Python 3.11 + PyQt6 — дизайн CyberPro (BG #040410, ACCENT #8B5CF6, CYAN #06B6D4)
- **Core:** async SMTP (aiosmtplib), spam checker, warmup, bounce IMAP
- **AI:** OpenAI API через `core/ai_fixer.py` — env `OPENAI_API_KEY`
- **Server:** FastAPI + aiogram Telegram Bot + aiosqlite + CryptoBot
- **Build:** PyInstaller → .exe, GitHub Actions, patch-система обновлений
- **i18n:** Qt Linguist (.ts файлы): `i18n/en_US.ts`, `i18n/ru_RU.ts`

## Абсолютные правила

1. **Никаких секретов в коде.** Всё через переменные окружения или .env (secret-guard)
2. **Синтаксис Python проверяется ДО push.** (python-syntax-guard)
3. **CyberPro дизайн не нарушается.** (gui-style-guard)
4. **Минимальный код.** Stdlib > новая зависимость. 1 строка > 50. (ponytail)
5. **Thread safety в GUI.** Никаких прямых вызовов Qt из не-UI потоков. (pyqt6-patterns)
6. **Backward compatibility в patch-системе.** (patch-updater-guard)
7. **MAX_CONCURRENT = 4.** Не увеличивать — rate limits у GMX и ip-api.com.
8. **Страна прокси кэшируется.** `_proxy_country_cache` — не сбрасывай при _refresh_table.

## Структура файлов

```
main.py              — точка входа + patch loader
core/
  sender.py          — async SMTP engine (SmtpAccount, _test_smtp_sync, configs)
  smtp_validator.py  — валидация аккаунтов (_try_smtp_connect, PROXY_BLOCKS_SMTP)
  ai_fixer.py        — OpenAI spam fixer
  spam_checker.py    — анализатор спама (score 0-100)
  warmup.py          — прогрев SMTP аккаунтов
  bounce.py          — IMAP bounce parser
  updater.py         — auto-updater с patch поддержкой
  license.py         — проверка JWT лицензий
  _version.py        — APP_VERSION, APP_NAME
gui/
  app.py             — MainWindow, sidebar nav
  theme.py           — Colors, Spacing, Typography, get_stylesheet()
  screens/           — 8 экранов приложения
    screen_accounts.py — аккаунты, валидация, _CountryWorker, TestWorker
    screen_sender.py   — рассылка писем
  widgets/           — animated_bg.py и прочие виджеты
server/
  bot.py             — Telegram Bot + FastAPI (120k chars!)
  database.py        — aiosqlite license DB
  crypto_pay.py      — CryptoBot payment client
  config.py          — env configuration
i18n/                — Qt Linguist переводы
.agents/
  skills/            — 52 специализированных скилла
  prompts/           — 10 агентных промптов
  memory/            — MEMORY.md (персистентная память агентов)
```

## GitHub API (вместо git commit)

В Replit main agent git commit запрещён. Используй GitHub REST API:
1. Читай token из `attached_assets/fmmail_*.txt` (НИКОГДА не выводи его)
2. Паттерн: create blobs → create tree → create commit → update ref
3. Owner: `FTPLabs`, Repo: `FMailSender`, Branch: `main`
4. Детали: `.agents/skills/release-workflow/SKILL.md`
