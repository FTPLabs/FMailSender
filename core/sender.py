"""
Асинхронный SMTP-движок для массовой рассылки.
Использует aiosmtplib + asyncio.Semaphore для управления параллелизмом.
"""
import asyncio
import logging
import queue
import random
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from datetime import date as date_t
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from pathlib import Path
from typing import List, Optional, Tuple

import aiosmtplib

logger = logging.getLogger("sender")


@dataclass
class SmtpAccount:
    email: str
    password: str
    host: str
    port: int
    use_ssl: bool = True
    use_tls: bool = False
    display_name: str = ""
    daily_limit: int = 500
    hourly_limit: int = 50
    sent_today: int = 0
    sent_this_hour: int = 0
    last_sent: float = 0.0
    is_active: bool = True
    warmup_day: int = 0
    _reset_date: str = field(default="", repr=False, compare=False)
    _reset_hour: int = field(default=-1, repr=False, compare=False)

    def __post_init__(self):
        self._reset_date = date_t.today().isoformat()
        self._reset_hour = datetime.now().hour
        object.__setattr__(self, '_lock', threading.Lock())

    def _refresh_counters(self) -> None:
        today = date_t.today().isoformat()
        hour = datetime.now().hour
        if today != self._reset_date:
            self.sent_today = 0
            self.sent_this_hour = 0
            self._reset_date = today
            self._reset_hour = hour
        elif hour != self._reset_hour:
            self.sent_this_hour = 0
            self._reset_hour = hour

    @property
    def display_email(self) -> str:
        if self.display_name:
            return f"{self.display_name} <{self.email}>"
        return self.email

    @property
    def can_send(self) -> bool:
        self._refresh_counters()
        return (
            self.is_active
            and self.sent_today < self.daily_limit
            and self.sent_this_hour < self.hourly_limit
        )



    def increment_sent(self) -> None:
        """Атомарно увеличивает счётчики (thread-safe)."""
        with self._lock:
            self._refresh_counters()
            self.sent_today += 1
            self.sent_this_hour += 1
            self.last_sent = time.time()
@dataclass
class Recipient:
    email: str
    first_name: str = ""
    last_name: str = ""
    company: str = ""
    custom_1: str = ""
    custom_2: str = ""
    custom_3: str = ""
    custom_4: str = ""
    custom_5: str = ""

    def get_vars(self) -> dict:
        return {
            "first_name": self.first_name,
            "last_name": self.last_name,
            "company": self.company,
            "custom_1": self.custom_1,
            "custom_2": self.custom_2,
            "custom_3": self.custom_3,
            "custom_4": self.custom_4,
            "custom_5": self.custom_5,
            "email": self.email,
        }


@dataclass
class EmailTemplate:
    subject: str
    body_html: str
    body_text: str = ""
    attachments: List[str] = field(default_factory=list)
    reply_to: str = ""
    unsubscribe_url: str = ""
    unsubscribe_email: str = ""
    tracking_domain: str = ""

    def personalize(self, recipient: "Recipient") -> "EmailTemplate":
        vars_ = recipient.get_vars()
        subject = _interpolate(self.subject, vars_)
        body_html = _interpolate(self.body_html, vars_)
        body_text = _interpolate(self.body_text, vars_) if self.body_text else _html_to_text(body_html)
        return EmailTemplate(
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            attachments=list(self.attachments),
            reply_to=self.reply_to,
            unsubscribe_url=self.unsubscribe_url,
            unsubscribe_email=self.unsubscribe_email,
            tracking_domain=self.tracking_domain,
        )


@dataclass
class CampaignConfig:
    min_delay_ms: int = 500
    max_delay_ms: int = 2000
    pause_after_n: int = 50
    pause_duration_sec: int = 60
    max_threads: int = 5
    track_opens: bool = False
    track_clicks: bool = False


@dataclass
class SendResult:
    recipient_email: str
    success: bool
    error: str = ""
    timestamp: float = field(default_factory=time.time)
    account_used: str = ""
    message_id: str = ""


# ── helpers ──────────────────────────────────────────────────────────────────

def _interpolate(template: str, variables: dict) -> str:
    """Single-pass regex substitution — O(n) instead of O(n*m)."""
    if not template:
        return template

    def _replacer(match: re.Match) -> str:
        key = match.group(1).strip()
        val = variables.get(key, "")
        return str(val) if val else ""

    return re.sub(r"\{\{([^}]+)\}\}", _replacer, template)


# HTML entities table — comprehensive coverage
_HTML_ENTITIES = {
    "&amp;": "&", "&lt;": "<", "&gt;": ">", "&nbsp;": " ",
    "&quot;": '"', "&#39;": "'", "&apos;": "'", "&#160;": " ",
    "&mdash;": "—", "&ndash;": "–", "&hellip;": "…",
    "&laquo;": "«", "&raquo;": "»", "&copy;": "©",
    "&reg;": "®", "&trade;": "™", "&euro;": "€",
    "&pound;": "£", "&cent;": "¢", "&yen;": "¥",
    "&deg;": "°", "&plusmn;": "±", "&times;": "×",
    "&divide;": "÷", "&frac12;": "½", "&frac14;": "¼",
}


