
## [3.7.5] — 2026-06-21

  ### Исправлено
  - **gui/screens/screen_accounts.py**: синтаксическая ошибка IndentationError в классе `AccountsScreen` — исправлен отступ с 2-space до стандартного 4-space (разблокирует Python Syntax Check CI)
  - **core/sender.py**: исправлены 4 нерабочих SMTP-хоста по результатам TCP-диагностики:
    - `verizon.net`: `outgoing.verizon.net` (ENOTFOUND) → `smtp.aol.com` (Verizon продала почту AOL в 2017)
    - `sky.com`: `smtp.sky.com` (ENOTFOUND) → `smtp.office365.com` (Sky UK перешла на Office 365)
    - `mail.ua`: `smtp.mail.ua` (ENOTFOUND) → `smtp.ukr.net` (инфраструктура ukr.net)
    - `mail.lt`: `smtp.mail.lt` (ENOTFOUND) → `smtp.domreg.lt`

  ### Диагностика
  - Проверено 51 уникальный SMTP-сервер: 43 ✅ доступны, 8 ❌ недоступны (4 исправлены, 4 временно недоступны)

  ## [3.7.4] — 2026-06-21

  ### Исправления безопасности и стабильности

  - **[БАГ КРИТ]** `bot.py`: 5 мест `bare except: pass` заменены на `except Exception as _e` с `logger.warning()` — ошибки больше не глотаются молча
    - `JsonFileStorage._load()`: ошибки чтения FSM-файла и восстановления из .tmp логируются
    - captcha handler: ошибка отправки капчи логируется
    - subscription check: ошибка обновления markup логируется
    - admin broadcast: ошибка уведомления админа логируется
  - **[БАГ]** `bot.py`: 8 мест прямого доступа `dict["key"]` заменены на `dict.get("key", default)` — устраняет потенциальный `KeyError` при неполных данных из БД
    - `payment["plan"]`, `payment["telegram_id"]` (2 обработчика платежей + polling)
    - `license_data["key"]` (2 хендлера покупки)
    - `lic["plan"]` (активация лицензии)
    - `_m["telegram_id"]` (загрузка модераторов при старте)
  - **[БАГ]** `core/smtp_validator.py`: 2 места `bare except: pass` — добавлено логирование через `logging.getLogger("smtp_validator")`
    - DNSBL проверка: неожиданные ошибки логируются как WARNING
    - progress_cb: исключения в колбэке логируются как DEBUG

  ## [3.7.3] — 2026-06-21

  ### 🐛 Исправления
  - **HTML preview**: внешние изображения (Twitch logo, CDN) теперь загружаются — включены `LocalContentCanAccessRemoteUrls` + base URL `https://fmail.shop/` вместо `about:blank`
  - **SMTP статус**: правильное отображение из `last_test_ok` (не сбрасывается при обновлении экрана)
  - **SMTP сортировка**: после «Проверить все» — валидные аккаунты наверху, невалидные внизу

  ### ✨ Новое
  - **Колонка «Отправлено»**: в таблице SMTP-аккаунтов — показывает `sent/daily_limit` по каждому адресу

  ## [3.7.3] — 2026-06-21

  ### 🐛 Исправления
  - **HTML preview**: загрузка внешних изображений (Twitch logo, CDN) в `QWebEngineView` —
    включены `LocalContentCanAccessRemoteUrls` + base URL `https://fmail.shop/` вместо `about:blank`
  - **SMTP аккаунты**: правильное отображение статуса из `last_test_ok` (не сбрасывается в «Ожидание» после первой проверки)
  - **SMTP сортировка**: после «Проверить все» аккаунты автоматически сортируются — валидные наверху, невалидные внизу

  ### ✨ Новые возможности
  - **Колонка «Отправлено»** в таблице SMTP-аккаунтов — показывает `sent/daily_limit` для каждого адреса

  # Changelog

  ## v3.7.2 — Bugfix Release (2025-06-21)

  ### 🐛 Bugfixes
  - **КРИТИЧЕСКИЙ** `gui/screens/screen_accounts.py` строка 841: исправлен `IndentationError` — метод `_update_contextual_buttons` имел отступ 4 пробела вместо 2. Приложение не запускалось.
  - `server/crypto_pay.py`: лишние пробелы в блоке `except aiohttp.ClientError` (14→12sp). PEP 8 восстановлен.
  - `main.py`: несоответствие комментария и кода (`timeout=10.0` сек, комментарий говорил «3 сек»).

  ### ✅ Проверено скиллами
  - python-syntax-guard, smtp-engine-guard, build-guard, changelog-guard

  ---

    ## v3.6.2 — GUI Python PyQt6 + Bugfixes (2025-06-19)

  ### ✨ New
  - **gui/**: Полный PyQt6 GUI-пакет v3.6.2 (CyberPro dark theme)
    - `gui/theme.py` — Colors, Spacing, Typography, get_stylesheet()
    - `gui/icons.py` — иконки и nav-конфигурация
    - `gui/app.py` — MainWindow с sidebar-навигацией и StackedWidget
    - `gui/widgets/animated_bg.py` — анимированный фон (3 orbs + dot grid)
    - `gui/screens/screen_activation.py` — экран активации лицензии (сигнал activation_success)
    - `gui/screens/screen_dashboard.py` — дашборд: KPI-карточки, прогресс, live-лог
    - `gui/screens/screen_accounts.py` — SMTP-аккаунты: таблица, добавление, импорт, проверка
    - `gui/screens/screen_recipients.py` — получатели: список, импорт, валидация, дедупликация, экспорт
    - `gui/screens/screen_compose.py` — редактор письма: HTML/plain, вложения, опции
    - `gui/screens/screen_sending.py` — рассылка: настройки, прогресс, лог, управление
    - `gui/screens/screen_inbox.py` — входящие: bounce-таблица, ответы, автоправила
  - `core/_version.py`: APP_VERSION обновлён до 3.6.2

  ### 🔧 Bugfixes v2.9.4
  - **smtp_validator**: удалены IMAP-порты 993/143/994 из SMTP fallback-списка
  - **bounce**: regex разделён на HARD_CODE_RE + HARD_TEXT_RE (многострочные DSN)
  - **duplicate_detector**: добавлены outlook.co.uk/jp, live.ru, hotmail.ru/es/it, internet.ru, ro.ru
  - **server/config**: WARN при некорректных значениях ADMIN_IDS
  - **sender v2.9.4**: логирование в silent except-блоках

  ### 🎨 Design
  - GUI_STATUS.md обновлён до v3.6.2
  - design/ — новые SVG-ассеты (color-palette, banner, avatar, icons-sprite)
  - .agents/skills/gui-status/ и .agents/skills/color-palette/ созданы

  ---

  ## v3.5.5 — Premium GUI overhaul (ранее)
  - Redesign всего GUI: тёмная тема CyberPro, фиолетовый неон
  