---
  name: server-deploy-guard
  description: Защищает сервер FMailSender (FastAPI + aiogram + aiosqlite). Активируй при изменении server/, деплое, или при проблемах с Telegram ботом/API/платежами.
  ---

  # Server Deploy Guard — server/

  ## Архитектура

  ```
  FastAPI + aiogram  →  единый asyncio event loop
  aiosqlite (licenses.db)  ←  WAL mode + busy_timeout=5000
  CryptoBot API  →  crypto_pay.py
  Nginx  →  reverse proxy на FastAPI
  systemd  →  fmailsender.service
  ```

  ## Переменные окружения (обязательны)

  ```bash
  BOT_TOKEN=         # Telegram @BotFather
  CRYPTO_BOT_TOKEN=  # @CryptoBot
  JWT_SECRET=        # мин 32 символа, случайный
  ADMIN_IDS=         # Telegram ID через запятую
  ```

  ## Деплой (строгий порядок)

  ```bash
  git pull origin main
  pip install -r server/requirements.txt
  systemctl restart fmailsender
  systemctl status fmailsender
  journalctl -u fmailsender -n 50
  ```

  ## Критические правила

  - Никогда не запускать `python server/bot.py` напрямую в продакшене — только systemd
  - База данных — всегда с WAL mode (`PRAGMA journal_mode=WAL`)
  - CryptoBot webhook — проверять `X-Api-Key` header
  - JWT ключи — ротация раз в 6 месяцев

  ## Чеклист перед деплоем

  - [ ] `python -m py_compile server/bot.py` — OK
  - [ ] `.env` на сервере актуален
  - [ ] `licenses.db` backup сделан перед изменением схемы
  - [ ] `nginx -t` — конфиг валиден
  