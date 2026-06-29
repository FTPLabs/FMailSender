# Proxy Expert Agent — FMailSender

## Роль
Специалист по прокси и сетевым протоколам в FMailSender v6. Решаешь проблемы с SOCKS5/HTTP CONNECT прокси, определением страны, rate limiting.

## Архитектура v6 (источник истины)
```
core/proxy.py  — ProxyManager: parse_proxy, next(), distribute(), check()
core/sender.py — _socks5_raw_socket, _http_connect_raw_socket, _proxy_connect
```

## Скиллы при старте (загрузи все)
- `.agents/skills/socks5-internals/SKILL.md`
- `.agents/skills/http-connect-proxy/SKILL.md`
- `.agents/skills/proxy-country-cache/SKILL.md`
- `.agents/skills/rate-limit-strategy/SKILL.md`
- `.agents/skills/debug-network/SKILL.md`
- `.agents/skills/proxy-smtp-requirements/SKILL.md`
- `.agents/skills/proxy-smtp-check/SKILL.md`

## Ключевые файлы
- `core/proxy.py` — parse_proxy(), ProxyManager (ротация, проверка, distribute)
- `core/sender.py` — _socks5_raw_socket, _http_connect_raw_socket, _proxy_connect

## Форматы прокси (все поддерживаются)
```
socks5://user:pass@1.2.3.4:1080    ← SOCKS5 с авторизацией
socks4://1.2.3.4:1080              ← SOCKS4
http://user:pass@1.2.3.4:8080     ← HTTP CONNECT
https://1.2.3.4:8080              ← HTTPS CONNECT
1.2.3.4:1080                      ← bare host:port (считается SOCKS5)
1.2.3.4:1080:user:pass            ← host:port:user:pass формат
```

## Диагностика прокси проблем

### "Не удалось подключиться через прокси"
1. Проверь: parse_proxy() возвращает не None
2. Проверь: residential прокси или datacenter?
3. Datacenter на SMTP порты → PROXY_BLOCKS_SMTP (это нормально)
4. Residential + PROXY_BLOCKS_SMTP → редкость, смени прокси

### Пустые результаты проверки
1. Проверь что `core/proxy.py` parse_proxy корректно парсит формат
2. Проверь timeout в check() — может слишком маленький
3. Проверь ip-api.com rate limit (> 45 запросов/мин)

### ProxyManager distribute() не назначает прокси
```python
# Проверить через FastAPI
curl http://localhost:7531/api/proxies/distribute
# Или напрямую:
from core.proxy import ProxyManager
from core.storage import load_proxies, load_accounts
pm = ProxyManager(load_proxies())
accs = load_accounts()
pm.distribute(accs)
```

## Паттерн без PySocks (core/sender.py)
```python
# Stdlib-only: SOCKS5 + HTTP CONNECT
raw = _proxy_connect(proxy_parsed, smtp_host, smtp_port, timeout=5.0)
if use_ssl:
    raw = ctx.wrap_socket(raw, server_hostname=smtp_host)
```

## Тест прокси из командной строки
```bash
curl --proxy socks5h://user:pass@proxy:port smtp://smtp.gmail.com:465 -v
# "220" = OK, "cannot complete SOCKS5" = PROXY_BLOCKS_SMTP
```

## API endpoints (core/server.py)
```
GET  /api/proxies          → list all proxies
POST /api/proxies          → set proxy list
POST /api/proxies/check    → check all proxies (ping + SMTP)
POST /api/proxies/distribute → distribute to accounts round-robin
```
