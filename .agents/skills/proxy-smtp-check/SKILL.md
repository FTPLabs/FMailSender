---
  name: proxy-smtp-check
  description: Проверка SMTP через прокси и умное распределение (v6 — Tauri + FastAPI + React). Активируй при проблемах с прокси, молчаливых сбоях рассылки, настройке ProxyManager.
  ---

  # Скилл: Проверка SMTP через прокси (v6)

  ## Архитектура (v6)
  - `core/proxy.py` — ProxyManager, parse_proxy, validate_proxy
  - `core/server.py` — POST /api/proxies/check, POST /api/proxies/distribute
  - `ui/src/pages/Proxies.tsx` — React UI управления прокси

  ## Проблема
  Прокси может успешно подключаться к HTTP/HTTPS, но **блокировать SMTP-порты** (25, 465, 587, 2525).
  Это ведёт к:
  - Молчаливым отказам при рассылке
  - Сожжённым лимитам без единого отправленного письма
  - "Все аккаунты недоступны" после прокси-теста

  ## validate_proxy (core/proxy.py)

  ```python
  validate_proxy(proxy_url: str, timeout: int = 7) -> dict
  # Возвращает: {"ok": bool, "error": str, "latency_ms": int}
  ```

  ## Умное распределение (POST /api/proxies/distribute)

  - N прокси на M аккаунтов → round-robin по индексу
  - 3 прокси + 30 аккаунтов = по 10 аккаунтов на каждый прокси
  - Каждый аккаунт: `acc.proxy = proxies[i % len(proxies)]`
  - `acc.proxy_list = all_proxies` — весь пул для fallback при рассылке

  ## Auth vs Proxy error — три состояния

  | Результат | `last_test_ok` | `is_active` |
  |---|---|---|
  | Успех | `True` | без изменений |
  | Ошибка аутентификации (535/534) | `False` | `False` |
  | Ошибка прокси/сети | `None` | без изменений |

  Ключевые маркеры auth-ошибки: "535", "534", "password", "oauth2 rejected".

  ## Провайдеры, блокирующие SMTP-порты
  - Большинство datacenter-прокси (Hetzner, Ovh, Linode IP)
  - Бесплатные прокси-листы
  - Mobile proxy пул без SMTP allowlist

  ## Антипаттерны
  - ❌ `is_active = False` при сбое прокси → уничтожает все аккаунты
  - ❌ Использовать прокси без SMTP-теста → молчаливые сбои
  - ❌ proxy без proxy_list → нет fallback при ротации
  