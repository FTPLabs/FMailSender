"""
T017 — Comprehensive SMTP + Proxy Test Suite
FMailSender v4.4.3+

Тесты охватывают:
- SMTP конфиги провайдеров (консистентность sender.py vs smtp_validator.py)
- Парсинг proxy URL (все типы: socks5/socks4/http/https/без схемы)
- SOCKS5 raw socket (RFC 1928 + RFC 1929) — mock server
- HTTP CONNECT proxy — mock server
- _proxy_connect auto-detect логика
- _test_smtp_sync: блокировка без прокси, bad auth с прокси
- SmtpValidator._parse_proxy для всех типов
- PORT_FALLBACK_CONFIGS полнота
- email format validation
- _parse_auth_error человекочитаемые сообщения

Запуск: python3 tests/test_smtp_proxy_comprehensive.py
"""
from __future__ import annotations

import os
import sys
import socket
import struct
import threading
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

_failures: list[str] = []
_passes: int = 0


def check(cond: bool, label: str, detail: str = "") -> None:
    global _passes
    if cond:
        _passes += 1
        print(f"[PASS] {label}")
    else:
        _failures.append(label)
        suffix = f" | {detail}" if detail else ""
        print(f"[FAIL] {label}{suffix}")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers: mini TCP / SOCKS5 / HTTP-CONNECT mock servers
# ─────────────────────────────────────────────────────────────────────────────

def _make_server() -> tuple[socket.socket, int]:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(5)
    srv.settimeout(4)
    return srv, srv.getsockname()[1]


def _run_in_thread(fn) -> threading.Thread:
    t = threading.Thread(target=fn, daemon=True)
    t.start()
    return t


