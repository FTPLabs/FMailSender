## [6.7.5] — 2026-07-01

### Security / Fixed

- **LIC-PERIODIC — Периодическая проверка лицензии каждый час** (`core/server.py`): добавлен фоновый поток `_periodic_license_checker` (daemon), запускается вместе с сервером через `_lifespan`. Каждые 3600 секунд (1 час) вызывает `validate_on_startup()` — строгая проверка, всегда обращается к серверу лицензий, не пропускает через кэш. Если сервер возвращает `valid=false` (подписка закончилась, ключ отозван) → `_license_ok = False` + активная рассылка немедленно останавливается. Клиент с истёкшей подпиской не сможет продолжать рассылку дольше 1 часа. Оффлайн-грейс (7 дней) применяется только при недоступности сети.

- **VER — Версия 6.7.5** (`core/_version.py`, `tauri.conf.json`, `ui/src/version.ts`, `src-tauri/Cargo.toml`).

---

## [6.7.4] — 2026-07-01

### Security / Fixed

- **EMBED-CORE — fmail-core вшит внутрь FMailSender.exe** (`src-tauri/src/main.rs`, `tauri.conf.json`, `portable.nsi`): ядро Python больше **не является отдельным файлом** рядом с приложением. При запуске FMailSender.exe распаковывает fmail-core из своего тела во временный `%TEMP%\fmailsender-{uuid}\`, запускает оттуда, при закрытии — убивает и удаляет временный файл. Клиент не может запустить старое ядро самостоятельно; злоумышленник не может подменить бинарь.

- **KILL-CLEANUP — Удаление старых копий fmail-core из %LOCALAPPDATA%** (`main.rs`): при старте 6.7.4 автоматически удаляются `fmail-core*.exe` из `%LOCALAPPDATA%\FMailSender\`, оставшиеся от версий 6.7.3 и ранее.

- **KILL-PORT-WAIT — Надёжное ожидание освобождения порта** (`main.rs`): вместо фиксированного `sleep(300ms)` используется цикл с проверкой `TcpStream::connect` (до 5 с), гарантирующий, что новое ядро не подключается к старому процессу.

- **VER — Версия 6.7.4** (`core/_version.py`, `tauri.conf.json`, `ui/src/version.ts`, `src-tauri/Cargo.toml`).

---

## [6.7.4] — 2026-07-01

### Fixed

- **CORE-KILL-1 — fmail-core оставался в диспетчере задач после закрытия** (`src-tauri/src/main.rs`): при закрытии окна приложения убивался только дочерний процесс текущей сессии. Если старый fmail-core выжил от предыдущего запуска (например, при принудительном закрытии), он оставался в памяти. Исправлено: в обработчик `on_window_event` добавлен явный `taskkill /F /IM fmail-core*.exe` — убивает все экземпляры по имени, независимо от того, кто их запустил.

- **CORE-KILL-2 — 300 мс сон после kill недостаточен при запуске** (`src-tauri/src/main.rs`): фиксированный `thread::sleep(300ms)` в `kill_existing_core()` не гарантировал освобождение порта — Windows может удерживать TCP-сокет до 2 с после SIGKILL. Заменён на цикл: ждём пока `TcpStream::connect` вернёт `Err` (порт свободен), максимум 5 с, затем дополнительно 300 мс для освобождения файловых хендлов. Результат: новый fmail-core 6.7.4 никогда не подключается к старому ядру.

- **VER-2 — Синхронизация версий на 6.7.4** (`core/_version.py`, `tauri.conf.json`, `ui/src/version.ts`).

---

## [6.7.3] — 2026-07-01

### Fixed

- **LIC-FIX-1 — activate_license_key() игнорировал valid=false при HTTP 200** (core/license.py): сломанная проверка `if not result.get("valid", True) is False: pass` заменена на явную: если сервер вернул valid=false при HTTP 200 — активация отклоняется с ошибкой. Ранее любой ответ с кодом 200 безусловно сохранял ключ как действительный.

- **LIC-FIX-2 — .catch() на проверке лицензии открывал приложение без ключа** (ui/src/components/StartupOverlay.tsx): при любой сетевой или parse-ошибке во время fetch /api/license — .catch(() => setLicenseOk(true)) скрытно открывал приложение. Исправлено: ошибка показывает экран активации.

- **LIC-FIX-3 — null-ответ сервера лицензий трактовался как valid** (ui/src/components/StartupOverlay.tsx): добавлена защита от null/malformed-ответа — теперь показывается экран активации вместо молчаливого входа.

- **VER-1 — Рассинхрон версий** (core/_version.py, tauri.conf.json, ui/src/version.ts): все файлы синхронизированы на 6.7.3. До исправления: core=6.7.2, tauri=6.7.0, frontend=6.7.0 — приложение отображало старую версию.

- **UI-1 — Логотип молнии в сайдбаре заменён на оригинальный fmail_logo.png** (ui/src/components/Layout.tsx): вместо иконки Lucide Zap используется фактический логотип в круглой рамке.

- **UI-2 — Логотип на экране активации и загрузки заменён на оригинальный** (ui/src/components/StartupOverlay.tsx): компонент AppLogo переделан с буквы F на реальное изображение fmail_logo.png с анимацией свечения.

- **UI-3 — Некорректное выравнивание полей в «Настройки отправки»** (ui/src/pages/Compose.tsx): метка смещала input выше остальных. Исправлено: grid-cols-3 items-end + разбивка меток.

---

## [6.7.2] — 2026-07-01

### Fixed

- **LIC-1 — Отозванная лицензия оставалась активной до 24 часов** (`core/license.py`): добавлена функция `validate_on_startup()`, которая **всегда** обращается к серверу лицензий при каждом запуске. Если сервер вернул `valid: false` — кэш немедленно инвалидируется, офлайн-грейс не применяется. Грейс-период (7 дней) сохраняется только при реальной недоступности сети.

- **LIC-2 — API-роуты были доступны без действующей лицензии** (`core/server.py`): добавлен FastAPI-middleware `_license_guard`, блокирующий все запросы (кроме `/api/health`, `/api/license`, `/api/license/activate`, `/api/events`) с кодом 403, пока лицензия не подтверждена. Состояние `_license_ok` устанавливается при старте сервера и обновляется при каждом обращении к `GET /api/license`.

- **LIC-3 — Клиент не реагировал на отзыв лицензии в активной сессии** (`ui/src/components/StartupOverlay.tsx`): добавлена периодическая ревалидация каждые 60 минут. При получении `valid: false` экран активации отображается повторно поверх приложения.

---

## [6.7.1] — 2026-07-01

### Fixed (Code Review — 5 bugs)

- **SEC-1 — `refresh_token` хранился в открытом виде** (`core/storage.py`): шифрование через Fernet добавлено для `refresh_token` в `save_accounts()` / `load_accounts()` — наравне с `access_token`.

- **COMPAT-1 — `load_campaign()` падал с TypeError при смене версии** (`core/storage.py`): ключи JSON фильтруются через `dataclasses.fields(CampaignConfig)` перед созданием объекта.

- **HANG-1 — IMAP reconnect в BounceMonitor зависал** (`core/bounce.py`): `_IMAP_TIMEOUT = 30` вынесен на уровень модуля; reconnect теперь передаёт `timeout=_IMAP_TIMEOUT`.

- **HANG-2 — IMAP в ReplyMonitor без таймаута** (`core/reply_monitor.py`): добавлен `timeout=30` к IMAP-соединению в `_check_inbox()`.

- **REGEX-1 — Опечатка `s*` вместо `\\s*` в `_parse_reply`** (`core/reply_monitor.py`): парсинг From-заголовка «Name \<addr\>» был полностью сломан — исправлено.

---


## [6.7.0] — 2026-06-30

### Fixed
- **CRITICAL — GMX SMTP validation**: `SMTPNotSupportedError` now probes a direct connection (without proxy) before classifying the error. Previously, all accounts using proxies showed "SMTP AUTH не поддерживается" even when SMTP was enabled — because the proxy was silently breaking STARTTLS negotiation, causing AUTH to disappear from the EHLO response. Now the app distinguishes: (A) proxy blocks STARTTLS → "смените прокси", (B) GMX SMTP genuinely disabled → enable in GMX settings.
- **Standalone EXE**: replaced 7-Zip SFX (extracted to random `%TEMP%\7z*` on every run, deleted after close) with NSIS persistent launcher. On first run: silently installs to `%LOCALAPPDATA%\FMailSender\`, creates Desktop shortcut. On subsequent runs: launches immediately from installed location. No wizard, no UAC prompt, no temp files.

## [6.6.0] — 2026-06-30

    ### Code Review & Sync

    - **Версии** — синхронизированы во всех манифестах (core/_version.py, ui/src/version.ts, tauri.conf.json, Cargo.toml): CI обновлял их только в памяти агента, в репо оставалась устаревшая 6.4.0
    - **Cargo.toml** — исправлены некорректные отступы в секции [package]
    - **release.yml** — обновлена версия по умолчанию для workflow_dispatch (была 6.4.0 → теперь 6.6.0)

    ---

  ## [6.4.0] — 2026-06-30

  ### Bug Fixes

  - **core/sender.py** — GMX/web.de: правильное сообщение «включите SMTP в настройках GMX» вместо инструкции для Outlook/Gmail  
  - **core/license.py** — Стабильный HWID: Windows MachineGuid → WMIC motherboard UUID → WMIC CPU ID → MAC fallback (меняется только при замене железа)  
  - **ui/src/components/StartupOverlay.tsx** — Race condition: окно активации лицензии больше не мигает и не исчезает до ответа /api/license

  ### Changes

  - GitHub Release теперь содержит единственный файл: `FMailSender-v6.4.0.exe` (без ZIP, без -setup суффикса)

  ---

  ## [6.3.1] — 2026-06-30

### Исправления (Bug Fixes)

#### 🔴 Критический: IndentationError в core/license.py
- **Причина**: весь файл имел лишний отступ 2 пробела (строки 8+) → `IndentationError` при импорте
- **Эффект**: `GET /api/license` и `POST /api/license/activate` падали с 500 Internal Server Error
- **Исправление**: убраны лишние 2 пробела в начале каждой строки

#### 🔴 Высокий: parse_proxy() классифицирует HTTP-прокси как socks5://
- **Причина**: ветка `if "@" in raw:` возвращала `socks5://` для нестандартных портов
- **Эффект**: коммерческие reseller-прокси (user:pass@host:port) не работали для SMTP
- **Исправление**: схема по умолчанию изменена с `socks5` на `http` для формата без явной схемы
  Явный `socks5://` от пользователя по-прежнему работает корректно

