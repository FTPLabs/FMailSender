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
  from core.dkim_signer import (
      load_configs as _dkim_load_configs,
      sign_message_bytes as _dkim_sign,
      get_config_for_domain as _dkim_get_cfg,
  )
  _HAS_DKIM_SIGNER = True
except ImportError:
  _HAS_DKIM_SIGNER = False
  def _dkim_load_configs(): return []
  def _dkim_sign(b, _cfg): return b
  def _dkim_get_cfg(d, cfgs): return None

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
      """Получает OAuth2 access_token; авто-обновляет через refresh_token."""
      _at = getattr(account, "access_token", "") or getattr(account, "oauth_token", "") or ""
      _rt = getattr(account, "refresh_token", "") or ""
      if not _at and _rt and _HAS_OAUTH2:
          try:
              from core.oauth2_refresh import refresh_ms_token
              info = refresh_ms_token(account.email, _rt, timeout=15.0)
              if info:
                  account.access_token = info.access_token
                  account.oauth_token  = info.access_token
                  return info.access_token
          except Exception:
              pass
      return _at
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
  # FIX v6.1: smtp.gmx.com → mail.gmx.net (официальный SMTP для всех GMX-доменов, включая .com)
  "gmx.com":           {"host": "mail.gmx.net",           "port": 587, "use_ssl": False, "use_tls": True, "fallback_port": 465},
  "gmx.net":           {"host": "mail.gmx.net",          "port": 587, "use_ssl": False, "use_tls": True, "fallback_port": 465},
  "gmx.de":            {"host": "mail.gmx.net",          "port": 587, "use_ssl": False, "use_tls": True, "fallback_port": 465},
  "gmx.at":            {"host": "mail.gmx.net",          "port": 587, "use_ssl": False, "use_tls": True, "fallback_port": 465},
  "gmx.ch":            {"host": "mail.gmx.net",          "port": 587, "use_ssl": False, "use_tls": True, "fallback_port": 465},
  "gmx.co.uk":         {"host": "mail.gmx.net",          "port": 587, "use_ssl": False, "use_tls": True, "fallback_port": 465},
  "gmx.fr":            {"host": "mail.gmx.net",          "port": 587, "use_ssl": False, "use_tls": True, "fallback_port": 465},
  "gmx.es":            {"host": "mail.gmx.net",          "port": 587, "use_ssl": False, "use_tls": True, "fallback_port": 465},
  "gmx.us":            {"host": "smtp.gmx.com",           "port": 587, "use_ssl": False, "use_tls": True, "fallback_port": 465},
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

  def __getattr__(self, name: str):
      """Safety net: пересоздаёт runtime-атрибуты при отсутствии.
      Срабатывает при старом .pyc кэше, copy.copy(), pickle — любом
      пути создания объекта без вызова __post_init__.
      """
      if name in ('_lock', '_day_reset', '_hour_reset'):
          object.__setattr__(self, '_lock', threading.Lock())
          object.__setattr__(self, '_day_reset', time.time())
          object.__setattr__(self, '_hour_reset', time.time())
          return object.__getattribute__(self, name)
      raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

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

  def decrement_sent(self) -> None:
      """Откатывает инкремент счётчика если отправка в итоге провалилась.
      Вызывается из _send_with_acct_delay при ошибке — лимиты не сжигаются впустую.
      """
      with self._lock:
          if self.sent_today > 0:
              self.sent_today -= 1
          if self.sent_this_hour > 0:
              self.sent_this_hour -= 1



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
  uniqueize: bool = True   # v4.4.5: уникализировать каждое письмо (spintax, CSS micro, fingerprint)


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
  uniqueize: bool = True,
) -> MIMEMultipart:
  """Build MIME message: multipart/mixed -> multipart/alternative -> html.
  v4.4.5: uniqueize=True — spintax, CSS micro, fingerprint per email.
  """
  # v4.4.5: уникализация — каждое письмо уникально (spintax, CSS fingerprint, data-attrs)
  _subject = template.subject
  _body_html = template.body_html
  if uniqueize and _body_html:
      try:
          from core.uniqueizer import (  # noqa: PLC0415
              technique_spintax,
              technique_css_micro,
              technique_css_custom_props,
              technique_data_attrs,
              technique_font_stack,
              technique_nbsp,
              technique_random_comments,
              technique_subject as _spin_subject,
          )
          _subject = _spin_subject(_subject)
          _body_html = technique_spintax(_body_html)
          _body_html = technique_css_micro(_body_html)
          _body_html = technique_css_custom_props(_body_html)
          _body_html = technique_data_attrs(_body_html)
          _body_html = technique_font_stack(_body_html)
          _body_html = technique_nbsp(_body_html)
          _body_html = technique_random_comments(_body_html)
      except Exception as _uq_err:
          import logging as _logging
          _logging.getLogger(__name__).warning(
              "Uniqueization failed (sending as-is): %s", _uq_err, exc_info=True
          )
  # BUG-FIX: используем домен отправителя, не SMTP-хост (RFC 2822)
  _sender_domain = account.email.split("@")[-1] if "@" in account.email else account.host
  msg_id = f"<{uuid.uuid4().hex}@{_sender_domain}>"
  from_addr = (
      f"{account.display_name} <{account.email}>"
      if account.display_name else account.email
  )
  from email.utils import formatdate as _formatdate
  outer = MIMEMultipart("mixed")
  outer["Subject"] = _subject
  outer["From"] = from_addr
  outer["To"] = recipient.email
  outer["Message-ID"] = msg_id
  outer["Date"] = _formatdate(localtime=False)  # RFC 2822 compliant
  outer["MIME-Version"] = "1.0"
  # List-Unsubscribe: required by Gmail/Yahoo since Feb 2024 for bulk senders (>5k/day)
  # RFC 8058 One-Click unsubscribe — mandatory for inbox placement
  _unsub_email = template.reply_to or account.email
  outer["List-Unsubscribe"] = f"<mailto:{_unsub_email}?subject=unsubscribe>"
  outer["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
  outer["Precedence"] = "bulk"
  if template.reply_to:
      outer["Reply-To"] = template.reply_to
  if template.cc:
      outer["CC"] = ", ".join(template.cc)

  alt = MIMEMultipart("alternative")
  # BUG-FIX: декодируем HTML entities (&amp;, &nbsp; и т.д.) в plain-text версии
  from core.utils import strip_html as _strip
  plain = template.body_text or _strip(template.body_html)
  alt.attach(MIMEText(plain, "plain", "utf-8"))
  alt.attach(MIMEText(_body_html, "html", "utf-8"))
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
      if "5.7.139" in d or "basic authentication is disabled" in d or "smtpclientauthentication is disabled" in d or "5.7.138" in d:
          return (  # FIX B001: else-branch
              "Microsoft: SMTP AUTH отключён для этого ящика.\n"
              "Ошибка: SmtpClientAuthentication is disabled.\n"
              "Решение:\n"
              "  1. Зайдите в Outlook.com → Настройки → Почта → Синхронизация\n"
              "  2. Включите SMTP AUTH для ящика\n"
              "  3. Или используйте OAuth2 (добавьте refresh_token)\n"
              "Ссылка: https://aka.ms/smtp_auth_disabled"
          )
      else:
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
      # Явный SOCKS5/SOCKS4; при "запрещено" (код 2) — прямое соединение
      try:
          return _socks5_raw_socket(host, port, target_host, target_port,
                                     uname, upass, timeout)
      except OSError as _socks_err:
          _msg = str(_socks_err)
          if "запрещено" in _msg or "код 2" in _msg or "not allowed" in _msg:
              # FIX_B002: no direct connect — proxy-only policy, would leak real IP
              raise OSError(
                  f"SOCKS5: proxy {host}:{port} blocked SMTP-port {target_port}"
                  f" (code 2). Change SMTP port (465/587/25) or use a different proxy."
              )
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

    # ── Proxy (optional) ─────────────────────────────────────────────────────
    # Если прокси задан — используем его; при ошибке — прямое соединение.
    _proxy_url = (account.proxy or "").strip()

    # ── Разбор прокси ──────────────────────────────────────────────────────────
    _proxy_parsed = None
    _proxy_auto = False  # True = схема не была задана явно → авто-определение
    if _proxy_url:
        if "://" not in _proxy_url:
            _proxy_url = "socks5://" + _proxy_url  # для urlparse; авто-детект ниже
            _proxy_auto = True
        _proxy_parsed = _up.urlparse(_proxy_url)

    # ── OAuth2 детектор ────────────────────────────────────────────────────────
    # FIX v6.3: проверяем SMTP-хост — JMX/корпоративные через office365 не детектируются по домену
    _is_ms_host = ("office365" in getattr(account, "host", "").lower()
                   or "outlook.microsoft" in getattr(account, "host", "").lower())
    _has_oauth_token = bool(getattr(account, "refresh_token", "")
                            or getattr(account, "access_token", "")
                            or getattr(account, "oauth_token", ""))
    _is_oauth_acct = (_is_ms_domain(account.email) or _is_ms_host) and _has_oauth_token

    def _make_smtp(host: str, port: int, use_ssl: bool, use_tls: bool,
                   ctx: "_ssl.SSLContext") -> "_smtplib.SMTP":
        """Создаёт SMTP-соединение (прямое или через прокси)."""
        # FIX v6.1: увеличен с 5 до 10 с.
        # 5 с слишком мало для TCP+banner+EHLO+STARTTLS+EHLO на международных серверах
        # (Outlook, GMX иногда отвечают 6-9 с из-за геолокации/геозащиты).
        # 10 с достаточно для любого реального сервера; общий таймаут 30 с на аккаунт
        # в asyncio.wait_for гарантирует, что один аккаунт не заморозит всю очередь.
        TIMEOUT = 10  # сек на каждую socket-операцию

        if _proxy_parsed:
            # ── SOCKS5 или HTTP CONNECT через raw stdlib-сокет ─────────────────
            raw = _proxy_connect(
                _proxy_parsed, host, port,
                timeout=TIMEOUT,
                auto_detect=_proxy_auto,
            )
            # FIX v4.4.1: _ProxySMTP subclass вместо __new__ хака.
            # SMTP.__new__() пропускает _tls_required, ehlo_resp и другие
            # атрибуты Python 3.11+, что вызывало AttributeError в
            # ehlo_or_helo_if_needed(). _get_socket override корректен для 3.9-3.13+.
            if use_ssl:
                _raw_ssl = raw  # замкнуть в closure
                _ctx_ssl = ctx

                class _ProxySMTP_SSL(_smtplib.SMTP_SSL):  # noqa: E501
                    def _get_socket(self, _h, _p, _t):
                        return _ctx_ssl.wrap_socket(_raw_ssl, server_hostname=_h)

                s = _ProxySMTP_SSL(host, port, timeout=TIMEOUT, context=ctx)
            else:
                _raw_plain = raw

                class _ProxySMTP(_smtplib.SMTP):  # noqa: E501
                    def _get_socket(self, _h, _p, _t):
                        return _raw_plain

                s = _ProxySMTP(host, port, timeout=TIMEOUT)
                if use_tls:
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
            _rt = bool(getattr(account, "refresh_token", "") or getattr(account, "oauth_token", ""))
            _at = bool(getattr(account, "access_token", ""))
            _h = getattr(account, "host", "").lower()
            _ms = "office365" in _h or "outlook.microsoft" in _h or _is_ms_domain(account.email)
            if _ms and not _rt and not _at:
                return False, (
                    "Microsoft: Basic AUTH отключён для этого ящика.\n"
                    "Решение: добавьте refresh_token в файл (email|пароль|refresh_token)\n"
                    "и переимпортируйте — приложение переключится на OAuth2.\n"
                    "Или: Outlook.com → Настройки → Почта → Синхронизация → включить SMTP AUTH."
                )
            if _ms and (_rt or _at):
                return False, ("Microsoft OAuth2: токен истёк или недействителен. Обновите refresh_token.")
            if "gmail" in _h or "googlemail" in _h:
                return False, ("Gmail: Basic AUTH отключён. App Password: Google Аккаунт → Безопасность → Пароли приложений.")
            # FIX v6.4: GMX / web.de — отдельная ветка, не Outlook и не Gmail
            _d_lower = account.email.split("@")[-1].lower() if "@" in account.email else ""
            _is_gmx = (
                any(x in _h for x in ("mail.gmx", "smtp.gmx"))
                or _d_lower in (
                    "gmx.com", "gmx.net", "gmx.de", "gmx.at", "gmx.ch",
                    "gmx.co.uk", "gmx.fr", "gmx.es", "gmx.us",
                )
            )
            _is_webde = "smtp.web.de" in _h or _d_lower == "web.de"
            if _is_gmx or _is_webde:
                _prov = "GMX" if _is_gmx else "web.de"
                # FIX v6.7: probe direct connection to distinguish
                #   (A) proxy blocks STARTTLS  vs  (B) GMX SMTP disabled in settings
                # Both raise SMTPNotSupportedError, but the root cause is different.
                # Our tests (June 2026) showed GMX accounts work fine without proxy —
                # the proxy was silently breaking STARTTLS, causing AUTH to vanish from EHLO.
                _direct_tried_ports = [
                    (587, False, True),   # STARTTLS (standard GMX)
                    (465, True,  False),  # SSL
                ]
                for _dp, _ds, _dt in _direct_tried_ports:
                    try:
                        _ctx2 = _ssl.create_default_context()
                        if _ds:
                            _s2 = _smtplib.SMTP_SSL(host, _dp, timeout=10, context=_ctx2)
                        else:
                            _s2 = _smtplib.SMTP(host, _dp, timeout=10)
                            _s2.ehlo()
                            _s2.starttls(context=_ctx2)
                            _s2.ehlo()
                        _s2.login(account.email, account.password)
                        _s2.quit()
                        # Direct succeeds → proxy is the culprit
                        _via = f"{_proxy_parsed.scheme}://{_proxy_parsed.hostname}:{_proxy_parsed.port or port}" if _proxy_parsed else "без прокси"
                        account.port    = _dp
                        account.use_ssl = _ds
                        account.use_tls = _dt
                        return False, (
                            f"{_prov}: прокси ({_via}) блокирует SMTP STARTTLS — "
                            f"без прокси аккаунт работает нормально (порт {_dp}).\n"
                            "Прокси не поддерживает STARTTLS туннелирование (порт 587).\n"
                            "Решение: смените прокси (нужен SOCKS5 с TCP-поддержкой порта 587)."
                        )
                    except _smtplib.SMTPAuthenticationError as _e2:
                        _raw2 = _e2.smtp_error
                        _d2 = _raw2.decode("utf-8", "replace") if isinstance(_raw2, bytes) else str(_raw2)
                        return False, f"Неверный логин/пароль {_prov}: {_d2[:120]}"
                    except _smtplib.SMTPNotSupportedError:
                        continue  # try next port
                    except Exception:
                        continue  # connection error on this port, try next
                # All direct attempts also got SMTPNotSupportedError → GMX SMTP disabled
                return False, (
                    f"{_prov}: SMTP AUTH не поддерживается — SMTP-доступ ОТКЛЮЧЁН в настройках ящика.\n"
                    "Решение: войдите на gmx.com → Email (⚙ Settings) → POP3 & IMAP →\n"
                    "  включите «Send emails via Thunderbird, Outlook or another email client».\n"
                    "Пароль верный. SMTP отключён по умолчанию в GMX — включите вручную для каждого аккаунта."
                )
            return False, ("SMTP AUTH не поддерживается. Для Outlook/Hotmail — refresh_token. Для Gmail — App Password.")
        except _smtplib.SMTPException as ex:
            msg = str(ex)
            # FIX v6.1: 5.7.139 / 5.7.138 = Microsoft отключил Basic Auth.
            # Это политика сервера — порт тут не при чём. Возвращаем False,
            # чтобы остановить бессмысленный перебор 12 портов (экономим ~5 минут на 61 аккаунт).
            _ms_auth_disabled = (
                "5.7.139" in msg
                or "5.7.138" in msg
                or "basic authentication is disabled" in msg.lower()
                or "smtpclientauthentication is disabled" in msg.lower()
                or "client was not authenticated" in msg.lower()
            )
            if _ms_auth_disabled:
                return False, (
                    "Microsoft: SMTP AUTH отключён для этого ящика.\n"
                    "Решение:\n"
                    "  1. Outlook.com → Настройки → Почта → Синхронизация → включить SMTP AUTH\n"
                    "  2. Или добавьте refresh_token для OAuth2 (без Basic Auth)\n"
                    "Подробнее: https://aka.ms/smtp_auth_disabled"
                )
            # FIX v6.1: GMX/web.de — «временный сбой» может быть rate-limit.
            # Возвращаем None только для настоящих ошибок соединения.
            _is_temp = any(x in msg.lower() for x in ("421", "temporarily", "try again"))
            if _is_temp:
                return None, f"Временный отказ сервера (rate limit?): {msg[:100]}"
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
    _msg1 = msg  # FIX v5.2.3+: сохраняем тип ошибки Step 1

    # ── Шаг 2: та же конфигурация без cert-verify (self-signed SSL) ──────────
    ok, msg = _attempt(account.host, account.port, account.use_ssl, account.use_tls, verify=False)
    if ok is True:
        return True, msg
    if ok is False:
        return False, msg

    # FIX v5.2.3+: если прокси задан и обе попытки вернули SMTP-уровневую ошибку
    # (IP прокси заблокирован SMTP-сервером), перебор 12 портов через тот же прокси
    # бессмысленен — все провалятся, а это ~6-8 сек потерянного времени на аккаунт.
    # "SMTP:" = SMTPConnectError/SMTPServerDisconnected (сервер сбросил соединение).
    # "connect/" = OSError (порт закрыт на TCP) → тогда перебор портов осмысленен.
    _smtp_ip_blocked = bool(_proxy_parsed) and any(
        (m or "").startswith("SMTP:") for m in [_msg1, msg]
    )

    # ── Шаг 3: fallback — перебираем ВСЕ стандартные порты (и с прокси, и без) ─
    # Ошибка соединения на одном порту ≠ «прокси не работает» или «хост недоступен» —
    # нужно проверить 465/587/25/2525 прежде чем сдаваться.
    # При SMTP-блокировке IP через прокси — пропускаем (все порты дадут тот же результат).
    _combos = [
        (465,  True,  False),   # SMTPS  — SSL напрямую
        (587,  False, True),    # Submission — STARTTLS
        (25,   False, False),   # SMTP plain (большинство серверов)
        (2525, False, False),   # SMTP plain (альтернативный, часто открыт прокси)
        (465,  False, True),    # 465 + STARTTLS (нестандартно, но встречается)
        (587,  True,  False),   # 587 + SSL (нестандартно)
    ]
    _tried = {account.port}
    for _port, _ssl_flag, _tls_flag in ([] if _smtp_ip_blocked else _combos):
        if _port in _tried:
            continue
        _tried.add(_port)
        for _verify in (True, False):
            ok, msg = _attempt(account.host, _port, _ssl_flag, _tls_flag, verify=_verify)
            if ok is True:
                # Найдена рабочая конфигурация — обновляем аккаунт на месте, чтобы
                # последующие отправки сразу использовали правильный порт.
                account.port    = _port
                account.use_ssl = _ssl_flag
                account.use_tls = _tls_flag
                _pfx = f" через прокси {_proxy_parsed.hostname}" if _proxy_parsed else ""
                return True, f"{msg} [авто-порт {_port}{_pfx}]"
            if ok is False:
                # FIX v6.1 (code review): сохраняем оригинальное сообщение из _attempt
                # вместо шаблонного "Неверный логин/пароль" — может быть policy error.
                return False, msg

    # ── Шаг 4 (FIX v4.4.3): прямое подключение когда прокси-IP заблокирован ──
    # Если все попытки через прокси провалились (пустой SMTP-баннер = SMTP-сервер
    # немедленно закрыл соединение из-за репутации IP прокси), пробуем прямое
    # подключение. Это позволяет: а) убедиться что пароль верный, б) дать
    # информативное сообщение об ошибке ("прокси-IP заблокирован" vs "неверный пароль").
    if _proxy_parsed:
        for _dp, _ds, _dt in [(587, False, True), (465, True, False), (587, True, False)]:
            try:
                _dctx = _ssl.create_default_context()
                _dctx.check_hostname = False
                _dctx.verify_mode = _ssl.CERT_NONE
                if _ds:
                    _dc = _smtplib.SMTP_SSL(account.host, _dp, timeout=15, context=_dctx)
                else:
                    _dc = _smtplib.SMTP(account.host, _dp, timeout=15)
                    _dc.ehlo()
                    _dc.starttls(context=_dctx)
                    _dc.ehlo()
                if _is_oauth_acct:
                    _tok = _get_oauth_token(account) if _HAS_OAUTH2 else ""
                    if _tok:
                        _xo = _build_xoauth2(account.email, _tok)
                        _dc.docmd("AUTH", "XOAUTH2 " + _xo)
                    else:
                        _dc.login(account.email, account.password)
                else:
                    _dc.login(account.email, account.password)
                try: _dc.quit()
                except Exception: pass
                # Прямое подключение успешно → IP прокси заблокирован SMTP-сервером
                account.port    = _dp
                account.use_ssl = _ds
                account.use_tls = _dt
                return False, (
                    f"ПРОКСИ НЕ РАБОТАЕТ ДЛЯ РАССЫЛКИ: "
                    f"IP прокси {_proxy_parsed.hostname} заблокирован SMTP-сервером {account.host}. "
                    f"Пароль верный (прямое подключение OK), но через этот прокси отправка невозможна. "
                    f"Используйте SMTP-совместимый прокси (резидентный или мобильный)."
                )
            except _smtplib.SMTPAuthenticationError as _dae:
                _raw_e = _dae.smtp_error
                _de = _raw_e.decode("utf-8", "replace") if isinstance(_raw_e, bytes) else str(_raw_e)
                # FIX v5.2.3+: НЕ помечаем как «невалидный» когда прокси заблокирован.
                # Прямое подключение с нашего IP ненадёжно — Gmail отклоняет из-за
                # подозрительного IP ИЛИ требует App-пароль, даже если основной пароль верен.
                # Не включаем слова "неверный пароль"/"535" — иначе on_result пометит
                # аккаунт как невалидный вместо «ошибка прокси».
                if _dae.smtp_code == 534 or "application-specific" in _de.lower():
                    return False, (
                        f"Прокси-IP заблокирован SMTP-сервером. "
                        f"Для Gmail нужен App-пароль — создайте: Google Аккаунт → "
                        f"Безопасность → Двухэтапная аутентификация → Пароли приложений."
                    )
                return False, (
                    f"Прокси-IP заблокирован SMTP-сервером. "
                    f"Авторизация при прямом подключении также не удалась. "
                    f"Возможные причины: нужен App-пароль, или наш IP тоже заблокирован Google."
                )
            except Exception:
                continue

    _via = f" через прокси {_proxy_parsed.hostname}" if _proxy_parsed else ""
    _ports = ", ".join(str(p) for p in sorted(_tried))
    return False, (
        f"Не удалось подключиться к {account.host}{_via}. "
        f"Проверено портов: {_ports}. "
        f"IP прокси заблокирован SMTP-сервером — используйте резидентные прокси."
    )

async def test_smtp_connection(account: SmtpAccount) -> tuple[bool, str]:
  """
  Проверяет SMTP-подключение.
  Всегда использует надёжный smtplib через executor — избегаем несовместимости aiosmtplib версий.
  Все ошибки выводятся понятным пользователю языком.

  FIX v6.1: жёсткий таймаут 30 секунд на аккаунт.
  Без него _test_smtp_sync мог зависать на 7+ минут (14 попыток × 5-30s каждая).
  asyncio.wait_for отменяет Future со стороны event loop; поток завершится
  сам по своему socket timeout — утечки нет.
  """
  loop = asyncio.get_running_loop()
  try:
      return await asyncio.wait_for(
          loop.run_in_executor(None, _test_smtp_sync, account),
          timeout=30.0,
      )
  except asyncio.TimeoutError:
      host = getattr(account, "host", "?")
      return False, (
          f"Тайм-аут проверки (> 30 с). Сервер {host} не отвечает "
          f"или заблокирован провайдером/файрволом."
      )


class _SmtpConnectionCache:
  """Thread-safe per-(account, proxy) SMTP connection reuse pool.

  Uses checkout/checkin pattern so a connection is never used concurrently
  by two threads. Connections are recycled after MAX_REUSE sends or
  MAX_IDLE_SECS of idle time (servers close idle connections around 5-10 min).
  """
  MAX_REUSE = 50      # reconnect after this many sends per connection
  MAX_IDLE_SECS = 90  # recycle if idle > 90 s (safer than server 300 s limit)

  def __init__(self):
      self._lock = threading.Lock()
      # key → (smtp_conn, sent_count, last_used_ts)
      self._cache: dict[str, tuple] = {}

  @staticmethod
  def _key(account_email: str, proxy: str) -> str:
      return f"{account_email}::{proxy or 'direct'}"

  def checkout(self, account_email: str, proxy: str):
      """Remove and return (conn, count) if reusable, else None."""
      key = self._key(account_email, proxy)
      with self._lock:
          entry = self._cache.pop(key, None)
      if entry is None:
          return None
      conn, count, last_used = entry
      if count >= self.MAX_REUSE or (time.time() - last_used) > self.MAX_IDLE_SECS:
          try:
              conn.close()
          except Exception:
              pass
          return None
      return conn, count

  def checkin(self, account_email: str, proxy: str, conn, count: int) -> None:
      """Return conn to pool after successful use."""
      key = self._key(account_email, proxy)
      with self._lock:
          self._cache[key] = (conn, count + 1, time.time())

  def invalidate(self, account_email: str, proxy: str) -> None:
      """Discard cached connection for this key (e.g. after error)."""
      key = self._key(account_email, proxy)
      with self._lock:
          entry = self._cache.pop(key, None)
      if entry:
          try:
              entry[0].close()
          except Exception:
              pass

  def clear(self) -> None:
      with self._lock:
          entries, self._cache = list(self._cache.values()), {}
      for conn, _, _ in entries:
          try:
              conn.quit()
          except Exception:
              pass


# Per-destination-domain hourly send limits to prevent burst blocks.
# These are conservative limits per source IP/account.
_DOMAIN_HOURLY_LIMITS: dict[str, int] = {
    "gmail.com": 150,
    "googlemail.com": 150,
    "yahoo.com": 100,
    "ymail.com": 100,
    "rocketmail.com": 100,
    "aol.com": 100,
    "outlook.com": 120,
    "hotmail.com": 120,
    "hotmail.co.uk": 120,
    "hotmail.de": 120,
    "hotmail.fr": 120,
    "hotmail.ru": 120,
    "live.com": 120,
    "msn.com": 120,
    "gmx.com": 60,
    "gmx.net": 60,
    "gmx.de": 60,
    "web.de": 80,
    "yandex.ru": 100,
    "yandex.com": 100,
    "mail.ru": 100,
}
_DEFAULT_DOMAIN_HOURLY = 200


class _DomainRateLimiter:
  """Track per-destination-domain hourly send counts to prevent burst blocks.

  Gmail, Yahoo, Outlook all have implicit per-source-IP rate limits per
  destination. Exceeding them triggers 421 "try again later" or
  permanent blocks. This tracks sends per destination domain per hour
  and throttles when approaching limits.
  """

  def __init__(self):
      self._lock = threading.Lock()
      # domain → (sent_count, window_start_ts)
      self._counters: dict[str, tuple[int, float]] = {}

  def _get_limit(self, domain: str) -> int:
      return _DOMAIN_HOURLY_LIMITS.get(domain.lower(), _DEFAULT_DOMAIN_HOURLY)

  def can_send(self, destination_domain: str) -> bool:
      """Return True if we are within the hourly limit for this domain."""
      d = destination_domain.lower()
      limit = self._get_limit(d)
      with self._lock:
          count, start = self._counters.get(d, (0, time.time()))
          if time.time() - start >= 3600:
              self._counters[d] = (0, time.time())
              return True
          return count < limit

  def record(self, destination_domain: str) -> None:
      """Increment counter for this domain after a successful send."""
      d = destination_domain.lower()
      with self._lock:
          count, start = self._counters.get(d, (0, time.time()))
          if time.time() - start >= 3600:
              self._counters[d] = (1, time.time())
          else:
              self._counters[d] = (count + 1, start)

  def current_count(self, destination_domain: str) -> int:
      d = destination_domain.lower()
      with self._lock:
          count, start = self._counters.get(d, (0, time.time()))
          if time.time() - start >= 3600:
              return 0
          return count

  def reset(self) -> None:
      with self._lock:
          self._counters.clear()


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
      self._loop: Optional[asyncio.AbstractEventLoop] = None  # FIX v4.5.2: thread-safe cancel
      # Connection reuse pool: avoids new TLS handshake per email
      self._conn_cache = _SmtpConnectionCache()
      # Per-destination-domain rate limiter: prevents Gmail/Yahoo burst blocks
      self._domain_limiter = _DomainRateLimiter()
      # DKIM configs: loaded once, used to sign every outgoing message
      self._dkim_configs = _dkim_load_configs() if _HAS_DKIM_SIGNER else []

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
      # FIX v4.5.2: task.cancel() ОБЯЗАН выполняться в asyncio loop потоке.
      # Прямой вызов из Qt потока — race condition, CancelledError не доставляется.
      _loop = getattr(self, "_loop", None)
      task = getattr(self, "_campaign_task", None)
      if task is not None and not task.done():
          if _loop and not _loop.is_closed():
              try:
                  _loop.call_soon_threadsafe(task.cancel)
              except Exception as _exc:
                  logging.getLogger("sender").debug("E001 stop cancel: %s", _exc)
          else:
              try:
                  task.cancel()
              except Exception as _exc:
                  logging.getLogger("sender").debug("E001 stop fallback: %s", _exc)

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
      self._loop = asyncio.get_running_loop()  # FIX v6.0.4: get_event_loop() deprecated in coroutines (Python 3.10+)
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
          # ── Domain rate limiter: throttle per destination domain ──────────
          _dest_domain = recipient.email.split("@")[-1].lower() if "@" in recipient.email else ""
          _rate_wait = 0
          while not self._domain_limiter.can_send(_dest_domain):
              if self.stop_event.is_set():
                  return SendResult(recipient_email=recipient.email, success=False, error="Отменено")
              _rate_wait += 1
              if _rate_wait == 1 and self._log_queue:
                  _cnt = self._domain_limiter.current_count(_dest_domain)
                  _lim = _DOMAIN_HOURLY_LIMITS.get(_dest_domain, _DEFAULT_DOMAIN_HOURLY)
                  self._log_queue.put_nowait({"type": "log", "level": "warn", "message":
                      f"[{time.strftime('%H:%M:%S')}] Rate limit @{_dest_domain}: "
                      f"{_cnt}/{_lim}/hour — жду 30s..."})
              await asyncio.sleep(30)

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
                  self._domain_limiter.record(_dest_domain)
                  if _attempt > 0 and self._log_queue:
                      self._log_queue.put_nowait({"type": "log", "level": "ok", "message":
                          f"[{time.strftime('%H:%M:%S')}] {recipient.email}: успех с {account.email} (попытка {_attempt + 1})"})
                  return _result
              # FIX v4.5.3: откатываем инкремент при ошибке — лимит не сжигается впустую
              account.decrement_sent()
              _last_result = _result
              if _attempt < _MAX_RETRIES - 1 and self._log_queue:
                  self._log_queue.put_nowait({"type": "log", "level": "warn", "message":
                      f"[{time.strftime('%H:%M:%S')}] {recipient.email}: {_result.error[:120]} — пробую другой аккаунт..."})
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
          self._loop = None

      if self._log_queue:
          with self._stats_lock:
              _ok = self._stats.get("success", 0)
              _fail = self._stats.get("errors", 0)
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
      # DEAD CODE — этот метод никогда не вызывается.
      # _send_one всегда использует _send_sync через executor (прокси обязателен,
      # aiosmtplib не поддерживает SOCKS5). Оставлено для возможного будущего
      # использования в no-proxy режиме (currently disabled).
      try:
          import aiosmtplib as _aiosmtplib  # noqa: F401
      except ImportError:
          return await asyncio.get_running_loop().run_in_executor(
              None, self._send_sync, account, recipient, template
          )  # FIX C1: fallback на sync при отсутствии aiosmtplib
      msg = _build_message(account, recipient, template, uniqueize=self.config.uniqueize)
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
        """Синхронная отправка через прокси с полной ротацией пула.

        Алгоритм:
        1. Собирает список кандидатов: acc.proxy → acc.proxy_list (дедуп).
        2. Для каждого прокси пробует соединение + отправку.
        3. При сетевой/прокси-ошибке → логирует и переходит к следующему прокси.
        4. При ошибке аутентификации → возвращает ошибку немедленно (нет смысла
           пробовать другой прокси с теми же учётными данными).
        5. Если все прокси исчерпаны → возвращает сводную ошибку.
        """
        import ssl as _ssl_mod
        import urllib.parse as _urlparse
        msg = _build_message(account, recipient, template, uniqueize=self.config.uniqueize)

        # ── DKIM: sign bytes before sending ───────────────────────────────
        _sender_domain_dkim = account.email.split("@")[-1].lower() if "@" in account.email else ""
        _dkim_cfg_for_send = None
        if _HAS_DKIM_SIGNER and self._dkim_configs:
            _dkim_cfg_for_send = _dkim_get_cfg(_sender_domain_dkim, self._dkim_configs)

        def _smtp_send_signed(conn, _msg) -> None:
            """Send via SMTP, signing with DKIM if a config is available."""
            if _dkim_cfg_for_send:
                _raw = _dkim_sign(_msg.as_bytes(), _dkim_cfg_for_send)
                conn.sendmail(account.email, [recipient.email], _raw)
            else:
                conn.send_message(_msg)

        # ── Собираем пул прокси для ротации ───────────────────────────────
        _proxy_first = (account.proxy or "").strip()
        _proxy_pool  = list(getattr(account, "proxy_list", None) or [])
        _seen_px: set[str] = set()
        _candidates: list[str] = []
        for _px in ([_proxy_first] + _proxy_pool):
            _px = (_px or "").strip()
            if _px and _px not in _seen_px:
                _seen_px.add(_px)
                _candidates.append(_px)

        if not _candidates:
            return SendResult(
                recipient_email=recipient.email,
                success=False,
                error="Прокси не настроен — отправка без прокси заблокирована (защита IP клиента)",
                account_used=account.email,
            )

        _domain = account.email.split("@")[-1].lower() if "@" in account.email else ""
        _ms_domains = frozenset({
            "outlook.com","hotmail.com","live.com","msn.com","windowslive.com",
            "outlook.de","hotmail.de","live.de","outlook.fr","hotmail.fr","live.fr",
            "outlook.ru","hotmail.ru","live.ru","outlook.co.uk","hotmail.co.uk",
            "outlook.es","hotmail.es","outlook.it","hotmail.it","outlook.nl",
        })
        _last_err = "Нет доступных прокси"
        # FIX v5.2.3: счётчик ретраев SMTPServerDisconnected per-proxy (мобильные прокси ротируют IP)
        _sd_retry: dict[str, int] = {}

        # ── Основной цикл ротации ─────────────────────────────────────────
        for _proxy_candidate in _candidates:
            try:
                ctx = _ssl_mod.create_default_context()
                proxy_url = _proxy_candidate
                _proxy_auto_send = "://" not in proxy_url
                if _proxy_auto_send:
                    proxy_url = "socks5://" + proxy_url
                _p = _urlparse.urlparse(proxy_url)
                # ── SOCKS5 или HTTP CONNECT через raw stdlib-сокет ──────────
                _raw = _proxy_connect(
                    _p, account.host, account.port,
                    timeout=30.0,
                    auto_detect=_proxy_auto_send,
                )
                if account.use_ssl:
                    _raw_ssl2 = _raw
                    _ctx2 = ctx

                    class _SendProxySMTP_SSL(smtplib.SMTP_SSL):  # noqa: E501
                        def _get_socket(self, _h, _p, _t):
                            return _ctx2.wrap_socket(_raw_ssl2, server_hostname=_h)

                    smtp_conn = _SendProxySMTP_SSL(account.host, account.port, timeout=30, context=ctx)
                else:
                    _raw2 = _raw

                    class _SendProxySMTP(smtplib.SMTP):  # noqa: E501
                        def _get_socket(self, _h, _p, _t):
                            return _raw2

                    smtp_conn = _SendProxySMTP(account.host, account.port, timeout=30)
                    if account.use_tls:
                        smtp_conn.starttls(context=ctx)
                        smtp_conn.ehlo()
                _current_token = _get_oauth_token(account) if _HAS_OAUTH2 else getattr(account, "oauth_token", "")
                if _current_token and _domain in _ms_domains:
                    _xoauth2 = base64.b64encode(
                        ("user=" + account.email + "\x01auth=Bearer " +
                         _current_token + "\x01\x01").encode()
                    ).decode()
                    smtp_conn.docmd("AUTH", "XOAUTH2 " + _xoauth2)
                else:
                    smtp_conn.login(account.email, account.password)
                _smtp_send_signed(smtp_conn, msg)
                # Connection reuse: store instead of quit when pool is active
                _reuse_stored = False
                if hasattr(self, "_conn_cache"):
                    try:
                        self._conn_cache.checkin(account.email, _proxy_candidate, smtp_conn, 0)
                        _reuse_stored = True
                    except Exception:
                        pass
                if not _reuse_stored:
                    try:
                        smtp_conn.quit()
                    except Exception:
                        pass
                # Обновляем acc.proxy на рабочий прокси для следующей итерации
                if _proxy_candidate != (account.proxy or "").strip():
                    account.proxy = _proxy_candidate
                return SendResult(
                    recipient_email=recipient.email,
                    success=True,
                    account_used=account.email,
                    message_id=msg.get("Message-ID", ""),
                )

            except smtplib.SMTPAuthenticationError as _sae:
                # Неверные учётные данные — нет смысла пробовать другие прокси
                # FIX v4.5.6: правильные аргументы _parse_auth_error (раньше передавался объект исключения → TypeError)
                _sae_raw = _sae.smtp_error
                _sae_detail = (
                    _sae_raw.decode("utf-8", errors="replace")
                    if isinstance(_sae_raw, (bytes, bytearray))
                    else str(_sae_raw)
                )
                return SendResult(
                    recipient_email=recipient.email,
                    success=False,
                    error=_parse_auth_error(account.host, _sae.smtp_code, _sae_detail),
                    account_used=account.email,
                )

            except smtplib.SMTPConnectError as _sce:
                # -1 = SMTP banner пустой = SMTP-сервер заблокировал IP этого прокси
                _last_err = f"IP прокси {_p.hostname} заблокирован {account.host}: {_sce}"
                if self._log_queue and len(_candidates) > 1:
                    self._log_queue.put_nowait({"type": "log", "level": "warn", "message":
                        f"[{time.strftime('%H:%M:%S')}] {account.email}: {_p.hostname} заблокирован "
                        f"SMTP-сервером → пробуем следующий прокси"})
                continue  # → следующий прокси из пула

            except smtplib.SMTPServerDisconnected as _ssd:
                # SMTP-сервер сбросил соединение.
                # FIX v5.2.3: мобильные прокси ротируют IP при каждом подключении.
                # Повторяем тот же прокси до 2 раз (3 попытки итого) с задержкой 1.5с —
                # новый ротационный IP с высокой вероятностью не будет заблокирован.
                # Трекер _sd_retry[proxy] хранится вне объекта исключения
                # (исключение всегда новый объект при каждом attempt).
                _sd_n = _sd_retry.get(_proxy_candidate, 0)
                if _sd_n < 2:
                    _sd_retry[_proxy_candidate] = _sd_n + 1
                    if self._log_queue:
                        self._log_queue.put_nowait({"type": "log", "level": "warn", "message":
                            f"[{time.strftime('%H:%M:%S')}] {account.email}: "
                            f"сервер сбросил соединение через {_p.hostname} "
                            f"(попытка {_sd_n + 1}/3, жду IP-ротацию...)"})
                    time.sleep(1.5)
                    # Вставляем тот же прокси в позицию 0 — после continue итератор
                    # окажется на следующей позиции, которая теперь == тот же прокси.
                    _candidates.insert(0, _proxy_candidate)
                    continue
                _last_err = f"Прокси {_p.hostname} сброшен сервером: {_ssd}"
                if self._log_queue and len(_candidates) > 1:
                    self._log_queue.put_nowait({"type": "log", "level": "warn", "message":
                        f"[{time.strftime('%H:%M:%S')}] {account.email}: сервер сбросил "
                        f"соединение через {_p.hostname} → пробуем следующий прокси"})
                continue  # → следующий прокси из пула

            except OSError as _ose:
                _ose_msg = str(_ose)
                _is_socks_block = "SOCKS5" in _ose_msg and any(
                    x in _ose_msg for x in ("общий сбой", "запрещено", "код 1", "код 2")
                )
                if _is_socks_block:
                    # Прокси блокирует текущий порт → пробуем альт. порты ЧЕРЕЗ ТОТ ЖЕ прокси
                    _tried_ports = {account.port}
                    _port_worked = False
                    for _ap, _as, _at in [(465, True, False), (587, False, True), (2525, False, True)]:
                        if _ap in _tried_ports:
                            continue
                        _tried_ports.add(_ap)
                        try:
                            _alt_raw = _proxy_connect(_p, account.host, _ap, timeout=15.0,
                                                      auto_detect=_proxy_auto_send)
                            _alt_ctx = _ssl_mod.create_default_context()
                            _alt_ctx.check_hostname = False
                            _alt_ctx.verify_mode = _ssl_mod.CERT_NONE
                            def _make_alt_ssl(rs, cs):
                                class _C(smtplib.SMTP_SSL):
                                    def _get_socket(self, h, p2, t2): return cs.wrap_socket(rs, server_hostname=h)
                                return _C
                            def _make_alt_plain(rs):
                                class _C(smtplib.SMTP):
                                    def _get_socket(self, h, p2, t2): return rs
                                return _C
                            _alt_conn = (
                                _make_alt_ssl(_alt_raw, _alt_ctx)(account.host, _ap, timeout=30, context=_alt_ctx)
                                if _as else _make_alt_plain(_alt_raw)(account.host, _ap, timeout=30)
                            )
                            if not _as and _at:
                                _alt_conn.starttls(context=_alt_ctx); _alt_conn.ehlo()
                            _tok2 = _get_oauth_token(account) if _HAS_OAUTH2 else getattr(account, "oauth_token", "")
                            _ms2  = frozenset({"outlook.com","hotmail.com","live.com","msn.com","windowslive.com"})
                            _dom2 = account.email.split("@")[-1].lower() if "@" in account.email else ""
                            if _tok2 and _dom2 in _ms2:
                                _alt_conn.docmd("AUTH", "XOAUTH2 " + base64.b64encode(
                                    ("user=" + account.email + "\x01auth=Bearer " + _tok2 + "\x01\x01").encode()
                                ).decode())
                            else:
                                _alt_conn.login(account.email, account.password)
                            _smtp_send_signed(_alt_conn, msg)
                            try: _alt_conn.quit()
                            except Exception: pass
                            account.port = _ap; account.use_ssl = _as; account.use_tls = _at
                            _port_worked = True
                            return SendResult(
                                recipient_email=recipient.email, success=True,
                                account_used=account.email, message_id=msg.get("Message-ID", ""),
                            )
                        except smtplib.SMTPAuthenticationError as _sae_alt:
                            # FIX v4.5.6: decode smtp_error bytes properly (was !r:.120 — invalid format spec)
                            _alt_raw = _sae_alt.smtp_error
                            _alt_detail = (
                                _alt_raw.decode("utf-8", errors="replace")
                                if isinstance(_alt_raw, (bytes, bytearray))
                                else str(_alt_raw)
                            )
                            return SendResult(
                                recipient_email=recipient.email, success=False,
                                error=_parse_auth_error(account.host, _sae_alt.smtp_code, _alt_detail),
                                account_used=account.email,
                            )
                        except Exception:
                            continue
                    if not _port_worked:
                        # Все порты на этом прокси провалились → следующий прокси
                        _last_err = f"Прокси {_p.hostname} блокирует все SMTP-порты ({_ose_msg[:80]})"
                        if self._log_queue and len(_candidates) > 1:
                            self._log_queue.put_nowait({"type": "log", "level": "warn", "message":
                                f"[{time.strftime('%H:%M:%S')}] {account.email}: {_p.hostname} блокирует "
                                f"все SMTP-порты → пробуем следующий прокси"})
                        continue  # → следующий прокси из пула
                else:
                      # FIX v5.1: SSL-таймаут на 465 → 587 STARTTLS через тот же прокси
                      _is_ssl_timeout = (
                          account.use_ssl and account.port == 465 and
                          any(x in _ose_msg.lower() for x in ("handshake", "ssl", "timed out", "eof"))
                      )
                      if _is_ssl_timeout:
                          if self._log_queue:
                              self._log_queue.put_nowait({"type": "log", "level": "warn", "message":
                                  f"[{time.strftime('%H:%M:%S')}] {account.email}: port 465 SSL недоступен"
                                  f" через прокси — автоматически переключаюсь на 587 STARTTLS"})
                          try:
                              _s587_raw = _proxy_connect(_p, account.host, 587, timeout=30.0,
                                                         auto_detect=_proxy_auto_send)
                              _s587_ctx = _ssl_mod.create_default_context()
                              _s587_ctx.check_hostname = False
                              _s587_ctx.verify_mode = _ssl_mod.CERT_NONE
                              _s587_r = _s587_raw
                              def _make_s587(rs):
                                  class _C587(smtplib.SMTP):
                                      def _get_socket(self, h, p2, t2): return rs
                                  return _C587
                              _s587_conn = _make_s587(_s587_r)(account.host, 587, timeout=30)
                              _s587_conn.ehlo()
                              _s587_conn.starttls(context=_s587_ctx)
                              _s587_conn.ehlo()
                              _tok587 = _get_oauth_token(account) if _HAS_OAUTH2 else getattr(account, "oauth_token", "")
                              _ms587 = frozenset({"outlook.com","hotmail.com","live.com","msn.com","windowslive.com",
                                                   "outlook.de","hotmail.de","live.de","outlook.fr","hotmail.fr",
                                                   "outlook.ru","hotmail.ru","live.ru"})
                              _dom587 = account.email.split("@")[-1].lower() if "@" in account.email else ""
                              if _tok587 and _dom587 in _ms587:
                                  _s587_conn.docmd("AUTH", "XOAUTH2 " + base64.b64encode(
                                      ("user=" + account.email + "\x01auth=Bearer " + _tok587 + "\x01\x01").encode()
                                  ).decode())
                              else:
                                  _s587_conn.login(account.email, account.password)
                              _smtp_send_signed(_s587_conn, msg)
                              try: _s587_conn.quit()
                              except Exception: pass
                              account.port = 587; account.use_ssl = False; account.use_tls = True
                              return SendResult(
                                  recipient_email=recipient.email, success=True,
                                  account_used=account.email, message_id=msg.get("Message-ID", ""),
                              )
                          except smtplib.SMTPAuthenticationError as _s587_ae:
                              _re587 = _s587_ae.smtp_error
                              _de587 = _re587.decode("utf-8", "replace") if isinstance(_re587, bytes) else str(_re587)
                              _last_err = f"AUTH 587: {_de587[:120]}"
                          except Exception as _s587_e:
                              _last_err = f"587 STARTTLS: {str(_s587_e)[:100]}"
                          continue
                      # Сетевая ошибка (таймаут, отказ TCP) → следующий прокси
                      _last_err = f"Сетевая ошибка через {_p.hostname}: {_ose_msg[:100]}"
                      if self._log_queue and len(_candidates) > 1:
                          self._log_queue.put_nowait({"type": "log", "level": "warn", "message":
                              f"[{time.strftime('%H:%M:%S')}] {account.email}: ошибка прокси "
                              f"{_p.hostname}: {_ose_msg[:60]} → пробуем следующий"})
                      continue  # → следующий прокси из пула

            except Exception as _any:
                _last_err = str(_any)[:120]
                continue  # → следующий прокси из пула

        # конец for _proxy_candidate

        # ── Все прокси исчерпаны ───────────────────────────────────────────
        _n = len(_candidates)
        return SendResult(
            recipient_email=recipient.email,
            success=False,
            error=(
                f"Все {_n} {'прокси' if _n == 1 else 'прокси из пула'} провалились. "
                f"Последняя ошибка: {_last_err}"
            ),
            account_used=account.email,
        )