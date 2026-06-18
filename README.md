# FMail Sender

  Десктопный клиент для email-рассылок на Windows. Python + PyQt6.

  ---

  ## Что умеет

  - Async SMTP с ротацией аккаунтов, авто-определение конфига по домену
  - HTML-редактор с live preview, персонализация через `{{name}}`, `{{email}}` и т.д.
  - Импорт получателей из CSV / XLSX / TXT
  - Спам-анализатор с DNS-проверкой (SPF, DKIM, DMARC)
  - Warm-up режим с нарастающим расписанием
  - Bounce-обработка через IMAP (hard/soft, автоблеклист)
  - Аналитика кампаний, экспорт CSV + PDF
  - Автообновление через GitHub Releases

  ---

  ## Структура

  ```
  ├── main.py
  ├── build.py                  # Сборка PyInstaller
  ├── core/
  │   ├── sender.py             # Async SMTP движок
  │   ├── license.py            # HWID, JWT активация
  │   ├── spam_checker.py       # Спам-анализатор
  │   ├── bounce.py             # IMAP / DSN парсер
  │   ├── warmup.py             # Warm-up планировщик
  │   ├── updater.py            # Автообновление
  │   └── utils.py              # Общие утилиты
  ├── gui/
  │   ├── app.py                # MainWindow + sidebar
  │   ├── theme.py              # QSS стили
  │   └── screens/              # 7 экранов приложения
  ├── server/
  │   ├── bot.py                # Telegram бот + FastAPI
  │   ├── database.py           # SQLite (aiosqlite)
  │   └── crypto_pay.py         # CryptoBot платежи
  └── data/
      └── spam_words.json
  ```

  ---

  ## Запуск (dev)

  ```bash
  pip install -r requirements.txt
  python main.py
  ```

  ---

  ## Сборка .exe

  ```bash
  python build.py
  ```

  Или через GitHub Actions — push тег `vX.Y.Z`, артефакт появится в Releases.

  ---

  ## Лицензирование

  Один ключ = полный доступ без ограничений. Ключ привязывается к железу (HWID). Покупка через Telegram-бота, оплата в USDT.

  Формат ключа: `FMSND-XXXXXX-XXXXXX-XXXXXX-XXXXXX`

  Данные хранятся в `%APPDATA%\FMailSender\license.dat`.

  ---

  ## Серверная часть

  FastAPI + aiogram 3 + SQLite. Переменные окружения (обязательные):

  ```
  BOT_TOKEN=...
  CRYPTO_BOT_TOKEN=...
  JWT_SECRET=...
  ```

  Запуск: `python server/bot.py`

  ---

  ## Лицензия

  Проприетарное ПО. Все права защищены.
  