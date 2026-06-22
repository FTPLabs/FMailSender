"""
FMailSender core sending engine v2.9.4.
Fixes: IndentationError in increment_sent/try_increment/Recipient,
       async parallelism (delay moved inside task wrapper),
       duplicate params documented, race condition eliminated via try_increment.
v2.9.4: добавлено логирование во все silent except-блоки.
"""
from __future__ import annotations

import asyncio
import logging
import base64
import mimetypes
import urllib.parse
import queue
import random
import re
import smtplib
import threading
import time
import socket
import uuid
from dataclasses import dataclass, field
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Callable, List, Optional

try:
    import dns.resolver as _dns_resolver
    _DNS_OK = True
except ImportError:
    _DNS_OK = False

try:
    import aiosmtplib
    _HAS_AIOSMTPLIB = True
except ImportError:
    _HAS_AIOSMTPLIB = False

try:
    from core.oauth2_refresh import (
        get_valid_access_token as _get_oauth_token,
        is_ms_domain as _is_ms_domain,
        build_xoauth2 as _build_xoauth2,
    )
    _HAS_OAUTH2 = True
except ImportError:
    _HAS_OAUTH2 = False
    def _get_oauth_token(account) -> str:
        return getattr(account, "oauth_token", "") or ""
    def _is_ms_domain(email: str) -> bool:
        return email.split("@")[-1].lower() in {
            "outlook.com","hotmail.com","live.com","msn.com","windowslive.com",
            "outlook.de","hotmail.de","live.de","outlook.fr","hotmail.fr",
        }
    def _build_xoauth2(email: str, access_token: str) -> str:
        import base64 as _b64
        raw = f"user={email}\x01auth=Bearer {access_token}\x01\x01"
        return _b64.b64encode(raw.encode()).decode()