---

## [6.3.0] — 2026-06-29

  ### Исправления (Bug Fixes)

  #### 🔴 Критический: SMTP AUTH не поддерживается сервером (JMX, Outlook, Office365)
  - **Причина**: импорт файла `email|password|refresh_token` парсил только 2 поля — refresh_token всегда терялся → OAuth2 никогда не активировался → Basic AUTH → `SMTPNotSupportedError`
  - **Исправление 1** (`core/server.py`): `AccountIn` теперь содержит поля `refresh_token: str = ""` и `access_token: str = ""`; `_make_account()` корректно передаёт их в `SmtpAccount`
  - **Исправление 2** (`core/server.py`): эндпоинт `/api/accounts/import-txt` читает 3-е поле строки как `refresh_token`
  - **Исправление 3** (`core/sender.py`): `_is_oauth_acct` теперь проверяет также SMTP-хост (`office365.com`) — аккаунты на кастомных доменах (JMX, корпоративные) через Office365 ранее не определялись
  - **Исправление 4** (`core/sender.py`): `SMTPNotSupportedError` теперь показывает конкретную инструкцию по решению в зависимости от типа аккаунта (MS без токена / MS с истёкшим токеном / Gmail)
  - **Исправление 5** (`ui/src/pages/Accounts.tsx`): добавлено поле `Refresh Token` в форму аккаунта
  - **Исправление 6** (`ui/src/api.ts`): интерфейс `Account` содержит поля `refresh_token` и `access_token`

  ### Новые возможности

  #### 🔐 Система лицензирования восстановлена
  - **`core/license.py`** (новый): валидация ключей против `fmail.shop`, кэш на диске (24ч), оффлайн-режим 7 дней
  - **`core/server.py`**: эндпоинты `GET /api/license` и `POST /api/license/activate`
  - **`ui/src/api.ts`**: API-хуки `api.license.get()` и `api.license.activate(key)`
  - **`ui/src/components/StartupOverlay.tsx`**: экран активации лицензии показывается при старте если ключ не введён или недействителен

  ---

  ## [6.2.0] — 2026-06-29

### 🔴 DKIM signing — полная реализация (#6)

- **core/dkim_signer.py** (новый модуль) — RFC 6376 DKIM подпись через `dkimpy`.
  Graceful fallback если dkimpy не установлен (письма отправляются без подписи, предупреждение в лог).
  Функции: `sign_message_bytes`, `load_configs/save_configs`, `validate_config`, `get_config_for_domain`.
  Хранение: `data/dkim_configs.json` (атомарная запись через tmp + os.replace).
- **core/sender.py** — DKIM подпись интегрирована в `_send_sync` во всех 3 точках отправки
  (основная + port fallback 465 + port fallback 587). `_smtp_send_signed()` — локальный хелпер,
  переключается между `sendmail(signed_bytes)` и `send_message(msg)`.
- **core/server.py** — REST API:
  - `GET /api/dkim` — список конфигов
  - `POST /api/dkim` — добавить/обновить конфиг
  - `DELETE /api/dkim/{domain}` — удалить
  - `POST /api/dkim/validate` — проверить ключ без сохранения

### ⚡ SMTP Connection Reuse (#5)

- **core/sender.py** — новый класс `_SmtpConnectionCache`:
  checkout/checkin паттерн, MAX_REUSE=50 писем на соединение, MAX_IDLE_SECS=90 сек.
  После успешной отправки соединение сохраняется в пуле вместо `quit()`.
  Thread-safe через `threading.Lock`. Инициализируется в `SendingEngine.__init__`.

### 🛡️ Rate Limiting per Destination Domain (#3)

