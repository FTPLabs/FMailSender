---
name: fmailsender-monitor
description: >
  Комплексный мониторинг безопасности FMailSender v7+.
  Проверяет HWID-привязку, целостность ключей, синхронизацию с Telegram-ботом,
  состояние ядра и безопасность сборки. Активировать при любых вопросах
  о безопасности, привязке HWID или проблемах с лицензией.
---

# FMailSender Security Monitor Skill

## Архитектура безопасности

```
Клиент (Windows)                    Сервер (fmail.shop)         Telegram-бот
─────────────────────              ───────────────────────     ─────────────
fmail-core.exe запускается
    │
    ├── get_hwid()                 
    │   MachineGuid → SHA-256
    │
    ├── get_app_fingerprint()      
    │   SHA-256(exe)
    │
    ├── POST /api/v2/verify ──────► verify_startup()
    │   {key, hwid, fingerprint}     ├── Ключ активен?
    │                                ├── HWID совпадает?      ──► bot.notify_hwid_ok()
    │                                ├── Fingerprint OK?
    │                                └── expires_at не истёк?
    │
    └── Результат: ok/hwid_mismatch/expired/invalid
```

## Потоки данных — полная синхронизация

### 1. Первая активация (клиент купил подписку)
```
Telegram-бот: клиент вводит /activate <KEY>
    └── bot.py: activate_license_key(key, hwid="")
        ├── DB: licenses.hwid = "" (привязка HWID отложена)
        └── Ответ: "Активирован. HWID привяжется при первом запуске."

Клиент запускает FMailSender:
    ├── core/license.py: activate_license_key(key)
    │   └── POST /v1/activate {key, hwid}
    │       ├── DB: licenses.hwid = HWID_клиента
    │       ├── DB: users.hwid = HWID_клиента
    │       └── bot.notify: "✅ HWID привязан: {hwid[:8]}..."
    │
    └── core/app_identity.py: verify_on_startup(key)
        └── POST /api/v2/verify {key, hwid, fingerprint}
            ├── hwid_bound = True
            └── ok = True
```

### 2. Повторный запуск (проверка целостности)
```
FMailSender стартует:
    └── core/app_identity.py: verify_on_startup(key)
        └── POST /api/v2/verify {key, hwid, fingerprint}
            ├── hwid == licenses.hwid?  → ok=True
            ├── hwid != licenses.hwid?  → ok=False, reason="hwid_mismatch"
            │   └── клиент видит: "Ключ уже используется на другом устройстве"
            └── fingerprint изменился? → WARNING в лог сервера (не блокирует)
```

### 3. Подмена бинаря (protection against cracking)
```
Кто-то подменяет fmail-core.exe:
    └── get_app_fingerprint() → другой SHA-256
        └── POST /api/v2/verify {fingerprint: "NEW_HASH"}
            └── Сервер: логирует как подозрительное, алертит в Telegram
                (не блокирует — только мониторинг)
```

## Серверные эндпоинты безопасности

### POST /api/v2/verify (новый)
```python
# server/bot.py или отдельный FastAPI на сервере
@app.post("/api/v2/verify")
async def verify_startup(request: Request):
    body = await request.json()
    key         = body.get("key", "")
    hwid        = body.get("hwid", "")
    fingerprint = body.get("fingerprint", "")
    
    # 1. Проверяем ключ
    license = await db.get_license_by_key(key)
    if not license or not license["is_active"]:
        return JSONResponse({"ok": False, "reason": "invalid_key"}, 403)
    
    # 2. Проверяем срок
    if license["expires_at"] < datetime.utcnow().isoformat():
        return JSONResponse({"ok": False, "reason": "expired"}, 403)
    
    # 3. HWID-проверка
    stored_hwid = license.get("hwid", "")
    hwid_bound = bool(stored_hwid)
    
    if not stored_hwid:
        # Первый запуск — привязываем HWID
        await db.bind_hwid_to_license(key, hwid)
        await db.set_user_hwid(license["telegram_id"], hwid)
        # Уведомляем бота
        await notify_hwid_bound(license["telegram_id"], key, hwid)
        hwid_bound = True
    elif stored_hwid.upper() != hwid.upper():
        return JSONResponse({
            "ok":        False,
            "reason":    "hwid_mismatch",
            "hwid_match": False,
        }, 403)
    
    # 4. Логируем fingerprint (для мониторинга подмены)
    await db.log_startup_fingerprint(key, hwid, fingerprint)
    
    return JSONResponse({
        "ok":         True,
        "plan":       license["plan"],
        "expires_at": license["expires_at"],
        "hwid_bound": hwid_bound,
        "hwid_match": True,
    })

### POST /api/v2/bind_hwid (новый)
@app.post("/api/v2/bind_hwid")
async def bind_hwid(request: Request):
    body = await request.json()
    key  = body.get("key", "")
    hwid = body.get("hwid", "")
    
    license = await db.get_license_by_key(key)
    if not license:
        return JSONResponse({"ok": False, "reason": "invalid_key"}, 403)
    
    stored_hwid = license.get("hwid", "")
    if stored_hwid and stored_hwid.upper() != hwid.upper():
        return JSONResponse({"ok": False, "reason": "hwid_already_bound"}, 403)
    
    await db.bind_hwid_to_license(key, hwid)
    await db.set_user_hwid(license["telegram_id"], hwid)
    await notify_hwid_bound(license["telegram_id"], key, hwid)
    
    return JSONResponse({"ok": True})
```

