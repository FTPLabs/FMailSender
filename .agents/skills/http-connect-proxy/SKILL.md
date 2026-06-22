---
name: http-connect-proxy
description: HTTP CONNECT прокси (RFC 7231) — реализация без библиотек, диагностика ошибок. Активируй при работе с HTTP-прокси, ошибках 407/502, написании HTTP CONNECT кода.
---

# HTTP CONNECT Proxy (RFC 7231 §4.3.6)

## Протокол

```
Client → Proxy:
  CONNECT smtp.gmail.com:465 HTTP/1.1
  Host: smtp.gmail.com:465
  Proxy-Authorization: Basic base64(user:pass)
  
Proxy → Client:
  HTTP/1.1 200 Connection Established
  (пустая строка)
  [теперь туннель открыт — любые данные проходят напрямую]
```

## Коды ответа

| Код | Причина | Действие |
|-----|---------|----------|
| 200 | OK — туннель открыт | Продолжай |
| 407 | Auth required | Добавь Proxy-Authorization |
| 403 | Forbidden | Прокси блокирует порт |
| 502 | Bad Gateway | Прокси не может подключиться к хосту |
| 503 | Service Unavailable | Прокси перегружен |

## _http_connect_raw_socket (core/sender.py)

```python
def _http_connect_raw_socket(proxy_host, proxy_port, target_host, target_port,
                             username="", password="", timeout=30.0):
    s = socket.socket()
    s.settimeout(timeout)
    s.connect((proxy_host, proxy_port))
    
    req = f"CONNECT {target_host}:{target_port} HTTP/1.1\r\n"
    req += f"Host: {target_host}:{target_port}\r\n"
    if username:
        cred = base64.b64encode(f"{username}:{password}".encode()).decode()
        req += f"Proxy-Authorization: Basic {cred}\r\n"
    req += "\r\n"
    s.sendall(req.encode())
    
    # Читаем ответ до двойного CRLF
    resp = b""
    while b"\r\n\r\n" not in resp:
        resp += s.recv(256)
    
    code = resp.split(b" ")[1].decode()  # "200"
    if code != "200":
        raise OSError(f"HTTP proxy rejected: {code}")
    return s  # туннелированный сокет
```

## Auto-detect: SOCKS5 или HTTP?

```python
def _proxy_connect(proxy_parsed, target_host, target_port, *, timeout=30.0, auto_detect=False):
    scheme = proxy_parsed.scheme.lower()
    if "http" in scheme:
        return _http_connect_raw_socket(...)
    elif "socks" in scheme and not auto_detect:
        return _socks5_raw_socket(...)
    else:
        # auto_detect: пробуем SOCKS5 (3с), при неудаче → HTTP CONNECT
        try:
            return _socks5_raw_socket(..., timeout=min(timeout, 3.0))
        except OSError:
            return _http_connect_raw_socket(..., timeout=timeout)
```