- **core/sender.py** — новый класс `_DomainRateLimiter`:
  консервативные почасовые лимиты для Gmail(150), Yahoo(100), Outlook(120), GMX(60) и др.
  Интегрирован в `_send_with_acct_delay` с ожиданием 30s при превышении.
  Лог-сообщение при начале throttling: "Rate limit @gmail.com: 150/150/hour — жду 30s..."

### 🔧 Tracking Pixel (#2)

- **core/uniqueizer.py** — `technique_tracking_pixel` переписан: data:URI УДАЛЁН.
  Функция принимает `tracking_base_url` параметр. Без URL — NO-OP (ничего не добавляет).
  Для работы нужен внешний tracking сервер: `https://track.yourdomain.com/open/{uid}.gif`.

---

## [6.1.0] — 2026-06-29

### 🔴 Критические исправления (deliverability)

- **core/sender.py** — добавлены заголовки `List-Unsubscribe`, `List-Unsubscribe-Post: List-Unsubscribe=One-Click` (RFC 8058) и `Precedence: bulk` в каждое письмо. **Обязательное требование Gmail + Yahoo с февраля 2024** для bulk-отправителей; без этого письма помечаются спамом автоматически.
- **core/sender.py** — `Date` заголовок теперь через `email.utils.formatdate(localtime=False)` — строгое RFC 2822 соответствие.
- **core/html_generator.py** — удалена инструкция `"Insert Zero Width Space (U+200B)"` из `UNIQUEIZE_PROMPT`. ZWS — классический спам-сигнал (SpamAssassin ZERO_WIDTH_SPACE +1.5); прямо противоречила `uniqueizer.py` где эта техника помечена как запрещённая.
- **core/spam_checker.py** — добавлена проверка **link density** (>5 ссылок = предупреждение, >10 = штраф). SpamAssassin даёт +1.5 за избыток ссылок. Добавлена проверка **inline base64 изображений** (data:URI) — спам-сигнал в Gmail.
- **core/send_checkpoint.py** — `CHECKPOINT_DIR` теперь **кросс-платформенный** (был захардкоден Windows-путь `AppData/Roaming`; на macOS/Linux создавал путь `~/AppData/Roaming/FMailSender/checkpoints` которого не существует → краш при первом checkpoint).

### 📊 Новое: официальные лимиты SMTP по провайдерам

- **core/smtp_limits.py** (новый файл) — официальные daily/hourly лимиты для **50+ провайдеров** на основе официальной документации каждого. Источники: support.google.com, help.yahoo.com/kb/SLN3403.html, support.microsoft.com, support.gmx.com, yandex.com/support, help.mail.ru, support.apple.com/en-us/102576, zoho.com/mail/help/smtp-access.html и др.
- **core/server.py** — `POST /api/accounts/import-txt` теперь автоматически применяет `apply_limits_to_account()` при импорте — каждый аккаунт получает правильный daily/hourly лимит по домену (не дефолтный 500/50 для всех).

### 📅 Warmup schedule исправлен

- **core/warmup.py** — убран безграничный рост после дня 30. Прежняя формула `500 + (day-30)*20` давала день 60 = 1100, день 90 = 1700 — GMX/Yahoo блокируют >500/день с новых аккаунтов. Новый cap: день 30-59 = 500→800 (+10/day), день 60+ = стабильные 800.

### 🧪 Тесты

- **tests/test_comprehensive.py** (новый файл) — 70+ тестов: smtp_limits, SMTP config resolution, uniqueizer, spam checker, proxy parser, duplicate detector, warmup, bounce parser, `_build_message` headers, checkpoint, OAuth2, email template personalization, SmtpAccount limits.

### 📚 Документация

- **.agents/skills/smtp-daily-limits/SKILL.md** (новый) — полная таблица лимитов, critical notes по GMX (residential proxies), Gmail App Password, Yahoo App Password, Outlook SMTP AUTH, Microsoft OAuth2.

---

## [6.0.5] — 2026-06-29

  ### 🐛 Исправления

  - **core/models.py** — добавлен `__getattr__` safety-net для `_lock`, `_day_reset`, `_hour_reset`.
    Гарантирует наличие `_lock` при **любом** способе создания объекта:
    старый `.pyc` кэш (Python переиспользует bytecode без `__post_init__`),
    `copy.copy()`, `pickle`, `dataclasses.replace()`. Окончательно закрывает
    `AttributeError: 'SmtpAccount' object has no attribute '_lock'`.
  - **core/sender.py** — аналогичный `__getattr__` safety-net добавлен в `sender.SmtpAccount`
    (defence-in-depth: engine работает с аккаунтами напрямую через duck-typing).
  - **core/server.py** — `asyncio.get_event_loop()` → `asyncio.get_running_loop()` в
    `check_proxies_endpoint` (deprecated Python 3.10+, вызывал DeprecationWarning).
  - **core/_version.py** — 6.0.4 → 6.0.5

  ### 📋 Код-ревью: что проверено

  - Все пути создания `SmtpAccount`: constructor / `from_dict` / `_make_account` / import-txt — OK
  - Duck-compat `models.SmtpAccount` ↔ `sender.SmtpAccount` — полный
  - Thread-safety: все инкременты через `try_increment()` — OK
  - asyncio: все вызовы внутри корутин используют `get_running_loop()` — OK

  ## [6.0.4] — 2026-06-29

  ### 🐛 Исправления

  - **core/sender.py** — `asyncio.get_event_loop()` заменён на `asyncio.get_running_loop()` в `run_campaign()`. `get_event_loop()` deprecated в Python 3.10+ при наличии работающего loop; вызов внутри корутины мог приводить к DeprecationWarning и ошибке в Python 3.12+. Исправляет SND-001.
  - **.gitignore** — добавлен (ранее отсутствовал): `data/`, `server/.env`, `server/licenses.db`, `__pycache__/`, `*.pyc`, `ui/node_modules/`, `src-tauri/target/`
  - **Скиллы агентов** — обновлены 4 скилла, содержавших устаревшие ссылки на PyQt6/Qt (v5): `proxy-smtp-check`, `smtp-engine-guard`, `full-system-audit`, `cancel-guard` — все переписаны под актуальную архитектуру v6 (Tauri + FastAPI + React)
  - **.agents/memory/MEMORY.md** — создан (ранее отсутствовал): индекс долгосрочной памяти агента

  ### 📦 Без изменений API — обратно совместимо

  
## [6.0.3] — 2026-06-29

  ### 🐛 Исправления

  - **models.SmtpAccount** — добавлен `__post_init__`: теперь создаются `_lock`, `_day_reset`, `_hour_reset` при инициализации. Исправляет `AttributeError: 'SmtpAccount' object has no attribute '_lock'` при запуске рассылки
  - Добавлены методы `try_increment()`, `decrement_sent()`, `can_send` — полный duck-compat с `sender.SmtpAccount`

  ### 📦 Без изменений API — обратно совместимо

  
## [6.0.2] — 2026-06-27

### 🔧 Исправления

