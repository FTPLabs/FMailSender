"""
FMailSender SMTP Validator v4.3.1
FIX v3.0.0:
  - Устранён дубль порта 465 в PORT_FALLBACK_CONFIGS + исправлен отступ
  - ОБЯЗАТЕЛЬНЫЙ прокси: если proxy не задан → возврат PROXY_REQUIRED
  - SOCKS5/SOCKS4/HTTP прокси для всех SMTP-соединений (через PySocks)
  - OAuth2/XOAUTH2 для Outlook/Hotmail (Microsoft Modern Auth)
  - MX-autodiscovery: если домен не в конфигах — ищем MX-запись
  - Расширен список портов: 25, 465, 587, 2525, 465(STARTTLS)
  - Параллельная validate_all через ThreadPoolExecutor
  - cancel_event для остановки проверки на полпути
"""
from __future__ import annotations

import base64
import socket
import smtplib
import ssl
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, List, Optional

try:
    import dns.resolver
    import dns.exception
    _DNS_OK = True
except ImportError:
    _DNS_OK = False

try:
    import socks as _socks_lib   # PySocks
    _HAS_SOCKS = True
except ImportError:
    _HAS_SOCKS = False


# ── Microsoft OAuth2 XOAUTH2 helper ──────────────────────────────────────────
def _build_xoauth2_string(user: str, access_token: str) -> str:
    """Build SASL XOAUTH2 string for Outlook/Hotmail OAuth login."""
    raw = f"user={user}\x01auth=Bearer {access_token}\x01\x01"
    return base64.b64encode(raw.encode()).decode()


# ── Microsoft/Outlook domains ─────────────────────────────────────────────────
_MICROSOFT_DOMAINS = frozenset({
    "outlook.com", "outlook.de", "outlook.fr", "outlook.es", "outlook.it",
    "outlook.co.uk", "outlook.jp", "outlook.ru", "outlook.nl", "outlook.be",
    "outlook.at", "outlook.com.br",
    "hotmail.com", "hotmail.co.uk", "hotmail.de", "hotmail.fr", "hotmail.es",
    "hotmail.it", "hotmail.ru", "hotmail.nl", "hotmail.be",
    "live.com", "live.co.uk", "live.de", "live.fr", "live.ru",
    "live.nl", "live.be", "live.se", "live.no", "live.dk",
    "msn.com", "windowslive.com",
})

# ── PORT fallback — УНИКАЛЬНЫЕ конфигурации (без дублей!) ────────────────────
# (port, use_ssl, use_tls, label)
# Все SMTP-конфигурации для полного перебора портов (port, ssl, starttls, label)
PORT_FALLBACK_CONFIGS = [
    (465,  True,  False, "SSL/465"),
    (587,  False, True,  "STARTTLS/587"),
    (25,   False, False, "Plain/25"),
    (2525, False, True,  "STARTTLS/2525"),
    (587,  True,  False, "SSL/587"),
    (465,  False, True,  "STARTTLS/465"),
    (2525, True,  False, "SSL/2525"),
]

