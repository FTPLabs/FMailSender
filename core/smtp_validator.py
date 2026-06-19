"""
FMailSender SMTP Validator v2.0.0
- FIX: Falsese typo -> False (критический баг)
- ADD: parallel validate_all via ThreadPoolExecutor (10x быстрее)
- ADD: validate_with_port_fallback — пробует 465/587/25/2525 автоматически
- ADD: cancel_event для остановки проверки на полпути
"""
from __future__ import annotations

import socket
import smtplib
import ssl
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, List, Optional

try:
    import dns.resolver
    import dns.exception
    _DNS_OK = True
except ImportError:
    _DNS_OK = False


# ── Порты для перебора при неудаче основного ─────────────────────────────────
# (port, use_ssl, use_tls, label)
PORT_FALLBACK_CONFIGS = [
    (465,  True,  False, "SSL/465"),
    (587,  False, True,  "STARTTLS/587"),
    (25,   False, False, "Plain/25"),
    (2525, False, True,  "STARTTLS/2525"),
    (994,  True,  False, "SSL/994"),
    (465,  False, True,  "STARTTLS/465"),
    (993,  True,  False, "SSL/993"),
    (143,  False, True,  "STARTTLS/143"),
]


# ── Result ───────────────────────────────────────────────────────────────────
@dataclass
class ValidateResult:
    email: str
    host: str
    port: int
    ok: bool
    code: str          # OK | AUTH_FAIL | SSL_ERROR | TIMEOUT | BLACKLISTED | CONN_ERROR | CANCELLED
    message: str = ""
    spf_ok:   Optional[bool] = None
    dkim_ok:  Optional[bool] = None
    dmarc_ok: Optional[bool] = None
    mx_ok:    Optional[bool] = None

    def summary(self) -> str:
        icon = "\u2705" if self.ok else "\u274c"
        dns_info = ""
        if self.spf_ok is not None:
            mx_str = f" MX:{'\u2713' if self.mx_ok else '\u2717'}" if self.mx_ok is not None else ""
            dns_info = (
                f" | SPF:{'\u2713' if self.spf_ok else '\u2717'}"
                f" DKIM:{'\u2713' if self.dkim_ok else '\u2717'}"
                f" DMARC:{'\u2713' if self.dmarc_ok else '\u2717'}{mx_str}"
            )
        return f"{icon} {self.email} -> {self.host}:{self.port} [{self.code}]{dns_info}"


# ── DNS helpers ───────────────────────────────────────────────────────────────
def _check_spf(domain: str) -> bool:
    if not _DNS_OK:
        return False
    try:
        answers = dns.resolver.resolve(domain, "TXT", lifetime=5)
        return any("v=spf1" in str(r) for r in answers)
    except Exception:
        return False


def _check_dmarc(domain: str) -> bool:
    if not _DNS_OK:
        return False
    try:
        answers = dns.resolver.resolve(f"_dmarc.{domain}", "TXT", lifetime=5)
        return any("v=DMARC1" in str(r) for r in answers)
    except Exception:
        return False


def _check_dkim(domain: str, selector: str = "") -> bool:
    """Параллельная проверка DKIM-селекторов — все одновременно (~3s max)."""
    if not _DNS_OK:
        return False
    _selectors = [selector] if selector else [
        "google", "mail", "default", "s1", "s2", "k1", "smtp",
        "dkim", "selector1", "selector2", "email", "mxvault",
    ]

    def _probe(sel: str) -> bool:
        try:
            dns.resolver.resolve(f"{sel}._domainkey.{domain}", "TXT", lifetime=3)
            return True
        except Exception:
            return False

    with ThreadPoolExecutor(max_workers=min(len(_selectors), 6)) as executor:
        futures = {executor.submit(_probe, sel): sel for sel in _selectors}
        for fut in as_completed(futures):
            if fut.result():
                for f in futures:
                    f.cancel()
                return True
    return False


def _check_mx(domain: str) -> bool:
    if not _DNS_OK:
        return False
    try:
        dns.resolver.resolve(domain, "MX", lifetime=5)
        return True
    except Exception:
        return False


def _check_dnsbl(host: str) -> bool:
    """Returns True if host is blacklisted in common DNSBLs."""
    DNSBL_ZONES = ["zen.spamhaus.org", "bl.spamcop.net", "dnsbl.sorbs.net"]
    try:
        ip = socket.gethostbyname(host)
        rev = ".".join(reversed(ip.split(".")))
        for zone in DNSBL_ZONES:
            try:
                socket.getaddrinfo(f"{rev}.{zone}", None, socket.AF_INET)
                return True
            except socket.gaierror:
                pass
    except Exception:
        pass
    return False


def _try_smtp_connect(host: str, port: int, use_ssl: bool, use_tls: bool,
                      email: str, password: str, timeout: int) -> None:
    """Попытка SMTP-соединения. Бросает исключение при ошибке."""
    ctx = ssl.create_default_context()
    if use_ssl:
        with smtplib.SMTP_SSL(host, port, timeout=timeout, context=ctx) as smtp:
            smtp.login(email, password)
    else:
        with smtplib.SMTP(host, port, timeout=timeout) as smtp:
            smtp.ehlo()
            if use_tls:
                smtp.starttls(context=ctx)
                smtp.ehlo()
            smtp.login(email, password)