- **storage.py** — данные теперь хранятся в `%APPDATA%\FMailSender\` (не в temp-директории PyInstaller)
- **api.ts** — добавлен отсутствующий метод `campaign.resume()`
- **Sending.tsx** — кнопка «Продолжить» теперь вызывает `/api/campaign/resume`, а не `/api/campaign/start` (был баг)
- **main.rs** — поиск sidecar теперь также проверяет директорию самого exe (portable-режим)
- **Версии** синхронизированы: `_version.py`, `Cargo.toml`, `tauri.conf.json` — все `6.0.2`
- **release.yml** — полностью переписан: теперь собирает portable `.exe` без установщика (NSIS-лаунчер + ZIP)

---

## [6.0.0] — 2026-06-27

  ### 🚀 Major — Полный редизайн: Tauri v2 + React + Vite

  Архитектура v6 полностью заменяет PyQt6-интерфейс на нативное десктопное приложение
  Tauri v2 с React/Vite фронтендом и Python FastAPI ядром.

  #### Новая архитектура
  - **Tauri v2 (Rust)** — нативная оболочка для Windows: WebView2, системный трей, NSIS-инсталлятор
  - **React 18 + Vite 5 + Tailwind CSS 3** — современный UI вместо PyQt6
  - **Python FastAPI** — ядро работает как sidecar-процесс (localhost:7531), упакован через PyInstaller в `fmail-core.exe`
  - **CyberPro дизайн-система** — тёмная тема #040410, акцент #8b5cf6 (фиолетовый) + #06b6d4 (голубой)

  #### Новые страницы
  - **Дашборд** — реалтайм-статистика: аккаунты, получатели, прокси, прогресс кампании
  - **Аккаунты** — CRUD + bulk-тест + импорт txt, автодетект SMTP-хоста по домену
  - **Получатели** — загрузка email-списков, импорт txt, переменные `{{name}}`
  - **Письмо** — редактор HTML/текст, превью в iframe, плейсхолдеры
  - **Рассылка** — ring-прогресс, скорость отправки, управление паузой/стопом
  - **Входящие** — IMAP-мониторинг ответов

  #### Сборка
  - PyInstaller 6.x совместимость (убран deprecated `cipher=`)
  - Единый CI/CD через `.github/workflows/release.yml`: Python core → Tauri bundle → NSIS/MSI
  - Размер установщика: ~20 МБ (vs ~60 МБ в v5.x)

  ---

  ## [5.2.4] â 2026-06-26

  ### Fix
  - **Ð¤Ð°Ð»ÑÑÐ¸Ð²ÑÐµ Â«Ð½ÐµÐ²Ð°Ð»Ð¸Ð´Ð½ÑÐµÂ» Ð°ÐºÐºÐ°ÑÐ½ÑÑ** (`core/sender.py`): ÐºÐ¾Ð³Ð´Ð° Ð¿ÑÐ¾ÐºÑÐ¸-IP Ð·Ð°Ð±Ð»Ð¾ÐºÐ¸ÑÐ¾Ð²Ð°Ð½ SMTP-ÑÐµÑÐ²ÐµÑÐ¾Ð¼ Ð¸ Ð¿ÑÑÐ¼Ð¾Ðµ Ð¿Ð¾Ð´ÐºÐ»ÑÑÐµÐ½Ð¸Ðµ ÑÐ°ÐºÐ¶Ðµ Ð½Ðµ Ð¿ÑÐ¾ÑÐ¾Ð´Ð¸Ñ Ð°Ð²ÑÐ¾ÑÐ¸Ð·Ð°ÑÐ¸Ñ, Ð°ÐºÐºÐ°ÑÐ½ÑÑ Ð±Ð¾Ð»ÑÑÐµ Ð½Ðµ Ð¿Ð¾Ð¼ÐµÑÐ°ÑÑÑÑ Â«ÐÐµÐ²Ð°Ð»Ð¸Ð´Ð½ÑÐ¹Â» (ÐºÑÐ°ÑÐ½ÑÐ¹). Ð¢ÐµÐ¿ÐµÑÑ Ð¾ÑÐ¾Ð±ÑÐ°Ð¶Ð°ÐµÑÑÑ Â«ÐÑÐ¸Ð±ÐºÐ° Ð¿ÑÐ¾ÐºÑÐ¸Â» (Ð¾ÑÐ°Ð½Ð¶ÐµÐ²ÑÐ¹) â ÑÑÐ¾ ÑÐµÑÑÐ½ÐµÐµ: Ð½ÐµÐ²Ð¾Ð·Ð¼Ð¾Ð¶Ð½Ð¾ Ð¿Ð¾Ð´ÑÐ²ÐµÑÐ´Ð¸ÑÑ Ð½ÐµÐ¿ÑÐ°Ð²Ð¸Ð»ÑÐ½ÑÐ¹ Ð¿Ð°ÑÐ¾Ð»Ñ, ÐµÑÐ»Ð¸ Ð¿ÑÐ¾ÐºÑÐ¸ Ð·Ð°Ð±Ð»Ð¾ÐºÐ¸ÑÐ¾Ð²Ð°Ð½. Ð¡Ð¾Ð¾Ð±ÑÐµÐ½Ð¸Ðµ Ð¾Ð± Ð¾ÑÐ¸Ð±ÐºÐµ ÑÑÐ°Ð»Ð¾ Ð±Ð¾Ð»ÐµÐµ Ð¸Ð½ÑÐ¾ÑÐ¼Ð°ÑÐ¸Ð²Ð½ÑÐ¼ (ÑÐ°Ð·Ð»Ð¸ÑÐ°ÐµÑ Ð¾ÑÐ¸Ð±ÐºÑ Ð°Ð²ÑÐ¾ÑÐ¸Ð·Ð°ÑÐ¸Ð¸ 534/535, Ð¿Ð¾Ð´ÑÐºÐ°Ð·ÑÐ²Ð°ÐµÑ Ð¿ÑÐ¾ App-Ð¿Ð°ÑÐ¾Ð»Ñ).
  - **ÐÐµÐ´Ð»ÐµÐ½Ð½Ð°Ñ Ð¿ÑÐ¾Ð²ÐµÑÐºÐ°** (`core/sender.py`): Ð¿ÑÐ¸ SMTP-Ð±Ð»Ð¾ÐºÐ¸ÑÐ¾Ð²ÐºÐµ IP Ð¿ÑÐ¾ÐºÑÐ¸ ÑÐµÐ¿ÐµÑÑ Ð¿ÑÐ¾Ð¿ÑÑÐºÐ°ÐµÑÑÑ Step 3 (12 Ð¿Ð¾Ð¿ÑÑÐ¾Ðº ÑÐµÑÐµÐ· Ð·Ð°Ð±Ð»Ð¾ÐºÐ¸ÑÐ¾Ð²Ð°Ð½Ð½ÑÐ¹ Ð¿ÑÐ¾ÐºÑÐ¸ Ð½Ð° ÑÐ°Ð·Ð½ÑÑ Ð¿Ð¾ÑÑÐ°Ñ). Ð­ÐºÐ¾Ð½Ð¾Ð¼Ð¸Ñ 6-8 ÑÐµÐºÑÐ½Ð´ Ð½Ð° Ð°ÐºÐºÐ°ÑÐ½Ñ â ÑÐºÐ¾ÑÐ¾ÑÑÑ Ð²ÐµÑÐ¸ÑÐ¸ÐºÐ°ÑÐ¸Ð¸ Ð·Ð½Ð°ÑÐ¸ÑÐµÐ»ÑÐ½Ð¾ Ð²Ð¾Ð·ÑÐ°ÑÑÐ°ÐµÑ.

  ## [5.2.3] â 2026-06-26

### Fix
- **ÐÐµÑÐ¸ÑÐ¸ÐºÐ°ÑÐ¸Ñ Ð°ÐºÐºÐ°ÑÐ½ÑÐ¾Ð²** (`gui/screens/screen_accounts.py`): ÑÑÑÑÐ°Ð½ÑÐ½ Ð»Ð°Ð³ Ð¸ Ð½ÐµÐ¿ÑÐ°Ð²Ð¸Ð»ÑÐ½Ð°Ñ ÑÑÐ°ÑÐ¸ÑÑÐ¸ÐºÐ° Ð¿ÑÐ¸ Ð¿ÑÐ¾Ð²ÐµÑÐºÐµ Ð¼Ð½Ð¾Ð¶ÐµÑÑÐ²Ð° Ð°ÐºÐºÐ°ÑÐ½ÑÐ¾Ð². Ð Ð°Ð½ÐµÐµ ÐºÐ°Ð¶Ð´ÑÐ¹ ÑÐµÐ·ÑÐ»ÑÑÐ°Ñ Ð²ÑÐ·ÑÐ²Ð°Ð» Ð¿Ð¾Ð»Ð½ÑÑ Ð¿ÐµÑÐµÑÐ±Ð¾ÑÐºÑ ÑÐ°Ð±Ð»Ð¸ÑÑ O(N) â ÑÐµÐ¿ÐµÑÑ Ð¾Ð±Ð½Ð¾Ð²Ð»ÑÐµÑÑÑ ÑÐ¾Ð»ÑÐºÐ¾ ÐºÐ¾Ð½ÐºÑÐµÑÐ½Ð°Ñ ÑÑÑÐ¾ÐºÐ°, Ð° Ð¿Ð¾Ð»Ð½ÑÐ¹ refresh Ð²ÑÐ·ÑÐ²Ð°ÐµÑÑÑ Ð¾ÑÐ»Ð¾Ð¶ÐµÐ½Ð½Ð¾ ÑÐµÑÐµÐ· debounce-ÑÐ°Ð¹Ð¼ÐµÑ 600Ð¼Ñ.
- **ÐÐ¾Ð±Ð¸Ð»ÑÐ½ÑÐµ Ð¿ÑÐ¾ÐºÑÐ¸** (`core/sender.py`): Ð´Ð¾Ð±Ð°Ð²Ð»ÐµÐ½Ð¾ Ð´Ð¾ 3 Ð¿Ð¾Ð¿ÑÑÐ¾Ðº Ð¿ÑÐ¸ `SMTPServerDisconnected` Ñ Ð¿Ð°ÑÐ·Ð¾Ð¹ 1.5Ñ Ð¼ÐµÐ¶Ð´Ñ Ð½Ð¸Ð¼Ð¸. ÐÐ¾Ð±Ð¸Ð»ÑÐ½ÑÐµ Ð¿ÑÐ¾ÐºÑÐ¸ ÑÐ¾ÑÐ¸ÑÑÑÑ IP Ð¿ÑÐ¸ ÐºÐ°Ð¶Ð´Ð¾Ð¼ ÑÐ¾ÐµÐ´Ð¸Ð½ÐµÐ½Ð¸Ð¸ â Ð¿Ð¾Ð²ÑÐ¾ÑÐ½Ð°Ñ Ð¿Ð¾Ð¿ÑÑÐºÐ° ÑÐ°ÑÑÐ¾ ÑÑÐ¿ÐµÑÐ½Ð° Ð¿Ð¾ÑÐ»Ðµ ÑÐ¾ÑÐ°ÑÐ¸Ð¸.
- **ÐÐ²ÑÐ¾Ð¾Ð±Ð½Ð¾Ð²Ð»ÐµÐ½Ð¸Ðµ Ð½Ðµ Ð¾Ð¿ÑÐµÐ´ÐµÐ»ÑÐ»Ð¾ Ð½Ð¾Ð²ÑÑ Ð²ÐµÑÑÐ¸Ñ** (`core/updater.py`): Ð¿ÑÐ¸ Ð¿ÑÐ¸Ð²Ð°ÑÐ½Ð¾Ð¼ ÑÐµÐ¿Ð¾Ð·Ð¸ÑÐ¾ÑÐ¸Ð¸ GitHub API Ð²Ð¾Ð·Ð²ÑÐ°ÑÐ°Ð» 404 Ð±ÐµÐ· ÑÐ¾ÐºÐµÐ½Ð° â updater Ð¼Ð¾Ð»ÑÐ° Ð²Ð¾Ð·Ð²ÑÐ°ÑÐ°Ð» None. ÐÐ¾Ð±Ð°Ð²Ð»ÐµÐ½ Ð¿ÐµÑÐ²Ð¸ÑÐ½ÑÐ¹ ÑÐ½Ð´Ð¿Ð¾Ð¸Ð½Ñ `https://fmail.shop/version.json` (Ð¿ÑÐ±Ð»Ð¸ÑÐ½ÑÐ¹, Ð½Ðµ Ð·Ð°Ð²Ð¸ÑÐ¸Ñ Ð¾Ñ Ð¿ÑÐ¸Ð²Ð°ÑÐ½Ð¾ÑÑÐ¸ ÑÐµÐ¿Ð¾). GitHub API Ð¾ÑÑÐ°ÑÑÑÑ ÑÐµÐ·ÐµÑÐ²Ð½ÑÐ¼.
- **Ð¢Ð¸ÑÐ¾Ðµ Ð¾Ð±Ð½Ð¾Ð²Ð»ÐµÐ½Ð¸Ðµ** (`core/updater.py`): `apply_update_windows` Ð·Ð°Ð¼ÐµÐ½Ð¸Ð»Ð° `os.startfile(.bat)` (Ð¾ÑÐºÑÑÐ²Ð°Ð» CMD-Ð¾ÐºÐ½Ð¾) Ð½Ð° `subprocess.Popen(['powershell', '-WindowStyle', 'Hidden'])`. ÐÐ±Ð½Ð¾Ð²Ð»ÐµÐ½Ð¸Ðµ Ð¿ÑÐ¸Ð¼ÐµÐ½ÑÐµÑÑÑ Ð¿Ð¾Ð»Ð½Ð¾ÑÑÑÑ Ð½ÐµÐ·Ð°Ð¼ÐµÑÐ½Ð¾ â ÑÐ¾Ð»ÑÐºÐ¾ Ð¿ÑÐ¾Ð³ÑÐµÑÑ-Ð±Ð°Ñ Ð² Ð´Ð¸Ð°Ð»Ð¾Ð³Ðµ, Ð·Ð°ÑÐµÐ¼ Ð°Ð²ÑÐ¾Ð·Ð°Ð¿ÑÑÐº.

