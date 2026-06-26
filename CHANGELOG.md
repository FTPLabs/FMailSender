## [5.2.3] — 2026-06-26

### Fix
- **Верификация аккаунтов** (`gui/screens/screen_accounts.py`): устранён лаг и неправильная статистика при проверке множества аккаунтов. Ранее каждый результат вызывал полную пересборку таблицы O(N) — теперь обновляется только конкретная строка, а полный refresh вызывается отложенно через debounce-таймер 600мс.
- **Мобильные прокси** (`core/sender.py`): добавлено до 3 попыток при `SMTPServerDisconnected` с паузой 1.5с между ними. Мобильные прокси ротируют IP при каждом соединении — повторная попытка часто успешна после ротации.
- **Автообновление не определяло новую версию** (`core/updater.py`): при приватном репозитории GitHub API возвращал 404 без токена — updater молча возвращал None. Добавлен первичный эндпоинт `https://fmail.shop/version.json` (публичный, не зависит от приватности репо). GitHub API остаётся резервным.
- **Тихое обновление** (`core/updater.py`): `apply_update_windows` заменила `os.startfile(.bat)` (открывал CMD-окно) на `subprocess.Popen(['powershell', '-WindowStyle', 'Hidden'])`. Обновление применяется полностью незаметно — только прогресс-бар в диалоге, затем автозапуск.

## [5.2.2] — 2026-06-26

### Fix
- **Верификация аккаунтов**: убрана принудительная проверка прокси в `_test_smtp_sync` — аккаунты без прокси теперь тестируются через прямое SMTP-соединение вместо немедленного возврата ошибки «Прокси обязателен»
- **CI post-deploy-check**: исправлено имя триггера `workflow_run` (было `"Auto Deploy"`, стало `"Auto Deploy to VPS"`) — проверка деплоя теперь срабатывает корректно
- **CI build**: добавлен job `make-public` в начало цепочки — репозиторий открывается PUBLIC перед сборкой и закрывается PRIVATE в `restore-privacy` (который теперь завершается с ошибкой при отсутствии ADMIN_PAT)

# CHANGELOG — FMailSender

## v5.2.1 — Pre-launch автообновление (patch-updater)

### Новые возможности

#### gui/dialogs/dialog_update_splash.py — Pre-launch диалог обновления
- Всплывает **до** запуска основного приложения — не мешает работе
- Дизайн в стиле CyberPro: анимированные orbs (violet/cyan), dot-grid, aurora, glassmorphism-карточка
- Показывает badge «Быстрый патч: ~X КБ (вместо Y МБ EXE)» когда patch-manifest доступен
- Три действия: **Установить обновление**, **Пропустить эту версию**, **Напомнить позже (24 ч)**
- Gradient progress-bar с отображением прогресса по каждому файлу
- После патча — автоматический `os.execv()` рестарт без потери argv

#### core/update_settings.py — Хранение предпочтений
- `skip_version(v)` — запоминает «больше не показывать для v5.2.1»
- `set_remind_later()` — откладывает на 24 часа
- JSON-файл `_update_prefs.json` рядом с EXE (не требует прав администратора)

#### main.py — Интеграция
- Проверка обновлений после `setStyleSheet`, **до** `check_license`
- Таймаут 6 с — не задерживает запуск при офлайне или медленной сети
- Обёрнута в `try/except` — любая ошибка updater не ломает запуск

### Исправления синтаксиса (v5.1.0)
- `core/_version.py` — IndentationError на строке 2
- `core/send_checkpoint.py` — лишний 2-пробельный отступ на уровне модуля
- `core/smtp_pool.py` — лишний 2-пробельный отступ на уровне модуля
- `tests/test_smtp_pool.py` — лишний 2-пробельный отступ на уровне модуля
- `core/sender.py` — непоследовательный отступ в dict fastmail/tutanota

---

  ## v5.0.0 — SMTP Connection Pool + Campaign Checkpoints

  ### Новые возможности (оптимизация для 10-15к писем)

  #### core/smtp_pool.py — Пул SMTP-соединений
  - **5-10x прирост скорости** за счёт переиспользования соединений (RSET вместо нового connect+AUTH)
  - Per-провайдер лимиты сессий: Gmail=400, Outlook=200, Yahoo=100, GMX=100, Rambler=150
  - Per-провайдер задержки: Gmail=0.3с, Outlook=0.5с, Yahoo/GMX=1.0с
  - Thread-safe: каждый поток независимо берёт/возвращает соединение
  - Автоматический reconnect при разрыве (stale >5 мин)
  - Глобальный пул: `from core.smtp_pool import get_global_pool`

  #### core/send_checkpoint.py — Система чекпоинтов
  - Сохранение прогресса каждые 25 отправленных писем
  - Атомарная запись (tmp + os.replace) — нет повреждённых файлов при крэше
  - Resume: пропуск уже отправленных адресов при перезапуске
  - Хранилище: %APPDATA%/FMailSender/checkpoints/<campaign_id>.json
  - Функция `list_checkpoints()` для UI — показывает незавершённые кампании

  ### Улучшения скиллов

  #### .agents/skills/performance-guide/SKILL.md
  - Обновлён с паттернами пула соединений и чекпоинтов
  - Таблица лимитов по провайдерам
  - Оптимальная конфигурация CampaignConfig для 10к+ писем
  - Расчёт реальной скорости

  #### .agents/prompts/optimizer-agent.md
  - Агент теперь знает о smtp_pool и send_checkpoint
  - Команды диагностики медленной рассылки

  ---

  ## v4.5.3
  - FIX: откат инкремента при ошибке (decrement_sent) — лимит не сжигался впустую
  - FIX v4.5.2: task.cancel() через call_soon_threadsafe — устранён race condition

  ## v4.5.2
  - FIX: stop() — cancel через call_soon_threadsafe (PyQt6 thread-safe)
  - FIX: _loop сохраняется в run_campaign для безопасного cancel

  ## v4.5.1
  - FIX: SOCKS5 код 2 теперь не fallback на direct (защита IP)
  - FIX: HTTP CONNECT прокси поддержка

  ## v4.4.6
  - FIX: SOCKS5 General Failure → автоматический fallback на другой порт
  - FIX: QPushButton RuntimeError в _poll_send → try/except RuntimeError

  ## v4.4.5
  - Уникализация писем: spintax, CSS micro, fingerprint (uniqueize=True в CampaignConfig)
  - Bounce-парсер: IMAP мониторинг + hard/soft bounce → blacklist
  - Warmup: экспоненциальный прогрев (5 * exp(0.15*(day-1)), cap 500/день)

  ## v2.9.4
  - Логирование во все silent except-блоки
  - IndentationError fix в increment_sent/try_increment/Recipient
  - Async parallelism: delay перенесён внутрь task wrapper
  - Race condition устранён через try_increment
  