---
  name: license-server-guard
  description: Защищает систему лицензий — JWT, SQLite, CryptoBot. Активируй при изменении server/database.py, server/bot.py (лицензионная логика), core/license.py, или при жалобах на неработающие ключи/платежи.
  ---

  # License Server Guard

  ## Структура ключа

  `FM-XXXXXXXX-XXXXXXXX-XXXXXXXX` (prefix `FM-` + 3 группы по 8 hex)

  Хранится в SQLite, активация привязывает к `hardware_id`.

  ## Безопасность JWT

  ```python
  # JWT подписывается JWT_SECRET из env — НЕ хардкодить
  # Payload: user_id, plan, expires_at, hardware_id
  # Алгоритм: HS256 (PyJWT)
  payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
  ```

  ## SQLite — правила

  ```python
  # ✅ Всегда через async context manager
  async with _db() as db:
      await db.execute("SELECT ...", (param,))
      await db.commit()
  ```

  ## CryptoBot — порядок

  1. Invoice создаётся → `invoice_id` сохраняется в pending
  2. Webhook → проверить `X-Api-Key` → найти pending → активировать лицензию
  3. Проверять `invoice_id` на уникальность перед активацией (защита от дублей)

  ## Чеклист

  - [ ] JWT_SECRET в env, не в коде
  - [ ] hardware_id проверяется при каждой валидации
  - [ ] expires_at в UTC (timezone-aware)
  - [ ] Все DB операции через `async with _db()`
  