## [5.2.2] â 2026-06-26

### Fix
- **ÐÐµÑÐ¸ÑÐ¸ÐºÐ°ÑÐ¸Ñ Ð°ÐºÐºÐ°ÑÐ½ÑÐ¾Ð²**: ÑÐ±ÑÐ°Ð½Ð° Ð¿ÑÐ¸Ð½ÑÐ´Ð¸ÑÐµÐ»ÑÐ½Ð°Ñ Ð¿ÑÐ¾Ð²ÐµÑÐºÐ° Ð¿ÑÐ¾ÐºÑÐ¸ Ð² `_test_smtp_sync` â Ð°ÐºÐºÐ°ÑÐ½ÑÑ Ð±ÐµÐ· Ð¿ÑÐ¾ÐºÑÐ¸ ÑÐµÐ¿ÐµÑÑ ÑÐµÑÑÐ¸ÑÑÑÑÑÑ ÑÐµÑÐµÐ· Ð¿ÑÑÐ¼Ð¾Ðµ SMTP-ÑÐ¾ÐµÐ´Ð¸Ð½ÐµÐ½Ð¸Ðµ Ð²Ð¼ÐµÑÑÐ¾ Ð½ÐµÐ¼ÐµÐ´Ð»ÐµÐ½Ð½Ð¾Ð³Ð¾ Ð²Ð¾Ð·Ð²ÑÐ°ÑÐ° Ð¾ÑÐ¸Ð±ÐºÐ¸ Â«ÐÑÐ¾ÐºÑÐ¸ Ð¾Ð±ÑÐ·Ð°ÑÐµÐ»ÐµÐ½Â»
- **CI post-deploy-check**: Ð¸ÑÐ¿ÑÐ°Ð²Ð»ÐµÐ½Ð¾ Ð¸Ð¼Ñ ÑÑÐ¸Ð³Ð³ÐµÑÐ° `workflow_run` (Ð±ÑÐ»Ð¾ `"Auto Deploy"`, ÑÑÐ°Ð»Ð¾ `"Auto Deploy to VPS"`) â Ð¿ÑÐ¾Ð²ÐµÑÐºÐ° Ð´ÐµÐ¿Ð»Ð¾Ñ ÑÐµÐ¿ÐµÑÑ ÑÑÐ°Ð±Ð°ÑÑÐ²Ð°ÐµÑ ÐºÐ¾ÑÑÐµÐºÑÐ½Ð¾
- **CI build**: Ð´Ð¾Ð±Ð°Ð²Ð»ÐµÐ½ job `make-public` Ð² Ð½Ð°ÑÐ°Ð»Ð¾ ÑÐµÐ¿Ð¾ÑÐºÐ¸ â ÑÐµÐ¿Ð¾Ð·Ð¸ÑÐ¾ÑÐ¸Ð¹ Ð¾ÑÐºÑÑÐ²Ð°ÐµÑÑÑ PUBLIC Ð¿ÐµÑÐµÐ´ ÑÐ±Ð¾ÑÐºÐ¾Ð¹ Ð¸ Ð·Ð°ÐºÑÑÐ²Ð°ÐµÑÑÑ PRIVATE Ð² `restore-privacy` (ÐºÐ¾ÑÐ¾ÑÑÐ¹ ÑÐµÐ¿ÐµÑÑ Ð·Ð°Ð²ÐµÑÑÐ°ÐµÑÑÑ Ñ Ð¾ÑÐ¸Ð±ÐºÐ¾Ð¹ Ð¿ÑÐ¸ Ð¾ÑÑÑÑÑÑÐ²Ð¸Ð¸ ADMIN_PAT)

