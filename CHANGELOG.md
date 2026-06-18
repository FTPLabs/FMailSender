# Changelog

  ## [3.4.3] — 2026-06-18

  ### 🔴 Критические исправления

  - **server/bot.py `_lic_rows()` / `_ticket_rows()`**: Функции генерации HTML внутри `admin_html`
    вызывались без `try/except` — при любом неожиданном поле в БД сервер возвращал HTTP 500.
    Теперь каждый блок обёрнут `try/except` с безопасным fallback-сообщением.
  - **server/bot.py `cb_mod_ticket_view`**: Обращение к `m["sender"]` вместо `m["role"]` вызывало
    `KeyError` при просмотре тикета модератором — кнопки "Ответить" и "Закрыть" недоступны.
    Исправлено на `m["role"]`.
  - **server/database.py `set_terms_accepted()` / `set_captcha_passed()`**: Использовались чистые
    `UPDATE`-запросы — silent fail если пользователь ещё не существует в БД.
    Заменены на `INSERT OR IGNORE + UPDATE` (UPSERT).

  ### 🟠 Высокоприоритетные исправления

  - **core/license.py `generate_hwid()`**: При таймауте WMI и пустом кэше все компоненты
    становились `UNKNOWN_*` — каждая машина получала одинаковый HWID, что ломало активацию.
    Добавлен fallback через `MachineGuid` (реестр Windows).
  - **server/bot.py**: `sys.path.insert()` стоял после части `import`-ов — потенциальный
    `ImportError` при нестандартной среде. Перемещён в самое начало файла.

  ### 🟡 Прочие исправления

  - **server/bot.py footer**: `{{APP_VERSION}}` теперь корректно отображает версию в /admin.
  - **server/database.py `_migrate_db()`**: Одно соединение вместо нового на каждый ALTER TABLE.
  - **server/bot.py**: Исправлен противоречивый комментарий про asyncio.Lock.

  ---

  ## [3.3.2] — 2026-06-17

### 🔴 Критические исправления (хотфикс: нестабильный HWID)

- **core/license.py `generate_hwid()`**: Полностью переработана формула HWID.
  - **Удалены** нестабильные компоненты: MAC-адрес (`uuid.getnode()` — менялся при установке VPN/Docker/Hyper-V/виртуальных адаптеров), серийник диска (нестабилен — разный порядок при нескольких дисках, меняется после замены), `HWID_SALT` (серверная константа, не должна входить в клиентский ID)
  - **Новая формула**: `SHA256(CPU_ProcessorId | Motherboard_SerialNumber | GPU_Name)[:32]`
  - **Добавлен** `_get_gpu_id()` — список GPU отсортированный, меняется при замене/добавлении видеокарты
  - **Улучшен** `_get_board_id()` — фильтрует мусорные значения ("Default string", "To be filled by O.E.M.", "None")
  - **Удалён файловый кэш** `hwid.dat` из логики `generate_hwid()` — файл удаляется при первом запуске чтобы не тянуть старые нестабильные ID. Кэш — только в памяти на время сессии
- **VPS**: HWID-привязка ключа `FMSND-GZ6V5U-Q7H94Z-Z9NDH5-BDZ37C` сброшена для повторной активации

### Гарантии стабильности HWID

| Событие | HWID меняется? |
|---|---|
| Переустановка Windows / обновление ОС | ❌ Нет |
| Установка VPN, Docker, Hyper-V | ❌ Нет |
| Замена жёсткого диска / SSD | ❌ Нет |
| Смена IP / сети / Wi-Fi | ❌ Нет |
| Замена процессора (CPU) | ✅ Да |
| Замена материнской платы | ✅ Да |
| Замена / добавление видеокарты | ✅ Да |

---

## [3.3.1] — 2026-06-17

### 🔴 Критические исправления (хотфикс: бесконечная проверка лицензии)

- **core/license.py**: Восстановлены `LICENSE_API_URL` / `LICENSE_VERIFY_URL` как константы с hardcoded fallback-URL сервера (`https://31.76.100.190:8000/v1/activate`). Замена на `_require_env()` + `sys.exit(1)` в v3.3.0 вызывала тихую гибель QThread → UI зависал в "Активация..." навсегда
- **core/license.py**: Восстановлен fallback в `_get_fernet_key()` — при отсутствии `HWID_SALT` используется встроенная строка с предупреждением вместо `sys.exit(1)`. Без фикса EXE на Windows падал при сохранении `license.dat`
- **core/license.py**: Исправлен `_get_ssl_verify()` — дефолт изменён с `"1"` (True) на `"0"` (False). Сервер использует self-signed сертификат; `verify=True` по умолчанию давало SSL-ошибку при каждом запросе к API лицензий

### Инфраструктура

- **VPS**: Добавлен ключ `FMSND-GZ6V5U-Q7H94Z-Z9NDH5-BDZ37C` в БД лицензий (план PRO, 365 дней, активен)

---

## [3.3.0] — 2026-06-16

### 🔴 Критические исправления