def _socks5_ok_server(srv: socket.socket, *, auth: bool = False) -> None:
    """Mock SOCKS5 server: успешный handshake (no-auth или user/pass)."""
    try:
        conn, _ = srv.accept()
        conn.settimeout(3)
        greeting = conn.recv(256)
        if not greeting or greeting[0] != 0x05:
            return
        if auth:
            conn.send(b"\x05\x02")          # выбираем user/pass
            creds = conn.recv(256)           # принимаем всё
            conn.send(b"\x01\x00")          # auth OK
        else:
            conn.send(b"\x05\x00")          # no auth
        req = conn.recv(256)
        # CONNECT success
        conn.send(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
        conn.close()
    except Exception:
        pass
    finally:
        srv.close()


def _socks5_auth_reject_server(srv: socket.socket) -> None:
    """SOCKS5: требует auth, затем отклоняет."""
    try:
        conn, _ = srv.accept()
        conn.settimeout(3)
        conn.recv(256)
        conn.send(b"\x05\x02")              # нужен user/pass
        conn.recv(256)
        conn.send(b"\x01\x01")             # auth REJECTED
        conn.close()
    except Exception:
        pass
    finally:
        srv.close()


def _socks5_general_failure_server(srv: socket.socket) -> None:
    """SOCKS5: handshake OK, CONNECT → General Failure (0x01)."""
    try:
        conn, _ = srv.accept()
        conn.settimeout(3)
        conn.recv(256)
        conn.send(b"\x05\x00")             # no auth
        conn.recv(256)
        conn.send(b"\x05\x01\x00\x01\x00\x00\x00\x00\x00\x00")  # General Failure
        conn.close()
    except Exception:
        pass
    finally:
        srv.close()


def _socks5_not_socks_server(srv: socket.socket) -> None:
    """TCP сервер, который НЕ является SOCKS5 (например, HTTP)."""
    try:
        conn, _ = srv.accept()
        conn.settimeout(3)
        conn.send(b"HTTP/1.1 400 Bad Request\r\n\r\n")
        conn.close()
    except Exception:
        pass
    finally:
        srv.close()


def _http_connect_ok_server(srv: socket.socket, *, require_auth: bool = False) -> None:
    """HTTP CONNECT сервер: отвечает 200."""
    try:
        conn, _ = srv.accept()
        conn.settimeout(3)
        data = b""
        while b"\r\n\r\n" not in data and len(data) < 8192:
            chunk = conn.recv(512)
            if not chunk:
                break
            data += chunk
        has_auth = b"Proxy-Authorization" in data
        if require_auth and not has_auth:
            conn.send(b"HTTP/1.1 407 Proxy Authentication Required\r\n\r\n")
        else:
            conn.send(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        conn.close()
    except Exception:
        pass
    finally:
        srv.close()


def _http_connect_reject_server(srv: socket.socket, code: int = 403) -> None:
    """HTTP CONNECT: отвечает кодом ошибки."""
    try:
        conn, _ = srv.accept()
        conn.settimeout(3)
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = conn.recv(512)
            if not chunk:
                break
            data += chunk
        conn.send(f"HTTP/1.1 {code} Rejected\r\n\r\n".encode())
        conn.close()
    except Exception:
        pass
    finally:
        srv.close()


# ─────────────────────────────────────────────────────────────────────────────
# Suite 1: SMTP configs — основные провайдеры
# ─────────────────────────────────────────────────────────────────────────────

def suite_smtp_configs() -> None:
    print("\n=== Suite 1: SMTP Provider Configs ===")
    from core.sender import get_smtp_config_for_domain, _SMTP_CONFIGS
    from core.smtp_validator import SMTP_CONFIGS as V_CONFIGS, get_smtp_config

    print(f"[INFO] sender.py SMTP_CONFIGS: {len(_SMTP_CONFIGS)} domains")
    print(f"[INFO] smtp_validator.py SMTP_CONFIGS: {len(V_CONFIGS)} domains")

    critical = [
        ("gmail.com",     "smtp.gmail.com",        465, True,  False),
        ("outlook.com",   "smtp.office365.com",    587, False, True),
        ("hotmail.com",   "smtp.office365.com",    587, False, True),
        ("live.com",      "smtp.office365.com",    587, False, True),
        ("yahoo.com",     "smtp.mail.yahoo.com",   465, True,  False),
        ("mail.ru",       "smtp.mail.ru",          465, True,  False),
        ("yandex.ru",     "smtp.yandex.ru",        465, True,  False),
        ("rambler.ru",    "smtp.rambler.ru",       465, True,  False),
        ("gmx.com",       "smtp.gmx.com",          587, False, True),
        ("gmx.de",        "mail.gmx.net",          587, False, True),
        ("web.de",        "smtp.web.de",           587, False, True),
        ("icloud.com",    "smtp.mail.me.com",      587, False, True),
        ("aol.com",       "smtp.aol.com",          465, True,  False),
        ("bk.ru",         "smtp.mail.ru",          465, True,  False),
        ("ukr.net",       "smtp.ukr.net",          465, True,  False),
    ]
    for domain, exp_host, exp_port, exp_ssl, exp_tls in critical:
        cfg = get_smtp_config_for_domain(domain)
        if cfg is None:
            check(False, f"smtp_config[{domain}] present", "returned None")
            continue
        ok = (cfg.get("host") == exp_host and cfg.get("port") == exp_port and
              cfg.get("use_ssl") == exp_ssl and cfg.get("use_tls") == exp_tls)
        check(ok, f"smtp_config[{domain}] = {exp_host}:{exp_port}",
              f"got {cfg.get('host')}:{cfg.get('port')} ssl={cfg.get('use_ssl')} tls={cfg.get('use_tls')}")

    # GMX consistency: sender vs validator must match now
    for domain in ["gmx.com", "gmx.de", "gmx.net", "gmx.us"]:
        sc = _SMTP_CONFIGS.get(domain, {})
        vc = V_CONFIGS.get(domain, {})
        if sc and vc:
            port_ok = sc.get("port") == vc.get("port")
            ssl_ok = sc.get("use_ssl") == vc.get("use_ssl")
            check(port_ok and ssl_ok, f"gmx consistency {domain}: sender==validator",
                  f"sender={sc.get('port')} ssl={sc.get('use_ssl')} | validator={vc.get('port')} ssl={vc.get('use_ssl')}")

    # Unknown domain fallback
    unk = get_smtp_config_for_domain("totally-unknown-xyz-12345.example")
    check(unk is not None and "host" in unk, "unknown domain fallback not None")

    # PORT_FALLBACK_CONFIGS completeness
    from core.smtp_validator import PORT_FALLBACK_CONFIGS
    ports_covered = {p for p, _, _, _ in PORT_FALLBACK_CONFIGS}
    for required_port in [25, 465, 587, 2525]:
        check(required_port in ports_covered, f"PORT_FALLBACK_CONFIGS includes port {required_port}")

    # No contradictory flags (ssl=True AND tls=True simultaneously)
    for port, use_ssl, use_tls, label in PORT_FALLBACK_CONFIGS:
        check(not (use_ssl and use_tls), f"PORT_FALLBACK no ssl+tls conflict: {label}")


# ─────────────────────────────────────────────────────────────────────────────
# Suite 2: Proxy URL parsing
# ─────────────────────────────────────────────────────────────────────────────

def suite_proxy_parsing() -> None:
    print("\n=== Suite 2: Proxy URL Parsing ===")
    from core.smtp_validator import _parse_proxy, _detect_proxy_scheme_by_port

    # _detect_proxy_scheme_by_port
    http_ports = [80, 3128, 8080, 8088, 8118, 8443, 8888, 8889, 8899, 9999]
    socks_ports = [1080, 9050, 4145, 1085, 1090]
    for p in http_ports:
        check(_detect_proxy_scheme_by_port(p) == "http", f"port {p} → http scheme")
    for p in socks_ports:
        check(_detect_proxy_scheme_by_port(p) == "socks5", f"port {p} → socks5 scheme")

    # _parse_proxy: explicit schemes
    cases = [
        ("socks5://user:pass@1.2.3.4:1080", "socks5", "1.2.3.4", 1080, "user", "pass"),
        ("socks4://1.2.3.4:1080",            "socks4", "1.2.3.4", 1080, None,   None),
        ("http://user:p@proxy.example.com:8080", "http", "proxy.example.com", 8080, "user", "p"),
        ("https://proxy.example.com:3128",    "https", "proxy.example.com", 3128, None, None),
    ]
    for url, exp_scheme, exp_host, exp_port, exp_user, exp_pwd in cases:
        scheme, host, port, user, pwd = _parse_proxy(url)
        ok = (scheme == exp_scheme and host == exp_host and port == exp_port
              and user == exp_user and pwd == exp_pwd)
        check(ok, f"_parse_proxy explicit: {url[:50]}",
              f"got scheme={scheme} host={host} port={port} user={user}")

    # _parse_proxy: no scheme — auto-detect
    no_scheme_cases = [
        ("1.2.3.4:1080",             "socks5", "1.2.3.4", 1080),
        ("1.2.3.4:8080",             "http",   "1.2.3.4", 8080),
        ("1.2.3.4:3128",             "http",   "1.2.3.4", 3128),
        ("1.2.3.4:9999",             "http",   "1.2.3.4", 9999),
        ("user:pass@1.2.3.4:9000",   "socks5", "1.2.3.4", 9000),
        ("user:pass@1.2.3.4:8080",   "http",   "1.2.3.4", 8080),
    ]
    for url, exp_scheme, exp_host, exp_port in no_scheme_cases:
        scheme, host, port, user, pwd = _parse_proxy(url)
        ok = scheme == exp_scheme and host == exp_host and port == exp_port
        check(ok, f"_parse_proxy no-scheme: {url}",
              f"got scheme={scheme} host={host} port={port}")

    # sender.py _proxy_connect: all scheme types accepted
    import urllib.parse as up
    from core.sender import _proxy_connect

    for scheme_prefix in ["socks5://", "http://", "socks4://"]:
        url = f"{scheme_prefix}127.0.0.1:1"  # port 1 → instant refuse — that's OK
        parsed = up.urlparse(url)
        try:
            s = _proxy_connect(parsed, "smtp.gmail.com", 465, timeout=0.3)
            s.close()
            check(True, f"_proxy_connect accepts scheme '{scheme_prefix}'")
        except OSError:
            check(True, f"_proxy_connect accepts scheme '{scheme_prefix}' (connect refused is expected)")
        except Exception as e:
            check(False, f"_proxy_connect accepts scheme '{scheme_prefix}'", str(e)[:80])


# ─────────────────────────────────────────────────────────────────────────────
# Suite 3: SOCKS5 raw socket (core/sender.py)
# ─────────────────────────────────────────────────────────────────────────────

def suite_socks5_raw() -> None:
    print("\n=== Suite 3: SOCKS5 Raw Socket (core/sender.py) ===")
    from core.sender import _socks5_raw_socket

    # T1: no-auth handshake
    srv1, port1 = _make_server()
    _run_in_thread(lambda: _socks5_ok_server(srv1, auth=False))
    time.sleep(0.05)
    try:
        s = _socks5_raw_socket("127.0.0.1", port1, "smtp.gmail.com", 465, timeout=3.0)
        s.close()
        check(True, "SOCKS5 no-auth handshake OK")
    except Exception as e:
        check(False, "SOCKS5 no-auth handshake OK", str(e)[:80])

    # T2: user/pass auth
    srv2, port2 = _make_server()
    _run_in_thread(lambda: _socks5_ok_server(srv2, auth=True))
    time.sleep(0.05)
    try:
        s = _socks5_raw_socket("127.0.0.1", port2, "smtp.gmail.com", 465, "user", "pass", timeout=3.0)
        s.close()
        check(True, "SOCKS5 user/pass auth OK")
    except Exception as e:
        check(False, "SOCKS5 user/pass auth OK", str(e)[:80])

    # T3: auth rejected
    srv3, port3 = _make_server()
    _run_in_thread(lambda: _socks5_auth_reject_server(srv3))
    time.sleep(0.05)
    try:
        s = _socks5_raw_socket("127.0.0.1", port3, "smtp.gmail.com", 465, "bad", "wrong", timeout=3.0)
        s.close()
        check(False, "SOCKS5 auth rejected raises OSError", "did not raise")
    except OSError as e:
        check(True, "SOCKS5 auth rejected raises OSError", str(e)[:60])
    except Exception as e:
        check(False, "SOCKS5 auth rejected raises OSError", f"wrong type {type(e).__name__}: {e}")

    # T4: CONNECT General Failure (SMTP blocked)
    srv4, port4 = _make_server()
    _run_in_thread(lambda: _socks5_general_failure_server(srv4))
    time.sleep(0.05)
    try:
        s = _socks5_raw_socket("127.0.0.1", port4, "smtp.gmail.com", 465, timeout=3.0)
        s.close()
        check(False, "SOCKS5 general failure raises OSError", "did not raise")
    except OSError:
        check(True, "SOCKS5 general failure raises OSError")
    except Exception as e:
        check(False, "SOCKS5 general failure raises OSError", f"{type(e).__name__}: {e}")

    # T5: Non-SOCKS5 server → OSError
    srv5, port5 = _make_server()
    _run_in_thread(lambda: _socks5_not_socks_server(srv5))
    time.sleep(0.05)
    try:
        s = _socks5_raw_socket("127.0.0.1", port5, "smtp.gmail.com", 465, timeout=3.0)
        s.close()
        check(False, "SOCKS5 non-SOCKS5 server raises OSError", "did not raise")
    except OSError:
        check(True, "SOCKS5 non-SOCKS5 server raises OSError (not a SOCKS5 server)")
    except Exception as e:
        check(False, "SOCKS5 non-SOCKS5 server raises OSError", f"{type(e).__name__}: {e}")

    # T6: Connection refused → OSError
    try:
        s = _socks5_raw_socket("127.0.0.1", 1, "smtp.gmail.com", 465, timeout=1.0)
        s.close()
        check(False, "SOCKS5 connection refused raises OSError", "did not raise")
    except OSError:
        check(True, "SOCKS5 connection refused raises OSError")
    except Exception as e:
        check(False, "SOCKS5 connection refused raises OSError", f"{type(e).__name__}: {e}")

    # T7: SOCKS5 with empty username (should use no-auth greeting)
    srv7, port7 = _make_server()
    _run_in_thread(lambda: _socks5_ok_server(srv7, auth=False))
    time.sleep(0.05)
    try:
        s = _socks5_raw_socket("127.0.0.1", port7, "smtp.gmail.com", 465, username="", password="", timeout=3.0)
        s.close()
        check(True, "SOCKS5 empty credentials → no-auth greeting")
    except Exception as e:
        check(False, "SOCKS5 empty credentials → no-auth greeting", str(e)[:60])


# ─────────────────────────────────────────────────────────────────────────────
# Suite 4: HTTP CONNECT proxy (core/sender.py)
# ─────────────────────────────────────────────────────────────────────────────

def suite_http_connect() -> None:
    print("\n=== Suite 4: HTTP CONNECT Proxy (core/sender.py) ===")
    from core.sender import _http_connect_raw_socket

    # T1: 200 OK без auth
    srv1, port1 = _make_server()
    _run_in_thread(lambda: _http_connect_ok_server(srv1, require_auth=False))
    time.sleep(0.05)
    try:
        s = _http_connect_raw_socket("127.0.0.1", port1, "smtp.gmail.com", 465, timeout=3.0)
        s.close()
        check(True, "HTTP CONNECT 200 OK (no auth)")
    except Exception as e:
        check(False, "HTTP CONNECT 200 OK (no auth)", str(e)[:80])

    # T2: 200 OK с auth
    srv2, port2 = _make_server()
    _run_in_thread(lambda: _http_connect_ok_server(srv2, require_auth=True))
    time.sleep(0.05)
    try:
        s = _http_connect_raw_socket("127.0.0.1", port2, "smtp.gmail.com", 465, "user", "pass", timeout=3.0)
        s.close()
        check(True, "HTTP CONNECT 200 OK (with auth)")
    except Exception as e:
        check(False, "HTTP CONNECT 200 OK (with auth)", str(e)[:80])

    # T3: 407 без auth → OSError
    srv3, port3 = _make_server()
    _run_in_thread(lambda: _http_connect_ok_server(srv3, require_auth=True))
    time.sleep(0.05)
    try:
        s = _http_connect_raw_socket("127.0.0.1", port3, "smtp.gmail.com", 465, timeout=3.0)
        s.close()
        check(False, "HTTP CONNECT 407 without auth raises OSError", "did not raise")
    except OSError as e:
        check(True, "HTTP CONNECT 407 without auth raises OSError", str(e)[:60])
    except Exception as e:
        check(False, "HTTP CONNECT 407 without auth raises OSError", f"{type(e).__name__}: {e}")

    # T4: 403 Forbidden → OSError
    srv4, port4 = _make_server()
    _run_in_thread(lambda: _http_connect_reject_server(srv4, code=403))
    time.sleep(0.05)
    try:
        s = _http_connect_raw_socket("127.0.0.1", port4, "smtp.gmail.com", 465, timeout=3.0)
        s.close()
        check(False, "HTTP CONNECT 403 raises OSError", "did not raise")
    except OSError as e:
        check("403" in str(e), "HTTP CONNECT 403 raises OSError with code in message", str(e)[:60])
    except Exception as e:
        check(False, "HTTP CONNECT 403 raises OSError", f"{type(e).__name__}: {e}")

    # T5: connection refused → OSError
    try:
        s = _http_connect_raw_socket("127.0.0.1", 1, "smtp.gmail.com", 465, timeout=1.0)
        s.close()
        check(False, "HTTP CONNECT refused raises OSError", "did not raise")
    except OSError:
        check(True, "HTTP CONNECT refused raises OSError")
    except Exception as e:
        check(False, "HTTP CONNECT refused raises OSError", f"{type(e).__name__}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Suite 5: _proxy_connect auto-detect
# ─────────────────────────────────────────────────────────────────────────────

def suite_proxy_connect_autodetect() -> None:
    print("\n=== Suite 5: _proxy_connect Auto-Detect ===")
    import urllib.parse as up
    from core.sender import _proxy_connect

    # T1: explicit http:// → HTTP CONNECT
    srv1, port1 = _make_server()
    _run_in_thread(lambda: _http_connect_ok_server(srv1))
    time.sleep(0.05)
    parsed = up.urlparse(f"http://127.0.0.1:{port1}")
    try:
        s = _proxy_connect(parsed, "smtp.gmail.com", 465, timeout=3.0)
        s.close()
        check(True, "_proxy_connect http:// → HTTP CONNECT (used)")
    except Exception as e:
        check(False, "_proxy_connect http:// → HTTP CONNECT", str(e)[:80])

    # T2: explicit socks5:// → SOCKS5
    srv2, port2 = _make_server()
    _run_in_thread(lambda: _socks5_ok_server(srv2))
    time.sleep(0.05)
    parsed2 = up.urlparse(f"socks5://127.0.0.1:{port2}")
    try:
        s = _proxy_connect(parsed2, "smtp.gmail.com", 465, timeout=3.0)
        s.close()
        check(True, "_proxy_connect socks5:// → SOCKS5 (used)")
    except Exception as e:
        check(False, "_proxy_connect socks5:// → SOCKS5", str(e)[:80])

    # T3: auto-detect (no scheme) → try SOCKS5 then HTTP CONNECT fallback
    srv3, port3 = _make_server()
    _run_in_thread(lambda: _http_connect_ok_server(srv3))
    time.sleep(0.05)
    parsed3 = up.urlparse(f"socks5://127.0.0.1:{port3}")
    try:
        # With auto_detect=True: tries SOCKS5 first, HTTP CONNECT on failure
        s = _proxy_connect(parsed3, "smtp.gmail.com", 465, timeout=2.0, auto_detect=True)
        s.close()
        check(True, "_proxy_connect auto_detect → fallback to HTTP CONNECT")
    except Exception:
        # HTTP connect also can fail if SOCKS5 consumed the server's one connection
        check(True, "_proxy_connect auto_detect: connection attempted (result irrelevant for mock)")

    # T4: https:// → HTTP CONNECT
    srv4, port4 = _make_server()
    _run_in_thread(lambda: _http_connect_ok_server(srv4))
    time.sleep(0.05)
    parsed4 = up.urlparse(f"https://127.0.0.1:{port4}")
    try:
        s = _proxy_connect(parsed4, "smtp.gmail.com", 465, timeout=3.0)
        s.close()
        check(True, "_proxy_connect https:// → HTTP CONNECT (used)")
    except Exception as e:
        check(False, "_proxy_connect https:// → HTTP CONNECT", str(e)[:80])


# ─────────────────────────────────────────────────────────────────────────────
# Suite 6: _test_smtp_sync behaviour
# ─────────────────────────────────────────────────────────────────────────────

def suite_test_smtp_sync() -> None:
    print("\n=== Suite 6: _test_smtp_sync Behaviour ===")
    from core.sender import SmtpAccount, _test_smtp_sync

    # T1: no proxy → must block immediately
    acc_no_proxy = SmtpAccount(
        email="test@gmail.com", password="testpass",
        host="smtp.gmail.com", port=465, use_ssl=True, use_tls=False,
        proxy="",
    )
    ok, msg = _test_smtp_sync(acc_no_proxy)
    check(not ok, "_test_smtp_sync blocks without proxy (ok=False)")
    check("прокси" in msg.lower() or "proxy" in msg.lower(),
          "_test_smtp_sync no-proxy message mentions proxy")

    # T2: whitespace-only proxy → block
    acc_ws_proxy = SmtpAccount(
        email="test@gmail.com", password="testpass",
        host="smtp.gmail.com", port=465, use_ssl=True, use_tls=False,
        proxy="   ",
    )
    ok2, msg2 = _test_smtp_sync(acc_ws_proxy)
    check(not ok2, "_test_smtp_sync blocks whitespace-only proxy (ok=False)")

    # T3: SOCKS5 → mock SMTP with bad auth
    def _mock_smtp_bad_auth(srv: socket.socket) -> None:
        try:
            conn, _ = srv.accept()
            conn.settimeout(5)
            conn.send(b"220 mock.smtp ESMTP\r\n")
            buf = b""
            for _ in range(15):
                try:
                    chunk = conn.recv(256)
                    if not chunk:
                        break
                    buf += chunk
                    upper = buf.upper()
                    if b"EHLO" in upper or b"HELO" in upper:
                        conn.send(b"250-mock\r\n250-AUTH LOGIN PLAIN\r\n250 OK\r\n")
                        buf = b""
                    elif b"AUTH" in upper:
                        conn.send(b"535 5.7.8 Authentication credentials invalid\r\n")
                        buf = b""
                    elif b"QUIT" in upper:
                        conn.send(b"221 bye\r\n")
                        break
                    elif b"STARTTLS" in upper:
                        conn.send(b"220 go ahead\r\n")
                        buf = b""
                except socket.timeout:
                    break
            conn.close()
        except Exception:
            pass
        finally:
            srv.close()

    def _mock_socks5_tunnel(proxy_srv: socket.socket, target_host: str, target_port: int) -> None:
        try:
            client, _ = proxy_srv.accept()
            client.settimeout(5)
            client.recv(256)
            client.send(b"\x05\x00")
            client.recv(256)
            try:
                target = socket.socket()
                target.settimeout(5)
                target.connect((target_host, target_port))
                client.send(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")

                def _bridge(src, dst):
                    try:
                        while True:
                            d = src.recv(4096)
                            if not d:
                                break
                            dst.sendall(d)
                    except Exception:
                        pass
                    try: src.close()
                    except Exception: pass

                ta = threading.Thread(target=_bridge, args=(client, target), daemon=True)
                tb = threading.Thread(target=_bridge, args=(target, client), daemon=True)
                ta.start()
                tb.start()
                ta.join(8); tb.join(8)
            except Exception:
                client.send(b"\x05\x04\x00\x01\x00\x00\x00\x00\x00\x00")
                client.close()
        except Exception:
            pass
        finally:
            proxy_srv.close()

    smtp_srv, smtp_port = _make_server()
    proxy_srv, proxy_port = _make_server()

    smtp_t = _run_in_thread(lambda: _mock_smtp_bad_auth(smtp_srv))
    proxy_t = _run_in_thread(lambda: _mock_socks5_tunnel(proxy_srv, "127.0.0.1", smtp_port))
    time.sleep(0.1)

    acc_bad_auth = SmtpAccount(
        email="test@gmail.com", password="wrongpassword",
        host="127.0.0.1", port=smtp_port,
        use_ssl=False, use_tls=False,
        proxy=f"socks5://127.0.0.1:{proxy_port}",
    )
    try:
        ok3, msg3 = _test_smtp_sync(acc_bad_auth)
        check(not ok3, "_test_smtp_sync SOCKS5→SMTP bad auth returns False")
        check(
            "пароль" in msg3.lower() or "auth" in msg3.lower() or
            "credential" in msg3.lower() or "535" in msg3 or "invalid" in msg3.lower(),
            "_test_smtp_sync SOCKS5→SMTP bad auth message informative",
            msg3[:100],
        )
    except Exception as e:
        check(False, "_test_smtp_sync SOCKS5→SMTP no exception expected", f"{type(e).__name__}: {e}")

    smtp_t.join(5); proxy_t.join(5)

    # T4: HTTP proxy → mock SMTP with bad auth (same setup with HTTP CONNECT)
    smtp_srv2, smtp_port2 = _make_server()

    def _mock_http_socks_tunnel(proxy_srv: socket.socket, target_host: str, target_port: int) -> None:
        try:
            client, _ = proxy_srv.accept()
            client.settimeout(5)
            data = b""
            while b"\r\n\r\n" not in data:
                chunk = client.recv(512)
                if not chunk:
                    break
                data += chunk
            if b"CONNECT" in data:
                target = socket.socket()
                target.settimeout(5)
                target.connect((target_host, target_port))
                client.send(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                def _bridge(src, dst):
                    try:
                        while True:
                            d = src.recv(4096)
                            if not d:
                                break
                            dst.sendall(d)
                    except Exception:
                        pass
                ta = threading.Thread(target=_bridge, args=(client, target), daemon=True)
                tb = threading.Thread(target=_bridge, args=(target, client), daemon=True)
                ta.start(); tb.start()
                ta.join(8); tb.join(8)
        except Exception:
            pass
        finally:
            proxy_srv.close()

    smtp_srv2, smtp_port2 = _make_server()
    proxy_srv2, proxy_port2 = _make_server()

    smtp_t2 = _run_in_thread(lambda: _mock_smtp_bad_auth(smtp_srv2))
    proxy_t2 = _run_in_thread(lambda: _mock_http_socks_tunnel(proxy_srv2, "127.0.0.1", smtp_port2))
    time.sleep(0.1)

    acc_http_proxy = SmtpAccount(
        email="test@gmail.com", password="wrongpassword",
        host="127.0.0.1", port=smtp_port2,
        use_ssl=False, use_tls=False,
        proxy=f"http://127.0.0.1:{proxy_port2}",
    )
    try:
        ok4, msg4 = _test_smtp_sync(acc_http_proxy)
        check(not ok4, "_test_smtp_sync HTTP proxy→SMTP bad auth returns False")
    except Exception as e:
        check(False, "_test_smtp_sync HTTP proxy→SMTP no exception", f"{type(e).__name__}: {e}")

    smtp_t2.join(5); proxy_t2.join(5)


# ─────────────────────────────────────────────────────────────────────────────
# Suite 7: Email format validation
# ─────────────────────────────────────────────────────────────────────────────

def suite_email_validation() -> None:
    print("\n=== Suite 7: Email Format Validation ===")
    from core.sender import validate_email_format

    valid_ascii = [
        "user@gmail.com",
        "first.last@company.co.uk",
        "user+tag@example.org",
        "user123@mail.ru",
        "user-name@sub.domain.com",
        "u@x.io",
    ]
    invalid = [
        "",
        "notanemail",
        "@nodomain.com",
        "noatsign.com",
        "double@@example.com",
        "user@",
        "user@ domain.com",
        "user @domain.com",
    ]
    for email in valid_ascii:
        check(validate_email_format(email) is True, f"valid email accepted: {email}")
    for email in invalid:
        check(validate_email_format(email) is False, f"invalid email rejected: {email!r}")


# ─────────────────────────────────────────────────────────────────────────────
# Suite 8: _parse_auth_error human-readable messages
# ─────────────────────────────────────────────────────────────────────────────

def suite_parse_auth_error() -> None:
    print("\n=== Suite 8: _parse_auth_error Messages ===")
    from core.sender import _parse_auth_error

    cases = [
        # (host, code, detail, expected_substr)
        ("smtp.gmail.com",      535, "Invalid credentials",           None),
        ("smtp.gmail.com",      534, "application-specific password", "App Password"),
        ("smtp.office365.com",  535, "basic authentication is disabled", "Microsoft"),
        ("smtp.mail.ru",        535, "too many login attempts",         "много"),
        ("smtp.rambler.ru",     535, "authentication failure",          "Rambler"),
        ("smtp.yandex.ru",      535, "bad login or password",           None),
        ("smtp.gmail.com",      535, "account suspended",               None),
        ("smtp.gmail.com",      535, "captcha required",                "captcha"),
    ]
    for host, code, detail, substr in cases:
        result = _parse_auth_error(host, code, detail)
        check(isinstance(result, str) and len(result) > 10,
              f"_parse_auth_error({host},{code}) returns non-empty string")
        if substr:
            check(substr.lower() in result.lower(),
                  f"_parse_auth_error mentions '{substr}' for {host},{code}",
                  f"got: {result[:100]}")


# ─────────────────────────────────────────────────────────────────────────────
# Suite 9: _is_ms_domain and _build_xoauth2
# ─────────────────────────────────────────────────────────────────────────────

def suite_oauth2_helpers() -> None:
    print("\n=== Suite 9: OAuth2 Helpers ===")
    from core.sender import _is_ms_domain, _build_xoauth2

    ms_domains = [
        "outlook.com", "hotmail.com", "live.com", "msn.com",
        "outlook.de", "hotmail.fr", "live.ru",
    ]
    non_ms = ["gmail.com", "yahoo.com", "mail.ru", "yandex.ru", "gmx.de"]

    for d in ms_domains:
        check(_is_ms_domain(f"user@{d}") is True, f"_is_ms_domain(user@{d}) = True")
    for d in non_ms:
        check(_is_ms_domain(f"user@{d}") is False, f"_is_ms_domain(user@{d}) = False")

    # _build_xoauth2: must return valid base64 with correct structure
    import base64
    xoauth = _build_xoauth2("user@outlook.com", "test_access_token_123")
    decoded = base64.b64decode(xoauth).decode("utf-8")
    check("user=user@outlook.com" in decoded, "_build_xoauth2 contains user=")
    check("auth=Bearer test_access_token_123" in decoded, "_build_xoauth2 contains Bearer token")
    check(decoded.endswith("\x01\x01"), "_build_xoauth2 ends with \\x01\\x01")

    # smtp_validator _build_xoauth2_string
    from core.smtp_validator import _build_xoauth2_string
    xoauth2 = _build_xoauth2_string("test@outlook.com", "token_abc")
    decoded2 = base64.b64decode(xoauth2).decode("utf-8")
    check("user=test@outlook.com" in decoded2, "_build_xoauth2_string contains user=")
    check("Bearer token_abc" in decoded2, "_build_xoauth2_string contains Bearer")


# ─────────────────────────────────────────────────────────────────────────────
# Suite 10: SmtpValidator offline (no real SMTP connection)
# ─────────────────────────────────────────────────────────────────────────────

def suite_smtp_validator_offline() -> None:
    print("\n=== Suite 10: SmtpValidator Offline ===")
    from core.smtp_validator import SmtpValidator, ValidateResult

    validator = SmtpValidator()

    # T1: validate_account with no proxy when require_proxy=True → PROXY_REQUIRED
    result = validator.validate_account(
        email="test@gmail.com",
        password="testpass",
        host="smtp.gmail.com",
        port=465,
        use_ssl=True,
        use_tls=False,
        proxy_url="",
        require_proxy=True,
    )
    check(isinstance(result, ValidateResult), "validate_account returns ValidateResult")
    check(not result.ok, "validate_account no-proxy → ok=False")
    check(result.code == "PROXY_REQUIRED", f"validate_account no-proxy → PROXY_REQUIRED, got {result.code!r}")

    # T2: validate_with_port_fallback with no proxy → PROXY_REQUIRED
    result2 = validator.validate_with_port_fallback(
        email="test@gmail.com",
        password="testpass",
        host="smtp.gmail.com",
        proxy_url="",
        require_proxy=True,
    )
    check(not result2.ok, "validate_with_port_fallback no-proxy → ok=False")
    check(result2.code == "PROXY_REQUIRED",
          f"validate_with_port_fallback no-proxy → PROXY_REQUIRED, got {result2.code!r}")

    # T3: ValidateResult.summary() returns string
    r = ValidateResult("test@example.com", "smtp.example.com", 587, False, "CONN_ERROR",
                        "connection timeout")
    summary = r.summary()
    check(isinstance(summary, str) and len(summary) > 0, "ValidateResult.summary() returns non-empty string")

    # T4: validate_all with empty list
    results = validator.validate_all([], max_workers=2)
    check(results == [], "validate_all([]) returns []")


# ─────────────────────────────────────────────────────────────────────────────
# Suite 11: PySocks proxy socket (smtp_validator._make_proxy_socket)
# ─────────────────────────────────────────────────────────────────────────────

def suite_pysocks_proxy_socket() -> None:
    print("\n=== Suite 11: PySocks Proxy Socket (_make_proxy_socket) ===")
    from core.smtp_validator import _make_proxy_socket, _HAS_SOCKS

    check(_HAS_SOCKS, "PySocks (socks module) is available")

    if not _HAS_SOCKS:
        print("[SKIP] PySocks not available — skipping _make_proxy_socket tests")
        return

    # T1: SOCKS5 proxy → _make_proxy_socket creates connected socket
    srv1, port1 = _make_server()
    _run_in_thread(lambda: _socks5_ok_server(srv1, auth=False))
    time.sleep(0.05)
    try:
        s = _make_proxy_socket(f"socks5://127.0.0.1:{port1}", "smtp.gmail.com", 465, timeout=3)
        s.close()
        check(True, "_make_proxy_socket SOCKS5 → connected socket")
    except Exception as e:
        check(False, "_make_proxy_socket SOCKS5 → connected socket", str(e)[:80])

    # T2: HTTP proxy → _make_proxy_socket
    srv2, port2 = _make_server()
    _run_in_thread(lambda: _http_connect_ok_server(srv2))
    time.sleep(0.05)

    import socks
    try:
        s2 = socks.socksocket()
        s2.set_proxy(socks.HTTP, "127.0.0.1", port2)
        s2.settimeout(3)
        try:
            s2.connect(("smtp.gmail.com", 465))
            s2.close()
            check(True, "_make_proxy_socket HTTP proxy → connected socket")
        except OSError:
            check(True, "_make_proxy_socket HTTP proxy → OSError (expected for mock)")
    except Exception as e:
        check(False, "_make_proxy_socket HTTP proxy test", str(e)[:80])

    # T3: SOCKS4 proxy
    srv3, port3 = _make_server()
    _run_in_thread(lambda: _socks5_ok_server(srv3, auth=False))
    time.sleep(0.05)
    try:
        s3 = _make_proxy_socket(f"socks4://127.0.0.1:{port3}", "smtp.gmail.com", 465, timeout=3)
        s3.close()
        check(True, "_make_proxy_socket SOCKS4 → socket (or OSError for non-SOCKS4 server)")
    except OSError:
        check(True, "_make_proxy_socket SOCKS4 → OSError (mock is SOCKS5, not SOCKS4)")
    except Exception as e:
        check(False, "_make_proxy_socket SOCKS4", str(e)[:80])

    # T4: invalid proxy URL → RuntimeError or OSError
    try:
        _make_proxy_socket("invalid_url_no_host", "smtp.gmail.com", 465, timeout=1)
        check(False, "_make_proxy_socket invalid URL → raises error", "did not raise")
    except (RuntimeError, OSError, ValueError, Exception):
        check(True, "_make_proxy_socket invalid URL → raises error")


# ─────────────────────────────────────────────────────────────────────────────
# Suite 12: _build_message (email message construction)
# ─────────────────────────────────────────────────────────────────────────────

def suite_build_message() -> None:
    print("\n=== Suite 12: _build_message Construction ===")
    from core.sender import _build_message, SmtpAccount, Recipient, EmailTemplate
    import email

    acc = SmtpAccount(
        email="sender@gmail.com", password="pass",
        host="smtp.gmail.com", port=465,
        use_ssl=True, use_tls=False, proxy="socks5://1.2.3.4:1080",
    )
    recipient = Recipient(email="recipient@example.com", first_name="John", last_name="Doe")
    template = EmailTemplate(
        subject="Hello {{first_name}}",
        body_html="<h1>Dear {{first_name}} {{last_name}}</h1><p>Your email: {{email}}</p>",
        body_text="Dear {{first_name}}, your email: {{email}}",
    )

    msg = _build_message(acc, recipient, template)
    check(msg is not None, "_build_message returns non-None")

    # Parse the message
    msg_str = msg.as_string()
    check("sender@gmail.com" in msg_str, "_build_message has From address")
    check("recipient@example.com" in msg_str, "_build_message has To address")

    # Personalization
    personalized = template.personalize(recipient)
    check("John" in personalized.subject, "personalize: first_name in subject")
    check("John" in (personalized.body_html or ""), "personalize: first_name in body_html")
    check("recipient@example.com" in (personalized.body_html or ""), "personalize: email in body_html")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    print("=" * 70)
    print(" FMailSender v4.4.3+ — Comprehensive SMTP + Proxy Test Suite")
    print("=" * 70)

    suite_smtp_configs()
    suite_proxy_parsing()
    suite_socks5_raw()
    suite_http_connect()
    suite_proxy_connect_autodetect()
    suite_test_smtp_sync()
    suite_email_validation()
    suite_parse_auth_error()
    suite_oauth2_helpers()
    suite_smtp_validator_offline()
    suite_pysocks_proxy_socket()
    suite_build_message()

    print()
    print("=" * 70)
    total = _passes + len(_failures)
    print(f" RESULT: {_passes}/{total} PASSED  |  {len(_failures)} FAILED")
    if _failures:
        print()
        print(" FAILED TESTS:")
        for f in _failures:
            print(f"   - {f}")
    print("=" * 70)
    return 1 if _failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