# CHANGELOG â FMailSender

## v5.2.1 â Pre-launch Ð°Ð²ÑÐ¾Ð¾Ð±Ð½Ð¾Ð²Ð»ÐµÐ½Ð¸Ðµ (patch-updater)

### ÐÐ¾Ð²ÑÐµ Ð²Ð¾Ð·Ð¼Ð¾Ð¶Ð½Ð¾ÑÑÐ¸

#### gui/dialogs/dialog_update_splash.py â Pre-launch Ð´Ð¸Ð°Ð»Ð¾Ð³ Ð¾Ð±Ð½Ð¾Ð²Ð»ÐµÐ½Ð¸Ñ
- ÐÑÐ¿Ð»ÑÐ²Ð°ÐµÑ **Ð´Ð¾** Ð·Ð°Ð¿ÑÑÐºÐ° Ð¾ÑÐ½Ð¾Ð²Ð½Ð¾Ð³Ð¾ Ð¿ÑÐ¸Ð»Ð¾Ð¶ÐµÐ½Ð¸Ñ â Ð½Ðµ Ð¼ÐµÑÐ°ÐµÑ ÑÐ°Ð±Ð¾ÑÐµ
- ÐÐ¸Ð·Ð°Ð¹Ð½ Ð² ÑÑÐ¸Ð»Ðµ CyberPro: Ð°Ð½Ð¸Ð¼Ð¸ÑÐ¾Ð²Ð°Ð½Ð½ÑÐµ orbs (violet/cyan), dot-grid, aurora, glassmorphism-ÐºÐ°ÑÑÐ¾ÑÐºÐ°
- ÐÐ¾ÐºÐ°Ð·ÑÐ²Ð°ÐµÑ badge Â«ÐÑÑÑÑÑÐ¹ Ð¿Ð°ÑÑ: ~X ÐÐ (Ð²Ð¼ÐµÑÑÐ¾ Y ÐÐ EXE)Â» ÐºÐ¾Ð³Ð´Ð° patch-manifest Ð´Ð¾ÑÑÑÐ¿ÐµÐ½
- Ð¢ÑÐ¸ Ð´ÐµÐ¹ÑÑÐ²Ð¸Ñ: **Ð£ÑÑÐ°Ð½Ð¾Ð²Ð¸ÑÑ Ð¾Ð±Ð½Ð¾Ð²Ð»ÐµÐ½Ð¸Ðµ**, **ÐÑÐ¾Ð¿ÑÑÑÐ¸ÑÑ ÑÑÑ Ð²ÐµÑÑÐ¸Ñ**, **ÐÐ°Ð¿Ð¾Ð¼Ð½Ð¸ÑÑ Ð¿Ð¾Ð·Ð¶Ðµ (24 Ñ)**
- Gradient progress-bar Ñ Ð¾ÑÐ¾Ð±ÑÐ°Ð¶ÐµÐ½Ð¸ÐµÐ¼ Ð¿ÑÐ¾Ð³ÑÐµÑÑÐ° Ð¿Ð¾ ÐºÐ°Ð¶Ð´Ð¾Ð¼Ñ ÑÐ°Ð¹Ð»Ñ
- ÐÐ¾ÑÐ»Ðµ Ð¿Ð°ÑÑÐ° â Ð°Ð²ÑÐ¾Ð¼Ð°ÑÐ¸ÑÐµÑÐºÐ¸Ð¹ `os.execv()` ÑÐµÑÑÐ°ÑÑ Ð±ÐµÐ· Ð¿Ð¾ÑÐµÑÐ¸ argv

