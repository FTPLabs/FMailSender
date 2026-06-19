---
  name: license-server-guard
  description: Защищает систему лицензий FMailSender — JWT, SQLite, CryptoBot. Активируй при изменении server/database.py, server/bot.py (лицензионная логика), core/license.py, или при жалобах на неработающие ключи/платежи.
  ---

  # License Server Guard — JWT + SQLite + CryptoBot

  ## Структура лицензионного ключа

  ```
  FM-XXXXXXXX-XXXXXXXX-XXXXXXXX  (prefix FM- + 3 группы по 8 hex)
  ```

  - Prefix: из `config.KEY_PREFIX = "FM-"`
  - Хранится в SQLite `licenses` таблице
  - Активация привязывает к `hardware_id` (fingerprint машины)

  ## Безопасность JWT

  ```python
  # JWT подписывается JWT_SECRET из env — НЕ хардкодить
  # Payload содержит: user_id, plan, expires_at, hardware_id
  # Алгоритм: HS256 (PyJWT)

  # ✅ Проверка в клиенте (core/license.py)
  import jwt
  payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
  ```

  ## SQLite — правила работы

  ```python
  # ✅ Всегда через async context manager
  async with _db() as db:
      await db.execute("SELECT ...", (param,))
      await db.commit()

  # ❌ Никогда напрямую
  db = await aiosqlite.connect(DB_PATH)  # без WAL mode!
  ```

  ## CryptoBot — обработка платежей

  1. Invoice создаётся → сохраняется `invoice_id` в pending таблице
  2. Webhook от CryptoBot → проверить `X-Api-Key` → найти pending → активировать лицензию
  3. Дублирование: проверять `invoice_id` на уникальность перед активацией

  ## Чеклист изменения лицензионной логики

  - [ ] JWT_SECRET в env, не в коде
  - [ ] hardware_id проверяется при каждой валидации
  - [ ] expires_at в UTC (timezone-aware datetime)
  - [ ] Все DB операции через `async with _db()`
  - [ ] Webhook проверяет подпись/API-Key CryptoBot
  