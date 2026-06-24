---
  name: bot-deploy-checker
  description: |
    Автоматически проверяет логи бота, доступность всех команд/кнопок и критических функций
    при каждом деплое на сервер. Активируй ОБЯЗАТЕЛЬНО после каждого git push на сервер.
    Запускается через GitHub Actions (auto-deploy.yml) и локально через скрипт.
  ---

  # Bot Deploy Checker — Проверка бота после деплоя

  ## Когда использовать

  - После каждого `git push` / деплоя на VPS
  - При сообщениях "бот не отвечает" / "кнопка не работает"
  - После обновления зависимостей (requirements.txt)
  - После изменений в `server/bot.py` или `server/database.py`
  - Перед сообщением пользователям о готовности

  ---

  ## Шаг 1 — Проверка systemd (сервис жив?)

  ```bash
  # Статус сервиса
  systemctl is-active fmailsender && echo "✅ Сервис активен" || echo "❌ Сервис УПАЛ"

  # Последние 50 строк лога (ошибки выделятся)
  journalctl -u fmailsender -n 50 --no-pager

  # Поиск критических ошибок в логах за последние 10 минут
  journalctl -u fmailsender --since "10 minutes ago" --no-pager | grep -iE "error|exception|traceback|critical|fatal" | head -30
  ```

  ---

  ## Шаг 2 — Проверка синтаксиса и импортов

  ```bash
  cd /opt/fmailsender
  source venv/bin/activate

  python3 -m py_compile server/bot.py && echo "✅ bot.py OK" || echo "❌ bot.py SYNTAX ERROR"
  python3 -m py_compile server/database.py && echo "✅ database.py OK" || echo "❌ database.py ERROR"
  python3 -m py_compile server/config.py && echo "✅ config.py OK" || echo "❌ config.py ERROR"
  python3 -m py_compile server/crypto_pay.py && echo "✅ crypto_pay.py OK" || echo "❌ crypto_pay.py ERROR"
  python3 -m py_compile server/xrocket_pay.py && echo "✅ xrocket_pay.py OK" || echo "❌ xrocket_pay.py ERROR"
  python3 -m py_compile server/lzt_pay.py && echo "✅ lzt_pay.py OK" || echo "❌ lzt_pay.py ERROR"
  python3 -m py_compile server/payment_providers.py && echo "✅ payment_providers.py OK" || echo "❌ payment_providers.py ERROR"
  ```

  ---

  ## Шаг 3 — Проверка API endpoints (HTTP-тесты)

  ```bash
  BASE="https://fmail.shop"

  echo "=== Health ==="
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/")
  [ "$STATUS" -lt 500 ] && echo "✅ / отвечает ($STATUS)" || echo "❌ / CRASH ($STATUS)"

  echo "=== /v1/verify ==="
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/v1/verify" \
    -H "Content-Type: application/json" \
    -d '{"key":"TEST-0000-0000-0000","hwid":"TESTHWID"}')
  [ "$STATUS" -lt 500 ] && echo "✅ /v1/verify отвечает ($STATUS)" || echo "❌ /v1/verify CRASH ($STATUS)"

  echo "=== /v1/activate ==="
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/v1/activate" \
    -H "Content-Type: application/json" \
    -d '{"key":"TEST-0000-0000-0000","hwid":"TESTHWID"}')
  [ "$STATUS" -lt 500 ] && echo "✅ /v1/activate отвечает ($STATUS)" || echo "❌ /v1/activate CRASH ($STATUS)"

  echo "=== /v1/download ==="
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/v1/download/FMailSender.exe?key=TEST-0000")
  [ "$STATUS" -lt 500 ] && echo "✅ /v1/download отвечает ($STATUS)" || echo "❌ /v1/download CRASH ($STATUS)"
  ```

  ---

  ## Шаг 4 — Полная карта кнопок и хендлеров бота

  ### Команды (/команда)

  | Команда | Хендлер | Описание |
  |---------|---------|---------|
  | `/start` | `cmd_start` | Главное меню |
  | `/help` | `cmd_help` | Помощь |
  | `/check` | `cmd_check` | Статус лицензии |
  | `/buy` | `cmd_buy` | Купить лицензию |
  | `/balance` | `cmd_balance` | Баланс пользователя |
  | `/ticket` | `cmd_ticket` | Открыть тикет |
  | `/cancel` | FSM reset | Отмена текущего действия |

  ### Inline кнопки — пользователь

  | callback_data | Хендлер | Описание |
  |---------------|---------|---------|
  | `buy_plan` | `cb_buy_plan` | Список тарифов |
  | `buy_plan:{id}` | `cb_plan_select` | Выбор тарифа |
  | `promo_yes` | `cb_promo_yes` | Ввести промокод |
  | `promo_no` | `cb_promo_no` | Без промокода |
  | `pay_crypto:{inv}` | `cb_pay_crypto` | Оплата CryptoBot |
  | `pay_xrocket:{inv}` | `cb_pay_xrocket` | Оплата xRocket |
  | `pay_lzt:{inv}` | `cb_pay_lzt` | Оплата LZT |
  | `pay_balance:{inv}` | `cb_pay_balance` | Оплата с баланса |
  | `check_pay:{inv}` | `cb_check_pay` | Проверить оплату |
  | `check_license` | `cb_check_license` | Статус лицензии |
  | `my_balance` | `cb_my_balance` | Мой баланс |
  | `open_ticket` | `cb_open_ticket` | Создать тикет |
  | `cancel_ticket` | `cb_cancel_ticket` | Отмена тикета |
  | `sub_check` | `cb_sub_check` | Проверка подписки |
  | `main_menu` | `cb_main_menu` | Главное меню |

  ### Inline кнопки — администратор

  | callback_data | Хендлер | Описание |
  |---------------|---------|---------|
  | `admin_panel` | `cb_admin_panel` | Панель админа |
  | `admin_stats` | `cb_admin_stats` | Статистика |
  | `admin_users` | `cb_admin_users` | Пользователи |
  | `admin_licenses` | `cb_admin_licenses` | Лицензии |
  | `admin_broadcast` | `cb_admin_broadcast` | Рассылка |
  | `admin_add_lic` | `cb_admin_add_lic` | Создать лицензию |
  | `admin_revoke_lic` | `cb_admin_revoke_lic` | Отозвать лицензию |
  | `admin_promos` | `cb_admin_promos` | Промокоды |
  | `admin_promo_create` | `cb_admin_promo_create` | Создать промокод |
  | `admin_promo_deactivate` | `cb_admin_promo_deactivate` | Деактивировать промо |
  | `admin_balance` | `cb_admin_balance` | Начислить баланс |
  | `admin_tickets` | `cb_admin_tickets` | Тикеты |
  | `admin_ticket:{id}:close` | close handler | Закрыть тикет |
  | `admin_reply:{id}` | reply handler | Ответить в тикет |
  | `admin_mods` | `cb_admin_mods` | Модераторы |
  | `admin_add_mod` | `cb_admin_add_mod` | Добавить модератора |
  | `admin_remove_mod:{id}` | remove handler | Удалить модератора |
  | `admin_set_prices` | `cb_admin_set_prices` | Управление ценами |
  | `admin_set_price:{plan}` | price handler | Цена тарифа |

  ---

  ## Шаг 5 — Python-скрипт статической проверки

  Файл: `scripts/bot_checker.py`

  ```python
  #!/usr/bin/env python3
  """
  Bot Handler Checker — статическая проверка регистрации хендлеров бота.
  Запуск: python3 scripts/bot_checker.py
  Используется в CI/CD после деплоя.
  """
  import sys
  from pathlib import Path

  BOT_FILE = Path(__file__).parent.parent / "server" / "bot.py"

  # Все callback_data-паттерны, которые должны быть зарегистрированы
  EXPECTED_CALLBACKS = [
      "buy_plan", "check_license", "my_balance", "open_ticket", "main_menu",
      "admin_panel", "admin_stats", "admin_broadcast", "admin_licenses",
      "admin_add_lic", "admin_revoke_lic", "admin_promos", "admin_promo_create",
      "admin_promo_deactivate", "admin_balance", "admin_mods", "admin_tickets",
      "promo_yes", "promo_no", "sub_check", "cancel_ticket",
      "pay_balance:", "check_pay:", "pay_crypto:", "pay_xrocket:",
      "admin_ticket:", "admin_reply:", "admin_remove_mod:", "admin_set_price",
  ]

  # Команды бота
  EXPECTED_COMMANDS = ["start", "help", "check", "buy", "balance", "ticket", "cancel"]

  errors = []

  try:
      source = BOT_FILE.read_text(encoding="utf-8")
  except FileNotFoundError:
      print(f"❌ КРИТИЧНО: {BOT_FILE} не найден!")
      sys.exit(1)

  # Проверяем команды
  for cmd in EXPECTED_COMMANDS:
      patterns = [f'Command("{cmd}")', f"Command('{cmd}')", f'commands=["{cmd}"', f"commands=['{cmd}'"]
      if not any(p in source for p in patterns):
          errors.append(f"❌ Команда /{cmd} не зарегистрирована в bot.py")

  # Проверяем callback patterns
  for cb in EXPECTED_CALLBACKS:
      if cb not in source:
          errors.append(f"❌ callback_data='{cb}' НЕ найден в bot.py")

  # Проверяем критические функции
  critical_functions = [
      "async def cmd_start",
      "async def cb_buy_plan",
      "async def cb_admin_panel",
      "async def cb_check_pay",
      "async def cb_pay_balance",
  ]
  for fn in critical_functions:
      if fn not in source:
          errors.append(f"❌ Критическая функция '{fn}' не найдена в bot.py")

  # Проверяем что FSM states не потеряны
  fsm_states = ["AdminFlow", "UserFlow", "SupportFlow"]
  for state in fsm_states:
      if state not in source:
          errors.append(f"⚠️  FSM class '{state}' не найден — возможна регрессия")

  print("=" * 60)
  print("  Bot Handler Checker — FMailSender")
  print("=" * 60)

  if errors:
      print(f"\n❌ Найдено {len(errors)} проблем:")
      for e in errors:
          print(f"  {e}")
      print("\n⛔ Деплой не рекомендован без исправления блокеров!")
  else:
      print(f"\n✅ Все {len(EXPECTED_CALLBACKS)} callbacks и {len(EXPECTED_COMMANDS)} команд зарегистрированы")
      print("✅ Критические функции на месте")
      print("✅ FSM states определены")
      print("\n🚀 Бот готов к работе!")

  sys.exit(1 if any(e.startswith("❌") for e in errors) else 0)
  ```

  ---

  ## Шаг 6 — Мониторинг логов (паттерны алертов)

  ```bash
  # Критические паттерны — требуют НЕМЕДЛЕННОГО отката деплоя
  CRITICAL_PATTERNS=(
    "cannot import"
    "ModuleNotFoundError"
    "SyntaxError"
    "OperationalError: database is locked"
    "Fatal error"
    "Address already in use"
    "Bot token invalid"
    "Unauthorized"
    "cannot connect to database"
  )

  FOUND=0
  for pat in "${CRITICAL_PATTERNS[@]}"; do
    COUNT=$(journalctl -u fmailsender --since "3 minutes ago" --no-pager 2>/dev/null | grep -ci "$pat" || true)
    if [ "$COUNT" -gt 0 ]; then
      echo "❌ КРИТИЧНО [$COUNT раз]: '$pat'"
      FOUND=1
    fi
  done

  if [ $FOUND -eq 1 ]; then
    echo ""
    echo "⛔ Критические ошибки обнаружены — выполняем автооткат..."
    cd /opt/fmailsender
    git reset --hard HEAD~1
    source venv/bin/activate
    pip install -q -r server/requirements.txt
    systemctl restart fmailsender
    sleep 3
    systemctl is-active fmailsender && echo "♻️ Откат выполнен, сервис восстановлен" || echo "❌ Сервис не поднялся после отката!"
    exit 1
  fi

  echo "✅ Критических паттернов в логах нет"
  ```

  ---

  ## Шаг 7 — Проверка БД после деплоя

  ```bash
  DB="/opt/fmailsender/server/licenses.db"

  # Целостность
  RESULT=$(sqlite3 "$DB" "PRAGMA integrity_check;" 2>&1)
  [ "$RESULT" = "ok" ] && echo "✅ БД целостность: OK" || echo "❌ БД повреждена: $RESULT"

  # Таблицы на месте
  TABLES=$(sqlite3 "$DB" ".tables" 2>&1)
  for t in licenses payments users settings tickets ticket_messages moderators promo_codes user_balance; do
    echo "$TABLES" | grep -q "$t" && echo "✅ Таблица $t: OK" || echo "❌ Таблица $t: ОТСУТСТВУЕТ"
  done
  ```

  ---

  ## Полный чеклист после деплоя

  ```
  [ ] systemctl is-active fmailsender → active
  [ ] journalctl -n 20 → нет ERROR/Traceback
  [ ] python3 -m py_compile server/bot.py → 0 ошибок
  [ ] python3 scripts/bot_checker.py → ✅ все хендлеры OK
  [ ] curl https://fmail.shop/ → не 500
  [ ] curl POST /v1/verify → не 500
  [ ] curl POST /v1/activate → не 500
  [ ] sqlite3 PRAGMA integrity_check → ok
  [ ] Все 9 таблиц БД на месте
  [ ] Нет критических паттернов в логах за 3 минуты после деплоя
  [ ] Платёжные провайдеры в config.py (CRYPTO/XROCKET/LZT) — статус проверен
  ```
  