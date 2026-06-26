---
  name: session-boot
  description: Инициализация сессии FMailSender — загрузка скиллов, проверка окружения, память между сессиями.
  ---

  # Session Boot

  ## Порядок загрузки при старте сессии

  1. Загрузить скиллы из .agents/skills/ (особенно smtp-engine-guard, performance-guide)
  2. Проверить наличие незавершённых кампаний: `list_checkpoints()`
  3. Инициализировать глобальный SMTP-пул (если рассылка планируется)
  4. Подтвердить что все аккаунты проверены (last_test_ok=True)

  ## Модули ядра (core/)

  | Модуль | Назначение |
  |--------|-----------|
  | core/sender.py | Основной движок отправки (SendingEngine) |
  | core/smtp_pool.py | Пул SMTP-соединений (NEW v5.0) |
  | core/send_checkpoint.py | Чекпоинты кампаний (NEW v5.0) |
  | core/smtp_validator.py | Валидатор аккаунтов |
  | core/warmup.py | Прогрев аккаунтов |
  | core/bounce.py | IMAP bounce-монитор |
  | core/uniqueizer.py | Уникализация писем |
  | core/spam_checker.py | Спам-скор проверка |

  ## Проверка окружения

  ```python
  # Проверить что все зависимости установлены
  import aiosmtplib  # async SMTP
  import PySocks     # SOCKS5
  import dns.resolver  # MX lookup

  # Проверить пул соединений
  from core.smtp_pool import get_global_pool
  pool = get_global_pool()

  # Проверить незавершённые кампании
  from core.send_checkpoint import list_checkpoints
  print(list_checkpoints())
  ```

  ## Ключевые скиллы для активации

  - smtp-engine-guard — перед изменением sender.py
  - performance-guide — перед настройкой рассылки 10к+
  - rate-limit-strategy — при ошибках 421
  - smtp-error-diagnosis — при ошибках AUTH
  - async-smtp-guide — при работе с event loop
  