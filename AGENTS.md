# FMailSender — AI Agent Instructions

  > **ВАЖНО: Прочти этот файл ПЕРВЫМ перед любым действием в репозитории.**

  ## Обязательные скиллы — активируй все при старте сессии

  Все скиллы находятся в `.agents/skills/`. Загружай полный SKILL.md каждого:

  | Скилл | Когда активен |
  |-------|---------------|
  | [secret-guard](.agents/skills/secret-guard/SKILL.md) | **ВСЕГДА** — перед любым push/commit |
  | [python-syntax-guard](.agents/skills/python-syntax-guard/SKILL.md) | **ВСЕГДА** — при редактировании .py |
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
  | [ponytail](.agents/skills/ponytail/SKILL.md) | **ВСЕГДА** — пиши минимальный код |

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

  ## Структура файлов

  ```
  main.py              — точка входа + patch loader
  core/
    sender.py          — async SMTP engine v2.9.1
    ai_fixer.py        — OpenAI spam fixer
    spam_checker.py    — анализатор спама (score 0-100)
    warmup.py          — прогрев SMTP аккаунтов
    bounce.py          — IMAP bounce parser
    updater.py         — auto-updater с patch поддержкой
    license.py         — проверка JWT лицензий
  gui/
    app.py             — MainWindow, sidebar nav
    theme.py           — Colors, Spacing, Typography, get_stylesheet()
    screens/           — 8 экранов приложения
    widgets/           — animated_bg.py и прочие виджеты
  server/
    bot.py             — Telegram Bot + FastAPI (120k chars!)
    database.py        — aiosqlite license DB
    crypto_pay.py      — CryptoBot payment client
    config.py          — env configuration
  i18n/                — Qt Linguist переводы
  ```
  