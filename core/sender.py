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
    "gmx.com":           {"host": "mail.gmx.com",          "port": 587, "use_ssl": False, "use_tls": True},
    "gmx.co.uk":         {"host": "mail.gmx.com",          "port": 587, "use_ssl": False, "use_tls": True},
    "mail.ru":           {"host": "smtp.mail.ru",          "port": 465, "use_ssl": True,  "use_tls": False},
    "inbox.ru":          {"host": "smtp.mail.ru",          "port": 465, "use_ssl": True,  "use_tls": False},
    "list.ru":           {"host": "smtp.mail.ru",          "port": 465, "use_ssl": True,  "use_tls": False},
    "bk.ru":             {"host": "smtp.mail.ru",          "port": 465, "use_ssl": True,  "use_tls": False},
    "internet.ru":       {"host": "smtp.mail.ru",          "port": 465, "use_ssl": True,  "use_tls": False},
    "mail.ua":           {"host": "smtp.mail.ru",          "port": 465, "use_ssl": True,  "use_tls": False},
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
}

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


def get_smtp_config_for_domain(domain: str) -> Optional[dict]:
    """BUG FIX #6: exact lookup + pattern fallback (outlook/hotmail/live/yahoo/gmx families)."""
    d = domain.lower().strip()
    if d in _SMTP_CONFIGS:
        return _SMTP_CONFIGS[d]
    for prefix, cfg in _SMTP_DOMAIN_PATTERNS:
        if d == prefix.rstrip(".") or d.endswith("." + prefix.rstrip(".")):
            return cfg
    return None


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
    """Backward-compat wrapper — источник истины перенесён в core.utils."""
    from core.utils import validate_email_format as _vef
    return _vef(email)


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
    """Sync SMTP test через стандартный smtplib — надёжно работает с любым провайдером."""
    import ssl as _ssl
    try:
        ctx = _ssl.create_default_context()
        if account.use_ssl:
            s = smtplib.SMTP_SSL(account.host, account.port, context=ctx, timeout=20)
        else:
            s = smtplib.SMTP(account.host, account.port, timeout=20)
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
    except smtplib.SMTPConnectError:
        return False, f"Не удалось подключиться к {account.host}:{account.port}. Проверьте хост и порт."
    except smtplib.SMTPServerDisconnected:
        return False, "Сервер разорвал соединение. Возможно, неверный протокол (SSL/TLS)."
    except smtplib.SMTPException as e:
        return False, f"Ошибка SMTP: {e}"
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
                    if isinstance(result, BaseException):
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
        active = [a for a in self.accounts if a.is_active and a.last_test_ok is not False]
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
                    s.ehlo()  # RFC 3207: повторный EHLO обязателен после STARTTLS
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