- **core/license.py**: Устранён `sys.exit(1)` при импорте модуля — `_require_env()` теперь вызывается лениво через `_get_license_api_url()` / `_get_license_verify_url()`, только при фактическом обращении к серверу лицензий
- **core/sender.py**: Исправлен конфликт параметров `aiosmtplib` ≥ 3.0 — удалён несуществующий `start_tls=` из конструктора SMTP; STARTTLS теперь корректно активируется через `await smtp.starttls()` после `connect()`

### 🟠 Серьёзные исправления

- **core/sender.py**: Исправлен сброс часового счётчика `sent_this_hour` — теперь обнуляется только если с момента предыдущего сброса прошло ≥ 3600 сек; ранее новая кампания обнуляла лимиты, отправленные за текущий час
- **core/sender.py**: Удалено мёртвое определение `_EMAIL_RE` — regex определялся, но никогда не использовался (вся валидация идёт через `core.utils.validate_email_format`)
- **core/license.py**: `datetime.utcnow()` заменён на `datetime.now(timezone.utc).replace(tzinfo=None)` — устранён `DeprecationWarning` в Python 3.12+

### 🟡 Минорные исправления

- **core/bounce.py**: Унифицированы отступы в `to_dict()` / `from_dict()` — смешение 2-пробельных и 4-пробельных отступов заменено единым 4-пробельным стандартом PEP 8

### Новое

- **`.agents/skills/build-guard`**: Новый скилл — полная проверка проекта перед сборкой `.exe` и созданием релиза: PyInstaller 6.x совместимость, aiosmtplib параметры, lazy license URLs, синтаксис, hourly counter, hiddenimports

---

## [3.0.1] — 2026-06-14

  ### Исправлено (Bug Fixes)
  - **core/ai_fixer.py**: Добавлен try/except вокруг `data["choices"][0]` и `json.loads()` — больше нет необработанных KeyError/IndexError при нестандартных ответах OpenAI
  - **server/database.py**: Исправлен баг в `save_payment()` — INSERT OR IGNORE возвращал lastrowid=0 при дублирующемся invoice_id; теперь корректно возвращает ID существующей записи
  - **server/bot.py**: `JsonFileStorage._dump()` переведён в асинхронный режим через `asyncio.to_thread()` — устранена блокировка event loop при каждом изменении состояния FSM
  - **server/bot.py**: `send_or_edit()` теперь логирует ошибки `edit_text()` через DEBUG вместо молчаливого проглатывания
  - **core/license.py**: Рефакторинг: дублирующийся WMI-код в `_get_cpu_id()`, `_get_disk_serial()`, `_get_board_id()` вынесен в единую вспомогательную функцию `_wmi_query()` (~180 строк → ~50 строк)

  ### Новое (New Features)
  - **Автоматизация Download URL**: Ссылка для скачивания теперь автоматически берётся из последнего GitHub Release (кэш 5 мин). Ручное переопределение через бот по-прежнему имеет приоритет
  - **Автоматизация VirusTotal**: CI/CD теперь автоматически отправляет .exe на VirusTotal после каждого релиза и вставляет ссылку в Release Notes. Бот автоматически парсит её из описания релиза — ручное обновление не требуется
  - **GitHub Actions**: Добавлен шаг VirusTotal в build.yml (требует секрет `VIRUSTOTAL_API_KEY`)

  ### Рефакторинг
  - Унифицирован WMI-helper, удалено ~130 строк дублирующегося кода в license.py

  ---

    All notable changes are documented here.

  ---

  ## [2.0.0] — 2025-06-11 — Premium Visual Overhaul

  ### Visual
  - New **Aether Dark** premium color palette: deep violet #8B5CF6 + hot-rose #EC4899 gradient
  - Updated entire QSS stylesheet across all screens, modals, dialogs, toasts
  - Progress bars, buttons, tabs now use violet→rose gradient
  - Activation screen: gradient CTA button with glow border

  ### Assets
  - Phase 2: SVG logo (envelope + gradient fill) embedded in activation screen
  - Custom in-app icon set (20 icons) as inline SVG in `gui/app.py`
  - Sidebar nav icons updated to new stroke colors

  ### Fixes
  - **build.py**: `APP_VERSION` was hardcoded as "1.0.0"; now imported from `core._version`
  - **core/license.py**: activation payload now sends real `APP_VERSION` (was "1.0.0")
  - **core/license.py**: `_load_license_data` now logs on decrypt error instead of silently returning `None`
  - **core/license.py**: `ESP_HWID_SALT` missing env now raises `WARNING` (was `DEBUG`)
  - **core/sender.py**: fixed regex `<brs*/?> ` (stray space) in `_html_to_text` — `<br>` tags now correctly become newlines
  - **core/sender.py**: `SMTP_CONFIGS` dict moved from inside function to module level — eliminates per-call allocation
  - **gui/screens/screen_sending.py**: `_speed_timer.start()` was never called — speed KPI now updates every 5 s
  - **core/spam_checker.py**: all `dns.resolver.resolve()` calls now have `lifetime=5` timeout — no more hangs on slow DNS
  - **requirements.txt**: removed unused `PyQt6-WebEngine` (~150 MB); moved `pyinstaller` to `requirements-dev.txt`

  ### Performance
  - SMTP config lookup is O(1) dict lookup (was O(n) re-allocation)
  - DNS checks time-bounded to 5 s maximum per call

  ---

  ## [1.0.1] — 2025-06-10

  - Initial public release
  