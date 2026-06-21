## [3.7.10] — 2026-06-21

### Исправлено (5 новых пользовательских багов)

- **БАГ-7 [КРИТ] gui/screens/screen_compose.py — крэш при HTML + нажатие кнопок**
  `textChanged` сигнала `html_editor` срабатывал рекурсивно при любом `setPlainText()`
  (из уникализатора, AI-фиксера, загрузки шаблона), пока `HtmlHighlighter` ещё обрабатывал
  документ → SIGSEGV в PyQt6. Добавлен флаг `_syncing: bool` — все программные вызовы
  `setPlainText` обёрнуты в `_syncing = True / finally False`; `_on_html_changed` пропускает
  итерацию при `_syncing`. Убрана лишняя строка `html = self.html_editor.toPlainText()`
  (результат не использовался).

- **БАГ-8 HTML-превью не обновлялся / показывал некорректный рендеринг**
  `QWebEngineView.setHtml()` получал `QUrl("https://mail.preview.local/")` — несуществующий
  origin вынуждал движок применять строгую CSP, блокируя inline-стили и CDN-ресурсы.
  Исправлено: base URL изменён на `QUrl("about:blank")` — корректный нейтральный origin
  без ограничений загрузки внешних ресурсов.

- **БАГ-9 [UI] Диалог уникализации открывается с OS-дефолтными цветами (чёрный текст)**
  `QDialog(self)` на Windows с некоторыми сборками PyQt6 не наследует stylesheet QApplication
  при использовании селектора `QMainWindow, QDialog {{ ... }}`. Явно применяется
  `dlg.setStyleSheet(QApplication.instance().styleSheet())` — диалог теперь всегда
  в тёмной теме приложения.

- **БАГ-10 [UI] Кнопка «Применить» в диалоге уникализации отображалась бело-чёрной**
  Следствие БАГ-9 (objectName `btn_primary` не подхватывался без stylesheet).
  Устранено тем же патчем — явным применением app stylesheet к диалогу.

- **БАГ-11 Тест доставки требовал полностью ручной отправки**
  `_test_delivery()` показывал только адрес и инструкцию «отправьте вручную».
  Добавлена **автоматическая отправка**: новый метод `set_accounts(accounts)` принимает
  список SMTP-аккаунтов; при наличии аккаунтов в диалоге появляется кнопка
  «⚡ Отправить тест автоматически» — письмо уходит через первый аккаунт (smtplib,
  поддержка STARTTLS / SSL, порты 587/465/25). При нескольких аккаунтах — выпадающий
  список выбора. Кнопка «🔍 Проверить результат» блокируется до момента отправки,
  чтобы исключить проверку ранее срока.

### Связанные изменения

- **gui/app.py**: сигнал `accounts.accounts_changed` теперь также подключён к
  `compose.set_accounts` — аккаунты автоматически поступают на экран письма при
  добавлении/изменении без перезапуска.

## [3.7.9] — 2026-06-21

### Исправлено (все баги из анализа v3.7.8)

- **[КРИТ] gui/theme.py**: `AttributeError: Colors has no attribute BG_SURFACE` — приложение не запускалось.
  Заменено `c.BG_SURFACE` -> `c.BG_SURFACE2` (2 вхождения в стилях QDialog). **БАГ-1**.
- **core/sender.py** `_send_sync()`: обязательный прокси блокировал отправку без proxy.
  Теперь прокси опционален: при отсутствии — прямое SMTP-соединение. **БАГ-2**.
- **gui/screens/screen_inbox.py**: IMAP без таймаута зависал навсегда.
  Добавлен `socket.setdefaulttimeout(15)` и `M.socket.settimeout(15)`. **БАГ-3**.
- **main.py** `security_check()`: race condition с `os.abort()` во время init QApplication.
  Исправлено: `security_check()` синхронно до создания QApplication. **БАГ-4**.
- **core/sender.py** `_send_aiosmtp()`: 6 дублированных `import logging as _lg`
  заменены на один `import logging` в начале файла. **ДУБ-2**.

### CI/CD

- **syntax-check.yml**: добавлена проверка атрибутов класса `Colors`.
  Теперь подобный AttributeError будет поймать CI до сборки EXE.
## [3.7.8] — 2026-06-21

    ### Исправлено (критические баги)
    - **gui/screens/screen_compose.py** стр.1035: IndentationError (`_on_spam_error`) — 6 пробелов → 4 (разблокирует Python Syntax Check CI и сборку EXE)
    - **core/license.py** `_get_fernet_key()`: race condition — `_hwid_cache` мог быть None при первом обращении → Fernet использовал fallback-ключ вместо машинного HWID → license.dat несовместим между запусками
    - **.github/workflows/auto-deploy.yml**: `git stash` без `git stash pop` → stash накапливался на сервере при каждом деплое → заменён на `git reset --hard origin/main`
    - **.github/workflows/build-release.yml**: `generate_release_notes: true` возвращал 403 → убран (GitHub Fine-grained токен не имеет доступа к /generate-release-notes)

  
## [3.7.6] — 2026-06-21

  ### Исправлено
  - **core/sender.py** `_test_smtp_sync`: полностью переработана логика подключения
    - Уровень 1: SSL/TLS со строгой проверкой сертификата (стандарт)
    - Уровень 2: SSL/TLS без проверки сертификата — для серверов с self-signed SSL (Rambler, корпоративные)
    - Уровень 3: перебор резервных портов 465→587→25→2525, каждый с 2 вариантами cert-verify
    - Устранена причина "✗ Ошибка" у аккаунтов которые фактически работают

  ### Диагностика 115 аккаунтов (SMTP AUTH глубокая проверка)
  - **Rambler.ru (50)**: 1 валидный, 49 с ошибкой "Invalid login or password" (пароли устарели)
  - **GMX.com (65)**: 54 валидных ✅, 9 с ошибкой аутентификации, 2 временно rate-limited (421)
  - **Итого**: 55/115 аккаунтов с рабочими паролями

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
  