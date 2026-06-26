# FMailSender

  Профессиональный инструмент для массовых email-рассылок с поддержкой SMTP через SOCKS5/HTTP прокси.

  ## Возможности

  - Рассылки до **10-15к+ писем** с оптимизированным пулом соединений
  - SMTP Connection Pool — 5-10x быстрее стандартной отправки
  - Чекпоинты кампаний — resume при перезапуске/крэше
  - SOCKS5/HTTP прокси для всех соединений (защита IP)
  - OAuth2/XOAUTH2 для Microsoft (Outlook/Hotmail)
  - 300+ SMTP-провайдеров предварительно настроены
  - Уникализация писем (spintax, CSS fingerprint)
  - IMAP bounce-монитор + автоматический blacklist
  - Прогрев аккаунтов (warmup scheduler)
  - Спам-скор проверка
  - Мультиязычный GUI (PyQt6, RU/EN)

  ## Быстрый старт

  ```bash
  pip install -r requirements.txt
  python main.py
  ```

  ## Архитектура (v5.0)

  ```
  core/
    sender.py          — Основной движок (SendingEngine)
    smtp_pool.py       — Пул SMTP-соединений (NEW v5.0)
    send_checkpoint.py — Чекпоинты кампаний  (NEW v5.0)
    smtp_validator.py  — Валидатор аккаунтов
    warmup.py          — Прогрев аккаунтов
    bounce.py          — IMAP bounce-монитор
    uniqueizer.py      — Уникализация писем
    spam_checker.py    — Спам-скор
  gui/
    app.py             — Главное окно
    screens/           — Экраны приложения
    dialogs/           — Диалоги
  server/
    bot.py             — Telegram-бот для управления
  scripts/
    rlm_agent/         — AI-ассистент (gptvibe.ru)
  ```

  ## Производительность

  | Аккаунты | Провайдер | Писем/час |
  |----------|-----------|-----------|
  | 1 | Gmail | ~7,000 |
  | 5 | Mix | ~20,000 |
  | 10 | Mix | ~35,000 |

  *С пулом соединений (smtp_pool.py) + корректными задержками по провайдерам*

  ## RLM Agent (AI-ассистент)

  ```bash
  cd scripts/rlm_agent
  cp .env.example .env  # заполнить OPENAI_API_KEY
  python run_agent.py "почему ошибка 535 на GMX?"
  python run_agent.py --diagnose
  ```

  ## Лицензия

  Платный продукт. Активация на сайте [fmail.shop](https://fmail.shop/)
  