---
name: socks5-internals
description: SOCKS5 протокол (RFC 1928 + RFC 1929) — реализация без PySocks, диагностика ошибок. Активируй при отладке proxy соединений, ошибках General Failure, написании proxy-tunneling кода.
---

# SOCKS5 Protocol Internals (RFC 1928 + RFC 1929)

## Handshake последовательность

```
Client → Server: \x05\x02\x00\x02  (SOCKS5, 2 методов: No-Auth + User/Pass)
Server → Client: \x05\x02           (SOCKS5, выбран User/Pass)
Client → Server: \x01<ulen><user><plen><pass>  (auth)
Server → Client: \x01\x00           (auth OK)
Client → Server: \x05\x01\x00\x03<hlen><host><port>  (CONNECT)
Server → Client: \x05\x00\x00\x01<ip4><port>  (success)
```

## Коды ошибок SOCKS5 CONNECT (byte[1] в ответе)

| Код | Значение | В FMailSender |
|-----|----------|--------------|
| 0x00 | Success | OK |
| 0x01 | General failure | PROXY_BLOCKS_SMTP — прокси запрещает соединение |
| 0x02 | Not allowed by ruleset | PROXY_BLOCKS_SMTP — правило запрещает |
| 0x03 | Network unreachable | CONN_ERROR — нет маршрута |
| 0x04 | Host unreachable | CONN_ERROR — хост недоступен |
| 0x05 | Connection refused | CONN_ERROR — отказано в соединении |
| 0x06 | TTL expired | CONN_ERROR — TTL истёк |
| 0x07 | Command not supported | — |
| 0x08 | Address type not supported | — |

## Только код 0x01 = PROXY_BLOCKS_SMTP

0x01 = "General Failure" = прокси ЯВНО блокирует SMTP-порты (anti-spam политика).
Остальные коды — это сетевые ошибки, а не блокировка прокси.

## _socks5_raw_socket (core/sender.py) — stdlib без PySocks

```python
def _socks5_raw_socket(proxy_host, proxy_port, target_host, target_port,
                       username="", password="", timeout=30.0):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect((proxy_host, proxy_port))
    # Greeting, auth, CONNECT — полная реализация RFC 1928/1929
    ...
    return s  # подключённый туннелированный сокет
```

## PySocks (socks.socksocket) — в smtp_validator.py

```python
import socks
probe = socks.socksocket()
probe.set_proxy(socks.SOCKS5, host, port, True, username, password)
probe.settimeout(8)
probe.connect((smtp_host, smtp_port))
probe.close()
```
Только для pre-check в smtp_validator.py. sender.py использует stdlib.

## Диагностика

```bash
# Тест SOCKS5 через curl
curl --proxy socks5h://user:pass@proxy:port smtp://smtp.gmx.com:465 --connect-timeout 10
# "220 ..." → OK | "cannot complete SOCKS5 (1)" → General Failure (PROXY_BLOCKS_SMTP)

# Python быстропроверка
python3 -c "import socks; s=socks.socksocket(); s.set_proxy(socks.SOCKS5,'host',port,True,'u','p'); s.settimeout(5); s.connect(('smtp.gmail.com',465)); print('OK'); s.close()"
```
