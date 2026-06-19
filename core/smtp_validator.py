"""
FMailSender SMTP Validator v1.0.0
Full SMTP + DNS + DNSBL connection check for all configured accounts.
"""
from __future__ import annotations

import socket
import smtplib
import ssl
import threading
from dataclasses import dataclass, field
from typing import Callable, List, Optional

try:
    import dns.resolver
    import dns.exception
    _DNS_OK = True
except ImportError:
    _DNS_OK = False


# ── Result ───────────────────────────────────────────────────────────────────
@dataclass
class ValidateResult:
    email: str
    host: str
    port: int
    ok: bool
    code: str          # OK | AUTH_FAIL | SSL_ERROR | TIMEOUT | BLACKLISTED | CONN_ERROR
    message: str = ""
    spf_ok:   Optional[bool] = None
    dkim_ok:  Optional[bool] = None
    dmarc_ok: Optional[bool] = None
    mx_ok:    Optional[bool] = None

    def summary(self) -> str:
        icon = "✅" if self.ok else "❌"
        dns_info = ""
        if self.spf_ok is not None:
            mx_str = f" MX:{'✓' if self.mx_ok else '✗'}" if self.mx_ok is not None else ""
            dns_info = f" | SPF:{'✓' if self.spf_ok else '✗'} DKIM:{'✓' if self.dkim_ok else '✗'} DMARC:{'✓' if self.dmarc_ok else '✗'}{mx_str}"  # FIX M3
        return f"{icon} {self.email} → {self.host}:{self.port} [{self.code}]{dns_info}"


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
    """FIX L1: перебираем популярные DKIM-селекторы (default почти никогда не используется)."""
    if not _DNS_OK:
        return False
    _selectors = [selector] if selector else [
        "google", "mail", "default", "s1", "s2", "k1", "smtp",
        "dkim", "selector1", "selector2", "email", "mxvault",
    ]
    for sel in _selectors:
        try:
            dns.resolver.resolve(f"{sel}._domainkey.{domain}", "TXT", lifetime=3)
            return True
        except Exception:
            continue
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
                return True  # blacklisted
            except socket.gaierror:
                pass
    except Exception:
        pass
    return False


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

        # DNS checks (non-blocking, best-effort)
        spf_ok   = _check_spf(domain)
        dkim_ok  = _check_dkim(domain)
        dmarc_ok = _check_dmarc(domain)

        # DNSBL check on SMTP host
        if _check_dnsbl(host):
            return ValidateResult(email, host, port, False, "BLACKLISTED",
                                  "SMTP host is in a DNSBL blacklist",
                                  spf_ok, dkim_ok, dmarc_ok)

        # TCP + AUTH test
        try:
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

    def validate_all(
        self,
        accounts: list,
        on_result: Callable[[ValidateResult], None],
        on_done: Callable[[List[ValidateResult]], None],
        timeout: int = 15,
    ) -> threading.Thread:
        """Validate all accounts in a daemon thread. Returns thread handle."""
        results: List[ValidateResult] = []

        def _run():
            for acc in accounts:
                r = self.validate_account(
                    acc.get("email", ""), acc.get("password", ""),
                    acc.get("host", ""), acc.get("port", 587),
                    acc.get("use_ssl", False), acc.get("use_tls", True),
                    timeout=timeout,
                )
                results.append(r)
                on_result(r)
            on_done(results)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return t