#### core/update_settings.py â Ð¥ÑÐ°Ð½ÐµÐ½Ð¸Ðµ Ð¿ÑÐµÐ´Ð¿Ð¾ÑÑÐµÐ½Ð¸Ð¹
- `skip_version(v)` â Ð·Ð°Ð¿Ð¾Ð¼Ð¸Ð½Ð°ÐµÑ Â«Ð±Ð¾Ð»ÑÑÐµ Ð½Ðµ Ð¿Ð¾ÐºÐ°Ð·ÑÐ²Ð°ÑÑ Ð´Ð»Ñ v5.2.1Â»
- `set_remind_later()` â Ð¾ÑÐºÐ»Ð°Ð´ÑÐ²Ð°ÐµÑ Ð½Ð° 24 ÑÐ°ÑÐ°
- JSON-ÑÐ°Ð¹Ð» `_update_prefs.json` ÑÑÐ´Ð¾Ð¼ Ñ EXE (Ð½Ðµ ÑÑÐµÐ±ÑÐµÑ Ð¿ÑÐ°Ð² Ð°Ð´Ð¼Ð¸Ð½Ð¸ÑÑÑÐ°ÑÐ¾ÑÐ°)

#### main.py â ÐÐ½ÑÐµÐ³ÑÐ°ÑÐ¸Ñ
- ÐÑÐ¾Ð²ÐµÑÐºÐ° Ð¾Ð±Ð½Ð¾Ð²Ð»ÐµÐ½Ð¸Ð¹ Ð¿Ð¾ÑÐ»Ðµ `setStyleSheet`, **Ð´Ð¾** `check_license`
- Ð¢Ð°Ð¹Ð¼Ð°ÑÑ 6 Ñ â Ð½Ðµ Ð·Ð°Ð´ÐµÑÐ¶Ð¸Ð²Ð°ÐµÑ Ð·Ð°Ð¿ÑÑÐº Ð¿ÑÐ¸ Ð¾ÑÐ»Ð°Ð¹Ð½Ðµ Ð¸Ð»Ð¸ Ð¼ÐµÐ´Ð»ÐµÐ½Ð½Ð¾Ð¹ ÑÐµÑÐ¸
- ÐÐ±ÑÑÐ½ÑÑÐ° Ð² `try/except` â Ð»ÑÐ±Ð°Ñ Ð¾ÑÐ¸Ð±ÐºÐ° updater Ð½Ðµ Ð»Ð¾Ð¼Ð°ÐµÑ Ð·Ð°Ð¿ÑÑÐº

### ÐÑÐ¿ÑÐ°Ð²Ð»ÐµÐ½Ð¸Ñ ÑÐ¸Ð½ÑÐ°ÐºÑÐ¸ÑÐ° (v5.1.0)
- `core/_version.py` â IndentationError Ð½Ð° ÑÑÑÐ¾ÐºÐµ 2
- `core/send_checkpoint.py` â Ð»Ð¸ÑÐ½Ð¸Ð¹ 2-Ð¿ÑÐ¾Ð±ÐµÐ»ÑÐ½ÑÐ¹ Ð¾ÑÑÑÑÐ¿ Ð½Ð° ÑÑÐ¾Ð²Ð½Ðµ Ð¼Ð¾Ð´ÑÐ»Ñ
- `core/smtp_pool.py` â Ð»Ð¸ÑÐ½Ð¸Ð¹ 2-Ð¿ÑÐ¾Ð±ÐµÐ»ÑÐ½ÑÐ¹ Ð¾ÑÑÑÑÐ¿ Ð½Ð° ÑÑÐ¾Ð²Ð½Ðµ Ð¼Ð¾Ð´ÑÐ»Ñ
- `tests/test_smtp_pool.py` â Ð»Ð¸ÑÐ½Ð¸Ð¹ 2-Ð¿ÑÐ¾Ð±ÐµÐ»ÑÐ½ÑÐ¹ Ð¾ÑÑÑÑÐ¿ Ð½Ð° ÑÑÐ¾Ð²Ð½Ðµ Ð¼Ð¾Ð´ÑÐ»Ñ
- `core/sender.py` â Ð½ÐµÐ¿Ð¾ÑÐ»ÐµÐ´Ð¾Ð²Ð°ÑÐµÐ»ÑÐ½ÑÐ¹ Ð¾ÑÑÑÑÐ¿ Ð² dict fastmail/tutanota

