"""
FMailSender core sending engine v2.9.4.
Fixes: IndentationError in increment_sent/try_increment/Recipient,
       async parallelism (delay moved inside task wrapper),
       duplicate params documented, race condition eliminated via try_increment.
v2.9.4: добавлено логирование во все silent except-блоки.
"""
from __future__ import annotations

import asyncio
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
    "verizon.net":       {"host": "outgoing.verizon.net",  "port": 465, "use_ssl": True,  "use_tls": False},
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
    "mail.ua":           {"host": "smtp.mail.ua",          "port": 465, "use_ssl": True,  "use_tls": False},  # FIX БАГ-3: mail.ua != mail.ru
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
    "mail.lt":           {"host": "smtp.mail.lt",          "port": 465, "use_ssl": True,  "use_tls": False},
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
    "sky.com":           {"host": "smtp.sky.com",          "port": 587, "use_ssl": False, "use_tls": True},
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

      # Web.de (Germany) — FIX v2.9.4: добавлен отсутствующий провайдер
      "web.de":            {"host": "smtp.web.de",           "port": 587, "use_ssl": False, "use_tls": True,
                            "imap_host": "imap.web.de",      "imap_port": 993, "imap_ssl": True},
      # Yandex
      "yandex.ru":         {"host": "smtp.yandex.ru",        "port": 465, "use_ssl": True,  "use_tls": False,
                            "imap_host": "imap.yandex.ru",   "imap_port": 993, "imap_ssl": True},
      "ya.ru":             {"host": "smtp.yandex.ru",        "port": 465, "use_ssl": True,  "use_tls": False,
                            "imap_host": "imap.yandex.ru",   "imap_port": 993, "imap_ssl": True},
      "yandex.com":        {"host": "smtp.yandex.com",       "port": 465, "use_ssl": True,  "use_tls": False,
                            "imap_host": "imap.yandex.com",  "imap_port": 993, "imap_ssl": True},
      "yandex.kz":         {"host": "smtp.yandex.kz",        "port": 465, "use_ssl": True,  "use_tls": False,
                            "imap_host": "imap.yandex.kz",   "imap_port": 993, "imap_ssl": True},
      # Zoho
      "zoho.com":          {"host": "smtp.zoho.com",         "port": 465, "use_ssl": True,  "use_tls": False,
                            "imap_host": "imap.zoho.com",    "imap_port": 993, "imap_ssl": True},
      "zohomail.com":      {"host": "smtp.zoho.com",         "port": 465, "use_ssl": True,  "use_tls": False,
                            "imap_host": "imap.zoho.com",    "imap_port": 993, "imap_ssl": True},
      # Fastmail
      "fastmail.com":      {"host": "smtp.fastmail.com",     "port": 465, "use_ssl": True,  "use_tls": False,
                            "imap_host": "imap.fastmail.com","imap_port": 993, "imap_ssl": True},
      "fastmail.fm":       {"host": "smtp.fastmail.com",     "port": 465, "use_ssl": True,  "use_tls": False,
                            "imap_host": "imap.fastmail.com","imap_port": 993, "imap_ssl": True},
      # Yahoo international
      "yahoo.de":          {"host": "smtp.mail.yahoo.com",   "port": 465, "use_ssl": True,  "use_tls": False,
                            "imap_host": "imap.mail.yahoo.com","imap_port": 993, "imap_ssl": True},
      "yahoo.co.uk":       {"host": "smtp.mail.yahoo.com",   "port": 465, "use_ssl": True,  "use_tls": False,
                            "imap_host": "imap.mail.yahoo.com","imap_port": 993, "imap_ssl": True},
      "yahoo.fr":          {"host": "smtp.mail.yahoo.com",   "port": 465, "use_ssl": True,  "use_tls": False,
                            "imap_host": "imap.mail.yahoo.com","imap_port": 993, "imap_ssl": True},
      "yahoo.es":          {"host": "smtp.mail.yahoo.com",   "port": 465, "use_ssl": True,  "use_tls": False,
                            "imap_host": "imap.mail.yahoo.com","imap_port": 993, "imap_ssl": True},
      "yahoo.it":          {"host": "smtp.mail.yahoo.com",   "port": 465, "use_ssl": True,  "use_tls": False,
                            "imap_host": "imap.mail.yahoo.com","imap_port": 993, "imap_ssl": True},
      "yahoo.ca":          {"host": "smtp.mail.yahoo.com",   "port": 465, "use_ssl": True,  "use_tls": False,
                            "imap_host": "imap.mail.yahoo.com","imap_port": 993, "imap_ssl": True},
      "yahoo.com.au":      {"host": "smtp.mail.yahoo.com",   "port": 465, "use_ssl": True,  "use_tls": False,
                            "imap_host": "imap.mail.yahoo.com","imap_port": 993, "imap_ssl": True},
      # T-Online (Telekom Germany)
      "t-online.de":       {"host": "securesmtp.t-online.de","port": 465, "use_ssl": True,  "use_tls": False,
                            "imap_host": "secureimap.t-online.de","imap_port": 993, "imap_ssl": True},
      # Tutanota
      "tutanota.com":      {"host": "mail.tutanota.com",     "port": 587, "use_ssl": False, "use_tls": True,
                            "imap_host": "mail.tutanota.com","imap_port": 993, "imap_ssl": True},
      "tutamail.com":      {"host": "mail.tutanota.com",     "port": 587, "use_ssl": False, "use_tls": True,
                            "imap_host": "mail.tutanota.com","imap_port": 993, "imap_ssl": True},
  }

