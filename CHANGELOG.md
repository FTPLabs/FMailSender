# CHANGELOG — FMailSender

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
  