---

  ## v5.0.0 â SMTP Connection Pool + Campaign Checkpoints

  ### ÐÐ¾Ð²ÑÐµ Ð²Ð¾Ð·Ð¼Ð¾Ð¶Ð½Ð¾ÑÑÐ¸ (Ð¾Ð¿ÑÐ¸Ð¼Ð¸Ð·Ð°ÑÐ¸Ñ Ð´Ð»Ñ 10-15Ðº Ð¿Ð¸ÑÐµÐ¼)

  #### core/smtp_pool.py â ÐÑÐ» SMTP-ÑÐ¾ÐµÐ´Ð¸Ð½ÐµÐ½Ð¸Ð¹
  - **5-10x Ð¿ÑÐ¸ÑÐ¾ÑÑ ÑÐºÐ¾ÑÐ¾ÑÑÐ¸** Ð·Ð° ÑÑÑÑ Ð¿ÐµÑÐµÐ¸ÑÐ¿Ð¾Ð»ÑÐ·Ð¾Ð²Ð°Ð½Ð¸Ñ ÑÐ¾ÐµÐ´Ð¸Ð½ÐµÐ½Ð¸Ð¹ (RSET Ð²Ð¼ÐµÑÑÐ¾ Ð½Ð¾Ð²Ð¾Ð³Ð¾ connect+AUTH)
  - Per-Ð¿ÑÐ¾Ð²Ð°Ð¹Ð´ÐµÑ Ð»Ð¸Ð¼Ð¸ÑÑ ÑÐµÑÑÐ¸Ð¹: Gmail=400, Outlook=200, Yahoo=100, GMX=100, Rambler=150
  - Per-Ð¿ÑÐ¾Ð²Ð°Ð¹Ð´ÐµÑ Ð·Ð°Ð´ÐµÑÐ¶ÐºÐ¸: Gmail=0.3Ñ, Outlook=0.5Ñ, Yahoo/GMX=1.0Ñ
  - Thread-safe: ÐºÐ°Ð¶Ð´ÑÐ¹ Ð¿Ð¾ÑÐ¾Ðº Ð½ÐµÐ·Ð°Ð²Ð¸ÑÐ¸Ð¼Ð¾ Ð±ÐµÑÑÑ/Ð²Ð¾Ð·Ð²ÑÐ°ÑÐ°ÐµÑ ÑÐ¾ÐµÐ´Ð¸Ð½ÐµÐ½Ð¸Ðµ
  - ÐÐ²ÑÐ¾Ð¼Ð°ÑÐ¸ÑÐµÑÐºÐ¸Ð¹ reconnect Ð¿ÑÐ¸ ÑÐ°Ð·ÑÑÐ²Ðµ (stale >5 Ð¼Ð¸Ð½)
  - ÐÐ»Ð¾Ð±Ð°Ð»ÑÐ½ÑÐ¹ Ð¿ÑÐ»: `from core.smtp_pool import get_global_pool`

  #### core/send_checkpoint.py â Ð¡Ð¸ÑÑÐµÐ¼Ð° ÑÐµÐºÐ¿Ð¾Ð¸Ð½ÑÐ¾Ð²
  - Ð¡Ð¾ÑÑÐ°Ð½ÐµÐ½Ð¸Ðµ Ð¿ÑÐ¾Ð³ÑÐµÑÑÐ° ÐºÐ°Ð¶Ð´ÑÐµ 25 Ð¾ÑÐ¿ÑÐ°Ð²Ð»ÐµÐ½Ð½ÑÑ Ð¿Ð¸ÑÐµÐ¼
  - ÐÑÐ¾Ð¼Ð°ÑÐ½Ð°Ñ Ð·Ð°Ð¿Ð¸ÑÑ (tmp + os.replace) â Ð½ÐµÑ Ð¿Ð¾Ð²ÑÐµÐ¶Ð´ÑÐ½Ð½ÑÑ ÑÐ°Ð¹Ð»Ð¾Ð² Ð¿ÑÐ¸ ÐºÑÑÑÐµ
  - Resume: Ð¿ÑÐ¾Ð¿ÑÑÐº ÑÐ¶Ðµ Ð¾ÑÐ¿ÑÐ°Ð²Ð»ÐµÐ½Ð½ÑÑ Ð°Ð´ÑÐµÑÐ¾Ð² Ð¿ÑÐ¸ Ð¿ÐµÑÐµÐ·Ð°Ð¿ÑÑÐºÐµ
  - Ð¥ÑÐ°Ð½Ð¸Ð»Ð¸ÑÐµ: %APPDATA%/FMailSender/checkpoints/<campaign_id>.json
  - Ð¤ÑÐ½ÐºÑÐ¸Ñ `list_checkpoints()` Ð´Ð»Ñ UI â Ð¿Ð¾ÐºÐ°Ð·ÑÐ²Ð°ÐµÑ Ð½ÐµÐ·Ð°Ð²ÐµÑÑÑÐ½Ð½ÑÐµ ÐºÐ°Ð¼Ð¿Ð°Ð½Ð¸Ð¸

  ### Ð£Ð»ÑÑÑÐµÐ½Ð¸Ñ ÑÐºÐ¸Ð»Ð»Ð¾Ð²

  #### .agents/skills/performance-guide/SKILL.md
  - ÐÐ±Ð½Ð¾Ð²Ð»ÑÐ½ Ñ Ð¿Ð°ÑÑÐµÑÐ½Ð°Ð¼Ð¸ Ð¿ÑÐ»Ð° ÑÐ¾ÐµÐ´Ð¸Ð½ÐµÐ½Ð¸Ð¹ Ð¸ ÑÐµÐºÐ¿Ð¾Ð¸Ð½ÑÐ¾Ð²
  - Ð¢Ð°Ð±Ð»Ð¸ÑÐ° Ð»Ð¸Ð¼Ð¸ÑÐ¾Ð² Ð¿Ð¾ Ð¿ÑÐ¾Ð²Ð°Ð¹Ð´ÐµÑÐ°Ð¼
  - ÐÐ¿ÑÐ¸Ð¼Ð°Ð»ÑÐ½Ð°Ñ ÐºÐ¾Ð½ÑÐ¸Ð³ÑÑÐ°ÑÐ¸Ñ CampaignConfig Ð´Ð»Ñ 10Ðº+ Ð¿Ð¸ÑÐµÐ¼
  - Ð Ð°ÑÑÑÑ ÑÐµÐ°Ð»ÑÐ½Ð¾Ð¹ ÑÐºÐ¾ÑÐ¾ÑÑÐ¸

  #### .agents/prompts/optimizer-agent.md
  - ÐÐ³ÐµÐ½Ñ ÑÐµÐ¿ÐµÑÑ Ð·Ð½Ð°ÐµÑ Ð¾ smtp_pool Ð¸ send_checkpoint
  - ÐÐ¾Ð¼Ð°Ð½Ð´Ñ Ð´Ð¸Ð°Ð³Ð½Ð¾ÑÑÐ¸ÐºÐ¸ Ð¼ÐµÐ´Ð»ÐµÐ½Ð½Ð¾Ð¹ ÑÐ°ÑÑÑÐ»ÐºÐ¸

  ---

  ## v4.5.3
  - FIX: Ð¾ÑÐºÐ°Ñ Ð¸Ð½ÐºÑÐµÐ¼ÐµÐ½ÑÐ° Ð¿ÑÐ¸ Ð¾ÑÐ¸Ð±ÐºÐµ (decrement_sent) â Ð»Ð¸Ð¼Ð¸Ñ Ð½Ðµ ÑÐ¶Ð¸Ð³Ð°Ð»ÑÑ Ð²Ð¿ÑÑÑÑÑ
  - FIX v4.5.2: task.cancel() ÑÐµÑÐµÐ· call_soon_threadsafe â ÑÑÑÑÐ°Ð½ÑÐ½ race condition

  ## v4.5.2
  - FIX: stop() â cancel ÑÐµÑÐµÐ· call_soon_threadsafe (PyQt6 thread-safe)
  - FIX: _loop ÑÐ¾ÑÑÐ°Ð½ÑÐµÑÑÑ Ð² run_campaign Ð´Ð»Ñ Ð±ÐµÐ·Ð¾Ð¿Ð°ÑÐ½Ð¾Ð³Ð¾ cancel

  ## v4.5.1
  - FIX: SOCKS5 ÐºÐ¾Ð´ 2 ÑÐµÐ¿ÐµÑÑ Ð½Ðµ fallback Ð½Ð° direct (Ð·Ð°ÑÐ¸ÑÐ° IP)
  - FIX: HTTP CONNECT Ð¿ÑÐ¾ÐºÑÐ¸ Ð¿Ð¾Ð´Ð´ÐµÑÐ¶ÐºÐ°

  ## v4.4.6
  - FIX: SOCKS5 General Failure â Ð°Ð²ÑÐ¾Ð¼Ð°ÑÐ¸ÑÐµÑÐºÐ¸Ð¹ fallback Ð½Ð° Ð´ÑÑÐ³Ð¾Ð¹ Ð¿Ð¾ÑÑ
  - FIX: QPushButton RuntimeError Ð² _poll_send â try/except RuntimeError

  ## v4.4.5
  - Ð£Ð½Ð¸ÐºÐ°Ð»Ð¸Ð·Ð°ÑÐ¸Ñ Ð¿Ð¸ÑÐµÐ¼: spintax, CSS micro, fingerprint (uniqueize=True Ð² CampaignConfig)
  - Bounce-Ð¿Ð°ÑÑÐµÑ: IMAP Ð¼Ð¾Ð½Ð¸ÑÐ¾ÑÐ¸Ð½Ð³ + hard/soft bounce â blacklist
  - Warmup: ÑÐºÑÐ¿Ð¾Ð½ÐµÐ½ÑÐ¸Ð°Ð»ÑÐ½ÑÐ¹ Ð¿ÑÐ¾Ð³ÑÐµÐ² (5 * exp(0.15*(day-1)), cap 500/Ð´ÐµÐ½Ñ)

  ## v2.9.4
  - ÐÐ¾Ð³Ð¸ÑÐ¾Ð²Ð°Ð½Ð¸Ðµ Ð²Ð¾ Ð²ÑÐµ silent except-Ð±Ð»Ð¾ÐºÐ¸
  - IndentationError fix Ð² increment_sent/try_increment/Recipient
  - Async parallelism: delay Ð¿ÐµÑÐµÐ½ÐµÑÑÐ½ Ð²Ð½ÑÑÑÑ task wrapper
  - Race condition ÑÑÑÑÐ°Ð½ÑÐ½ ÑÐµÑÐµÐ· try_increment
  