def _html_to_text(html_str: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html_str, flags=re.IGNORECASE)
    text = re.sub(r"<p[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    for ent, rep in _HTML_ENTITIES.items():
        text = text.replace(ent, rep)
    text = re.sub(r"&#([0-9]+);", lambda m: chr(int(m.group(1))), text)
    text = re.sub(r"&#x([0-9a-fA-F]+);", lambda m: chr(int(m.group(1), 16)), text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def validate_email_format(email: str) -> bool:
    """Single source of truth for email format validation."""
    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email.strip()))


# SMTP host presets
CONFIGS = {
    "gmail.com":        {"host": "smtp.gmail.com",          "port": 465, "use_ssl": True,  "use_tls": False},
    "googlemail.com":   {"host": "smtp.gmail.com",          "port": 465, "use_ssl": True,  "use_tls": False},
    "outlook.com":      {"host": "smtp.office365.com",      "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.com":      {"host": "smtp.office365.com",      "port": 587, "use_ssl": False, "use_tls": True},
    "live.com":         {"host": "smtp.office365.com",      "port": 587, "use_ssl": False, "use_tls": True},
    "msn.com":          {"host": "smtp.office365.com",      "port": 587, "use_ssl": False, "use_tls": True},
    "yahoo.com":        {"host": "smtp.mail.yahoo.com",     "port": 465, "use_ssl": True,  "use_tls": False},
    "yahoo.co.uk":      {"host": "smtp.mail.yahoo.co.uk",   "port": 465, "use_ssl": True,  "use_tls": False},
    "yahoo.fr":         {"host": "smtp.mail.yahoo.fr",      "port": 465, "use_ssl": True,  "use_tls": False},
    "mail.ru":          {"host": "smtp.mail.ru",            "port": 465, "use_ssl": True,  "use_tls": False},
    "bk.ru":            {"host": "smtp.mail.ru",            "port": 465, "use_ssl": True,  "use_tls": False},
    "inbox.ru":         {"host": "smtp.mail.ru",            "port": 465, "use_ssl": True,  "use_tls": False},
    "list.ru":          {"host": "smtp.mail.ru",            "port": 465, "use_ssl": True,  "use_tls": False},
    "yandex.ru":        {"host": "smtp.yandex.ru",          "port": 465, "use_ssl": True,  "use_tls": False},
    "yandex.com":       {"host": "smtp.yandex.ru",          "port": 465, "use_ssl": True,  "use_tls": False},
    "ya.ru":            {"host": "smtp.yandex.ru",          "port": 465, "use_ssl": True,  "use_tls": False},
    "rambler.ru":       {"host": "smtp.rambler.ru",         "port": 465, "use_ssl": True,  "use_tls": False},
    "gmx.com":          {"host": "mail.gmx.com",            "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.net":          {"host": "mail.gmx.net",            "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.de":           {"host": "mail.gmx.net",            "port": 587, "use_ssl": False, "use_tls": True},
    "web.de":           {"host": "smtp.web.de",             "port": 587, "use_ssl": False, "use_tls": True},
    "orange.fr":        {"host": "smtp.orange.fr",          "port": 587, "use_ssl": False, "use_tls": True},
    "sfr.fr":           {"host": "smtp.sfr.fr",             "port": 587, "use_ssl": False, "use_tls": True},
    "free.fr":          {"host": "smtp.free.fr",            "port": 465, "use_ssl": True,  "use_tls": False},
    "icloud.com":       {"host": "smtp.mail.me.com",        "port": 587, "use_ssl": False, "use_tls": True},
    "me.com":           {"host": "smtp.mail.me.com",        "port": 587, "use_ssl": False, "use_tls": True},
    "mac.com":          {"host": "smtp.mail.me.com",        "port": 587, "use_ssl": False, "use_tls": True},
    "protonmail.com":   {"host": "smtp.protonmail.com",     "port": 587, "use_ssl": False, "use_tls": True},
    "proton.me":        {"host": "smtp.protonmail.com",     "port": 587, "use_ssl": False, "use_tls": True},
}


def get_smtp_config(email: str) -> dict:
    """Alias — delegates to get_smtp_config_for_domain."""
    domain = email.split("@")[-1].lower() if "@" in email else ""
    return get_smtp_config_for_domain(domain)




def get_smtp_config_for_domain(domain: str) -> dict:
    """Return SMTP preset config for a given domain string (no @ needed)."""
    d = domain.lower().strip()
    return CONFIGS.get(d, {"host": "", "port": 587, "use_ssl": False, "use_tls": True})


async def test_smtp_connection(account: "SmtpAccount") -> Tuple[bool, str]:
    """
    Test SMTP authentication without sending any email.
    Returns (success: bool, log: str).
    """
    lines = [
        f"Хост: {account.host}:{account.port}",
        f"Режим: {'SSL/TLS' if account.use_ssl else 'STARTTLS' if account.use_tls else 'Нет шифрования'}",
        f"Логин: {account.email}",
    ]
    try:
        if account.use_ssl:
            smtp = aiosmtplib.SMTP(
                hostname=account.host,
                port=account.port,
                use_tls=True,
                timeout=15,
            )
        else:
            smtp = aiosmtplib.SMTP(
                hostname=account.host,
                port=account.port,
                use_tls=False,
                timeout=15,
            )
        async with smtp:
            if not account.use_ssl and account.use_tls:
                await smtp.starttls()
            await smtp.login(account.email, account.password)
            lines.append("✅ Аутентификация успешна")
        return True, "\n".join(lines)
    except aiosmtplib.SMTPAuthenticationError as e:
        lines.append(f"❌ Ошибка авторизации: {e.message if hasattr(e, 'message') else e}")
        return False, "\n".join(lines)
    except aiosmtplib.SMTPConnectError as e:
        lines.append(f"❌ Ошибка подключения: {e}")
        return False, "\n".join(lines)
    except aiosmtplib.SMTPException as e:
        lines.append(f"❌ SMTP ошибка: {e}")
        return False, "\n".join(lines)
    except Exception as e:
        lines.append(f"❌ Ошибка: {e}")
        return False, "\n".join(lines)


def _build_message(
    account: SmtpAccount,
    recipient: Recipient,
    template: EmailTemplate,
) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["From"] = account.display_email
    msg["To"] = recipient.email
    msg["Subject"] = template.subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=account.email.split("@")[-1])

    if template.reply_to:
        msg["Reply-To"] = template.reply_to

    headers = []
    if template.unsubscribe_url:
        headers.append(f"<{template.unsubscribe_url}>")
    if template.unsubscribe_email:
        headers.append(f"<mailto:{template.unsubscribe_email}>")
    if headers:
        msg["List-Unsubscribe"] = ", ".join(headers)
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

    if template.body_text:
        msg.attach(MIMEText(template.body_text, "plain", "utf-8"))
    msg.attach(MIMEText(template.body_html, "html", "utf-8"))

    for path_str in template.attachments:
        path = Path(path_str)
        if path.exists():
            part = MIMEBase("application", "octet-stream")
            part.set_payload(path.read_bytes())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{path.name}"')
            msg.attach(part)

    return msg


class SendingEngine:
    def __init__(
        self,
        accounts: List[SmtpAccount],
        recipients: List[Recipient],
        template: EmailTemplate,
        config: CampaignConfig,
        result_queue: queue.Queue,
        stop_event: Optional[threading.Event] = None,
    ):
        self.accounts = accounts
        self.recipients = recipients
        self.template = template
        self.config = config
        self.result_queue = result_queue
        self.stop_event = stop_event or threading.Event()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._async_run())
        finally:
            self._loop.close()

    def stop(self):
        self.stop_event.set()

    async def _async_run(self):
        sem = asyncio.Semaphore(self.config.max_threads)
        tasks = []
        for i, recipient in enumerate(self.recipients):
            if self.stop_event.is_set():
                break
            account = self._pick_account()
            if account is None:
                self.result_queue.put(SendResult(
                    recipient_email=recipient.email,
                    success=False,
                    error="Нет доступных аккаунтов",
                ))
                continue

            if i > 0 and i % self.config.pause_after_n == 0:
                await asyncio.sleep(self.config.pause_duration_sec)

            delay = random.randint(self.config.min_delay_ms, self.config.max_delay_ms) / 1000.0
            await asyncio.sleep(delay)

            task = asyncio.create_task(self._send_one(sem, account, recipient))
            tasks.append(task)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _pick_account(self) -> Optional[SmtpAccount]:
        available = [a for a in self.accounts if a.can_send]
        if not available:
            return None
        return min(available, key=lambda a: a.sent_today)

    async def _send_one(self, sem: asyncio.Semaphore, account: SmtpAccount, recipient: Recipient):
        async with sem:
            if self.stop_event.is_set():
                return
            personalized = self.template.personalize(recipient)
            msg = _build_message(account, recipient, personalized)
            try:
                if account.use_ssl:
                    # SSL/TLS from the start (port 465) — use_tls=True
                    await aiosmtplib.send(
                        msg,
                        hostname=account.host,
                        port=account.port,
                        username=account.email,
                        password=account.password,
                        use_tls=True,
                        start_tls=False,
                        timeout=30,
                    )
                else:
                    # Plain or STARTTLS (port 587)
                    await aiosmtplib.send(
                        msg,
                        hostname=account.host,
                        port=account.port,
                        username=account.email,
                        password=account.password,
                        use_tls=False,
                        start_tls=account.use_tls,
                        timeout=30,
                    )
                account.sent_today += 1
                account.sent_this_hour += 1
                account.last_sent = time.time()
                result = SendResult(
                    recipient_email=recipient.email,
                    success=True,
                    account_used=account.email,
                    message_id=msg.get("Message-ID", ""),
                )
            except Exception as e:
                result = SendResult(
                    recipient_email=recipient.email,
                    success=False,
                    error=str(e),
                    account_used=account.email,
                )
            self.result_queue.put(result)