# ── Core validator ───────────────────────────────────────────────────────────
class SmtpValidator:
    """Test SMTP connectivity and DNS health for email accounts."""

    def validate_account(
        self,
        email: str,
        password: str,
        host: str,
        port: int,
        use_ssl: bool,
        use_tls: bool,
        timeout: int = 15,
    ) -> ValidateResult:
        domain = email.split("@")[-1] if "@" in email else email

        spf_ok   = _check_spf(domain)
        dkim_ok  = _check_dkim(domain)
        dmarc_ok = _check_dmarc(domain)

        if _check_dnsbl(host):
            return ValidateResult(email, host, port, False, "BLACKLISTED",
                                  "SMTP host is in a DNSBL blacklist",
                                  spf_ok, dkim_ok, dmarc_ok)

        try:
            _try_smtp_connect(host, port, use_ssl, use_tls, email, password, timeout)
            return ValidateResult(email, host, port, True, "OK",
                                  "Connection successful",
                                  spf_ok, dkim_ok, dmarc_ok)
        except smtplib.SMTPAuthenticationError as e:
            return ValidateResult(email, host, port, False, "AUTH_FAIL", str(e),
                                  spf_ok, dkim_ok, dmarc_ok)
        except ssl.SSLError as e:
            return ValidateResult(email, host, port, False, "SSL_ERROR", str(e),
                                  spf_ok, dkim_ok, dmarc_ok)
        except (socket.timeout, TimeoutError):
            return ValidateResult(email, host, port, False, "TIMEOUT",
                                  f"No response from {host}:{port} in {timeout}s",
                                  spf_ok, dkim_ok, dmarc_ok)
        except Exception as e:
            return ValidateResult(email, host, port, False, "CONN_ERROR", str(e),
                                  spf_ok, dkim_ok, dmarc_ok)

    def validate_with_port_fallback(
        self,
        email: str,
        password: str,
        host: str,
        primary_port: int,
        primary_ssl: bool,
        primary_tls: bool,
        timeout: int = 10,
    ) -> ValidateResult:
        """Пробует основной порт, затем все альтернативы при CONN_ERROR/TIMEOUT.
        AUTH_FAIL на любом порту = неверные данные (стоп).
        Возвращает первый успешный результат или последнюю ошибку.
        """
        configs_to_try = [(primary_port, primary_ssl, primary_tls, "primary")]
        seen_ports = {primary_port}
        for p, ssl_, tls, lbl in PORT_FALLBACK_CONFIGS:
            if p not in seen_ports:
                configs_to_try.append((p, ssl_, tls, lbl))
                seen_ports.add(p)

        domain = email.split("@")[-1] if "@" in email else email
        spf_ok   = _check_spf(domain)
        dkim_ok  = _check_dkim(domain)
        dmarc_ok = _check_dmarc(domain)

        last_result: Optional[ValidateResult] = None
        for port, use_ssl, use_tls, label in configs_to_try:
            try:
                _try_smtp_connect(host, port, use_ssl, use_tls, email, password, timeout)
                return ValidateResult(email, host, port, True, "OK",
                                      f"Connected via {label}",
                                      spf_ok, dkim_ok, dmarc_ok)
            except smtplib.SMTPAuthenticationError as e:
                return ValidateResult(email, host, port, False, "AUTH_FAIL", str(e),
                                      spf_ok, dkim_ok, dmarc_ok)
            except Exception as e:
                last_result = ValidateResult(email, host, port, False, "CONN_ERROR",
                                             f"[{label}] {e}",
                                             spf_ok, dkim_ok, dmarc_ok)
        return last_result or ValidateResult(email, host, 0, False, "CONN_ERROR", "No ports available")

    def validate_all(
        self,
        accounts: list,
        on_result: Callable[[ValidateResult], None],
        on_done: Callable[[List[ValidateResult]], None],
        timeout: int = 15,
        max_workers: int = 10,
        cancel_event: Optional[threading.Event] = None,
        use_port_fallback: bool = True,
    ) -> threading.Thread:
        """Параллельная проверка всех аккаунтов через ThreadPoolExecutor.
        - max_workers: параллельных соединений (по умолч. 10)
        - cancel_event: .set() для прерывания на ходу
        - use_port_fallback: перебор портов при ошибке подключения
        """
        results: List[ValidateResult] = []
        _cancel = cancel_event or threading.Event()

        def _validate_one(acc: dict) -> ValidateResult:
            if _cancel.is_set():
                return ValidateResult(
                    acc.get("email", ""), acc.get("host", ""), acc.get("port", 587),
                    False, "CANCELLED", "Validation cancelled by user"
                )
            if use_port_fallback:
                return self.validate_with_port_fallback(
                    acc.get("email", ""), acc.get("password", ""),
                    acc.get("host", ""), acc.get("port", 587),
                    acc.get("use_ssl", False), acc.get("use_tls", True),
                    timeout=timeout,
                )
            return self.validate_account(
                acc.get("email", ""), acc.get("password", ""),
                acc.get("host", ""), acc.get("port", 587),
                acc.get("use_ssl", False), acc.get("use_tls", True),
                timeout=timeout,
            )

        def _run() -> None:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_map = {executor.submit(_validate_one, acc): acc for acc in accounts}
                for future in as_completed(future_map):
                    if _cancel.is_set():
                        break
                    try:
                        r = future.result()
                    except Exception as e:
                        acc = future_map[future]
                        r = ValidateResult(
                            acc.get("email", ""), acc.get("host", ""), acc.get("port", 587),
                            False, "CONN_ERROR", str(e)
                        )
                    results.append(r)
                    on_result(r)
            on_done(results)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return t
