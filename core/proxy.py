"""
FMailSender — Proxy manager v6.0
Handles SOCKS5/SOCKS4/HTTP proxy parsing, rotation and SMTP port checking.
"""
from __future__ import annotations
import socket
import threading
import time
import urllib.parse
from typing import Optional

_HTTP_PORTS = frozenset({80, 8080, 8088, 8118, 3128, 3129, 8443, 8888, 8889, 9999})


def parse_proxy(raw: str) -> Optional[str]:
    """Normalize proxy string to scheme://[user:pass@]host:port format."""
    raw = raw.strip()
    if not raw or raw.startswith("#"):
        return None
    if "://" in raw:
        return raw
    # user:pass@host:port OR host:port OR host:port:user:pass OR user:pass:host:port
    parts = raw.split(":")
    if len(parts) == 2:
        host, port = parts
        scheme = "http" if int(port) in _HTTP_PORTS else "socks5"
        return f"{scheme}://{host}:{port}"
    if len(parts) == 4:
        # BUG FIX v6.3: previous logic returned None for host:port:user:pass
        # when password was non-numeric (only numeric ports were checked on both sides).
        # Fixed: try parts[1] as port first (host:port:user:pass),
        #        then parts[3] as port (user:pass:host:port).
        try:
            port_val = int(parts[1])
            host, port, user, pw = parts
            scheme = "http" if port_val in _HTTP_PORTS else "socks5"
            return f"{scheme}://{user}:{pw}@{host}:{port}"
        except ValueError:
            pass
        try:
            port_val = int(parts[3])
            user, pw, host, port = parts
            scheme = "http" if port_val in _HTTP_PORTS else "socks5"
            return f"{scheme}://{user}:{pw}@{host}:{port}"
        except ValueError:
            pass
    if "@" in raw:
        # user:pass@host:port without scheme
        # BUG FIX v6.3.1: default scheme is "http" (not "socks5").
        # Commercial reseller/datacenter proxies with credentials always use
        # HTTP CONNECT; only explicit socks5:// prefix should trigger SOCKS5.
        p = urllib.parse.urlparse("http://" + raw)
        port = p.port or 3128
        scheme = "http"
        return f"{scheme}://{p.username or ''}:{p.password or ''}@{p.hostname}:{port}"
    return None


class ProxyManager:
    """Round-robin or random proxy rotation pool."""

    def __init__(self, raw_list: list[str], mode: str = "round_robin"):
        self._mode = mode
        self._index = 0
        self._lock = threading.Lock()
        self._proxies = [p for raw in raw_list if (p := parse_proxy(raw))]

    @property
    def proxies(self) -> list[str]:
        return list(self._proxies)

    def next(self) -> Optional[str]:
        if not self._proxies:
            return None
        with self._lock:
            if self._mode == "random":
                import random
                return random.choice(self._proxies)
            idx = self._index % len(self._proxies)
            self._index += 1
            return self._proxies[idx]

    def distribute(self, accounts: list, start_index: int = 0) -> None:
        """Assign proxies round-robin to accounts list."""
        if not self._proxies:
            return
        for i, acc in enumerate(accounts):
            acc.proxy = self._proxies[(start_index + i) % len(self._proxies)]
            acc.proxy_list = list(self._proxies)


def check_proxy(proxy_url: str, timeout: int = 7) -> tuple[bool, str, int]:
    """Test proxy connectivity. Returns (ok, error_msg, ping_ms)."""
    TEST_HOST, TEST_PORT = "httpbin.org", 80
    try:
        p = urllib.parse.urlparse(proxy_url if "://" in proxy_url else "socks5://" + proxy_url)
        scheme = p.scheme.lower()
        px_host, px_port = p.hostname or "", p.port or 1080
        uname, upass = p.username or "", p.password or ""
        t0 = time.monotonic()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((px_host, px_port))
        if "socks5" in scheme:
            # SOCKS5 handshake
            auth = b"\x05\x02\x00\x02" if uname else b"\x05\x01\x00"
            s.sendall(auth)
            r = s.recv(2)
            if len(r) < 2 or r[0] != 5:
                s.close(); return False, "SOCKS5 handshake failed", 0
            if r[1] == 2 and uname:
                creds = bytes([1, len(uname)]) + uname.encode() + bytes([len(upass)]) + upass.encode()
                s.sendall(creds)
                if s.recv(2)[1] != 0:
                    s.close(); return False, "SOCKS5 auth failed", 0
        elif "socks4" in scheme:
            s.sendall(b"\x04\x01\x00\x50" + socket.inet_aton(socket.gethostbyname(TEST_HOST)) + b"\x00")
            if s.recv(8)[1] != 90:
                s.close(); return False, "SOCKS4 connect failed", 0
        s.close()
        ping = int((time.monotonic() - t0) * 1000)
        return True, "", ping
    except Exception as e:
        return False, str(e), 0


def check_smtp_via_proxy(proxy_url: str, timeout: int = 8) -> bool:
    """Check if SMTP port 587 is accessible via proxy (gmail test)."""
    SMTP_HOST, SMTP_PORT = "smtp.gmail.com", 587
    try:
        p = urllib.parse.urlparse(proxy_url if "://" in proxy_url else "socks5://" + proxy_url)
        scheme = p.scheme.lower()
        px_host, px_port = p.hostname or "", p.port or 1080
        uname, upass = p.username or "", p.password or ""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((px_host, px_port))
        if "socks5" in scheme:
            auth = b"\x05\x02\x00\x02" if uname else b"\x05\x01\x00"
            s.sendall(auth)
            r = s.recv(2)
            if r[1] == 2:
                creds = bytes([1, len(uname)]) + uname.encode() + bytes([len(upass)]) + upass.encode()
                s.sendall(creds)
                s.recv(2)
            # Connect to SMTP host
            host_b = SMTP_HOST.encode()
            req = bytes([5, 1, 0, 3, len(host_b)]) + host_b + SMTP_PORT.to_bytes(2, "big")
            s.sendall(req)
            resp = s.recv(10)
            if resp[1] != 0:
                s.close(); return False
        elif "http" in scheme:
            import base64 as b64
            connect = f"CONNECT {SMTP_HOST}:{SMTP_PORT} HTTP/1.1\r\nHost: {SMTP_HOST}:{SMTP_PORT}\r\n"
            if uname:
                cred = b64.b64encode(f"{uname}:{upass}".encode()).decode()
                connect += f"Proxy-Authorization: Basic {cred}\r\n"
            s.sendall((connect + "\r\n").encode())
            resp = b""
            while b"\r\n\r\n" not in resp:
                resp += s.recv(256)
            if b"200" not in resp.split(b"\r\n")[0]:
                s.close(); return False
        banner = b""
        while b"\n" not in banner and len(banner) < 512:
            banner += s.recv(128)
        s.close()
        return banner.startswith(b"220")
    except Exception:
        return False


def validate_proxy(proxy_url: str, timeout: int = 7) -> dict:
    """FIX: was missing — server.py imports this.
    Run connectivity + SMTP check and return a unified result dict.
    """
    ok, error, ping_ms = check_proxy(proxy_url, timeout=timeout)
    smtp_ok = False
    if ok:
        smtp_ok = check_smtp_via_proxy(proxy_url, timeout=timeout)
    return {
        "proxy":    proxy_url,
        "ok":       ok,
        "smtp_ok":  smtp_ok,
        "error":    error,
        "ping_ms":  ping_ms,
    }
