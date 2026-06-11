"""
Асинхронный SMTP-движок для массовой рассылки.
Использует aiosmtplib + asyncio.Semaphore для управления параллелизмом.
"""
import asyncio
import logging
import queue
import random
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from datetime import date as date_t
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from pathlib import Path
from typing import Callable, List, Optional

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

    def personalize(self, recipient: Recipient) -> "EmailTemplate":
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
    for key, value in variables.items():
        template = template.replace("{{" + key + "}}", str(value) if value else "")
    return template


def _html_to_text(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<p[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    for ent, rep in [("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&nbsp;", " "), ("&quot;", '"')]:
        text = text.replace(ent, rep)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def validate_email_format(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email.strip()))


def get_smtp_config_for_domain(domain: str) -> Optional[dict]:
    CONFIGS = {
        "gmail.com":      {"host": "smtp.gmail.com",      "port": 465, "use_ssl": True,  "use_tls": False},
        "googlemail.com": {"host": "smtp.gmail.com",      "port": 465, "use_ssl": True,  "use_tls": False},
        "outlook.com":    {"host": "smtp.office365.com",  "port": 587, "use_ssl": False, "use_tls": True},
        "hotmail.com":    {"host": "smtp.office365.com",  "port": 587, "use_ssl": False, "use_tls": True},
        "live.com":       {"host": "smtp.office365.com",  "port": 587, "use_ssl": False, "use_tls": True},
        "yahoo.com":      {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True,  "use_tls": False},
        "mail.ru":        {"host": "smtp.mail.ru",        "port": 465, "use_ssl": True,  "use_tls": False},
        "yandex.ru":      {"host": "smtp.yandex.ru",      "port": 465, "use_ssl": True,  "use_tls": False},
        "yandex.com":     {"host": "smtp.yandex.ru",      "port": 465, "use_ssl": True,  "use_tls": False},
        "icloud.com":     {"host": "smtp.mail.me.com",    "port": 587, "use_ssl": False, "use_tls": True},
    }
    return CONFIGS.get(domain.lower())


async def test_smtp_connection(account: SmtpAccount) -> tuple[bool, str]:
    log_lines = []
    try:
        log_lines.append(f"Подключение к {account.host}:{account.port}...")
        smtp = aiosmtplib.SMTP(
            hostname=account.host,
            port=account.port,
            use_tls=account.use_ssl,
            start_tls=account.use_tls,
            timeout=15,
        )
        await smtp.connect()
        log_lines.append("Соединение установлено. Авторизация...")
        await smtp.login(account.email, account.password)
        log_lines.append(f"\u2713 Успешно! Аккаунт {account.email} готов к отправке.")
        await smtp.quit()
        return True, "\n".join(log_lines)
    except aiosmtplib.SMTPAuthenticationError:
        log_lines.append("\u2717 Ошибка авторизации: неверный email или пароль.")
        return False, "\n".join(log_lines)
    except Exception as e:
        log_lines.append(f"\u2717 Ошибка: {e}")
        return False, "\n".join(log_lines)


def build_email_message(account: SmtpAccount, recipient: Recipient, template: EmailTemplate) -> MIMEMultipart:
      # BUG FIX: multipart/alternative cannot carry binary attachments.
      # Use multipart/mixed (outer) + multipart/alternative (inner) when attachments exist.
      has_attachments = bool(template.attachments)
      if has_attachments:
          msg = MIMEMultipart("mixed")
          alt = MIMEMultipart("alternative")
      else:
          msg = MIMEMultipart("alternative")
          alt = msg
      msg["From"] = account.display_email
      msg["To"] = recipient.email
      msg["Subject"] = template.subject
      msg["Date"] = formatdate(localtime=True)
      msg["Message-ID"] = make_msgid(domain=account.host)
      if template.reply_to:
          msg["Reply-To"] = template.reply_to
      if template.unsubscribe_url:
          msg["List-Unsubscribe"] = f"<{template.unsubscribe_url}>"
          msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
      elif template.unsubscribe_email:
          msg["List-Unsubscribe"] = f"<mailto:{template.unsubscribe_email}>"
      text_body = template.body_text or _html_to_text(template.body_html)
      alt.attach(MIMEText(text_body, "plain", "utf-8"))
      if template.body_html:
          alt.attach(MIMEText(template.body_html, "html", "utf-8"))
      if has_attachments:
          msg.attach(alt)
          for att_path in template.attachments:
              path = Path(att_path)
              if not path.exists():
                  logger.warning(f"Attachment not found: {att_path}")
                  continue
              with open(path, "rb") as f:
                  part = MIMEBase("application", "octet-stream")
                  part.set_payload(f.read())
              encoders.encode_base64(part)
              part.add_header("Content-Disposition", f'attachment; filename="{path.name}"')
              msg.attach(part)
      return msg


class SendingEngine:
    def __init__(self, accounts: List[SmtpAccount], config: CampaignConfig, log_queue: Optional[queue.Queue] = None):
        self.accounts = [a for a in accounts if a.is_active]
        self.config = config
        self.log_queue = log_queue
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._account_lock: Optional[asyncio.Lock] = None

        self._semaphore: Optional[asyncio.Semaphore] = None
        self._stopped = False
        self._paused = False
        self._account_index = 0
        self.on_progress: Optional[Callable] = None
        self.on_finished: Optional[Callable] = None
        self.stats = {"sent": 0, "success": 0, "errors": 0, "start_time": 0.0}

    def stop(self) -> None:
        self._stopped = True

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    async def _get_next_account(self) -> Optional[SmtpAccount]:
          # BUG FIX: Lock prevents multiple coroutines from selecting
          # the same account before any counter has been incremented.
          async with self._account_lock:
              active = [a for a in self.accounts if a.can_send]
              if not active:
                  return None
              account = active[self._account_index % len(active)]
              self._account_index += 1
              return account

    def _log(self, message: str) -> None:
        if self.log_queue:
            try:
                self.log_queue.put_nowait({"type": "log", "message": message})
            except Exception:
                pass

    async def _send_one(self, account: SmtpAccount, recipient: Recipient, template: EmailTemplate) -> SendResult:
        personalized = template.personalize(recipient)
        msg = build_email_message(account, recipient, personalized)
        try:
            smtp = aiosmtplib.SMTP(
                hostname=account.host,
                port=account.port,
                use_tls=account.use_ssl,
                start_tls=account.use_tls,
                timeout=30,
            )
            async with smtp:
                await smtp.login(account.email, account.password)
                await smtp.send_message(msg)
            async with self._account_lock:

                account.sent_today += 1

                account.sent_this_hour += 1

            account.last_sent = time.time()
            return SendResult(
                recipient_email=recipient.email,
                success=True,
                account_used=account.email,
                message_id=msg.get("Message-ID", ""),
            )
        except aiosmtplib.SMTPAuthenticationError:
            account.is_active = False
            self._log(f"\u26a0 {account.email} деактивирован: ошибка авторизации")
            return SendResult(recipient_email=recipient.email, success=False,
                              error="SMTP auth error", account_used=account.email)
        except asyncio.TimeoutError:
            return SendResult(recipient_email=recipient.email, success=False,
                              error="Timeout", account_used=account.email)
        except Exception as e:
            return SendResult(recipient_email=recipient.email, success=False,
                              error=str(e), account_used=account.email)

    async def run_campaign(self, recipients: List[Recipient], template: EmailTemplate) -> List[SendResult]:
        self._semaphore = asyncio.Semaphore(self.config.max_threads)
        self._account_lock = asyncio.Lock()
        self._stopped = False
        self.stats["start_time"] = time.time()
        total = len(recipients)

        async def send_with_semaphore(recipient: Recipient) -> SendResult:
            async with self._semaphore:
                if self._stopped:
                    return SendResult(recipient_email=recipient.email, success=False, error="stopped")
                while self._paused and not self._stopped:
                    await asyncio.sleep(0.5)
                account = await self._get_next_account()
                if not account:
                    return SendResult(recipient_email=recipient.email, success=False,
                                      error="Нет доступных аккаунтов")
                result = await self._send_one(account, recipient, template)
                if result.success:
                    self.stats["success"] += 1
                    self._log(f"\u2713 {recipient.email}")
                else:
                    self.stats["errors"] += 1
                    self._log(f"\u2717 {recipient.email}: {result.error}")
                self.stats["sent"] += 1
                if self.on_progress:
                    self.on_progress(self.stats["sent"], total, result)
                if self.stats["sent"] % self.config.pause_after_n == 0:
                    self._log(f"\u23f8 Пауза {self.config.pause_duration_sec}с")
                    await asyncio.sleep(self.config.pause_duration_sec)
                else:
                    delay_ms = random.randint(
                        self.config.min_delay_ms,
                        max(self.config.min_delay_ms, self.config.max_delay_ms)
                    )
                    await asyncio.sleep(delay_ms / 1000.0)
                return result

        results = await asyncio.gather(*[send_with_semaphore(r) for r in recipients])
        if self.on_finished:
            self.on_finished(list(results))
        return list(results)