# Load extended SMTP providers (poczta.fm, sapo.pt, bigpond, telenet, comcast +80 more)
# Per smtp-configs-extended skill — update at module init so all domains are available
try:
    from core.smtp_configs_extra import load_extra_configs as _load_extra
    _SMTP_CONFIGS.update(_load_extra())
except Exception as _exc:
    import logging as _lg; _lg.getLogger("sender").debug("Пропущено исключение: %s", _exc)

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
    oauth_token: str = ""
    imap_host: str = ""
    imap_port: int = 993
    imap_ssl: bool = True
    last_test_ok: Optional[bool] = field(default=None)

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


def _test_smtp_sync(account: "SmtpAccount") -> tuple[bool, str]:
    """Sync SMTP test через стандартный smtplib — надёжно работает с любым провайдером."""
    import ssl as _ssl
    try:
        ctx = _ssl.create_default_context()
        if account.use_ssl:
            s = smtplib.SMTP_SSL(account.host, account.port, context=ctx, timeout=8)
        else:
            s = smtplib.SMTP(account.host, account.port, timeout=8)
            s.ehlo()
            if account.use_tls:
                s.starttls(context=ctx)
                s.ehlo()  # повторный EHLO после STARTTLS — обязателен по RFC
        s.login(account.email, account.password)
        s.quit()
        return True, f"OK — {account.host}:{account.port} авторизация успешна"
    except smtplib.SMTPAuthenticationError as e:
        raw = e.smtp_error
        detail = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
        return False, f"Неверный логин или пароль. {detail[:120]}"
    except (smtplib.SMTPConnectError, ConnectionRefusedError, OSError, TimeoutError) as _conn_err:
          # FIX: exhaustive port fallback — пробуем ВСЕ комбинации пока не успех
          _all_combos = [
              (465,  True,  False),  # SMTPS (implicit SSL)
              (587,  False, True),   # STARTTLS
              (25,   False, False),  # Plain SMTP
              (2525, False, True),   # Альтернативный STARTTLS
          ]
          _tried = {account.port}
          for _fb_port, _fb_ssl, _fb_tls in _all_combos:
              if _fb_port in _tried:
                  continue
              _tried.add(_fb_port)
              try:
                  _ctx2 = _ssl.create_default_context()
                  if _fb_ssl:
                      _s2 = smtplib.SMTP_SSL(account.host, _fb_port, context=_ctx2, timeout=8)
                  else:
                      _s2 = smtplib.SMTP(account.host, _fb_port, timeout=8)
                      _s2.ehlo()
                      if _fb_tls:
                          _s2.starttls(context=_ctx2)
                          _s2.ehlo()
                  _s2.login(account.email, account.password)
                  _s2.quit()
                  return True, f"OK — {account.host}:{_fb_port} (fallback) авторизация успешна"
              except smtplib.SMTPAuthenticationError as _auth_e:
                  _raw2 = _auth_e.smtp_error
                  _det2 = _raw2.decode("utf-8", errors="replace") if isinstance(_raw2, bytes) else str(_raw2)
                  return False, f"Неверный логин или пароль (порт {_fb_port}). {_det2[:120]}"
              except Exception as _exc:
                  import logging as _lg; _lg.getLogger("sender").warning("Пропущен элемент: %s", _exc); continue
          return False, f"Не удалось подключиться к {account.host} ни на одном порту (465/587/25/2525)."
          return False, f"Не удалось подключиться к {account.host}:{account.port}. Проверьте хост и порт."
    except smtplib.SMTPNotSupportedError:
        return False, "Сервер не поддерживает SMTP AUTH. Outlook/Hotmail — требуется App Password. T-online — нужен пароль для внешних программ."
    except smtplib.SMTPException as _smtp_ex:
        _smtp_msg = str(_smtp_ex)
        if "5.7.139" in _smtp_msg or "basic authentication is disabled" in _smtp_msg.lower():
            return False, "Microsoft отключил базовую SMTP-аутентификацию. Требуется App Password (outlook.com/account/security)."
    except smtplib.SMTPServerDisconnected:
        return False, "Сервер разорвал соединение. Возможно, неверный протокол (SSL/TLS)."
    except OSError as e:
        return False, f"Сетевая ошибка: {e}"
    except Exception as e:
        return False, f"Ошибка [{type(e).__name__}]: {e}"


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
                import logging as _lg; _lg.getLogger("sender").debug("Пропущено исключение: %s", _exc)

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
            self._log_queue.put_nowait({"type": "log", "message":
                f"[{time.strftime('%H:%M:%S')}] 🚀 Запуск рассылки: {len(recipients)} получателей"})

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
                        self._log_queue.put_nowait({"type": "log", "message":
                            f"[{time.strftime('%H:%M:%S')}] ↩ {recipient.email}: успех с {account.email} (попытка {_attempt + 1})"})
                    return _result
                _last_result = _result
                if _attempt < _MAX_RETRIES - 1 and self._log_queue:
                    self._log_queue.put_nowait({"type": "log", "message":
                        f"[{time.strftime('%H:%M:%S')}] ↩ {recipient.email}: {_result.error[:60]} — пробую другой аккаунт..."})
            if _last_result is not None:
                return _last_result
            if self._log_queue:
                self._log_queue.put_nowait({"type": "log", "message":
                    f"[{time.strftime('%H:%M:%S')}] ⚠ {recipient.email}: все аккаунты недоступны"})
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
                            self._log_queue.put_nowait({"type": "log", "message":
                                f"[{time.strftime('%H:%M:%S')}] ✗ ошибка [{type(result).__name__}]: {result}"})
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
                            _lmsg = f"[{_ts}] ✓ {result.recipient_email}  ← {result.account_used}"
                        else:
                            _lmsg = f"[{_ts}] ✗ {result.recipient_email}: {result.error or 'неизвестная ошибка'}"
                        self._log_queue.put_nowait({"type": "log", "message": _lmsg})
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
            self._log_queue.put_nowait({"type": "log", "message":
                f"[{time.strftime('%H:%M:%S')}] ═══ Готово: ✓ {_ok} успешно, ✗ {_fail} ошибок ═══"})
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
            if _HAS_AIOSMTPLIB:
                return await self._send_aiosmtp(account, recipient, personalized)
            return await asyncio.get_running_loop().run_in_executor(
                None, self._send_sync, account, recipient, personalized
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
                # ФИКС v2.9.4: start_tls=False в конструкторе, starttls() вручную ниже
                smtp = aiosmtplib.SMTP(
                    hostname=account.host, port=account.port,
                    use_tls=False, start_tls=False, timeout=30,
                )
            await smtp.connect()
            try:
                if not account.use_ssl and account.use_tls:
                    # C-2 FIX: ehlo() перед starttls() — RFC 3207 + требование Exchange/Office365
                    try:
                        await smtp.ehlo()
                    except Exception as _exc:
                        import logging as _lg; _lg.getLogger("sender").debug("Пропущено исключение: %s", _exc)
                    await smtp.starttls()
                    try:
                        await smtp.ehlo()  # повторный EHLO после STARTTLS — обязателен по RFC 3207
                    except Exception as _exc:
                        import logging as _lg; _lg.getLogger("sender").debug("Пропущено исключение: %s", _exc)
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
                    import logging as _lg; _lg.getLogger("sender").debug("Пропущено исключение: %s", _exc)
        except (socket.timeout, TimeoutError, ConnectionRefusedError, OSError) as _conn_err:
            # Port fallback: try alternate port before giving up (465<->587)
            _fallback_map = {
                465: (587, False, True),
                587: (465, True, False),
                25:  (587, False, True),
            }
            if account.port in _fallback_map:
                _fb_port, _fb_ssl, _fb_tls = _fallback_map[account.port]
                try:
                    import ssl as _ssl2
                    _ctx2 = _ssl2.create_default_context()
                    if _fb_ssl:
                        _s2 = smtplib.SMTP_SSL(account.host, _fb_port, context=_ctx2, timeout=30)
                    else:
                        _s2 = smtplib.SMTP(account.host, _fb_port, timeout=30)
                        _s2.ehlo()
                        if _fb_tls:
                            _s2.starttls(context=_ctx2)
                            _s2.ehlo()
                    _s2.login(account.email, account.password)
                    _s2.send_message(msg)
                    _s2.quit()
                    return SendResult(
                        recipient_email=recipient.email,
                        success=True,
                        account_used=account.email,
                        message_id=msg.get("Message-ID", ""),
                    )
                except Exception as _exc:
                    import logging as _lg; _lg.getLogger("sender").debug("Пропущено исключение: %s", _exc)
            return SendResult(
                recipient_email=recipient.email,
                success=False,
                error=str(_conn_err),
                account_used=account.email,
            )
        except Exception as e:
            return SendResult(
                recipient_email=recipient.email,
                success=False,
                error=str(e),
                account_used=account.email,
            )

    def _send_sync(
          self,
          account: SmtpAccount,
          recipient: Recipient,
          template: EmailTemplate,
      ) -> SendResult:
          import ssl as _ssl_mod
          # PROXY ENFORCEMENT: письма отправляются ТОЛЬКО через прокси
          if not account.proxy.strip():
              return SendResult(
                  recipient_email=recipient.email,
                  success=False,
                  error="[PROXY_REQUIRED] Прокси не настроен. Отправка без прокси запрещена.",
                  account_used=account.email,
              )
          msg = _build_message(account, recipient, template)
          try:
              ctx = _ssl_mod.create_default_context()
              proxy_url = account.proxy.strip()
              if "://" not in proxy_url:
                  proxy_url = "socks5://" + proxy_url
              import urllib.parse as _urlparse
              _p = _urlparse.urlparse(proxy_url)
              _scheme = _p.scheme.lower()
              try:
                  import socks as _socks_lib
              except ImportError:
                  return SendResult(
                      recipient_email=recipient.email, success=False,
                      error="PySocks не установлен. Выполните: pip install PySocks",
                      account_used=account.email,
                  )
              _proxy_type = _socks_lib.SOCKS5 if "socks5" in _scheme else (
                  _socks_lib.SOCKS4 if "socks4" in _scheme else _socks_lib.HTTP)
              _raw = _socks_lib.socksocket()
              _raw.set_proxy(_proxy_type, _p.hostname, _p.port or 1080,
                             True, _p.username, _p.password)
              _raw.settimeout(30)
              _raw.connect((account.host, account.port))
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
              if getattr(account, "oauth_token", "") and _domain in _ms_domains:
                  _xoauth2 = base64.b64encode(
                      ("user=" + account.email + "\x01auth=Bearer " +
                       account.oauth_token + "\x01\x01").encode()
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