# BUG FIX #6: заменяем 200+ дублированных записей на паттерн-матчинг.
# outlook/hotmail/live/* все используют один сервер — хранить 150 записей бессмысленно.
_SMTP_CONFIGS: dict[str, dict] = {
    "gmail.com":         {"host": "smtp.gmail.com",        "port": 465, "use_ssl": True,  "use_tls": False},
    "googlemail.com":    {"host": "smtp.gmail.com",        "port": 465, "use_ssl": True,  "use_tls": False},
    "msn.com":           {"host": "smtp.office365.com",    "port": 587, "use_ssl": False, "use_tls": True},
    "windowslive.com":   {"host": "smtp.office365.com",    "port": 587, "use_ssl": False, "use_tls": True},
    "ymail.com":         {"host": "smtp.mail.yahoo.com",   "port": 465, "use_ssl": True,  "use_tls": False},
    "rocketmail.com":    {"host": "smtp.mail.yahoo.com",   "port": 465, "use_ssl": True,  "use_tls": False},
    "icloud.com":        {"host": "smtp.mail.me.com",      "port": 587, "use_ssl": False, "use_tls": True},
    "me.com":            {"host": "smtp.mail.me.com",      "port": 587, "use_ssl": False, "use_tls": True},
    "mac.com":           {"host": "smtp.mail.me.com",      "port": 587, "use_ssl": False, "use_tls": True},
    "aol.com":           {"host": "smtp.aol.com",          "port": 465, "use_ssl": True,  "use_tls": False},
    "aim.com":           {"host": "smtp.aol.com",          "port": 465, "use_ssl": True,  "use_tls": False},
    "netscape.net":      {"host": "smtp.aol.com",          "port": 465, "use_ssl": True,  "use_tls": False},
    "compuserve.com":    {"host": "smtp.aol.com",          "port": 465, "use_ssl": True,  "use_tls": False},
    "verizon.net":       {"host": "smtp.aol.com",          "port": 465, "use_ssl": True,  "use_tls": False},  # FIX: outgoing.verizon.net→smtp.aol.com (Verizon→AOL 2017)
    "att.net":           {"host": "smtp.att.yahoo.com",    "port": 465, "use_ssl": True,  "use_tls": False},
    "sbcglobal.net":     {"host": "smtp.att.yahoo.com",    "port": 465, "use_ssl": True,  "use_tls": False},
    "bellsouth.net":     {"host": "smtp.att.yahoo.com",    "port": 465, "use_ssl": True,  "use_tls": False},
    "ameritech.net":     {"host": "smtp.att.yahoo.com",    "port": 465, "use_ssl": True,  "use_tls": False},
    "cs.com":            {"host": "smtp.cs.com",           "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.com":           {"host": "smtp.gmx.com",           "port": 465, "use_ssl": True,  "use_tls": False},
    "gmx.net":           {"host": "mail.gmx.net",          "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.de":            {"host": "mail.gmx.net",          "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.at":            {"host": "mail.gmx.net",          "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.ch":            {"host": "mail.gmx.net",          "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.co.uk":         {"host": "mail.gmx.net",          "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.fr":            {"host": "mail.gmx.net",          "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.es":            {"host": "mail.gmx.net",          "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.us":            {"host": "smtp.gmx.com",           "port": 465, "use_ssl": True,  "use_tls": False},
    # Outlook / Hotmail / Live family — explicit popular TLDs as safety net
    "outlook.com":       {"host": "smtp.office365.com",    "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.de":        {"host": "smtp.office365.com",    "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.fr":        {"host": "smtp.office365.com",    "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.es":        {"host": "smtp.office365.com",    "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.it":        {"host": "smtp.office365.com",    "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.co.uk":     {"host": "smtp.office365.com",    "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.jp":        {"host": "smtp.office365.com",    "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.com":       {"host": "smtp.office365.com",    "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.co.uk":     {"host": "smtp.office365.com",    "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.de":        {"host": "smtp.office365.com",    "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.fr":        {"host": "smtp.office365.com",    "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.es":        {"host": "smtp.office365.com",    "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.it":        {"host": "smtp.office365.com",    "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.ru":        {"host": "smtp.office365.com",    "port": 587, "use_ssl": False, "use_tls": True},
    "live.com":          {"host": "smtp.office365.com",    "port": 587, "use_ssl": False, "use_tls": True},
    "live.co.uk":        {"host": "smtp.office365.com",    "port": 587, "use_ssl": False, "use_tls": True},
    "live.de":           {"host": "smtp.office365.com",    "port": 587, "use_ssl": False, "use_tls": True},
    "live.fr":           {"host": "smtp.office365.com",    "port": 587, "use_ssl": False, "use_tls": True},
    "live.ru":           {"host": "smtp.office365.com",    "port": 587, "use_ssl": False, "use_tls": True},
    # Yahoo family — explicit popular TLDs as safety net
    "yahoo.com":         {"host": "smtp.mail.yahoo.com",   "port": 465, "use_ssl": True,  "use_tls": False},
    "yahoo.co.uk":       {"host": "smtp.mail.yahoo.com",   "port": 465, "use_ssl": True,  "use_tls": False},
    "yahoo.de":          {"host": "smtp.mail.yahoo.com",   "port": 465, "use_ssl": True,  "use_tls": False},
    "yahoo.fr":          {"host": "smtp.mail.yahoo.com",   "port": 465, "use_ssl": True,  "use_tls": False},
    "yahoo.es":          {"host": "smtp.mail.yahoo.com",   "port": 465, "use_ssl": True,  "use_tls": False},
    "yahoo.it":          {"host": "smtp.mail.yahoo.com",   "port": 465, "use_ssl": True,  "use_tls": False},
    "yahoo.co.jp":       {"host": "smtp.mail.yahoo.com",   "port": 465, "use_ssl": True,  "use_tls": False},
    "yahoo.ru":          {"host": "smtp.mail.yahoo.com",   "port": 465, "use_ssl": True,  "use_tls": False},
    "yahoo.com.br":      {"host": "smtp.mail.yahoo.com",   "port": 465, "use_ssl": True,  "use_tls": False},
    "yahoo.com.ar":      {"host": "smtp.mail.yahoo.com",   "port": 465, "use_ssl": True,  "use_tls": False},
    "yahoo.com.mx":      {"host": "smtp.mail.yahoo.com",   "port": 465, "use_ssl": True,  "use_tls": False},
    "yahoo.com.au":      {"host": "smtp.mail.yahoo.com",   "port": 465, "use_ssl": True,  "use_tls": False},
    "mail.ru":           {"host": "smtp.mail.ru",          "port": 465, "use_ssl": True,  "use_tls": False},
    "inbox.ru":          {"host": "smtp.mail.ru",          "port": 465, "use_ssl": True,  "use_tls": False},
    "list.ru":           {"host": "smtp.mail.ru",          "port": 465, "use_ssl": True,  "use_tls": False},
    "bk.ru":             {"host": "smtp.mail.ru",          "port": 465, "use_ssl": True,  "use_tls": False},
    "internet.ru":       {"host": "smtp.mail.ru",          "port": 465, "use_ssl": True,  "use_tls": False},
    "mail.ua":           {"host": "smtp.ukr.net",          "port": 465, "use_ssl": True,  "use_tls": False},  # FIX: smtp.mail.ua ENOTFOUND→smtp.ukr.net (mail.ua→ukr.net infrastructure)
    "ro.ru":             {"host": "smtp.mail.ru",          "port": 465, "use_ssl": True,  "use_tls": False},
    "yandex.ru":         {"host": "smtp.yandex.ru",        "port": 465, "use_ssl": True,  "use_tls": False},
    "yandex.com":        {"host": "smtp.yandex.com",       "port": 465, "use_ssl": True,  "use_tls": False},
    "ya.ru":             {"host": "smtp.yandex.ru",        "port": 465, "use_ssl": True,  "use_tls": False},
    "yandex.ua":         {"host": "smtp.yandex.ru",        "port": 465, "use_ssl": True,  "use_tls": False},
    "yandex.by":         {"host": "smtp.yandex.by",        "port": 465, "use_ssl": True,  "use_tls": False},
    "yandex.kz":         {"host": "smtp.yandex.ru",        "port": 465, "use_ssl": True,  "use_tls": False},
    "rambler.ru":        {"host": "smtp.rambler.ru",       "port": 465, "use_ssl": True,  "use_tls": False},
    "lenta.ru":          {"host": "smtp.rambler.ru",       "port": 465, "use_ssl": True,  "use_tls": False},
    "autorambler.ru":    {"host": "smtp.rambler.ru",       "port": 465, "use_ssl": True,  "use_tls": False},
    "myrambler.ru":      {"host": "smtp.rambler.ru",       "port": 465, "use_ssl": True,  "use_tls": False},
    "i.ua":              {"host": "smtp.i.ua",             "port": 465, "use_ssl": True,  "use_tls": False},
    "ukr.net":           {"host": "smtp.ukr.net",          "port": 465, "use_ssl": True,  "use_tls": False},
    "meta.ua":           {"host": "smtp.meta.ua",          "port": 465, "use_ssl": True,  "use_tls": False},
    "bigmir.net":        {"host": "smtp.bigmir.net",       "port": 465, "use_ssl": True,  "use_tls": False},
    "email.ua":          {"host": "smtp.email.ua",         "port": 465, "use_ssl": True,  "use_tls": False},
    "inbox.lv":          {"host": "smtp.inbox.lv",         "port": 465, "use_ssl": True,  "use_tls": False},
    "mail.lt":           {"host": "smtp.domreg.lt",        "port": 587, "use_ssl": False, "use_tls": True},   # FIX: smtp.mail.lt ENOTFOUND→smtp.domreg.lt
    "web.de":            {"host": "smtp.web.de",           "port": 587, "use_ssl": False, "use_tls": True},
    "freenet.de":        {"host": "mx.freenet.de",         "port": 587, "use_ssl": False, "use_tls": True},
    "t-online.de":       {"host": "securesmtp.t-online.de","port": 465, "use_ssl": True,  "use_tls": False},
    "telekom.de":        {"host": "securesmtp.t-online.de","port": 465, "use_ssl": True,  "use_tls": False},
    "arcor.de":          {"host": "smtp.arcor.de",         "port": 465, "use_ssl": True,  "use_tls": False},
    "kabelbw.de":        {"host": "smtp.kabelbw.de",       "port": 587, "use_ssl": False, "use_tls": True},
    "vodafone.de":       {"host": "smtp.vodafone.de",      "port": 465, "use_ssl": True,  "use_tls": False},
    "mailbox.org":       {"host": "smtp.mailbox.org",      "port": 465, "use_ssl": True,  "use_tls": False},
    "posteo.de":         {"host": "posteo.de",             "port": 587, "use_ssl": False, "use_tls": True},
    "posteo.net":        {"host": "posteo.de",             "port": 587, "use_ssl": False, "use_tls": True},
    "strato.de":         {"host": "smtp.strato.de",        "port": 465, "use_ssl": True,  "use_tls": False},
    "strato.com":        {"host": "smtp.strato.de",        "port": 465, "use_ssl": True,  "use_tls": False},
    "ionos.de":          {"host": "smtp.ionos.de",         "port": 465, "use_ssl": True,  "use_tls": False},
    "1und1.de":          {"host": "smtp.1and1.com",        "port": 587, "use_ssl": False, "use_tls": True},
    "1and1.com":         {"host": "smtp.1and1.com",        "port": 587, "use_ssl": False, "use_tls": True},
    "orange.fr":         {"host": "smtp.orange.fr",        "port": 465, "use_ssl": True,  "use_tls": False},
    "wanadoo.fr":        {"host": "smtp.orange.fr",        "port": 465, "use_ssl": True,  "use_tls": False},
    "free.fr":           {"host": "smtp.free.fr",          "port": 465, "use_ssl": True,  "use_tls": False},
    "sfr.fr":            {"host": "smtp.sfr.fr",           "port": 465, "use_ssl": True,  "use_tls": False},
    "laposte.net":       {"host": "smtp.laposte.net",      "port": 465, "use_ssl": True,  "use_tls": False},
    "bbox.fr":           {"host": "smtp.bbox.fr",          "port": 465, "use_ssl": True,  "use_tls": False},
    "btinternet.com":    {"host": "smtp.btinternet.com",   "port": 465, "use_ssl": True,  "use_tls": False},
    "btopenworld.com":   {"host": "smtp.btinternet.com",   "port": 465, "use_ssl": True,  "use_tls": False},
    "sky.com":           {"host": "smtp.office365.com",    "port": 587, "use_ssl": False, "use_tls": True},  # FIX: smtp.sky.com ENOTFOUND→office365 (Sky UK 2023+)
    "virginmedia.com":   {"host": "smtp.virginmedia.com",  "port": 465, "use_ssl": True,  "use_tls": False},
    "ntlworld.com":      {"host": "smtp.ntlworld.com",     "port": 465, "use_ssl": True,  "use_tls": False},
    "zoho.com":          {"host": "smtp.zoho.com",         "port": 465, "use_ssl": True,  "use_tls": False},
    "zohomail.com":      {"host": "smtp.zoho.com",         "port": 465, "use_ssl": True,  "use_tls": False},
    "zoho.eu":           {"host": "smtp.zoho.eu",          "port": 465, "use_ssl": True,  "use_tls": False},
    "zohomail.eu":       {"host": "smtp.zoho.eu",          "port": 465, "use_ssl": True,  "use_tls": False},
    "zoho.in":           {"host": "smtp.zoho.com",         "port": 465, "use_ssl": True,  "use_tls": False},
    # firstmail.ltd family — FIX: port 465 SSL (port 25 блокируется ISP/VPN)
    "blackfirsta.com":   {"host": "smtp.firstmail.ltd",    "port": 465, "use_ssl": True,  "use_tls": False, "imap_host": "imap.firstmail.ltd", "imap_port": 993, "imap_ssl": True},
    "firsthidden.com":   {"host": "smtp.firstmail.ltd",    "port": 465, "use_ssl": True,  "use_tls": False, "imap_host": "imap.firstmail.ltd", "imap_port": 993, "imap_ssl": True},
    "ishowfirstmail.com":{"host": "smtp.firstmail.ltd",    "port": 465, "use_ssl": True,  "use_tls": False, "imap_host": "imap.firstmail.ltd", "imap_port": 993, "imap_ssl": True},
    "analismail.com":    {"host": "smtp.firstmail.ltd",    "port": 465, "use_ssl": True,  "use_tls": False, "imap_host": "imap.firstmail.ltd", "imap_port": 993, "imap_ssl": True},
    # Google Workspace custom domains — FIX: iejesusmirey.com / buzzmaster.market = G Suite → smtp.gmail.com
    "iejesusmirey.com":  {"host": "smtp.gmail.com",        "port": 465, "use_ssl": True,  "use_tls": False},
    "buzzmaster.market": {"host": "smtp.gmail.com",        "port": 465, "use_ssl": True,  "use_tls": False},
      # Fastmail
      "fastmail.com":      {"host": "smtp.fastmail.com",     "port": 465, "use_ssl": True,  "use_tls": False},
      "fastmail.fm":       {"host": "smtp.fastmail.com",     "port": 465, "use_ssl": True,  "use_tls": False},
      # Tutanota / Tuta
      "tutanota.com":      {"host": "mail.tutanota.com",     "port": 587, "use_ssl": False, "use_tls": True},
      "tutamail.com":      {"host": "mail.tutanota.com",     "port": 587, "use_ssl": False, "use_tls": True},
      "tuta.io":           {"host": "mail.tutanota.com",     "port": 587, "use_ssl": False, "use_tls": True},
      # Yahoo — дополнительные TLD
      "yahoo.ca":          {"host": "smtp.mail.yahoo.com",   "port": 465, "use_ssl": True,  "use_tls": False},
}

# Load extended SMTP providers (poczta.fm, sapo.pt, bigpond, telenet, comcast +80 more)
# Per smtp-configs-extended skill — update at module init so all domains are available
try:
    from core.smtp_configs_extra import load_extra_configs as _load_extra
    _SMTP_CONFIGS.update(_load_extra())
except Exception as _exc:
    logging.getLogger("sender").debug("Пропущено исключение: %s", _exc)

# Pattern-based fallback: outline/hotmail/live/* → office365; yahoo.* → yahoo; gmx.* → gmx.net
_O365 = {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True}
_YAHOO = {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False}
_GMX = {"host": "mail.gmx.net", "port": 587, "use_ssl": False, "use_tls": True}

_SMTP_DOMAIN_PATTERNS: list[tuple[str, dict]] = [
    ("outlook.",  _O365),
    ("hotmail.",  _O365),
    ("live.",     _O365),
    ("yahoo.",    _YAHOO),
    ("gmx.",      _GMX),
]


@dataclass
class Recipient:
    """Один получатель рассылки с полями персонализации."""
    email: str
    first_name: str = ""
    last_name: str = ""
    company: str = ""
    custom_1: str = ""
    custom_2: str = ""
    custom_3: str = ""
    custom_4: str = ""
    custom_5: str = ""


@dataclass
class EmailTemplate:
    """Шаблон письма с поддержкой персонализации через {{placeholders}}."""
    subject: str
    body_html: str
    body_text: str = ""
    attachments: List[str] = field(default_factory=list)
    reply_to: str = ""
    cc: List[str] = field(default_factory=list)

    def personalize(self, recipient: Recipient) -> "EmailTemplate":
        """Возвращает копию шаблона с заменёнными плейсхолдерами для получателя."""
        subs = {
            "{{email}}":      recipient.email,
            "{{first_name}}": recipient.first_name,
            "{{last_name}}":  recipient.last_name,
            "{{company}}":    recipient.company,
            "{{custom_1}}":   recipient.custom_1,
            "{{custom_2}}":   recipient.custom_2,
            "{{custom_3}}":   recipient.custom_3,
            "{{custom_4}}":   recipient.custom_4,
            "{{custom_5}}":   recipient.custom_5,
            "{{full_name}}":  f"{recipient.first_name} {recipient.last_name}".strip(),
        }

        def sub(text: str) -> str:
            for k, v in subs.items():
                text = text.replace(k, v)
            return text

        return EmailTemplate(
            subject=sub(self.subject),
            body_html=sub(self.body_html),
            body_text=sub(self.body_text),
            attachments=self.attachments,
            reply_to=self.reply_to,
            cc=self.cc,
        )


# H-1 FIX: MX-запись = ВХОДЯЩИЙ сервер, не исходящий SMTP!
# Карта: подстрока MX-хоста → правильный исходящий SMTP
_MX_TO_SMTP: dict[str, dict] = {
    "google.com":         {"host": "smtp.gmail.com",                         "port": 465, "use_ssl": True,  "use_tls": False},
    "googlemail.com":     {"host": "smtp.gmail.com",                         "port": 465, "use_ssl": True,  "use_tls": False},
    "outlook.com":        {"host": "smtp.office365.com",                     "port": 587, "use_ssl": False, "use_tls": True},
    "protection.outlook": {"host": "smtp.office365.com",                     "port": 587, "use_ssl": False, "use_tls": True},
    "yahoodns.net":       {"host": "smtp.mail.yahoo.com",                    "port": 465, "use_ssl": True,  "use_tls": False},
    "mimecast.com":       {"host": "smtp.office365.com",                     "port": 587, "use_ssl": False, "use_tls": True},
    "pphosted.com":       {"host": "smtp.office365.com",                     "port": 587, "use_ssl": False, "use_tls": True},
    "mailgun.org":        {"host": "smtp.mailgun.org",                       "port": 587, "use_ssl": False, "use_tls": True},
    "amazonses.com":      {"host": "email-smtp.us-east-1.amazonaws.com",     "port": 587, "use_ssl": False, "use_tls": True},
}


def _resolve_via_mx(domain: str) -> "Optional[dict]":
    """Query DNS MX records and map to the correct OUTGOING SMTP server.

    H-1 FIX: MX-хост — это входящий сервер. Мы маппим его на исходящий SMTP
    через известные паттерны. Напрямую MX-хост как SMTP НЕ используем.
    """
    if not _DNS_OK:
        return None
    try:
        answers = sorted(
            _dns_resolver.resolve(domain, "MX", lifetime=5),
            key=lambda r: r.preference,
        )
        if not answers:
            return None
        mx_host = str(answers[0].exchange).rstrip(".").lower()
        mx_base = ".".join(mx_host.split(".")[-2:])

        # 1) Точное совпадение в основном конфиге
        if mx_base in _SMTP_CONFIGS:
            return _SMTP_CONFIGS[mx_base]

        # 2) Паттерн-матчинг (outlook.*, hotmail.*, live.*, yahoo.*, gmx.*)
        for prefix, cfg in _SMTP_DOMAIN_PATTERNS:
            if prefix.rstrip(".") in mx_host:
                return cfg

        # 3) Карта MX-провайдеров → исходящий SMTP
        for mx_key, smtp_cfg in _MX_TO_SMTP.items():
            if mx_key in mx_host:
                return smtp_cfg

        # 4) НЕ используем mx_host напрямую — вернём None, tier-4 даст smtp.<domain>
        return None
    except Exception:
        return None


def get_smtp_config_for_domain(domain: str) -> Optional[dict]:
    """4-tier SMTP resolution: dict -> pattern -> MX lookup -> generic smtp.<domain> fallback."""
    d = domain.lower().strip()
    # Tier 1: exact match in master config
    if d in _SMTP_CONFIGS:
        return _SMTP_CONFIGS[d]
    # Tier 2: prefix pattern (outlook.*, hotmail.*, live.*, yahoo.*, gmx.*)
    for prefix, cfg in _SMTP_DOMAIN_PATTERNS:
        if d.startswith(prefix):
            return cfg
    # Tier 3: MX record lookup via dnspython
    mx_cfg = _resolve_via_mx(d)
    if mx_cfg:
        return mx_cfg
    # Tier 4: generic fallback
    return {"host": "smtp." + d, "port": 587, "use_ssl": False, "use_tls": True}


@dataclass
class SmtpAccount:
    email: str
    password: str
    host: str
    port: int = 465
    use_ssl: bool = True
    use_tls: bool = False
    display_name: str = ""
    daily_limit: int = 500
    hourly_limit: int = 50
    is_active: bool = True
    proxy: str = ""
    oauth_token: str = ""       # access_token (legacy field — используй access_token)
    access_token: str = ""      # Актуальный OAuth2 Bearer access_token
    refresh_token: str = ""     # OAuth2 refresh_token для авто-обновления
    token_expires_at: float = 0.0  # Unix-timestamp истечения access_token
    imap_host: str = ""
    imap_port: int = 993
    imap_ssl: bool = True
    last_test_ok: Optional[bool] = field(default=None)
    last_test_msg: str = field(default="")

    def __post_init__(self):
        self._lock = threading.Lock()
        self.sent_today: int = 0
        self.sent_this_hour: int = 0
        self._hour_reset: float = time.time()
        self._day_reset: float = time.time()

    def _tick_resets(self) -> None:
        """Сбрасывает часовой и суточный счётчики при смене периода."""
        now = time.time()
        if now - self._day_reset >= 86400:
            self.sent_today = 0
            self.sent_this_hour = 0
            self._day_reset = now
            self._hour_reset = now
        elif now - self._hour_reset >= 3600:
            self.sent_this_hour = 0
            self._hour_reset = now

    @property
    def can_send(self) -> bool:
        """Thread-safe проверка лимитов; вызывает _tick_resets() для актуализации счётчиков."""
        if not self.is_active:
            return False
        with self._lock:
            self._tick_resets()
            return self.sent_today < self.daily_limit and self.sent_this_hour < self.hourly_limit

    def try_increment(self) -> bool:
        """Атомарная проверка+инкремент. Устраняет TOCTOU race condition."""
        if not self.is_active:
            return False
        with self._lock:
            self._tick_resets()
            if self.sent_today < self.daily_limit and self.sent_this_hour < self.hourly_limit:
                self.sent_today += 1
                self.sent_this_hour += 1
                return True
            return False
  


@dataclass
class CampaignConfig:
    max_threads: int = 5
    min_delay_ms: int = 500
    max_delay_ms: int = 2000
    pause_after_n: int = 100
    pause_duration_sec: float = 60.0
    track_opens: bool = True
    track_clicks: bool = True
    unsubscribe_link: str = ""
    rotate_accounts: bool = True


@dataclass
class SendResult:
    recipient_email: str
    success: bool = False
    error: str = ""
    account_used: str = ""
    message_id: str = ""
    timestamp: float = field(default_factory=time.time)


def validate_email_format(email: str) -> bool:
    """Backward-compat wrapper — источник истины в core.utils."""
    from core.utils import validate_email_format as _vef
    return _vef(email)


def _build_message(
    account: SmtpAccount,
    recipient: Recipient,
    template: EmailTemplate,
) -> MIMEMultipart:
    """Build MIME message: multipart/mixed -> multipart/alternative -> html."""
    # BUG-FIX: используем домен отправителя, не SMTP-хост (RFC 2822)
    _sender_domain = account.email.split("@")[-1] if "@" in account.email else account.host
    msg_id = f"<{uuid.uuid4().hex}@{_sender_domain}>"
    from_addr = (
        f"{account.display_name} <{account.email}>"
        if account.display_name else account.email
    )
    outer = MIMEMultipart("mixed")
    outer["Subject"] = template.subject
    outer["From"] = from_addr
    outer["To"] = recipient.email
    outer["Message-ID"] = msg_id
    outer["Date"] = time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime())
    if template.reply_to:
        outer["Reply-To"] = template.reply_to
    if template.cc:
        outer["CC"] = ", ".join(template.cc)

    alt = MIMEMultipart("alternative")
    # BUG-FIX: декодируем HTML entities (&amp;, &nbsp; и т.д.) в plain-text версии
    from core.utils import strip_html as _strip
    plain = template.body_text or _strip(template.body_html)
    alt.attach(MIMEText(plain, "plain", "utf-8"))
    alt.attach(MIMEText(template.body_html, "html", "utf-8"))
    outer.attach(alt)

    for att_path in template.attachments:
        p = Path(att_path)
        if not p.exists():
            continue
        mime_type, _ = mimetypes.guess_type(str(p))
        main_type, sub_type = (mime_type or "application/octet-stream").split("/", 1)
        with open(p, "rb") as f:
            data = f.read()
        att = MIMEApplication(data, _subtype=sub_type)
        att.add_header("Content-Disposition", "attachment", filename=p.name)
        outer.attach(att)

    return outer

def _parse_auth_error(host: str, smtp_code: int, detail: str) -> str:
    """Возвращает понятное пользователю описание ошибки SMTP-аутентификации."""
    d = detail.lower()
    h = host.lower()

    # Rambler / Lenta / Championat
    if "rambler" in h or "lenta" in h or "championat" in h:
        if "invalid login" in d or "invalid password" in d or "535" in str(smtp_code) or "535" in d:
            return ("Неверный логин/пароль Rambler.\n"
                    "Причина: пароль устарел или аккаунт заблокирован.\n"
                    "Решение: зайдите на rambler.ru → Настройки → Безопасность → смените пароль.")
        if "too many" in d or "rate" in d:
            return "Rambler: слишком много попыток. Подождите 5-10 минут."

    # GMX / WEB.DE / T-Online
    if any(s in h for s in ["gmx", "web.de", "t-online"]):
        if "535" in d or "authentication" in d or "incorrect" in d:
            return ("Неверный логин/пароль GMX.\n"
                    "Возможная причина: SMTP отключён в настройках.\n"
                    "Решение: gmx.com → Настройки → POP3 & IMAP → Разрешить SMTP.")
        if "550" in d and "blocked" in d:
            return "GMX: аккаунт заблокирован. Войдите на gmx.com и разблокируйте."

    # Google / Gmail
    if "gmail" in h or "google" in h or "googlemail" in h:
        if "534" in d or "application-specific" in d:
            return ("Google: требуется App Password.\n"
                    "Решение: myaccount.google.com → Безопасность → Пароли приложений.")
        if "535" in d or "username and password" in d:
            return ("Google: неверный пароль или требуется App Password.\n"
                    "Решение: включите 2FA и создайте пароль приложения на myaccount.google.com.")

    # Microsoft / Outlook / Hotmail
    if any(s in h for s in ["outlook", "hotmail", "live.com", "office365", "microsoft"]):
        if "5.7.139" in d or "basic authentication is disabled" in d:
            return ("Microsoft: базовая аутентификация отключена.\n"
                    "Решение: account.microsoft.com → Безопасность → App Password.")
        if "535" in d or "5.7.3" in d:
            return ("Microsoft: неверный пароль или нужен App Password.\n"
                    "Решение: создайте App Password на account.microsoft.com.")

    # Yahoo / AOL
    if any(s in h for s in ["yahoo", "aol", "ymail"]):
        if "535" in d:
            return ("Yahoo/AOL: неверный пароль или нужен App Password.\n"
                    "Решение: security.yahoo.com → Manage App Passwords.")

    # Универсальные коды
    if "too many" in d or "rate limit" in d or "421" in d:
        return f"Слишком много попыток входа. Подождите 10-15 минут. ({detail[:60]})"
    if any(w in d for w in ["suspend", "disabled", "inactive", "locked", "deactiv"]):
        return f"Аккаунт заблокирован или деактивирован. Зайдите на сайт почты и разблокируйте. ({detail[:60]})"
    if any(w in d for w in ["blacklist", "banned", "blocked"]):
        return f"IP-адрес заблокирован провайдером. Используйте прокси. ({detail[:60]})"
    if "captcha" in d or "verify" in d:
        return f"Требуется подтверждение через браузер. Зайдите на сайт почты. ({detail[:60]})"
    if "2fa" in d or "two-factor" in d or "two factor" in d:
        return f"Включена двухфакторная аутентификация. Используйте App Password. ({detail[:60]})"
    if "password" in d and ("expired" in d or "must be changed" in d):
        return f"Пароль устарел. Зайдите на сайт почты и смените пароль. ({detail[:60]})"
    if "quota" in d or "storage" in d or "full" in d:
        return f"Почтовый ящик переполнен. Освободите место. ({detail[:60]})"

    return f"Неверный логин или пароль ({smtp_code}): {detail[:120]}"



def _socks5_raw_socket(
    proxy_host: str, proxy_port: int,
    target_host: str, target_port: int,
    username: str = "", password: str = "",
    timeout: float = 30.0,
):
    """RFC-1928 SOCKS5 + RFC-1929 user/pass auth — только stdlib, PySocks не нужен.
    Возвращает подключённый socket.socket, туннелированный через SOCKS5-прокси.
    """
    import socket as _socket
    import struct as _struct

    s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect((proxy_host, proxy_port))

    # 1. Greeting
    s.sendall(b"\x05\x02\x00\x02" if username else b"\x05\x01\x00")
    resp = s.recv(2)
    if len(resp) < 2 or resp[0] != 0x05:
        s.close(); raise OSError("Не SOCKS5-сервер")
    if resp[1] == 0xFF:
        s.close(); raise OSError("SOCKS5: сервер отклонил все методы аутентификации")

    # 2. User/pass auth (RFC 1929)
    if resp[1] == 0x02:
        if not username:
            s.close(); raise OSError("SOCKS5: требуется логин/пароль, но они не заданы")
        un, pw = username.encode("utf-8"), (password or "").encode("utf-8")
        s.sendall(b"\x01" + bytes([len(un)]) + un + bytes([len(pw)]) + pw)
        ar = s.recv(2)
        if len(ar) < 2 or ar[1] != 0x00:
            s.close(); raise OSError("SOCKS5: неверный логин/пароль (auth rejected)")

    # 3. CONNECT
    tb = target_host.encode("utf-8")
    s.sendall(b"\x05\x01\x00\x03" + bytes([len(tb)]) + tb + _struct.pack(">H", target_port))
    hdr = b""
    while len(hdr) < 4:
        chunk = s.recv(4 - len(hdr))
        if not chunk:
            s.close(); raise OSError("SOCKS5: соединение закрыто до ответа")
        hdr += chunk
    if hdr[1] != 0x00:
        _e = {1:"общий сбой",2:"запрещено",3:"сеть недоступна",4:"хост недоступен",5:"отклонено"}
        s.close(); raise OSError(f"SOCKS5 CONNECT отклонён: {_e.get(hdr[1], f'код {hdr[1]}')}")
    # Drain BNDADDR/BNDPORT
    atyp = hdr[3]
    if atyp == 0x01: s.recv(6)
    elif atyp == 0x03:
        n = s.recv(1)[0]; s.recv(n + 2)
    elif atyp == 0x04: s.recv(18)
    return s


def _http_connect_raw_socket(
    proxy_host: str, proxy_port: int,
    target_host: str, target_port: int,
    username: str = "", password: str = "",
    timeout: float = 30.0,
):
    """HTTP CONNECT туннель — stdlib only, PySocks не нужен.
    Возвращает подключённый socket уже туннелированный через прокси.
    """
    import socket as _socket, base64 as _b64
    s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect((proxy_host, proxy_port))
    lines = [
        f"CONNECT {target_host}:{target_port} HTTP/1.1",
        f"Host: {target_host}:{target_port}",
        "Proxy-Connection: Keep-Alive",
    ]
    if username:
        cred = _b64.b64encode(
            f"{username}:{password or ''}".encode("utf-8")
        ).decode()
        lines.append(f"Proxy-Authorization: Basic {cred}")
    s.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("utf-8"))
    resp = b""
    while b"\r\n\r\n" not in resp and len(resp) < 8192:
        chunk = s.recv(256)
        if not chunk:
            break
        resp += chunk
    first = resp.split(b"\r\n")[0].decode("utf-8", "replace") if resp else ""
    parts = first.split(" ", 2)
    code = parts[1] if len(parts) >= 2 else "?"
    reason = parts[2].strip() if len(parts) >= 3 else ""
    if code != "200":
        s.close()
        raise OSError(f"HTTP прокси отклонил CONNECT {target_host}:{target_port}: {code} {reason[:80]}")
    return s


def _proxy_connect(
    proxy_parsed,
    target_host: str,
    target_port: int,
    *,
    timeout: float = 30.0,
    auto_detect: bool = False,
):
    """
    Универсальный прокси-туннель. Выбирает протокол по scheme.

    Схема `http://` / `https://` → HTTP CONNECT (RFC 7231).
    Схема `socks5://` / `socks4://` → SOCKS5 (RFC 1928).
    Нет схемы (auto_detect=True) → SOCKS5 (3 с), при неудаче → HTTP CONNECT.
    """
    scheme = (getattr(proxy_parsed, "scheme", "") or "").lower()
    host = proxy_parsed.hostname or ""
    port = proxy_parsed.port or (1080 if "socks" in scheme else 3128)
    uname = proxy_parsed.username or ""
    upass = proxy_parsed.password or ""

    if "http" in scheme and "socks" not in scheme:
        # Явный HTTP/HTTPS-прокси — только HTTP CONNECT
        return _http_connect_raw_socket(host, port, target_host, target_port,
                                        uname, upass, timeout)
    elif "socks" in scheme and not auto_detect:
        # Явный SOCKS5/SOCKS4 — только SOCKS5
        return _socks5_raw_socket(host, port, target_host, target_port,
                                   uname, upass, timeout)
    else:
        # auto_detect или неизвестная схема: пробуем SOCKS5 с коротким таймаутом,
        # при любой ошибке переключаемся на HTTP CONNECT
        try:
            return _socks5_raw_socket(host, port, target_host, target_port,
                                       uname, upass, min(timeout, 3.0))
        except OSError:
            return _http_connect_raw_socket(host, port, target_host, target_port,
                                             uname, upass, timeout)


def _test_smtp_sync(account: "SmtpAccount") -> tuple[bool, str]:
      """
      Sync SMTP test с автоматическим многоуровневым fallback.
      Поддерживает SOCKS5/SOCKS4/HTTP прокси через stdlib-сокет (PySocks не нужен).

      Стратегия:
        1) Основная конфигурация аккаунта (с cert-verify)
        2) Та же конфигурация без cert-verify (self-signed SSL)
        3) Fallback порты: 465 → 587 (только если прокси НЕ используется)
           При прокси fallback-перебор портов бессмысленен.
      """
      import ssl as _ssl
      import smtplib as _smtplib
      import urllib.parse as _up

      # ── Разбор прокси ──────────────────────────────────────────────────────────
      _proxy_url = (account.proxy or "").strip()
      _proxy_parsed = None
      _proxy_auto = False  # True = схема не была задана явно → авто-определение
      if _proxy_url:
          if "://" not in _proxy_url:
              _proxy_url = "socks5://" + _proxy_url  # для urlparse; авто-детект ниже
              _proxy_auto = True
          _proxy_parsed = _up.urlparse(_proxy_url)

      # ── OAuth2 детектор ────────────────────────────────────────────────────────
      _is_oauth_acct = _is_ms_domain(account.email) and bool(
          getattr(account, "refresh_token", "")
          or getattr(account, "access_token", "")
          or getattr(account, "oauth_token", "")
      )

      def _make_smtp(host: str, port: int, use_ssl: bool, use_tls: bool,
                     ctx: "_ssl.SSLContext") -> "_smtplib.SMTP":
          """Создаёт SMTP-соединение (прямое или через прокси)."""
          TIMEOUT = 5  # сек на попытку — быстро определяем недоступность

          if _proxy_parsed:
              # ── SOCKS5 или HTTP CONNECT через raw stdlib-сокет ─────────────────
              raw = _proxy_connect(
                  _proxy_parsed, host, port,
                  timeout=TIMEOUT,
                  auto_detect=_proxy_auto,
              )
              if use_ssl:
                  raw = ctx.wrap_socket(raw, server_hostname=host)
              s = _smtplib.SMTP.__new__(_smtplib.SMTP)
              s._host = host
              s.sock = raw
              s.file = raw.makefile("rb")
              s.ehlo_or_helo_if_needed()
              if not use_ssl and use_tls:
                  s.starttls(context=ctx)
                  s.ehlo()
          else:
              # ── Прямое подключение ─────────────────────────────────────────────
              if use_ssl:
                  s = _smtplib.SMTP_SSL(host, port, context=ctx, timeout=TIMEOUT)
              else:
                  s = _smtplib.SMTP(host, port, timeout=TIMEOUT)
                  s.ehlo()
                  if use_tls:
                      s.starttls(context=ctx)
                      s.ehlo()
          return s

      def _attempt(host: str, port: int, use_ssl: bool, use_tls: bool, verify: bool = True):
          """Одна попытка. True=успех, False=неверный пароль, None=ошибка соединения."""
          ctx = _ssl.create_default_context()
          if not verify:
              ctx.check_hostname = False
              ctx.verify_mode = _ssl.CERT_NONE
          s = None
          try:
              s = _make_smtp(host, port, use_ssl, use_tls, ctx)

              # ── Аутентификация ─────────────────────────────────────────────────
              _oauth_tok = ""
              if _is_oauth_acct:
                  _oauth_tok = (
                      _get_oauth_token(account) if _HAS_OAUTH2
                      else (getattr(account, "access_token", "") or getattr(account, "oauth_token", ""))
                  )
                  if not _oauth_tok:
                      return False, "OAuth2: не удалось получить access token"
              if _oauth_tok:
                  s.ehlo()
                  _xo = _build_xoauth2(account.email, _oauth_tok)
                  code, resp = s.docmd("AUTH", "XOAUTH2 " + _xo)
                  if code == 334:
                      code, resp = s.docmd("")
                  if code != 235:
                      _rmsg = resp.decode("utf-8", "replace") if isinstance(resp, (bytes, bytearray)) else str(resp)
                      return False, f"OAuth2 отклонён: {_rmsg[:120]}"
              else:
                  s.login(account.email, account.password)

              _cv = "" if verify else " (no-cert)"
              _ak = " (OAuth2)" if _oauth_tok else ""
              _px = f" via {_proxy_parsed.scheme}://{_proxy_parsed.hostname}" if _proxy_parsed else ""
              return True, f"OK — {host}:{port}{_cv}{_ak}{_px}"

          except _smtplib.SMTPAuthenticationError as e:
              raw = e.smtp_error
              detail = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
              if _is_oauth_acct:
                  return False, f"OAuth2 отклонён сервером: {detail[:120]}"
              return False, f"Неверный логин или пароль: {detail[:120]}"
          except _smtplib.SMTPNotSupportedError:
              return None, "SMTP AUTH не поддерживается. Требуется App Password."
          except _smtplib.SMTPException as ex:
              msg = str(ex)
              if "5.7.139" in msg or "basic authentication is disabled" in msg.lower():
                  return None, "Microsoft отключил базовую SMTP-аутентификацию. Нужен App Password."
              return None, f"SMTP: {msg[:100]}"
          except OSError as e:
              return None, f"connect/{type(e).__name__}: {e}"
          except Exception as e:
              return None, f"err/{type(e).__name__}: {e}"
          finally:
              if s is not None:
                  try:
                      s.quit()
                  except Exception:
                      try:
                          s.close()
                      except Exception:
                          pass

      # ── Шаг 1: основная конфигурация с cert-verify ────────────────────────────
      ok, msg = _attempt(account.host, account.port, account.use_ssl, account.use_tls, verify=True)
      if ok is True:
          return True, msg
      if ok is False:
          return False, msg  # Пароль неверен — дальше пробовать бессмысленно

      # ── Шаг 2: та же конфигурация без cert-verify (self-signed SSL) ──────────
      ok, msg = _attempt(account.host, account.port, account.use_ssl, account.use_tls, verify=False)
      if ok is True:
          return True, msg
      if ok is False:
          return False, msg

      # ── Шаг 3: fallback порты — только без прокси ─────────────────────────────
      # При прокси каждая попытка добавляет 5с задержки и всё равно не помогает —
      # прокси либо работает (тогда шаги 1-2 уже прошли), либо нет.
      if _proxy_parsed:
          return False, f"Не удалось подключиться через прокси к {account.host}:{account.port}. Проверьте прокси."

      _combos = [(465, True, False), (587, False, True)]  # 25/2525 убраны — почти никогда не нужны
      _tried = {account.port}
      for _port, _ssl_flag, _tls_flag in _combos:
          if _port in _tried:
              continue
          _tried.add(_port)
          for _verify in (True, False):
              ok, msg = _attempt(account.host, _port, _ssl_flag, _tls_flag, verify=_verify)
              if ok is True:
                  return True, msg
              if ok is False:
                  return False, f"Неверный логин или пароль (порт {_port}). {msg}"

      return False, f"Не удалось подключиться к {account.host}. Проверьте сетевой доступ."

async def test_smtp_connection(account: SmtpAccount) -> tuple[bool, str]:
    """
    Проверяет SMTP-подключение.
    Всегда использует надёжный smtplib через executor — избегаем несовместимости aiosmtplib версий.
    Все ошибки выводятся понятным пользователю языком.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _test_smtp_sync, account)


class SendingEngine:
    """
    Async campaign engine.

    engine = SendingEngine(accounts, config, log_queue=q)
    engine.on_progress = lambda sent, total, result: ...
    engine.on_finished = lambda results: ...
    loop.run_until_complete(engine.run_campaign(recipients, template))

    engine.stats       -> {"success": N, "errors": N, "total": N}
    engine._paused     -> bool
    engine.pause()  /  engine.resume()  /  engine.stop()
    """

    def __init__(
        self,
        accounts: List[SmtpAccount],
        config: CampaignConfig,
        log_queue: Optional[queue.Queue] = None,
        recipients: Optional[List[Recipient]] = None,
        template: Optional[EmailTemplate] = None,
        stop_event: Optional[threading.Event] = None,
    ):
        self.accounts = accounts
        self.config = config
        self._log_queue: Optional[queue.Queue] = log_queue
        self._recipients: List[Recipient] = recipients or []
        self._template: Optional[EmailTemplate] = template
        self.stop_event = stop_event or threading.Event()
        self._paused = False
        self.on_progress: Optional[Callable] = None
        self.on_finished: Optional[Callable] = None
        self._stats: dict = {"success": 0, "errors": 0, "total": 0}
        self._stats_lock = threading.Lock()

    @property
    def stats(self) -> dict:
        with self._stats_lock:
            return dict(self._stats)

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def stop(self) -> None:
        self.stop_event.set()
        self._paused = False
        # Отменяем текущую asyncio-задачу для мгновенной остановки
        task = getattr(self, "_campaign_task", None)
        if task is not None and not task.done():
            try:
                task.cancel()
            except Exception as _exc:
                logging.getLogger("sender").debug("Пропущено исключение: %s", _exc)

    def run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            tpl = self._template or EmailTemplate(subject="(no subject)", body_html="")
            loop.run_until_complete(self.run_campaign(self._recipients, tpl))
        finally:
            loop.close()

    async def run_campaign(
        self,
        recipients: List[Recipient],
        template: EmailTemplate,
    ) -> List[SendResult]:
        self._recipients = recipients
        self._template = template
        with self._stats_lock:
            self._stats = {"success": 0, "errors": 0, "total": len(recipients)}
        self.stop_event.clear()
        self._paused = False
        self._campaign_task = asyncio.current_task()
        if self._log_queue:
            self._log_queue.put_nowait({"type": "log", "level": "info", "message":
                f"[{time.strftime('%H:%M:%S')}] Запуск рассылки: {len(recipients)} получателей"})

        # Сбрасываем суточный/часовой счётчик если период истёк
        _now = time.time()
        for _acct in self.accounts:
            if _acct.is_active:
                with _acct._lock:
                    if _now - _acct._day_reset >= 86400:
                        _acct.sent_today = 0
                        _acct.sent_this_hour = 0
                        _acct._day_reset = _now
                        _acct._hour_reset = _now
                    elif _now - _acct._hour_reset >= 3600:
                        _acct.sent_this_hour = 0
                        _acct._hour_reset = _now

        results: List[SendResult] = []
        sem = asyncio.Semaphore(self.config.max_threads)

        async def _send_with_acct_delay(recipient: Recipient) -> SendResult:
            """Задержка + выбор аккаунта ВНУТРИ задачи — для честной ротации."""
            if self.stop_event.is_set():
                return SendResult(
                    recipient_email=recipient.email,
                    success=False,
                    error="Отменено",
                )
            delay = random.randint(self.config.min_delay_ms, self.config.max_delay_ms) / 1000.0
            await asyncio.sleep(delay)
            if self.stop_event.is_set():
                return SendResult(
                    recipient_email=recipient.email,
                    success=False,
                    error="Отменено",
                )
            # ── Retry: до 3 разных аккаунтов ─────────────────────────────────
            _MAX_RETRIES = 3
            _tried: set = set()
            _last_result = None
            for _attempt in range(_MAX_RETRIES):
                account = self._pick_account(exclude=_tried)
                if account is None:
                    break
                _tried.add(account.email)
                _result = await self._send_one(sem, account, recipient, template)
                if _result.success:
                    if _attempt > 0 and self._log_queue:
                        self._log_queue.put_nowait({"type": "log", "level": "ok", "message":
                            f"[{time.strftime('%H:%M:%S')}] {recipient.email}: успех с {account.email} (попытка {_attempt + 1})"})
                    return _result
                _last_result = _result
                if _attempt < _MAX_RETRIES - 1 and self._log_queue:
                    self._log_queue.put_nowait({"type": "log", "level": "warn", "message":
                        f"[{time.strftime('%H:%M:%S')}] {recipient.email}: {_result.error[:60]} — пробую другой аккаунт..."})
            if _last_result is not None:
                return _last_result
            if self._log_queue:
                self._log_queue.put_nowait({"type": "log", "level": "err", "message":
                    f"[{time.strftime('%H:%M:%S')}] {recipient.email}: все аккаунты недоступны"})
            return SendResult(
                recipient_email=recipient.email,
                success=False,
                error="Нет доступных аккаунтов",
            )

        async def _process_batch(batch_recipients: List[Recipient]) -> List[SendResult]:
            tasks = [_send_with_acct_delay(r) for r in batch_recipients]
            return await asyncio.gather(*tasks, return_exceptions=True)

        try:
            batch_size = max(self.config.max_threads, 1)
            i = 0
            while i < len(recipients):
                if self.stop_event.is_set():
                    break
                while self._paused and not self.stop_event.is_set():
                    await asyncio.sleep(0.1)
                if self.stop_event.is_set():
                    break
                batch = recipients[i:i + batch_size]
                batch_results = await _process_batch(batch)
                for result in batch_results:
                    if isinstance(result, BaseException):
                        with self._stats_lock:
                            self._stats["errors"] += 1
                        if self._log_queue:
                            self._log_queue.put_nowait({"type": "log", "level": "err", "message":
                                f"[{time.strftime('%H:%M:%S')}] ошибка [{type(result).__name__}]: {result}"})
                        continue
                    results.append(result)
                    with self._stats_lock:
                        if result.success:
                            self._stats["success"] += 1
                        else:
                            self._stats["errors"] += 1
                    if self._log_queue:
                        _ts = time.strftime('%H:%M:%S')
                        if result.success:
                            _lmsg = f"[{_ts}] {result.recipient_email}  via {result.account_used}"
                            _lvl = "ok"
                        else:
                            _lmsg = f"[{_ts}] {result.recipient_email}: {result.error or 'неизвестная ошибка'}"
                            _lvl = "err"
                        self._log_queue.put_nowait({"type": "log", "level": _lvl, "message": _lmsg})
                    self._emit_progress(results, recipients, result)
                if (
                    self.config.pause_after_n > 0
                    and len(results) > 0  # FIX БАГ-1: 0 % N == 0 вызывал ложную паузу при пустых results
                    and len(results) % self.config.pause_after_n == 0
                    and len(results) < len(recipients)
                ):
                    await asyncio.sleep(self.config.pause_duration_sec)
                i += batch_size

        except asyncio.CancelledError:
            pass  # Остановлено через stop()
        finally:
            self._campaign_task = None

        if self._log_queue:
            _ok = sum(1 for r in results if r.success)
            _fail = len(results) - _ok
            self._log_queue.put_nowait({"type": "log", "level": "info", "message":
                f"[{time.strftime('%H:%M:%S')}] Готово: {_ok} успешно, {_fail} ошибок"})
        if self.on_finished:
            self.on_finished(results)
        return results


    def _pick_account(self, exclude: "set | None" = None) -> Optional[SmtpAccount]:
          """Pick first account that passes atomic try_increment check.
          exclude: set of account emails to skip (retry logic).
          FIX v2.9.3: added missing exclude param — TypeError crashed every send.
          """
          _skip = exclude or set()
          active = [
              a for a in self.accounts
              if a.is_active and a.last_test_ok is not False and a.email not in _skip
          ]
          if self.config.rotate_accounts:
              random.shuffle(active)
          for account in active:
              if account.try_increment():
                  return account
          return None
    def _emit_progress(
        self,
        results: list,
        recipients: List[Recipient],
        result: SendResult,
    ) -> None:
        if self.on_progress:
            self.on_progress(len(results), len(recipients), result)

    async def _send_one(
        self,
        sem: asyncio.Semaphore,
        account: SmtpAccount,
        recipient: Recipient,
        template: EmailTemplate,
    ) -> SendResult:
        personalized = template.personalize(recipient)
        async with sem:
            # Если прокси задан — ВСЕГДА используем sync-путь (aiosmtplib не поддерживает SOCKS).
            # Если прокси НЕ задан — отправка заблокирована: IP клиента не должен утекать.
            if account.proxy and account.proxy.strip():
                return await asyncio.get_running_loop().run_in_executor(
                    None, self._send_sync, account, recipient, personalized
                )
            # Нет прокси → блокируем отправку
            return SendResult(
                recipient_email=recipient.email,
                success=False,
                error="Прокси не настроен для этого аккаунта — отправка без прокси заблокирована (защита IP)",
                account_used=account.email,
            )

    async def _send_aiosmtp(
        self,
        account: SmtpAccount,
        recipient: Recipient,
        template: EmailTemplate,
    ) -> SendResult:
        try:
            import aiosmtplib as _aiosmtplib  # noqa: F401
        except ImportError:
            return await asyncio.get_running_loop().run_in_executor(
                None, self._send_sync, account, recipient, template
            )  # FIX C1: fallback на sync при отсутствии aiosmtplib
        msg = _build_message(account, recipient, template)
        try:
            if account.use_ssl:
                # SSL/TLS (порт 465) — передаём только use_tls=True
                smtp = aiosmtplib.SMTP(
                    hostname=account.host, port=account.port,
                    use_tls=True, timeout=30,
                )
            else:
                # STARTTLS (порт 587): start_tls=False ОБЯЗАТЕЛЕН — aiosmtplib по умолчанию
                # (start_tls=None) АВТОМАТИЧЕСКИ делает STARTTLS при connect() если сервер
                # его анонсирует в EHLO. Явный starttls() ниже дублировал → "Connection already using TLS"
                # v3.7.7: start_tls= удалён (aiosmtplib 3.x несовместим). starttls() вызывается ниже.
                smtp = aiosmtplib.SMTP(
                    hostname=account.host, port=account.port,
                    use_tls=False, timeout=30,  # fix: start_tls= удалён (aiosmtplib 3.x)
                )
            await smtp.connect()
            try:
                if not account.use_ssl and account.use_tls:
                    # C-2 FIX: ehlo() перед starttls() — RFC 3207 + требование Exchange/Office365
                    try:
                        await smtp.ehlo()
                    except Exception as _exc:
                        logging.getLogger("sender").debug("Пропущено исключение: %s", _exc)
                    await smtp.starttls()
                    try:
                        await smtp.ehlo()  # повторный EHLO после STARTTLS — обязателен по RFC 3207
                    except Exception as _exc:
                        logging.getLogger("sender").debug("Пропущено исключение: %s", _exc)
                # OAuth2/XOAUTH2 для Microsoft (Outlook/Hotmail/Live)
                _domain_async = account.email.split("@")[-1].lower() if "@" in account.email else ""
                _ms_domains_async = frozenset({
                    "outlook.com", "hotmail.com", "live.com", "msn.com", "windowslive.com",
                    "outlook.de", "hotmail.de", "live.de", "outlook.fr", "hotmail.fr",
                    "live.fr", "outlook.ru", "hotmail.ru", "live.ru", "outlook.co.uk",
                    "hotmail.co.uk", "outlook.es", "hotmail.es", "outlook.it", "hotmail.it",
                })
                # Авто-обновление OAuth2 токена через refresh_token
                _oauth = _get_oauth_token(account) if _HAS_OAUTH2 else getattr(account, "oauth_token", "")
                if _oauth and _domain_async in _ms_domains_async:
                    # Для Outlook OAuth2: используем токен как пароль через LOGIN
                    await smtp.login(account.email, _oauth)
                else:
                    await smtp.login(account.email, account.password)
                await smtp.send_message(msg)
                return SendResult(
                    recipient_email=recipient.email,
                    success=True,
                    account_used=account.email,
                    message_id=msg.get("Message-ID", ""),
                )
            finally:
                try:
                    await smtp.quit()
                except Exception as _exc:
                    logging.getLogger("sender").debug("Пропущено исключение: %s", _exc)
        except Exception as _any_err:
            # Port fallback: try alternate port before giving up (465<->587).
            # Catches both OS-level errors (socket.timeout, OSError) AND
            # aiosmtplib-wrapped errors (SMTPConnectError, SMTPServerDisconnected).
            _fallback_map = {
                465: (587, False, True),
                587: (465, True, False),
                25:  (587, False, True),
            }
            _err_str = str(_any_err)
            _err_low = _err_str.lower()
            # НЕ делаем fallback на прямое соединение — это вызвало бы утечку IP.
            # aiosmtplib не поддерживает SOCKS — эта ветка вызывается только если
            # прокси не задан, что теперь блокируется в _send_one.
            return SendResult(
                recipient_email=recipient.email,
                success=False,
                error=_err_str,
                account_used=account.email,
            )

    def _send_sync(
          self,
          account: SmtpAccount,
          recipient: Recipient,
          template: EmailTemplate,
      ) -> SendResult:
          import ssl as _ssl_mod
          msg = _build_message(account, recipient, template)
          try:
              ctx = _ssl_mod.create_default_context()
              proxy_url = account.proxy.strip() if account.proxy else ""
              if not proxy_url:
                  # Прокси не настроен — блокируем отправку во избежание утечки реального IP
                  return SendResult(
                      recipient_email=recipient.email,
                      success=False,
                      error="Прокси не настроен — отправка без прокси заблокирована (защита IP клиента)",
                      account_used=account.email,
                  )
              _proxy_auto_send = "://" not in proxy_url
              if _proxy_auto_send:
                  proxy_url = "socks5://" + proxy_url
              import urllib.parse as _urlparse
              _p = _urlparse.urlparse(proxy_url)
              # ── SOCKS5 или HTTP CONNECT через raw stdlib-сокет ───────────────
              _raw = _proxy_connect(
                  _p, account.host, account.port,
                  timeout=30.0,
                  auto_detect=_proxy_auto_send,
              )
              if account.use_ssl:
                  _raw = ctx.wrap_socket(_raw, server_hostname=account.host)
              smtp_conn = smtplib.SMTP.__new__(smtplib.SMTP)
              smtp_conn._host = account.host
              smtp_conn.sock = _raw
              smtp_conn.file = _raw.makefile("rb")
              smtp_conn.ehlo_or_helo_if_needed()
              if not account.use_ssl and account.use_tls:
                  smtp_conn.starttls(context=ctx)
                  smtp_conn.ehlo()
              # OAuth2/XOAUTH2 для Microsoft или обычный LOGIN
              _domain = account.email.split("@")[-1].lower() if "@" in account.email else ""
              _ms_domains = frozenset({
                  "outlook.com","hotmail.com","live.com","msn.com","windowslive.com",
                  "outlook.de","hotmail.de","live.de","outlook.fr","hotmail.fr","live.fr",
                  "outlook.ru","hotmail.ru","live.ru","outlook.co.uk","hotmail.co.uk",
                  "outlook.es","hotmail.es","outlook.it","hotmail.it","outlook.nl",
              })
              _current_token = _get_oauth_token(account) if _HAS_OAUTH2 else getattr(account, "oauth_token", "")
              if _current_token and _domain in _ms_domains:
                  _xoauth2 = base64.b64encode(
                      ("user=" + account.email + "\x01auth=Bearer " +
                       _current_token + "\x01\x01").encode()
                  ).decode()
                  smtp_conn.docmd("AUTH", "XOAUTH2 " + _xoauth2)
              else:
                  smtp_conn.login(account.email, account.password)
              smtp_conn.send_message(msg)
              try:
                  smtp_conn.quit()
              except Exception:
                  pass
              return SendResult(
                  recipient_email=recipient.email,
                  success=True,
                  account_used=account.email,
                  message_id=msg.get("Message-ID", ""),
              )
          except Exception as e:
              return SendResult(
                  recipient_email=recipient.email,
                  success=False,
                  error=str(e),
                  account_used=account.email,
              )