## Чеклист безопасности — запуск

```
□ core/app_identity.py импортирован в core/server.py
□ /api/v2/verify endpoint добавлен в server/bot.py (серверный FastAPI)
□ /api/v2/bind_hwid endpoint добавлен
□ database.py: функции log_startup_fingerprint, bind_hwid_to_license существуют
□ bot.py: notify_hwid_bound() уведомляет пользователя и администратора
□ main.rs: после ready — JS вызывает /api/identity для отображения HWID в UI
```

## Чеклист сборки (PyInstaller 6.21)

```
□ fmail-core.spec: все uvicorn/fastapi/aiosmtplib в hiddenimports
□ requirements.txt: pyinstaller не в списке (только runtime зависимости)
□ release.yml: timeout-minutes: 60 (было 180 с Nuitka)
□ CI шаг "Verify core binary" проходит (--test флаг в main.py)
□ Portable EXE > 20 MB (иначе что-то не упаковалось)
□ Отпечаток core: запомни SHA-256 для следующего релиза
```

## Диагностика — ядро не запускается

### Чек-лист (по порядку)
1. **Смотри startup.log**: `%LOCALAPPDATA%\FMailSender\startup.log`
   - `ModuleNotFoundError` → добавь модуль в hiddenimports в spec
   - `Address already in use` → порт 7531 занят, перезапусти ПК
   - `Access denied` → антивирус блокирует, добавь в исключения

2. **AV проверка**: запусти `dist/fmail-core.exe` вручную, смотри ошибку

3. **Проверь импорты**: `dist/fmail-core.exe --test`
   - exit 0 = всё OK
   - exit 1 = ошибка импорта (смотри stderr)

4. **Порт**: `netstat -an | findstr 7531`
   - Если занят: `taskkill /f /im fmail-core.exe`

5. **Логи Tauri**: `%APPDATA%\FMailSender\logs\`

## Мониторинг HWID — что проверять

### В Telegram-боте (команда /admin hwid_stats)
```
Показывает:
  - Количество пользователей с привязанным HWID
  - Попытки активации с чужим HWID (hwid_mismatch events)
  - Подозрительные fingerprint изменения
  - Дубли HWID (один HWID на несколько ключей)
```

### Алерты (автоматические)
```
🔴 КРИТИЧНО:
  - Один HWID → 2+ активных ключа (кража ключей)
  - hwid_mismatch rate > 10/час (брутфорс активации)
  - Fingerprint изменился у 5+ пользователей в 1 час (malware распространение)

🟡 ПРЕДУПРЕЖДЕНИЕ:
  - HWID сброс 3+ раза за 30 дней (злоупотребление сбросом)
  - Offline mode > 3 дней (возможен деактив без нашего ведома)
```

## Правила для агентов

```
✅ ВСЕГДА:
  - app_identity.get_hwid() — единственный источник HWID в клиенте
  - verify_on_startup() вызывать ДО разблокировки UI
  - bind_hwid() вызывать ПОСЛЕ успешной активации
  - Все запросы к серверу — с заголовками X-FMail-HWID, X-FMail-Version

❌ НИКОГДА:
  - Не хранить HWID в plaintext вне зашифрованного хранилища
  - Не пропускать verify_on_startup() при offline (использовать кеш)
  - Не hardcode-ить ключи безопасности в исходном коде
  - Не логировать полный HWID (только первые 8 символов)
```

## Синхронизация версий

| Файл | Что содержит | Синхронизируется |
|------|-------------|-----------------|
| `core/_version.py` | `APP_VERSION` | CI: sync_version шаг |
| `src-tauri/tauri.conf.json` | `version` | CI: sync_version шаг |
| `src-tauri/Cargo.toml` | `version` | CI: sync_version шаг |
| `ui/src/version.ts` | `FRONTEND_VERSION` | CI: sync_version шаг |

При запуске: core сверяет `APP_VERSION` с версией в таможне Tauri.
Если не совпадает → предупреждение в UI (устаревший WebView кеш).
