"""
FMailSender core sending engine v2.9.1.
Fixes: IndentationError in increment_sent/try_increment/Recipient,
       async parallelism (delay moved inside task wrapper),
       duplicate params documented, race condition eliminated via try_increment.
"""
from __future__ import annotations

import asyncio
import mimetypes
import queue
import random
import re
import smtplib
import threading
import time
import uuid
from dataclasses import dataclass, field
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Callable, List, Optional

try:
    import aiosmtplib
    _HAS_AIOSMTPLIB = True
except ImportError:
    _HAS_AIOSMTPLIB = False


_SMTP_CONFIGS: dict[str, dict] = {
    "gmail.com": {"host": "smtp.gmail.com", "port": 465, "use_ssl": True, "use_tls": False},
    "googlemail.com": {"host": "smtp.gmail.com", "port": 465, "use_ssl": True, "use_tls": False},
    "outlook.com": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.co.uk": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.fr": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.de": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.com.br": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.com.au": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.es": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.it": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.jp": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.co.nz": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.ie": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.at": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.be": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.nl": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.pt": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.cz": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.sk": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.pl": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.hu": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.gr": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.com.tr": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.com.vn": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.co.id": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.com.ph": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.my": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.sg": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.co.th": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.co.il": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.sa": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.ae": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.com.mx": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.cl": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.com.ar": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.co.za": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.co.ke": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.com.ng": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.co.in": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.lv": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.lt": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.ee": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.com.pk": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.com.eg": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.rs": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "outlook.com.ua": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.com": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.co.uk": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.fr": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.de": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.it": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.es": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.com.au": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.ca": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.com.br": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.nl": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.be": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.co.jp": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.co.in": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.se": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.no": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.dk": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.fi": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.com.tr": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.com.mx": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.com.ar": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.cl": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.co.za": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.gr": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.ro": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.hu": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.pl": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.cz": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.sk": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.pt": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.ie": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.at": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.com.co": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.com.pe": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.co.nz": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.co.id": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.my": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.sg": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.com.eg": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.co.il": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.rs": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.com": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.co.uk": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.fr": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.de": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.it": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.es": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.com.au": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.ca": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.in": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.com.ar": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.com.mx": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.com.br": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.com.sg": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.co.za": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.nl": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.se": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.no": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.dk": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.fi": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.be": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.at": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.ie": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.co.nz": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.co.in": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.jp": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.com.tr": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.gr": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.ro": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.hu": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.pl": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.com.ph": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.co.id": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.my": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.co.th": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.com.vn": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.co.il": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "msn.com": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "windowslive.com": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "yahoo.com": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.co.uk": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.fr": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.de": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.it": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.es": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.com.au": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.co.jp": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.co.in": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.com.br": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.ca": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.com.mx": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.com.ar": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.com.sg": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.co.nz": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.co.za": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.co.id": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.com.ph": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.com.vn": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.com.tw": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.gr": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.ro": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.dk": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.se": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.no": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.fi": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.ie": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.at": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.be": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.nl": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.pl": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.pt": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.hu": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.sk": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.cz": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.com.co": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.com.pe": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.com.ve": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.com.hk": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.com.my": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.com.tr": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.co.th": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.com.eg": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.co.il": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.ae": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.com.pk": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.com.ng": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.co.ke": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yahoo.com.sa": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "ymail.com": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "rocketmail.com": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "icloud.com": {"host": "smtp.mail.me.com", "port": 587, "use_ssl": False, "use_tls": True},
    "me.com": {"host": "smtp.mail.me.com", "port": 587, "use_ssl": False, "use_tls": True},
    "mac.com": {"host": "smtp.mail.me.com", "port": 587, "use_ssl": False, "use_tls": True},
    "aol.com": {"host": "smtp.aol.com", "port": 465, "use_ssl": True, "use_tls": False},
    "aim.com": {"host": "smtp.aol.com", "port": 465, "use_ssl": True, "use_tls": False},
    "netscape.net": {"host": "smtp.aol.com", "port": 465, "use_ssl": True, "use_tls": False},
    "compuserve.com": {"host": "smtp.aol.com", "port": 465, "use_ssl": True, "use_tls": False},
    "verizon.net": {"host": "outgoing.verizon.net", "port": 465, "use_ssl": True, "use_tls": False},
    "att.net": {"host": "smtp.att.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "sbcglobal.net": {"host": "smtp.att.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "bellsouth.net": {"host": "smtp.att.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "ameritech.net": {"host": "smtp.att.yahoo.com", "port": 465, "use_ssl": True, "use_tls": False},
    "cs.com": {"host": "smtp.cs.com", "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.com": {"host": "mail.gmx.com", "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.net": {"host": "mail.gmx.net", "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.de": {"host": "mail.gmx.net", "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.at": {"host": "mail.gmx.net", "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.ch": {"host": "mail.gmx.net", "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.li": {"host": "mail.gmx.net", "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.info": {"host": "mail.gmx.net", "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.biz": {"host": "mail.gmx.net", "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.org": {"host": "mail.gmx.net", "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.co.uk": {"host": "mail.gmx.com", "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.es": {"host": "mail.gmx.net", "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.fr": {"host": "mail.gmx.net", "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.it": {"host": "mail.gmx.net", "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.nl": {"host": "mail.gmx.net", "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.be": {"host": "mail.gmx.net", "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.pt": {"host": "mail.gmx.net", "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.pl": {"host": "mail.gmx.net", "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.ro": {"host": "mail.gmx.net", "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.hu": {"host": "mail.gmx.net", "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.se": {"host": "mail.gmx.net", "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.dk": {"host": "mail.gmx.net", "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.no": {"host": "mail.gmx.net", "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.fi": {"host": "mail.gmx.net", "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.gr": {"host": "mail.gmx.net", "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.cz": {"host": "mail.gmx.net", "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.sk": {"host": "mail.gmx.net", "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.ie": {"host": "mail.gmx.net", "port": 587, "use_ssl": False, "use_tls": True},
    "zoho.com": {"host": "smtp.zoho.com", "port": 465, "use_ssl": True, "use_tls": False},
    "zohomail.com": {"host": "smtp.zoho.com", "port": 465, "use_ssl": True, "use_tls": False},
    "zoho.eu": {"host": "smtp.zoho.eu", "port": 465, "use_ssl": True, "use_tls": False},
    "zoho.in": {"host": "smtp.zoho.com", "port": 465, "use_ssl": True, "use_tls": False},
    "zohomail.eu": {"host": "smtp.zoho.eu", "port": 465, "use_ssl": True, "use_tls": False},
    "mail.ru": {"host": "smtp.mail.ru", "port": 465, "use_ssl": True, "use_tls": False},
    "inbox.ru": {"host": "smtp.mail.ru", "port": 465, "use_ssl": True, "use_tls": False},
    "list.ru": {"host": "smtp.mail.ru", "port": 465, "use_ssl": True, "use_tls": False},
    "bk.ru": {"host": "smtp.mail.ru", "port": 465, "use_ssl": True, "use_tls": False},
    "internet.ru": {"host": "smtp.mail.ru", "port": 465, "use_ssl": True, "use_tls": False},
    "mail.ua": {"host": "smtp.mail.ru", "port": 465, "use_ssl": True, "use_tls": False},
    "ro.ru": {"host": "smtp.mail.ru", "port": 465, "use_ssl": True, "use_tls": False},
    "yandex.ru": {"host": "smtp.yandex.ru", "port": 465, "use_ssl": True, "use_tls": False},
    "yandex.com": {"host": "smtp.yandex.com", "port": 465, "use_ssl": True, "use_tls": False},
    "ya.ru": {"host": "smtp.yandex.ru", "port": 465, "use_ssl": True, "use_tls": False},
    "yandex.ua": {"host": "smtp.yandex.ru", "port": 465, "use_ssl": True, "use_tls": False},
    "yandex.by": {"host": "smtp.yandex.by", "port": 465, "use_ssl": True, "use_tls": False},
    "yandex.kz": {"host": "smtp.yandex.ru", "port": 465, "use_ssl": True, "use_tls": False},
    "rambler.ru": {"host": "smtp.rambler.ru", "port": 465, "use_ssl": True, "use_tls": False},
    "lenta.ru": {"host": "smtp.rambler.ru", "port": 465, "use_ssl": True, "use_tls": False},
    "autorambler.ru": {"host": "smtp.rambler.ru", "port": 465, "use_ssl": True, "use_tls": False},
    "myrambler.ru": {"host": "smtp.rambler.ru", "port": 465, "use_ssl": True, "use_tls": False},
    "i.ua": {"host": "smtp.i.ua", "port": 465, "use_ssl": True, "use_tls": False},
    "ukr.net": {"host": "smtp.ukr.net", "port": 465, "use_ssl": True, "use_tls": False},
    "meta.ua": {"host": "smtp.meta.ua", "port": 465, "use_ssl": True, "use_tls": False},
    "bigmir.net": {"host": "smtp.bigmir.net", "port": 465, "use_ssl": True, "use_tls": False},
    "email.ua": {"host": "smtp.email.ua", "port": 465, "use_ssl": True, "use_tls": False},
    "inbox.lv": {"host": "smtp.inbox.lv", "port": 465, "use_ssl": True, "use_tls": False},
    "mail.lt": {"host": "smtp.mail.lt", "port": 465, "use_ssl": True, "use_tls": False},
    "web.de": {"host": "smtp.web.de", "port": 587, "use_ssl": False, "use_tls": True},
    "freenet.de": {"host": "mx.freenet.de", "port": 587, "use_ssl": False, "use_tls": True},
    "t-online.de": {"host": "securesmtp.t-online.de", "port": 465, "use_ssl": True, "use_tls": False},
    "telekom.de": {"host": "securesmtp.t-online.de", "port": 465, "use_ssl": True, "use_tls": False},
    "arcor.de": {"host": "smtp.arcor.de", "port": 465, "use_ssl": True, "use_tls": False},
    "kabelbw.de": {"host": "smtp.kabelbw.de", "port": 587, "use_ssl": False, "use_tls": True},
    "vodafone.de": {"host": "smtp.vodafone.de", "port": 465, "use_ssl": True, "use_tls": False},
    "o2online.de": {"host": "smtp.o2online.de", "port": 465, "use_ssl": True, "use_tls": False},
    "mailbox.org": {"host": "smtp.mailbox.org", "port": 465, "use_ssl": True, "use_tls": False},
    "posteo.de": {"host": "posteo.de", "port": 587, "use_ssl": False, "use_tls": True},
    "posteo.net": {"host": "posteo.de", "port": 587, "use_ssl": False, "use_tls": True},
    "strato.de": {"host": "smtp.strato.de", "port": 465, "use_ssl": True, "use_tls": False},
    "strato.com": {"host": "smtp.strato.de", "port": 465, "use_ssl": True, "use_tls": False},
    "ionos.de": {"host": "smtp.ionos.de", "port": 465, "use_ssl": True, "use_tls": False},
    "1und1.de": {"host": "smtp.1and1.com", "port": 587, "use_ssl": False, "use_tls": True},
    "1and1.com": {"host": "smtp.1and1.com", "port": 587, "use_ssl": False, "use_tls": True},
    "lycos.de": {"host": "smtp.lycos.de", "port": 465, "use_ssl": True, "use_tls": False},
    "netcologne.de": {"host": "smtp.netcologne.de", "port": 587, "use_ssl": False, "use_tls": True},
    "unitymedia.de": {"host": "smtp.unitymedia.de", "port": 587, "use_ssl": False, "use_tls": True},
    "kabel.de": {"host": "smtp.kabel.de", "port": 587, "use_ssl": False, "use_tls": True},
    "orange.fr": {"host": "smtp.orange.fr", "port": 465, "use_ssl": True, "use_tls": False},
    "wanadoo.fr": {"host": "smtp.orange.fr", "port": 465, "use_ssl": True, "use_tls": False},
    "free.fr": {"host": "smtp.free.fr", "port": 465, "use_ssl": True, "use_tls": False},
    "sfr.fr": {"host": "smtp.sfr.fr", "port": 465, "use_ssl": True, "use_tls": False},
    "laposte.net": {"host": "smtp.laposte.net", "port": 465, "use_ssl": True, "use_tls": False},
    "bbox.fr": {"host": "smtp.bbox.fr", "port": 465, "use_ssl": True, "use_tls": False},
    "neuf.fr": {"host": "smtp.neuf.fr", "port": 465, "use_ssl": True, "use_tls": False},
    "cegetel.fr": {"host": "smtp.cegetel.fr", "port": 465, "use_ssl": True, "use_tls": False},
    "numericable.fr": {"host": "smtp.numericable.fr", "port": 587, "use_ssl": False, "use_tls": True},
    "club-internet.fr": {"host": "smtp.club-internet.fr", "port": 465, "use_ssl": True, "use_tls": False},
    "aliceadsl.fr": {"host": "smtp.aliceadsl.fr", "port": 587, "use_ssl": False, "use_tls": True},
    "voila.fr": {"host": "smtp.orange.fr", "port": 465, "use_ssl": True, "use_tls": False},
    "noos.fr": {"host": "smtp.noos.fr", "port": 465, "use_ssl": True, "use_tls": False},
    "btinternet.com": {"host": "smtp.btinternet.com", "port": 465, "use_ssl": True, "use_tls": False},
    "btopenworld.com": {"host": "smtp.btinternet.com", "port": 465, "use_ssl": True, "use_tls": False},
    "talk21.com": {"host": "smtp.btinternet.com", "port": 465, "use_ssl": True, "use_tls": False},
    "sky.com": {"host": "smtp.sky.com", "port": 587, "use_ssl": False, "use_tls": True},
    "virginmedia.com": {"host": "smtp.virginmedia.com", "port": 465, "use_ssl": True, "use_tls": False},
    "ntlworld.com": {"host": "smtp.ntlworld.com", "port": 465, "use_ssl": True, "use_tls": False},
    "blueyonder.co.uk": {"host": "smtp.blueyonder.co.uk", "port": 465, "use_ssl": True, "use_tls": False},
    "tiscali.co.uk": {"host": "smtp.tiscali.co.uk", "port": 465, "use_ssl": True, "use_tls": False},
    "o2.co.uk": {"host": "smtp.o2.co.uk", "port": 587, "use_ssl": False, "use_tls": True},
    "talktalk.net": {"host": "smtp.talktalk.net", "port": 587, "use_ssl": False, "use_tls": True},
    "plus.net": {"host": "smtp.plus.net", "port": 587, "use_ssl": False, "use_tls": True},
    "ic24.net": {"host": "smtp.btinternet.com", "port": 465, "use_ssl": True, "use_tls": False},
    "fsmail.net": {"host": "smtp.fsmail.net", "port": 587, "use_ssl": False, "use_tls": True},
    "libero.it": {"host": "smtp.libero.it", "port": 465, "use_ssl": True, "use_tls": False},
    "virgilio.it": {"host": "smtp.virgilio.it", "port": 465, "use_ssl": True, "use_tls": False},
    "alice.it": {"host": "smtp.alice.it", "port": 465, "use_ssl": True, "use_tls": False},
    "tim.it": {"host": "smtp.tim.it", "port": 465, "use_ssl": True, "use_tls": False},
    "tiscali.it": {"host": "smtp.tiscali.it", "port": 465, "use_ssl": True, "use_tls": False},
    "fastwebnet.it": {"host": "smtp.fastwebnet.it", "port": 465, "use_ssl": True, "use_tls": False},
    "poste.it": {"host": "smtp.poste.it", "port": 465, "use_ssl": True, "use_tls": False},
    "tin.it": {"host": "smtp.tin.it", "port": 465, "use_ssl": True, "use_tls": False},
    "inwind.it": {"host": "smtp.inwind.it", "port": 465, "use_ssl": True, "use_tls": False},
    "email.it": {"host": "smtp.email.it", "port": 465, "use_ssl": True, "use_tls": False},
    "wind.it": {"host": "smtp.wind.it", "port": 465, "use_ssl": True, "use_tls": False},
    "vodafone.it": {"host": "smtp.vodafone.it", "port": 465, "use_ssl": True, "use_tls": False},
    "terra.es": {"host": "smtp.movistar.es", "port": 465, "use_ssl": True, "use_tls": False},
    "telefonica.net": {"host": "smtp.movistar.es", "port": 465, "use_ssl": True, "use_tls": False},
    "movistar.es": {"host": "smtp.movistar.es", "port": 465, "use_ssl": True, "use_tls": False},
    "orange.es": {"host": "smtp.orange.es", "port": 465, "use_ssl": True, "use_tls": False},
    "jazztel.es": {"host": "smtp.jazztel.es", "port": 465, "use_ssl": True, "use_tls": False},
    "ono.com": {"host": "smtp.ono.com", "port": 465, "use_ssl": True, "use_tls": False},
    "vodafone.es": {"host": "smtp.vodafone.es", "port": 465, "use_ssl": True, "use_tls": False},
    "ya.com": {"host": "smtp.ya.com", "port": 465, "use_ssl": True, "use_tls": False},
    "xs4all.nl": {"host": "smtp.xs4all.nl", "port": 465, "use_ssl": True, "use_tls": False},
    "hetnet.nl": {"host": "smtp.xs4all.nl", "port": 465, "use_ssl": True, "use_tls": False},
    "chello.nl": {"host": "smtp.chello.nl", "port": 465, "use_ssl": True, "use_tls": False},
    "planet.nl": {"host": "smtp.chello.nl", "port": 465, "use_ssl": True, "use_tls": False},
    "telfort.nl": {"host": "smtp.telfort.nl", "port": 587, "use_ssl": False, "use_tls": True},
    "ziggo.nl": {"host": "smtp.ziggo.nl", "port": 587, "use_ssl": False, "use_tls": True},
    "kpnmail.nl": {"host": "smtp.kpnmail.nl", "port": 587, "use_ssl": False, "use_tls": True},
    "upcmail.nl": {"host": "smtp.upcmail.nl", "port": 587, "use_ssl": False, "use_tls": True},
    "skynet.be": {"host": "smtp.skynet.be", "port": 465, "use_ssl": True, "use_tls": False},
    "proximus.be": {"host": "smtp.proximus.be", "port": 587, "use_ssl": False, "use_tls": True},
    "telenet.be": {"host": "smtp.telenet.be", "port": 587, "use_ssl": False, "use_tls": True},
    "scarlet.be": {"host": "smtp.scarlet.be", "port": 465, "use_ssl": True, "use_tls": False},
    "belgacom.be": {"host": "smtp.proximus.be", "port": 587, "use_ssl": False, "use_tls": True},
    "wp.pl": {"host": "smtp.wp.pl", "port": 465, "use_ssl": True, "use_tls": False},
    "onet.pl": {"host": "smtp.poczta.onet.pl", "port": 465, "use_ssl": True, "use_tls": False},
    "poczta.onet.pl": {"host": "smtp.poczta.onet.pl", "port": 465, "use_ssl": True, "use_tls": False},
    "interia.pl": {"host": "poczta.interia.pl", "port": 465, "use_ssl": True, "use_tls": False},
    "o2.pl": {"host": "smtp.o2.pl", "port": 465, "use_ssl": True, "use_tls": False},
    "gazeta.pl": {"host": "smtp.gazeta.pl", "port": 465, "use_ssl": True, "use_tls": False},
    "tlen.pl": {"host": "smtp.tlen.pl", "port": 465, "use_ssl": True, "use_tls": False},
    "vp.pl": {"host": "smtp.vp.pl", "port": 465, "use_ssl": True, "use_tls": False},
    "poczta.fm": {"host": "smtp.poczta.fm", "port": 465, "use_ssl": True, "use_tls": False},
    "op.pl": {"host": "smtp.op.pl", "port": 465, "use_ssl": True, "use_tls": False},
    "go2.pl": {"host": "smtp.go2.pl", "port": 465, "use_ssl": True, "use_tls": False},
    "seznam.cz": {"host": "smtp.seznam.cz", "port": 465, "use_ssl": True, "use_tls": False},
    "centrum.cz": {"host": "smtp.centrum.cz", "port": 465, "use_ssl": True, "use_tls": False},
    "atlas.cz": {"host": "smtp.atlas.cz", "port": 465, "use_ssl": True, "use_tls": False},
    "email.cz": {"host": "smtp.email.cz", "port": 465, "use_ssl": True, "use_tls": False},
    "post.cz": {"host": "smtp.post.cz", "port": 465, "use_ssl": True, "use_tls": False},
    "volny.cz": {"host": "smtp.volny.cz", "port": 465, "use_ssl": True, "use_tls": False},
    "zoznam.sk": {"host": "smtp.zoznam.sk", "port": 465, "use_ssl": True, "use_tls": False},
    "centrum.sk": {"host": "smtp.centrum.sk", "port": 465, "use_ssl": True, "use_tls": False},
    "atlas.sk": {"host": "smtp.atlas.sk", "port": 465, "use_ssl": True, "use_tls": False},
    "azet.sk": {"host": "smtp.azet.sk", "port": 465, "use_ssl": True, "use_tls": False},
    "freemail.hu": {"host": "smtp.freemail.hu", "port": 465, "use_ssl": True, "use_tls": False},
    "citromail.hu": {"host": "smtp.citromail.hu", "port": 587, "use_ssl": False, "use_tls": True},
    "indamail.hu": {"host": "smtp.indamail.hu", "port": 465, "use_ssl": True, "use_tls": False},
    "rdslink.ro": {"host": "smtp.rdslink.ro", "port": 465, "use_ssl": True, "use_tls": False},
    "digi.ro": {"host": "smtp.digi.ro", "port": 587, "use_ssl": False, "use_tls": True},
    "spray.se": {"host": "smtp.spray.se", "port": 465, "use_ssl": True, "use_tls": False},
    "telia.com": {"host": "smtp.telia.com", "port": 587, "use_ssl": False, "use_tls": True},
    "bredband.net": {"host": "smtp.bredband.net", "port": 465, "use_ssl": True, "use_tls": False},
    "tele2.se": {"host": "smtp.tele2.se", "port": 465, "use_ssl": True, "use_tls": False},
    "comhem.se": {"host": "smtp.comhem.se", "port": 587, "use_ssl": False, "use_tls": True},
    "passagen.se": {"host": "smtp.passagen.se", "port": 465, "use_ssl": True, "use_tls": False},
    "online.no": {"host": "smtp.online.no", "port": 465, "use_ssl": True, "use_tls": False},
    "start.no": {"host": "smtp.online.no", "port": 465, "use_ssl": True, "use_tls": False},
    "frisurf.no": {"host": "smtp.frisurf.no", "port": 465, "use_ssl": True, "use_tls": False},
    "telenor.no": {"host": "smtp.telenor.no", "port": 587, "use_ssl": False, "use_tls": True},
    "tdc.dk": {"host": "smtp.tdc.dk", "port": 465, "use_ssl": True, "use_tls": False},
    "post.dk": {"host": "smtp.tdc.dk", "port": 465, "use_ssl": True, "use_tls": False},
    "stofanet.dk": {"host": "smtp.stofanet.dk", "port": 587, "use_ssl": False, "use_tls": True},
    "jubii.dk": {"host": "smtp.jubii.dk", "port": 465, "use_ssl": True, "use_tls": False},
    "luukku.com": {"host": "smtp.luukku.com", "port": 465, "use_ssl": True, "use_tls": False},
    "welho.com": {"host": "smtp.welho.com", "port": 465, "use_ssl": True, "use_tls": False},
    "saunalahti.fi": {"host": "smtp.saunalahti.fi", "port": 465, "use_ssl": True, "use_tls": False},
    "elisa.fi": {"host": "smtp.elisa.fi", "port": 465, "use_ssl": True, "use_tls": False},
    "bluewin.ch": {"host": "smtp.bluewin.ch", "port": 465, "use_ssl": True, "use_tls": False},
    "sunrise.ch": {"host": "smtp.sunrise.ch", "port": 465, "use_ssl": True, "use_tls": False},
    "swisscom.ch": {"host": "smtp.swisscom.ch", "port": 587, "use_ssl": False, "use_tls": True},
    "hispeed.ch": {"host": "smtp.hispeed.ch", "port": 587, "use_ssl": False, "use_tls": True},
    "infomaniak.com": {"host": "mail.infomaniak.com", "port": 465, "use_ssl": True, "use_tls": False},
    "infomaniak.ch": {"host": "mail.infomaniak.com", "port": 465, "use_ssl": True, "use_tls": False},
    "aon.at": {"host": "smtp.aon.at", "port": 465, "use_ssl": True, "use_tls": False},
    "chello.at": {"host": "smtp.chello.at", "port": 587, "use_ssl": False, "use_tls": True},
    "a1.net": {"host": "smtp.a1.net", "port": 465, "use_ssl": True, "use_tls": False},
    "drei.at": {"host": "smtp.drei.at", "port": 587, "use_ssl": False, "use_tls": True},
    "sapo.pt": {"host": "smtp.sapo.pt", "port": 465, "use_ssl": True, "use_tls": False},
    "clix.pt": {"host": "smtp.clix.pt", "port": 465, "use_ssl": True, "use_tls": False},
    "netcabo.pt": {"host": "smtp.netcabo.pt", "port": 465, "use_ssl": True, "use_tls": False},
    "iol.pt": {"host": "smtp.iol.pt", "port": 465, "use_ssl": True, "use_tls": False},
    "forthnet.gr": {"host": "smtp.forthnet.gr", "port": 465, "use_ssl": True, "use_tls": False},
    "otenet.gr": {"host": "smtp.otenet.gr", "port": 465, "use_ssl": True, "use_tls": False},
    "mynet.com": {"host": "smtp.mynet.com", "port": 465, "use_ssl": True, "use_tls": False},
    "superonline.com": {"host": "smtp.superonline.com", "port": 465, "use_ssl": True, "use_tls": False},
    "turk.net": {"host": "smtp.turk.net", "port": 465, "use_ssl": True, "use_tls": False},
    "ttnet.net.tr": {"host": "smtp.ttnet.net.tr", "port": 587, "use_ssl": False, "use_tls": True},
    "qq.com": {"host": "smtp.qq.com", "port": 465, "use_ssl": True, "use_tls": False},
    "163.com": {"host": "smtp.163.com", "port": 465, "use_ssl": True, "use_tls": False},
    "126.com": {"host": "smtp.126.com", "port": 465, "use_ssl": True, "use_tls": False},
    "sina.com": {"host": "smtp.sina.com", "port": 465, "use_ssl": True, "use_tls": False},
    "sina.cn": {"host": "smtp.sina.com", "port": 465, "use_ssl": True, "use_tls": False},
    "sohu.com": {"host": "smtp.sohu.com", "port": 465, "use_ssl": True, "use_tls": False},
    "aliyun.com": {"host": "smtp.aliyun.com", "port": 465, "use_ssl": True, "use_tls": False},
    "foxmail.com": {"host": "smtp.foxmail.com", "port": 465, "use_ssl": True, "use_tls": False},
    "139.com": {"host": "smtp.139.com", "port": 465, "use_ssl": True, "use_tls": False},
    "189.cn": {"host": "smtp.189.cn", "port": 465, "use_ssl": True, "use_tls": False},
    "21cn.com": {"host": "smtp.21cn.com", "port": 465, "use_ssl": True, "use_tls": False},
    "tom.com": {"host": "smtp.tom.com", "port": 465, "use_ssl": True, "use_tls": False},
    "vip.163.com": {"host": "smtp.163.com", "port": 465, "use_ssl": True, "use_tls": False},
    "vip.126.com": {"host": "smtp.126.com", "port": 465, "use_ssl": True, "use_tls": False},
    "vip.qq.com": {"host": "smtp.qq.com", "port": 465, "use_ssl": True, "use_tls": False},
    "yeah.net": {"host": "smtp.yeah.net", "port": 465, "use_ssl": True, "use_tls": False},
    "188.com": {"host": "smtp.188.com", "port": 465, "use_ssl": True, "use_tls": False},
    "nifty.com": {"host": "smtp.nifty.com", "port": 465, "use_ssl": True, "use_tls": False},
    "biglobe.ne.jp": {"host": "smtp.biglobe.ne.jp", "port": 465, "use_ssl": True, "use_tls": False},
    "plala.or.jp": {"host": "smtp.plala.or.jp", "port": 465, "use_ssl": True, "use_tls": False},
    "ocn.ne.jp": {"host": "smtp.ocn.ne.jp", "port": 465, "use_ssl": True, "use_tls": False},
    "excite.co.jp": {"host": "smtp.excite.co.jp", "port": 465, "use_ssl": True, "use_tls": False},
    "ezweb.ne.jp": {"host": "smtp.au.com", "port": 587, "use_ssl": False, "use_tls": True},
    "au.com": {"host": "smtp.au.com", "port": 587, "use_ssl": False, "use_tls": True},
    "naver.com": {"host": "smtp.naver.com", "port": 465, "use_ssl": True, "use_tls": False},
    "daum.net": {"host": "smtp.daum.net", "port": 465, "use_ssl": True, "use_tls": False},
    "hanmail.net": {"host": "smtp.daum.net", "port": 465, "use_ssl": True, "use_tls": False},
    "nate.com": {"host": "smtp.nate.com", "port": 465, "use_ssl": True, "use_tls": False},
    "korea.com": {"host": "smtp.korea.com", "port": 465, "use_ssl": True, "use_tls": False},
    "dreamwiz.com": {"host": "smtp.dreamwiz.com", "port": 465, "use_ssl": True, "use_tls": False},
    "rediffmail.com": {"host": "smtp.rediffmail.com", "port": 465, "use_ssl": True, "use_tls": False},
    "sify.com": {"host": "smtp.sify.com", "port": 465, "use_ssl": True, "use_tls": False},
    "indiatimes.com": {"host": "smtp.indiatimes.com", "port": 465, "use_ssl": True, "use_tls": False},
    "dataone.in": {"host": "smtp.dataone.in", "port": 587, "use_ssl": False, "use_tls": True},
    "airtelmail.in": {"host": "smtp.airtelmail.in", "port": 587, "use_ssl": False, "use_tls": True},
    "bigpond.com": {"host": "mail.bigpond.com", "port": 465, "use_ssl": True, "use_tls": False},
    "bigpond.net.au": {"host": "mail.bigpond.com", "port": 465, "use_ssl": True, "use_tls": False},
    "telstra.com": {"host": "mail.bigpond.com", "port": 465, "use_ssl": True, "use_tls": False},
    "optusnet.com.au": {"host": "mail.optusnet.com.au", "port": 465, "use_ssl": True, "use_tls": False},
    "iprimus.com.au": {"host": "smtp.iprimus.com.au", "port": 465, "use_ssl": True, "use_tls": False},
    "westnet.com.au": {"host": "smtp.westnet.com.au", "port": 465, "use_ssl": True, "use_tls": False},
    "dodo.com.au": {"host": "smtp.dodo.com.au", "port": 465, "use_ssl": True, "use_tls": False},
    "internode.on.net": {"host": "smtp.internode.on.net", "port": 465, "use_ssl": True, "use_tls": False},
    "xtra.co.nz": {"host": "smtp.xtra.co.nz", "port": 587, "use_ssl": False, "use_tls": True},
    "rogers.com": {"host": "smtp.rogers.com", "port": 465, "use_ssl": True, "use_tls": False},
    "shaw.ca": {"host": "mail.shaw.ca", "port": 465, "use_ssl": True, "use_tls": False},
    "bell.net": {"host": "smtp.bell.net", "port": 465, "use_ssl": True, "use_tls": False},
    "bell.ca": {"host": "smtp.bell.ca", "port": 465, "use_ssl": True, "use_tls": False},
    "sympatico.ca": {"host": "smtp.sympatico.ca", "port": 465, "use_ssl": True, "use_tls": False},
    "telus.net": {"host": "smtp.telus.net", "port": 465, "use_ssl": True, "use_tls": False},
    "telusplanet.net": {"host": "smtp.telus.net", "port": 465, "use_ssl": True, "use_tls": False},
    "videotron.ca": {"host": "smtp.videotron.ca", "port": 465, "use_ssl": True, "use_tls": False},
    "cogeco.ca": {"host": "smtp.cogeco.ca", "port": 465, "use_ssl": True, "use_tls": False},
    "eastlink.ca": {"host": "smtp.eastlink.ca", "port": 465, "use_ssl": True, "use_tls": False},
    "mts.net": {"host": "smtp.mts.net", "port": 465, "use_ssl": True, "use_tls": False},
    "sasktel.net": {"host": "smtp.sasktel.net", "port": 465, "use_ssl": True, "use_tls": False},
    "uol.com.br": {"host": "smtp.uol.com.br", "port": 587, "use_ssl": False, "use_tls": True},
    "bol.com.br": {"host": "smtp.bol.com.br", "port": 587, "use_ssl": False, "use_tls": True},
    "terra.com.br": {"host": "smtp.terra.com.br", "port": 587, "use_ssl": False, "use_tls": True},
    "ig.com.br": {"host": "smtp.ig.com.br", "port": 587, "use_ssl": False, "use_tls": True},
    "globo.com": {"host": "smtp.globo.com", "port": 587, "use_ssl": False, "use_tls": True},
    "r7.com": {"host": "smtp.r7.com", "port": 587, "use_ssl": False, "use_tls": True},
    "zipmail.com.br": {"host": "smtp.zipmail.com.br", "port": 587, "use_ssl": False, "use_tls": True},
    "oi.com.br": {"host": "smtp.oi.com.br", "port": 587, "use_ssl": False, "use_tls": True},
    "telmex.com": {"host": "smtp.telmex.com", "port": 587, "use_ssl": False, "use_tls": True},
    "infinitum.com.mx": {"host": "smtp.infinitum.com.mx", "port": 587, "use_ssl": False, "use_tls": True},
    "fibertel.com.ar": {"host": "smtp.fibertel.com.ar", "port": 465, "use_ssl": True, "use_tls": False},
    "arnet.com.ar": {"host": "smtp.arnet.com.ar", "port": 465, "use_ssl": True, "use_tls": False},
    "speedy.com.ar": {"host": "smtp.speedy.com.ar", "port": 465, "use_ssl": True, "use_tls": False},
    "webmail.co.za": {"host": "smtp.mweb.co.za", "port": 465, "use_ssl": True, "use_tls": False},
    "vodamail.co.za": {"host": "smtp.vodamail.co.za", "port": 465, "use_ssl": True, "use_tls": False},
    "mweb.co.za": {"host": "smtp.mweb.co.za", "port": 465, "use_ssl": True, "use_tls": False},
    "telkomsa.net": {"host": "smtp.telkomsa.net", "port": 465, "use_ssl": True, "use_tls": False},
    "walla.co.il": {"host": "smtp.walla.co.il", "port": 465, "use_ssl": True, "use_tls": False},
    "netvision.net.il": {"host": "smtp.netvision.net.il", "port": 465, "use_ssl": True, "use_tls": False},
    "bezeqint.net": {"host": "smtp.bezeqint.net", "port": 465, "use_ssl": True, "use_tls": False},
    "maktoob.com": {"host": "smtp.maktoob.com", "port": 587, "use_ssl": False, "use_tls": True},
    "emirates.net.ae": {"host": "smtp.emirates.net.ae", "port": 587, "use_ssl": False, "use_tls": True},
    "singnet.com.sg": {"host": "smtp.singnet.com.sg", "port": 465, "use_ssl": True, "use_tls": False},
    "starhub.net.sg": {"host": "smtp.starhub.net.sg", "port": 465, "use_ssl": True, "use_tls": False},
    "streamyx.com": {"host": "smtp.tm.com.my", "port": 587, "use_ssl": False, "use_tls": True},
    "tm.com.my": {"host": "smtp.tm.com.my", "port": 587, "use_ssl": False, "use_tls": True},
    "comcast.net": {"host": "smtp.comcast.net", "port": 587, "use_ssl": False, "use_tls": True},
    "earthlink.net": {"host": "smtp.earthlink.net", "port": 587, "use_ssl": False, "use_tls": True},
    "cox.net": {"host": "smtp.cox.net", "port": 465, "use_ssl": True, "use_tls": False},
    "charter.net": {"host": "smtp.charter.net", "port": 465, "use_ssl": True, "use_tls": False},
    "roadrunner.com": {"host": "smtp.rr.com", "port": 465, "use_ssl": True, "use_tls": False},
    "rr.com": {"host": "smtp.rr.com", "port": 465, "use_ssl": True, "use_tls": False},
    "optonline.net": {"host": "mail.optonline.net", "port": 465, "use_ssl": True, "use_tls": False},
    "netzero.net": {"host": "smtp.netzero.net", "port": 465, "use_ssl": True, "use_tls": False},
    "juno.com": {"host": "smtp.juno.com", "port": 465, "use_ssl": True, "use_tls": False},
    "mindspring.com": {"host": "smtp.earthlink.net", "port": 587, "use_ssl": False, "use_tls": True},
    "twc.com": {"host": "smtp.rr.com", "port": 465, "use_ssl": True, "use_tls": False},
    "mail.com": {"host": "smtp.mail.com", "port": 465, "use_ssl": True, "use_tls": False},
    "email.com": {"host": "smtp.mail.com", "port": 465, "use_ssl": True, "use_tls": False},
    "consultant.com": {"host": "smtp.mail.com", "port": 465, "use_ssl": True, "use_tls": False},
    "engineer.com": {"host": "smtp.mail.com", "port": 465, "use_ssl": True, "use_tls": False},
    "programmer.net": {"host": "smtp.mail.com", "port": 465, "use_ssl": True, "use_tls": False},
    "accountant.com": {"host": "smtp.mail.com", "port": 465, "use_ssl": True, "use_tls": False},
    "techie.com": {"host": "smtp.mail.com", "port": 465, "use_ssl": True, "use_tls": False},
    "lawyer.com": {"host": "smtp.mail.com", "port": 465, "use_ssl": True, "use_tls": False},
    "dr.com": {"host": "smtp.mail.com", "port": 465, "use_ssl": True, "use_tls": False},
    "protonmail.com": {"host": "smtp.protonmail.ch", "port": 587, "use_ssl": False, "use_tls": True},
    "protonmail.ch": {"host": "smtp.protonmail.ch", "port": 587, "use_ssl": False, "use_tls": True},
    "pm.me": {"host": "smtp.protonmail.ch", "port": 587, "use_ssl": False, "use_tls": True},
    "fastmail.com": {"host": "smtp.fastmail.com", "port": 465, "use_ssl": True, "use_tls": False},
    "fastmail.fm": {"host": "smtp.fastmail.com", "port": 465, "use_ssl": True, "use_tls": False},
    "fastmail.net": {"host": "smtp.fastmail.com", "port": 465, "use_ssl": True, "use_tls": False},
    "fastmail.org": {"host": "smtp.fastmail.com", "port": 465, "use_ssl": True, "use_tls": False},
    "hushmail.com": {"host": "smtp.hushmail.com", "port": 465, "use_ssl": True, "use_tls": False},
    "disroot.org": {"host": "disroot.org", "port": 587, "use_ssl": False, "use_tls": True},
    "runbox.com": {"host": "smtp.runbox.com", "port": 465, "use_ssl": True, "use_tls": False},
    "riseup.net": {"host": "mail.riseup.net", "port": 465, "use_ssl": True, "use_tls": False},
    "mailfence.com": {"host": "smtp.mailfence.com", "port": 465, "use_ssl": True, "use_tls": False},
    "kolabnow.com": {"host": "smtp.kolabnow.com", "port": 587, "use_ssl": False, "use_tls": True},
    "startmail.com": {"host": "smtp.startmail.com", "port": 465, "use_ssl": True, "use_tls": False},
    "godaddy.com": {"host": "smtpout.secureserver.net", "port": 465, "use_ssl": True, "use_tls": False},
    "secureserver.net": {"host": "smtpout.secureserver.net", "port": 465, "use_ssl": True, "use_tls": False},
    "bluehost.com": {"host": "mail.bluehost.com", "port": 465, "use_ssl": True, "use_tls": False},
    "namecheap.com": {"host": "mail.privateemail.com", "port": 465, "use_ssl": True, "use_tls": False},
    "dreamhost.com": {"host": "smtp.dreamhost.com", "port": 465, "use_ssl": True, "use_tls": False},
    "siteground.com": {"host": "smtp.siteground.com", "port": 465, "use_ssl": True, "use_tls": False},
    "hostgator.com": {"host": "gator.hostgator.com", "port": 465, "use_ssl": True, "use_tls": False},
    "ovh.net": {"host": "ssl0.ovh.net", "port": 465, "use_ssl": True, "use_tls": False},
    "ovh.com": {"host": "ssl0.ovh.net", "port": 465, "use_ssl": True, "use_tls": False},
    "infomaniak.net": {"host": "mail.infomaniak.com", "port": 465, "use_ssl": True, "use_tls": False},
    "sendgrid.net": {"host": "smtp.sendgrid.net", "port": 587, "use_ssl": False, "use_tls": True},
    "mailgun.org": {"host": "smtp.mailgun.org", "port": 587, "use_ssl": False, "use_tls": True},
    "zick-mail.casa": {"host": "smtp.zick-mail.casa", "port": 465, "use_ssl": True, "use_tls": False, "imap_host": "imap.zick-mail.casa", "imap_port": 993, "imap_ssl": True},
}


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


def get_smtp_config_for_domain(domain: str) -> Optional[dict]:
    return _SMTP_CONFIGS.get(domain.lower().strip())


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
    imap_host: str = ""
    imap_port: int = 993
    imap_ssl: bool = True

    def __post_init__(self):
        self._lock = threading.Lock()
        self.sent_today: int = 0
        self.sent_this_hour: int = 0
        self._hour_reset: float = time.time()
        self._day_reset: float = time.time()

    def _tick_hour_reset(self) -> None:  # noqa: DEPRECATED — use _tick_resets(); kept for compatibility
        """Сбрасывает часовой счётчик если прошёл час. Вызывать только под self._lock."""
        now = time.time()
        if now - self._hour_reset >= 3600:
            self.sent_this_hour = 0
            self._hour_reset = now

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
        """Thread-safe read-only проверка лимитов (без побочных эффектов)."""
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


_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def validate_email_format(email: str) -> bool:
    return bool(_EMAIL_RE.match(email.strip())) if email else False


def _build_message(
    account: SmtpAccount,
    recipient: Recipient,
    template: EmailTemplate,
) -> MIMEMultipart:
    """Build MIME message: multipart/mixed -> multipart/alternative -> html."""
    msg_id = f"<{uuid.uuid4().hex}@{account.host}>"
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
    plain = template.body_text or re.sub(r"<[^>]+>", "", template.body_html)
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
    """Sync SMTP test — runs in thread pool to avoid blocking the event loop."""
    import ssl
    try:
        ctx = ssl.create_default_context()
        if account.use_ssl:
            s = smtplib.SMTP_SSL(account.host, account.port, context=ctx, timeout=15)
        else:
            s = smtplib.SMTP(account.host, account.port, timeout=15)
            if account.use_tls:
                s.starttls(context=ctx)
        s.login(account.email, account.password)
        s.quit()
        return True, f"OK — {account.host}:{account.port}"
    except Exception as e:
        return False, f"ОШИБКА: {e}"


async def test_smtp_connection(account: SmtpAccount) -> tuple[bool, str]:
    if not _HAS_AIOSMTPLIB:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _test_smtp_sync, account)
    try:
        if account.use_ssl:
            smtp = aiosmtplib.SMTP(
                hostname=account.host, port=account.port,
                use_tls=True, start_tls=False, timeout=20,
            )
            await smtp.connect()
        else:
            smtp = aiosmtplib.SMTP(
                hostname=account.host, port=account.port,
                use_tls=False, timeout=20,
            )
            await smtp.connect()
            if account.use_tls:
                await smtp.starttls()
        await smtp.login(account.email, account.password)
        await smtp.quit()
        return True, f"OK — SMTP {account.host}:{account.port} авторизация успешна"
    except Exception as e:
        return False, f"ОШИБКА [{type(e).__name__}]: {e}"


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
            except Exception:
                pass

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

        # Сбрасываем только часовой счётчик — дневные лимиты накапливаются
        for _acct in self.accounts:
            if _acct.is_active:
                with _acct._lock:
                    _acct.sent_this_hour = 0
                    _acct._hour_reset = time.time()

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
            account = self._pick_account()
            if account is None:
                with self._stats_lock:
                    self._stats["errors"] += 1
                return SendResult(
                    recipient_email=recipient.email,
                    success=False,
                    error="Нет доступных аккаунтов",
                )
            return await self._send_one(sem, account, recipient, template)

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
                    if isinstance(result, Exception):
                        with self._stats_lock:
                            self._stats["errors"] += 1
                        continue
                    results.append(result)
                    with self._stats_lock:
                        if result.success:
                            self._stats["success"] += 1
                        else:
                            self._stats["errors"] += 1
                    self._emit_progress(results, recipients, result)
                if (
                    self.config.pause_after_n > 0
                    and len(results) % self.config.pause_after_n == 0
                    and len(results) < len(recipients)
                ):
                    await asyncio.sleep(self.config.pause_duration_sec)
                i += batch_size

        except asyncio.CancelledError:
            pass  # Остановлено через stop()
        finally:
            self._campaign_task = None

        if self.on_finished:
            self.on_finished(results)
        return results


    def _pick_account(self) -> Optional[SmtpAccount]:
        """Pick first account that passes atomic try_increment check."""
        active = [a for a in self.accounts if a.is_active]
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
            return await asyncio.get_event_loop().run_in_executor(
                None, self._send_sync, account, recipient, personalized
            )

    async def _send_aiosmtp(
        self,
        account: SmtpAccount,
        recipient: Recipient,
        template: EmailTemplate,
    ) -> SendResult:
        msg = _build_message(account, recipient, template)
        try:
            if account.use_ssl:
                smtp = aiosmtplib.SMTP(
                    hostname=account.host, port=account.port,
                    use_tls=True, start_tls=False, timeout=30,
                )
            else:
                smtp = aiosmtplib.SMTP(
                    hostname=account.host, port=account.port,
                    use_tls=False, start_tls=account.use_tls, timeout=30,
                )
            await smtp.connect()
            try:
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
                except Exception:
                    pass
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
        import ssl
        msg = _build_message(account, recipient, template)
        try:
            ctx = ssl.create_default_context()
            if account.use_ssl:
                s = smtplib.SMTP_SSL(account.host, account.port, context=ctx, timeout=30)
            else:
                s = smtplib.SMTP(account.host, account.port, timeout=30)
                if account.use_tls:
                    s.starttls(context=ctx)
            s.login(account.email, account.password)
            s.send_message(msg)
            s.quit()
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