# ── SMTP CONFIGS: 300+ доменов ────────────────────────────────────────────────
SMTP_CONFIGS: dict[str, dict] = {
    # Google
    "gmail.com":         {"host": "smtp.gmail.com",           "port": 465, "use_ssl": True,  "use_tls": False},
    "googlemail.com":    {"host": "smtp.gmail.com",           "port": 465, "use_ssl": True,  "use_tls": False},
    # Microsoft (Outlook/Hotmail/Live) — STARTTLS 587 официальный порт
    "outlook.com":       {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.de":        {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.fr":        {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.es":        {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.it":        {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.co.uk":     {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.jp":        {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.ru":        {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.nl":        {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.be":        {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.at":        {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.com.br":    {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.com":       {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.co.uk":     {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.de":        {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.fr":        {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.es":        {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.it":        {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.ru":        {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.nl":        {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.be":        {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.se":        {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.no":        {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.dk":        {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.fi":        {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.com.br":    {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.com.ar":    {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.com.mx":    {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "live.com":          {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "live.co.uk":        {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "live.de":           {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "live.fr":           {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "live.ru":           {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "live.nl":           {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "live.be":           {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "live.se":           {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "live.no":           {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "live.dk":           {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "msn.com":           {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "windowslive.com":   {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    # Yahoo
    "yahoo.com":         {"host": "smtp.mail.yahoo.com",      "port": 465, "use_ssl": True,  "use_tls": False},
    "yahoo.co.uk":       {"host": "smtp.mail.yahoo.com",      "port": 465, "use_ssl": True,  "use_tls": False},
    "yahoo.de":          {"host": "smtp.mail.yahoo.com",      "port": 465, "use_ssl": True,  "use_tls": False},
    "yahoo.fr":          {"host": "smtp.mail.yahoo.com",      "port": 465, "use_ssl": True,  "use_tls": False},
    "yahoo.es":          {"host": "smtp.mail.yahoo.com",      "port": 465, "use_ssl": True,  "use_tls": False},
    "yahoo.it":          {"host": "smtp.mail.yahoo.com",      "port": 465, "use_ssl": True,  "use_tls": False},
    "yahoo.co.jp":       {"host": "smtp.mail.yahoo.com",      "port": 465, "use_ssl": True,  "use_tls": False},
    "yahoo.ru":          {"host": "smtp.mail.yahoo.com",      "port": 465, "use_ssl": True,  "use_tls": False},
    "yahoo.com.br":      {"host": "smtp.mail.yahoo.com",      "port": 465, "use_ssl": True,  "use_tls": False},
    "yahoo.com.ar":      {"host": "smtp.mail.yahoo.com",      "port": 465, "use_ssl": True,  "use_tls": False},
    "yahoo.com.mx":      {"host": "smtp.mail.yahoo.com",      "port": 465, "use_ssl": True,  "use_tls": False},
    "yahoo.com.au":      {"host": "smtp.mail.yahoo.com",      "port": 465, "use_ssl": True,  "use_tls": False},
    "ymail.com":         {"host": "smtp.mail.yahoo.com",      "port": 465, "use_ssl": True,  "use_tls": False},
    "rocketmail.com":    {"host": "smtp.mail.yahoo.com",      "port": 465, "use_ssl": True,  "use_tls": False},
    # iCloud
    "icloud.com":        {"host": "smtp.mail.me.com",         "port": 587, "use_ssl": False, "use_tls": True},
    "me.com":            {"host": "smtp.mail.me.com",         "port": 587, "use_ssl": False, "use_tls": True},
    "mac.com":           {"host": "smtp.mail.me.com",         "port": 587, "use_ssl": False, "use_tls": True},
    # AOL
    "aol.com":           {"host": "smtp.aol.com",             "port": 465, "use_ssl": True,  "use_tls": False},
    "aim.com":           {"host": "smtp.aol.com",             "port": 465, "use_ssl": True,  "use_tls": False},
    "netscape.net":      {"host": "smtp.aol.com",             "port": 465, "use_ssl": True,  "use_tls": False},
    "compuserve.com":    {"host": "smtp.aol.com",             "port": 465, "use_ssl": True,  "use_tls": False},
    # GMX — STARTTLS 587 (официально рекомендован) + fallback SSL 465
    "gmx.com":           {"host": "smtp.gmx.com",             "port": 587, "use_ssl": False, "use_tls": True, "fallback_port": 465},
    "gmx.net":           {"host": "mail.gmx.net",             "port": 587, "use_ssl": False, "use_tls": True, "fallback_port": 465},
    "gmx.de":            {"host": "mail.gmx.net",             "port": 587, "use_ssl": False, "use_tls": True, "fallback_port": 465},
    "gmx.at":            {"host": "mail.gmx.net",             "port": 587, "use_ssl": False, "use_tls": True, "fallback_port": 465},
    "gmx.ch":            {"host": "mail.gmx.net",             "port": 587, "use_ssl": False, "use_tls": True, "fallback_port": 465},
    "gmx.co.uk":         {"host": "mail.gmx.net",             "port": 587, "use_ssl": False, "use_tls": True, "fallback_port": 465},
    "gmx.fr":            {"host": "mail.gmx.net",             "port": 587, "use_ssl": False, "use_tls": True, "fallback_port": 465},
    "gmx.es":            {"host": "mail.gmx.net",             "port": 587, "use_ssl": False, "use_tls": True, "fallback_port": 465},
    "gmx.us":            {"host": "smtp.gmx.com",             "port": 587, "use_ssl": False, "use_tls": True, "fallback_port": 465},
    # Web.de — STARTTLS 587 (проверено) + fallback SSL 465
    "web.de":            {"host": "smtp.web.de",              "port": 587, "use_ssl": False, "use_tls": True, "fallback_port": 465},
    # Freenet.de
    "freenet.de":        {"host": "mx.freenet.de",            "port": 587, "use_ssl": False, "use_tls": True, "fallback_port": 465},
    # T-Online / Deutsche Telekom
    "t-online.de":       {"host": "securesmtp.t-online.de",   "port": 465, "use_ssl": True,  "use_tls": False},
    "telekom.de":        {"host": "securesmtp.t-online.de",   "port": 465, "use_ssl": True,  "use_tls": False},
    "arcor.de":          {"host": "smtp.arcor.de",            "port": 465, "use_ssl": True,  "use_tls": False},
    "kabelbw.de":        {"host": "smtp.kabelbw.de",          "port": 587, "use_ssl": False, "use_tls": True},
    "vodafone.de":       {"host": "smtp.vodafone.de",         "port": 465, "use_ssl": True,  "use_tls": False},
    "mailbox.org":       {"host": "smtp.mailbox.org",         "port": 465, "use_ssl": True,  "use_tls": False},
    "posteo.de":         {"host": "posteo.de",                "port": 587, "use_ssl": False, "use_tls": True},
    "posteo.net":        {"host": "posteo.de",                "port": 587, "use_ssl": False, "use_tls": True},
    "strato.de":         {"host": "smtp.strato.de",           "port": 465, "use_ssl": True,  "use_tls": False},
    "strato.com":        {"host": "smtp.strato.de",           "port": 465, "use_ssl": True,  "use_tls": False},
    "ionos.de":          {"host": "smtp.ionos.de",            "port": 465, "use_ssl": True,  "use_tls": False},
    "ionos.com":         {"host": "smtp.ionos.com",           "port": 465, "use_ssl": True,  "use_tls": False},
    "1und1.de":          {"host": "smtp.1and1.com",           "port": 587, "use_ssl": False, "use_tls": True},
    "1and1.com":         {"host": "smtp.1and1.com",           "port": 587, "use_ssl": False, "use_tls": True},
    # France
    "orange.fr":         {"host": "smtp.orange.fr",           "port": 465, "use_ssl": True,  "use_tls": False},
    "wanadoo.fr":        {"host": "smtp.orange.fr",           "port": 465, "use_ssl": True,  "use_tls": False},
    "free.fr":           {"host": "smtp.free.fr",             "port": 465, "use_ssl": True,  "use_tls": False},
    "sfr.fr":            {"host": "smtp.sfr.fr",              "port": 465, "use_ssl": True,  "use_tls": False},
    "laposte.net":       {"host": "smtp.laposte.net",         "port": 465, "use_ssl": True,  "use_tls": False},
    "bbox.fr":           {"host": "smtp.bbox.fr",             "port": 465, "use_ssl": True,  "use_tls": False},
    "numericable.fr":    {"host": "smtp.sfr.fr",              "port": 465, "use_ssl": True,  "use_tls": False},
    # UK
    "btinternet.com":    {"host": "smtp.btinternet.com",      "port": 465, "use_ssl": True,  "use_tls": False},
    "btopenworld.com":   {"host": "smtp.btinternet.com",      "port": 465, "use_ssl": True,  "use_tls": False},
    "sky.com":           {"host": "smtp.office365.com",       "port": 587, "use_ssl": False, "use_tls": True},
    "virginmedia.com":   {"host": "smtp.virginmedia.com",     "port": 465, "use_ssl": True,  "use_tls": False},
    "ntlworld.com":      {"host": "smtp.ntlworld.com",        "port": 465, "use_ssl": True,  "use_tls": False},
    "talktalk.net":      {"host": "smtp.talktalk.net",        "port": 587, "use_ssl": False, "use_tls": True},
    "plusnet.com":       {"host": "relay.plus.net",           "port": 587, "use_ssl": False, "use_tls": True},
    # Russia
    "mail.ru":           {"host": "smtp.mail.ru",             "port": 465, "use_ssl": True,  "use_tls": False},
    "inbox.ru":          {"host": "smtp.mail.ru",             "port": 465, "use_ssl": True,  "use_tls": False},
    "list.ru":           {"host": "smtp.mail.ru",             "port": 465, "use_ssl": True,  "use_tls": False},
    "bk.ru":             {"host": "smtp.mail.ru",             "port": 465, "use_ssl": True,  "use_tls": False},
    "internet.ru":       {"host": "smtp.mail.ru",             "port": 465, "use_ssl": True,  "use_tls": False},
    "ro.ru":             {"host": "smtp.mail.ru",             "port": 465, "use_ssl": True,  "use_tls": False},
    "yandex.ru":         {"host": "smtp.yandex.ru",           "port": 465, "use_ssl": True,  "use_tls": False},
    "yandex.com":        {"host": "smtp.yandex.com",          "port": 465, "use_ssl": True,  "use_tls": False},
    "ya.ru":             {"host": "smtp.yandex.ru",           "port": 465, "use_ssl": True,  "use_tls": False},
    "yandex.ua":         {"host": "smtp.yandex.ru",          "port": 465, "use_ssl": True,  "use_tls": False},
    "yandex.by":         {"host": "smtp.yandex.by",           "port": 465, "use_ssl": True,  "use_tls": False},
    "yandex.kz":         {"host": "smtp.yandex.kz",           "port": 465, "use_ssl": True,  "use_tls": False},
    "rambler.ru":        {"host": "smtp.rambler.ru",          "port": 465, "use_ssl": True,  "use_tls": False},
    "lenta.ru":          {"host": "smtp.rambler.ru",          "port": 465, "use_ssl": True,  "use_tls": False},
    "autorambler.ru":    {"host": "smtp.rambler.ru",          "port": 465, "use_ssl": True,  "use_tls": False},
    "myrambler.ru":      {"host": "smtp.rambler.ru",          "port": 465, "use_ssl": True,  "use_tls": False},
    # Ukraine
    "i.ua":              {"host": "smtp.i.ua",                "port": 465, "use_ssl": True,  "use_tls": False},
    "ukr.net":           {"host": "smtp.ukr.net",             "port": 465, "use_ssl": True,  "use_tls": False},
    "meta.ua":           {"host": "smtp.meta.ua",             "port": 465, "use_ssl": True,  "use_tls": False},
    "mail.ua":           {"host": "smtp.ukr.net",             "port": 465, "use_ssl": True,  "use_tls": False},
    # Baltics
    "inbox.lv":          {"host": "smtp.inbox.lv",            "port": 465, "use_ssl": True,  "use_tls": False},
    "mail.lt":           {"host": "smtp.domreg.lt",           "port": 465, "use_ssl": True,  "use_tls": False},
    # Zoho
    "zoho.com":          {"host": "smtp.zoho.com",            "port": 465, "use_ssl": True,  "use_tls": False},
    "zohomail.com":      {"host": "smtp.zoho.com",            "port": 465, "use_ssl": True,  "use_tls": False},
    "zoho.eu":           {"host": "smtp.zoho.eu",             "port": 465, "use_ssl": True,  "use_tls": False},
    "zohomail.eu":       {"host": "smtp.zoho.eu",             "port": 465, "use_ssl": True,  "use_tls": False},
    # Proton
    "protonmail.com":    {"host": "127.0.0.1",                "port": 1025, "use_ssl": False, "use_tls": False},
    "proton.me":         {"host": "127.0.0.1",                "port": 1025, "use_ssl": False, "use_tls": False},
    "protonmail.ch":     {"host": "127.0.0.1",                "port": 1025, "use_ssl": False, "use_tls": False},
    "pm.me":             {"host": "127.0.0.1",                "port": 1025, "use_ssl": False, "use_tls": False},
    # AT&T
    "att.net":           {"host": "smtp.att.yahoo.com",       "port": 465, "use_ssl": True,  "use_tls": False},
    "sbcglobal.net":     {"host": "smtp.att.yahoo.com",       "port": 465, "use_ssl": True,  "use_tls": False},
    "bellsouth.net":     {"host": "smtp.att.yahoo.com",       "port": 465, "use_ssl": True,  "use_tls": False},
    "ameritech.net":     {"host": "smtp.att.yahoo.com",       "port": 465, "use_ssl": True,  "use_tls": False},
    "verizon.net":       {"host": "smtp.aol.com",             "port": 465, "use_ssl": True,  "use_tls": False},
    # Eastern Europe / Poland
    "wp.pl":             {"host": "smtp.wp.pl",               "port": 465, "use_ssl": True,  "use_tls": False},
    "o2.pl":             {"host": "poczta.o2.pl",             "port": 465, "use_ssl": True,  "use_tls": False},
    "interia.pl":        {"host": "poczta.interia.pl",        "port": 587, "use_ssl": False, "use_tls": True},
    "2gb.pl":            {"host": "poczta.interia.pl",        "port": 587, "use_ssl": False, "use_tls": True},
    "intmail.pl":        {"host": "poczta.interia.pl",        "port": 587, "use_ssl": False, "use_tls": True},
    "adresik.net":       {"host": "poczta.interia.pl",        "port": 587, "use_ssl": False, "use_tls": True},
    "onet.pl":           {"host": "smtp.poczta.onet.pl",      "port": 465, "use_ssl": True,  "use_tls": False},
    "onet.eu":           {"host": "smtp.poczta.onet.pl",      "port": 465, "use_ssl": True,  "use_tls": False},
    "tlen.pl":           {"host": "smtp.tlen.pl",             "port": 465, "use_ssl": True,  "use_tls": False},
    "cs.com":            {"host": "smtp.cs.com",              "port": 587, "use_ssl": False, "use_tls": True},
}


# ── Proxy helpers ─────────────────────────────────────────────────────────────
# Порты, характерные для HTTP-прокси (автоопределение при отсутствии схемы)
_HTTP_PROXY_PORTS = frozenset({80, 8080, 8088, 8118, 3128, 3129, 8443, 8888, 8889, 9999})


def _detect_proxy_scheme_by_port(port: int) -> str:
    """HTTP-характерные порты → 'http'; остальные → 'socks5'."""
    return "http" if port in _HTTP_PROXY_PORTS else "socks5"


def _parse_proxy(proxy_url: str) -> tuple[str, int, str, str | None, str | None]:
    """Parse proxy URL → (scheme, host, port, user, pass).
    Supported: socks5://user:pass@host:port  socks4://  http://  https://
    Без схемы — тип определяется по порту:
      80/8080/3128/8888/8118/... → http; иначе → socks5.
    """
    raw = proxy_url.strip()
    if "://" not in raw:
        try:
            hostport = raw.rsplit("@", 1)[1] if "@" in raw else raw
            detected_port = int(hostport.rsplit(":", 1)[1])
            scheme_guess = _detect_proxy_scheme_by_port(detected_port)
        except (ValueError, IndexError):
            scheme_guess = "socks5"
        raw = f"{scheme_guess}://{raw}"
    p = urllib.parse.urlparse(raw)
    scheme = p.scheme.lower()
    host = p.hostname or ""
    port = p.port or (1080 if "socks" in scheme else 8080)
    user = p.username
    pwd = p.password
    return scheme, host, port, user, pwd


def _make_proxy_socket(proxy_url: str, target_host: str, target_port: int,
                       timeout: int = 30) -> socket.socket:
    """Create a TCP socket connected through the proxy."""
    if not _HAS_SOCKS:
        raise RuntimeError(
            "PySocks не установлен — прокси невозможен. Установите: pip install PySocks"
        )
    scheme, ph, pp, pu, ppwd = _parse_proxy(proxy_url)
    proxy_type = _socks_lib.SOCKS5 if "socks5" in scheme else (
        _socks_lib.SOCKS4 if "socks4" in scheme else _socks_lib.HTTP
    )
    s = _socks_lib.socksocket()
    s.set_proxy(proxy_type, ph, pp, True, pu, ppwd)
    s.settimeout(timeout)
    s.connect((target_host, target_port))
    return s


# ── MX-autodiscovery ──────────────────────────────────────────────────────────
def _autodiscover_smtp(domain: str) -> dict | None:
    """Try to find SMTP server via MX record for unknown domains."""
    if not _DNS_OK:
        return None
    try:
        mx_records = dns.resolver.resolve(domain, "MX", lifetime=5)
        mx_host = str(sorted(mx_records, key=lambda r: r.preference)[0].exchange).rstrip(".")
        # Try to infer SMTP host from MX
        if mx_host.startswith("mx"):
            smtp_host = mx_host.replace("mx.", "smtp.", 1).replace("mx1.", "smtp.").replace("mx2.", "smtp.")
        else:
            smtp_host = f"smtp.{domain}"
        return {"host": smtp_host, "port": 587, "use_ssl": False, "use_tls": True}
    except Exception:
        return {"host": f"smtp.{domain}", "port": 587, "use_ssl": False, "use_tls": True}


def get_smtp_config(domain: str) -> dict:
    """Return SMTP config for domain, with MX-autodiscovery fallback."""
    domain = domain.lower().strip()
    if domain in SMTP_CONFIGS:
        return dict(SMTP_CONFIGS[domain])
    # Pattern matching for subdomains
    for key, cfg in SMTP_CONFIGS.items():
        if domain.endswith("." + key) or domain == key:
            return dict(cfg)
    # MX autodiscovery
    discovered = _autodiscover_smtp(domain)
    if discovered:
        return discovered
    return {"host": f"smtp.{domain}", "port": 587, "use_ssl": False, "use_tls": True}


# ── Result ────────────────────────────────────────────────────────────────────
@dataclass
class ValidateResult:
    email: str
    host: str
    port: int
    ok: bool
    code: str  # OK | AUTH_FAIL | SSL_ERROR | TIMEOUT | BLACKLISTED | CONN_ERROR | CANCELLED | PROXY_REQUIRED | PROXY_ERROR | PROXY_BLOCKED_SMTP
    message: str = ""
    spf_ok:   Optional[bool] = None
    dkim_ok:  Optional[bool] = None
    dmarc_ok: Optional[bool] = None
    mx_ok:    Optional[bool] = None

    def summary(self) -> str:
        tick  = "\u2713"
        cross = "\u2717"
        icon  = "\u2705" if self.ok else "\u274c"
        dns_info = ""
        if self.spf_ok is not None:
            mx_val = (tick if self.mx_ok else cross) if self.mx_ok is not None else ""
            mx_str = (" MX:" + mx_val) if mx_val else ""
            spf_v   = tick if self.spf_ok  else cross
            dkim_v  = tick if self.dkim_ok else cross
            dmarc_v = tick if self.dmarc_ok else cross
            dns_info = " | SPF:" + spf_v + " DKIM:" + dkim_v + " DMARC:" + dmarc_v + mx_str
        return icon + " " + self.email + " -> " + self.host + ":" + str(self.port) + " [" + self.code + "]" + dns_info


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
    except Exception as _smtp_e:
        import logging as _log; _log.getLogger("smtp_validator").warning("dnsbl_check: неожиданная ошибка: %s", _smtp_e)
    return False


# ── Core SMTP connect (proxy-aware) ───────────────────────────────────────────
def _try_smtp_connect(
      host: str,
      port: int,
      use_ssl: bool,
      use_tls: bool,
      email: str,
      password: str,
      timeout: int,
      proxy_url: str = "",
      oauth_token: str = "",
  ) -> None:
      """Attempt SMTP connection. If proxy_url is set, connects through proxy socket.
      Raises exception on failure.
      FIX v4.3.0: replaced broken __new__ hack with proper _get_socket subclass override.
      Works correctly with Python 3.11/3.12/3.13+.
      oauth_token: если задан — использует XOAUTH2 вместо LOGIN (Outlook/Hotmail).
      """
      ctx = ssl.create_default_context()
      domain = email.split("@")[-1] if "@" in email else ""

      def _auth(smtp: smtplib.SMTP) -> None:
          if oauth_token and domain in _MICROSOFT_DOMAINS:
              xoauth2 = _build_xoauth2_string(email, oauth_token)
              smtp.docmd("AUTH", "XOAUTH2 " + xoauth2)
          else:
              smtp.login(email, password)

      if proxy_url:
          # Parse proxy once
          scheme, ph, pp, pu, ppwd = _parse_proxy(proxy_url)
          proxy_type = _socks_lib.SOCKS5 if "socks5" in scheme else (
              _socks_lib.SOCKS4 if "socks4" in scheme else _socks_lib.HTTP
          )

          # Pre-check: verify proxy allows SMTP connections (quick TCP test, no auth)
          # SOCKS5 error code 1 = General Failure = proxy blocks this destination/port
          try:
              import socks as _socks_check
              _probe = _socks_check.socksocket()
              _probe.set_proxy(proxy_type, ph, pp, True, pu, ppwd)
              _probe.settimeout(min(timeout, 8))
              _probe.connect((host, port))
              _probe.close()
          except Exception as _pe:
              _pe_msg = str(_pe).lower()
              # ТОЛЬКО явный SOCKS5 General Failure (код 1) → прокси блокирует SMTP.
              # Таймауты, connection refused, host unreachable — НЕ являются признаком
              # блокировки SMTP прокси. Это медленный/недоступный прокси или хост.
              # Не классифицируем их как PROXY_BLOCKS_SMTP — иначе будет ложный
              # fallback на direct, который тоже упадёт → «Не удалось подключиться».
              _SOCKS5_BLOCK_SIGNALS = ("general failure", "socks5 error", "not allowed by ruleset")
              if any(x in _pe_msg for x in _SOCKS5_BLOCK_SIGNALS):
                  raise ConnectionError(f"PROXY_BLOCKS_SMTP:{host}:{port}:{_pe_msg[:80]}")
              # Остальные ошибки pre-check: игнорируем, основное подключение продолжается.

          # Use subclass override of _get_socket — works with Python 3.9–3.13+
          # This avoids the broken __new__ hack that fails on Python 3.11+ due to
          # missing internal attributes (_tls_required, etc.) added in newer versions.
          class _ProxySMTP(smtplib.SMTP):
              def _get_socket(self, _h, _p, _t):  # type: ignore[override]
                  s = _socks_lib.socksocket()
                  s.set_proxy(proxy_type, ph, pp, True, pu, ppwd)
                  s.settimeout(_t)
                  s.connect((_h, _p))
                  return s

          class _ProxySMTP_SSL(smtplib.SMTP_SSL):
              def _get_socket(self, _h, _p, _t):  # type: ignore[override]
                  s = _socks_lib.socksocket()
                  s.set_proxy(proxy_type, ph, pp, True, pu, ppwd)
                  s.settimeout(_t)
                  s.connect((_h, _p))
                  return self.context.wrap_socket(s, server_hostname=_h)

          if use_ssl:
              with _ProxySMTP_SSL(host, port, timeout=timeout, context=ctx) as smtp:
                  _auth(smtp)
          else:
              with _ProxySMTP(host, port, timeout=timeout) as smtp:
                  smtp.ehlo()
                  if use_tls:
                      smtp.starttls(context=ctx)
                      smtp.ehlo()
                  _auth(smtp)
      else:
          # Direct connection (no proxy)
          if use_ssl:
              with smtplib.SMTP_SSL(host, port, timeout=timeout, context=ctx) as smtp:
                  _auth(smtp)
          else:
              with smtplib.SMTP(host, port, timeout=timeout) as smtp:
                  smtp.ehlo()
                  if use_tls:
                      smtp.starttls(context=ctx)
                      smtp.ehlo()
                  _auth(smtp)
def _get_mx_host(domain: str) -> str:
    """Возвращает первый MX-хост для домена или пустую строку если DNS недоступен."""
    if not _DNS_OK:
        return ""
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=5)
        mx = sorted(answers, key=lambda r: r.preference)[0]
        return str(mx.exchange).rstrip(".")
    except Exception:
        return ""


# ── Core validator ─────────────────────────────────────────────────────────────
class SmtpValidator:
    """Test SMTP connectivity (via proxy) and DNS health for email accounts."""

    def validate_account(
        self,
        email: str,
        password: str,
        host: str,
        port: int,
        use_ssl: bool,
        use_tls: bool,
        timeout: int = 20,
        proxy_url: str = "",
        require_proxy: bool = True,
        oauth_token: str = "",
    ) -> ValidateResult:
        """
        require_proxy=True: если proxy_url пустой — немедленно возвращает PROXY_REQUIRED.
        oauth_token: OAuth2 Bearer token для XOAUTH2 (Outlook/Hotmail).
        """
        domain = email.split("@")[-1] if "@" in email else email

        # ── Proxy enforcement ─────────────────────────────────────────────────
        if require_proxy and not proxy_url.strip():
            return ValidateResult(
                email, host, port, False, "PROXY_REQUIRED",
                "Прокси обязателен. Добавьте прокси к аккаунту перед тестированием."
            )

        if proxy_url and not _HAS_SOCKS:
            return ValidateResult(
                email, host, port, False, "PROXY_ERROR",
                "PySocks не установлен. Выполните: pip install PySocks"
            )

        spf_ok   = _check_spf(domain)
        dkim_ok  = _check_dkim(domain)
        dmarc_ok = _check_dmarc(domain)
        mx_ok    = _check_mx(domain)

        if _check_dnsbl(host):
            return ValidateResult(email, host, port, False, "BLACKLISTED",
                                  "SMTP-хост находится в DNSBL-чёрном списке",
                                  spf_ok, dkim_ok, dmarc_ok, mx_ok)

        # ── Основная попытка ─────────────────────────────────────────────────
        try:
            _try_smtp_connect(host, port, use_ssl, use_tls, email, password,
                              timeout, proxy_url, oauth_token)
            return ValidateResult(email, host, port, True, "OK",
                                  "Подключение успешно",
                                  spf_ok, dkim_ok, dmarc_ok, mx_ok)
        except ConnectionError as _ce:
            _ce_msg = str(_ce)
            if "PROXY_BLOCKS_SMTP" in _ce_msg:
                # Proxy blocks SMTP — автоматический fallback на прямое подключение
                for _fp, _fs, _ft in [(port, use_ssl, use_tls), (465, True, False), (587, False, True)]:
                    try:
                        _try_smtp_connect(host, _fp, _fs, _ft, email, password, timeout, "", oauth_token)
                        return ValidateResult(email, host, _fp, True, "OK",
                                              f"Подключено напрямую порт {_fp} (прокси блокирует SMTP)",
                                              spf_ok, dkim_ok, dmarc_ok, mx_ok)
                    except smtplib.SMTPAuthenticationError as _dae:
                        _das = str(_dae)
                        if "535" in _das:
                            _dd = "Неверный пароль или SMTP отключён в настройках аккаунта"
                        elif "534" in _das:
                            _dd = "Требуется App Password (включена 2FA)"
                        else:
                            _dd = f"AUTH: {_das[:80]}"
                        return ValidateResult(email, host, _fp, False, "AUTH_FAIL",
                                              _dd, spf_ok, dkim_ok, dmarc_ok, mx_ok)
                    except Exception:
                        continue
                return ValidateResult(
                    email, host, port, False, "PROXY_BLOCKED_SMTP",
                    "Прокси блокирует SMTP, прямое подключение тоже недоступно. "
                    "Проверьте пароль и SMTP-доступ в настройках почты.",
                    spf_ok, dkim_ok, dmarc_ok, mx_ok)
        except smtplib.SMTPAuthenticationError as e:
            err_str = str(e)
            if "535" in err_str:
                detail = "Неверный пароль или отключена SMTP-авторизация в настройках почты"
            elif "534" in err_str:
                detail = "Требуется App Password (включена двухфакторная аутентификация)"
            elif "username" in err_str.lower() or "user" in err_str.lower():
                detail = "Пользователь не найден или неверный формат email"
            elif "oauth" in err_str.lower() or "xoauth" in err_str.lower():
                detail = "Ошибка OAuth2 — используйте App Password вместо основного пароля"
            else:
                detail = f"Ошибка авторизации [{err_str[:120]}]"
            return ValidateResult(email, host, port, False, "AUTH_FAIL",
                                  detail, spf_ok, dkim_ok, dmarc_ok, mx_ok)
        except ssl.SSLError as e:
            import logging as _lg
            _lg.getLogger("smtp_validator").warning("SSL error %s:%s — %s", host, port, str(e)[:60])
            pass  # Try fallback below
        except socket.timeout:
            import logging as _lg
            _lg.getLogger("smtp_validator").warning("Timeout %s:%s", host, port)
            pass  # Try fallback below
        except ConnectionRefusedError:
            import logging as _lg
            _lg.getLogger("smtp_validator").warning("Refused %s:%s", host, port)
            pass  # Try fallback below
        except OSError as e:
            _oe = str(e)
            if any(x in _oe for x in ("11001", "getaddrinfo", "Name or service", "nodename")):
                return ValidateResult(email, host, port, False, "DNS_ERROR",
                                      f"Не удалось разрешить хост {host} — проверьте SMTP-сервер",
                                      spf_ok, dkim_ok, dmarc_ok, mx_ok)
            pass  # Try fallback below
        except Exception as e:
            err = str(e)[:200]
            if "auth" in err.lower() or "535" in err or "534" in err:
                return ValidateResult(email, host, port, False, "AUTH_FAIL",
                                      err, spf_ok, dkim_ok, dmarc_ok, mx_ok)
            pass  # Try fallback below


        # ── Port fallback ─────────────────────────────────────────────────────
        cfg = get_smtp_config(domain)
        fallback_port = cfg.get("fallback_port")
        fb_tries = []
        if fallback_port and fallback_port != port:
            fb_tries.append((fallback_port, not use_ssl, use_ssl))
        for fb_port, fb_ssl, fb_tls, _label in PORT_FALLBACK_CONFIGS:
            if fb_port != port:
                fb_tries.append((fb_port, fb_ssl, fb_tls))

        for fb_port, fb_ssl, fb_tls in fb_tries:  # перебираем ВСЕ fallback-порты
            try:
                _try_smtp_connect(host, fb_port, fb_ssl, fb_tls, email, password,
                                  timeout, proxy_url, oauth_token)
                return ValidateResult(email, host, fb_port, True, "OK",
                                      f"Подключено через запасной порт {fb_port}",
                                      spf_ok, dkim_ok, dmarc_ok, mx_ok)
            except smtplib.SMTPAuthenticationError as e:
                return ValidateResult(email, host, fb_port, False, "AUTH_FAIL",
                                      str(e)[:200], spf_ok, dkim_ok, dmarc_ok, mx_ok)
            except Exception:
                continue

        # MX autodiscovery: если все порты не сработали — пробуем MX-запись домена
        mx_host = _get_mx_host(domain)
        if mx_host and mx_host.lower() != host.lower():
            for _mx_port, _mx_ssl, _mx_tls in [(465, True, False), (587, False, True)]:
                try:
                    _try_smtp_connect(mx_host, _mx_port, _mx_ssl, _mx_tls,
                                      email, password, timeout, proxy_url, oauth_token)
                    return ValidateResult(email, mx_host, _mx_port, True, "OK",
                                          f"Подключено через MX: {mx_host}:{_mx_port}",
                                          spf_ok, dkim_ok, dmarc_ok, mx_ok)
                except smtplib.SMTPAuthenticationError as _e:
                    _es = str(_e)
                    return ValidateResult(email, mx_host, _mx_port, False, "AUTH_FAIL",
                                          "Неверный пароль" if "535" in _es else f"AUTH: {_es[:80]}",
                                          spf_ok, dkim_ok, dmarc_ok, mx_ok)
                except Exception:
                    continue
        # ── Прямое соединение: fallback если прокси не помог ────────────────
        if proxy_url:
            for _dp, _ds, _dt in [(port, use_ssl, use_tls), (465, True, False), (587, False, True)]:
                try:
                    _try_smtp_connect(host, _dp, _ds, _dt, email, password, timeout, "", oauth_token)
                    return ValidateResult(email, host, _dp, True, "OK",
                                          f"Подключено напрямую порт {_dp} (прокси не работает с SMTP)",
                                          spf_ok, dkim_ok, dmarc_ok, mx_ok)
                except smtplib.SMTPAuthenticationError as _dae2:
                    _das2 = str(_dae2)
                    if "535" in _das2:
                        _dd2 = "Неверный пароль или SMTP отключён в настройках аккаунта"
                    elif "534" in _das2:
                        _dd2 = "Требуется App Password (включена 2FA)"
                    else:
                        _dd2 = f"AUTH: {_das2[:80]}"
                    return ValidateResult(email, host, _dp, False, "AUTH_FAIL",
                                          _dd2, spf_ok, dkim_ok, dmarc_ok, mx_ok)
                except Exception:
                    continue

        return ValidateResult(email, host, port, False, "CONN_ERROR",
                                f"Не удалось подключиться к {host} ни через один порт (465/587/25/2525). "
                                f"Проверьте: 1) SMTP включён в настройках; "
                                f"2) Используйте App Password; 3) Прокси не блокирует порт; "
                                f"4) Хост {host} корректен.",
                                spf_ok, dkim_ok, dmarc_ok, mx_ok)

    def validate_all(
        self,
        accounts: list,
        max_workers: int = 8,
        progress_cb: Optional[Callable[[int, int, ValidateResult], None]] = None,
        cancel_event: Optional[threading.Event] = None,
        require_proxy: bool = True,
    ) -> List[ValidateResult]:
        """Validate list of SmtpAccount objects in parallel."""
        results: List[ValidateResult] = [None] * len(accounts)  # type: ignore
        done = 0
        total = len(accounts)

        def _task(i: int, acc) -> tuple[int, ValidateResult]:
            if cancel_event and cancel_event.is_set():
                return i, ValidateResult(acc.email, acc.host, acc.port, False, "CANCELLED")
            r = self.validate_account(
                email=acc.email,
                password=acc.password,
                host=acc.host,
                port=acc.port,
                use_ssl=acc.use_ssl,
                use_tls=acc.use_tls,
                proxy_url=getattr(acc, "proxy", ""),
                require_proxy=require_proxy,
                oauth_token=getattr(acc, "oauth_token", ""),
            )
            return i, r

        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(_task, i, acc): i for i, acc in enumerate(accounts)}
            for fut in as_completed(futures):
                i, r = fut.result()
                results[i] = r
                done += 1
                if progress_cb:
                    try:
                        progress_cb(done, total, r)
                    except Exception as _cb_e:
                        import logging as _log; _log.getLogger("smtp_validator").debug("progress_cb exception (ignored): %s", _cb_e)
                if cancel_event and cancel_event.is_set():
                    break

        return [r for r in results if r is not None]

    def validate_with_port_fallback(
        self,
        email: str,
        password: str,
        host: str,
        proxy_url: str = "",
        timeout: int = 20,
        require_proxy: bool = True,
        oauth_token: str = "",
    ) -> ValidateResult:
        """Try all port/SSL combinations until one works. For unknown domains."""
        if require_proxy and not proxy_url.strip():
            return ValidateResult(email, host, 0, False, "PROXY_REQUIRED",
                                  "Прокси обязателен.")
        for port, use_ssl, use_tls, label in PORT_FALLBACK_CONFIGS:
            try:
                _try_smtp_connect(host, port, use_ssl, use_tls, email, password,
                                  timeout, proxy_url, oauth_token)
                return ValidateResult(email, host, port, True, "OK",
                                      f"Подключено через {label}")
            except smtplib.SMTPAuthenticationError as e:
                return ValidateResult(email, host, port, False, "AUTH_FAIL", str(e)[:200])
            except Exception:
                continue
        return ValidateResult(email, host, 0, False, "CONN_ERROR",
                              "Не удалось подключиться ни через один порт/протокол")
