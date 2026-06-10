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
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from pathlib import Path
from typing import Callable, List, Optional

import aiosmtplib

logger = logging.getLogger("sender")

# ──────────────────────────────────────────────
# Структуры данных
# ──────────────────────────────────────────────

@dataclass
class SmtpAccount:
    """SMTP-аккаунт для отправки."""
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

    @property
    def display_email(self) -> str:
        if self.display_name:
            return f"{self.display_name} <{self.email}>"
        return self.email

    @property
    def can_send(self) -> bool:
        return (
            self.is_active and
            self.sent_today < self.daily_limit and
            self.sent_this_hour < self.hourly_limit
        )


@dataclass
class Recipient:
    """Получатель письма."""
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
    """Шаблон письма."""
    subject: str
    body_html: str
    body_text: str = ""
    attachments: List[str] = field(default_factory=list)
    reply_to: str = ""
    unsubscribe_url: str = ""
    unsubscribe_email: str = ""
    tracking_domain: str = ""

    def personalize(self, recipient: Recipient) -> "EmailTemplate":
        """Применяет персонализацию для конкретного получателя."""
        vars_ = recipient.get_vars()
        subject = _interpolate(self.subject, vars_)
        body_html = _interpolate(self.body_html, vars_)
        body_text = _interpolate(self.body_text, vars_) if self.body_text else _html_to_text(body_html)
        return EmailTemplate(
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            attachments=self.attachments,
            reply_to=self.reply_to,
            unsubscribe_url=self.unsubscribe_url,
            unsubscribe_email=self.unsubscribe_email,
            tracking_domain=self.tracking_domain,
        )


@dataclass
class SendResult:
    """Результат отправки одного письма."""
    recipient_email: str
    success: bool
    error: str = ""
    timestamp: float = field(default_factory=time.time)
    account_used: str = ""
    message_id: str = ""


@dataclass
class CampaignConfig:
    """Конфигурация кампании рассылки."""
    min_delay_ms: int = 500
    max_delay_ms: int = 2000
    pause_after_n: int = 50
    pause_duration_sec: int = 60
    max_threads: int = 5
    rotation_mode: str = "round-robin"  # round-robin / weighted / random
    scheduled_at: Optional[datetime] = None


# ──────────────────────────────────────────────
# Утилиты персонализации и MIME
# ──────────────────────────────────────────────

_X_MAILER_POOL = [
    "Microsoft Outlook 16.0",
    "Apple Mail 16.0",
    "Thunderbird 115.0",
    "Gmail Web Client",
    "Yahoo Mail",
    "Outlook Express 6.0",
    "The Bat! 10.5",
    "Evolution 3.50",
]

_ZERO_WIDTH_CHARS = ["\u200b", "\u200c", "\u200d", "\ufeff"]


def _interpolate(template: str, vars_: dict) -> str:
    """Заменяет {{variable}} на значения с fallback на пустую строку."""
    def replace_var(m):
        key = m.group(1).strip()
        return vars_.get(key, "")
    return re.sub(r"\{\{(\w+)\}\}", replace_var, template)


def _html_to_text(html: str) -> str:
    """Конвертирует HTML в plain text."""
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<p[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _uniquify_html(html: str, tracking_id: str) -> str:
    """
    Уникализирует HTML для каждого получателя:
    - Добавляет zero-width spaces в конце параграфов
    - Рандомизирует порядок CSS-свойств
    - Добавляет микровариации пробелов в атрибутах
    """
    # Добавляем случайный zero-width char в конце параграфов
    zwc = random.choice(_ZERO_WIDTH_CHARS)
    html = re.sub(r"(</p>)", lambda m: zwc + m.group(1), html)

    # Рандомизируем порядок CSS-свойств в inline-стилях
    def shuffle_css(m):
        style_content = m.group(1)
        props = [p.strip() for p in style_content.split(";") if p.strip()]
        random.shuffle(props)
        return f'style="{"; ".join(props)}"'

    html = re.sub(r'style="([^"]+)"', shuffle_css, html)

    # Добавляем tracking pixel с уникальным ID
    if tracking_id:
        pixel = f'<img src="https://track.emailsenderpro.io/open/{tracking_id}.gif" width="1" height="1" style="display:none" />'
        html = html.replace("</body>", pixel + "</body>")
        if "</body>" not in html:
            html += pixel

    return html


def _build_message(
    sender_account: SmtpAccount,
    recipient: Recipient,
    template: EmailTemplate,
    tracking_id: str,
) -> MIMEMultipart:
    """Строит полное MIME-сообщение с правильными заголовками."""
    msg = MIMEMultipart("alternative")

    # Заголовки письма
    msg["From"] = sender_account.display_email
    msg["To"] = recipient.email
    msg["Subject"] = template.subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=sender_account.email.split("@")[-1])
    msg["MIME-Version"] = "1.0"
    msg["X-Mailer"] = random.choice(_X_MAILER_POOL)

    # List-Unsubscribe
    if template.unsubscribe_email or template.unsubscribe_url:
        parts = []
        if template.unsubscribe_email:
            parts.append(f"<mailto:{template.unsubscribe_email}?subject=unsubscribe>")
        if template.unsubscribe_url:
            parts.append(f"<{template.unsubscribe_url}>")
        msg["List-Unsubscribe"] = ", ".join(parts)
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

    msg["Precedence"] = "bulk"

    if template.reply_to:
        msg["Reply-To"] = template.reply_to

    # Plain text версия (ОБЯЗАТЕЛЬНО)
    body_text = template.body_text or _html_to_text(template.body_html)
    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    # HTML версия с уникализацией
    unique_html = _uniquify_html(template.body_html, tracking_id)
    msg.attach(MIMEText(unique_html, "html", "utf-8"))

    # Вложения
    for attachment_path in template.attachments:
        path = Path(attachment_path)
        if path.exists():
            with open(path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                "attachment",
                filename=path.name,
            )
            msg.attach(part)

    return msg


# ──────────────────────────────────────────────
# Ротация аккаунтов
# ──────────────────────────────────────────────

class AccountRotator:
    """Управляет ротацией SMTP-аккаунтов."""

    def __init__(self, accounts: List[SmtpAccount], mode: str = "round-robin"):
        self.accounts = [a for a in accounts if a.is_active]
        self.mode = mode
        self._index = 0

    def get_account(self) -> Optional[SmtpAccount]:
        """Возвращает следующий доступный аккаунт."""
        available = [a for a in self.accounts if a.can_send]
        if not available:
            return None

        if self.mode == "round-robin":
            self._index = self._index % len(available)
            account = available[self._index]
            self._index += 1
            return account

        elif self.mode == "random":
            return random.choice(available)

        elif self.mode == "weighted":
            # Вес = (daily_limit - sent_today) / daily_limit
            weights = [
                max(0, (a.daily_limit - a.sent_today) / a.daily_limit)
                for a in available
            ]
            total = sum(weights)
            if total == 0:
                return None
            r = random.uniform(0, total)
            cumulative = 0.0
            for a, w in zip(available, weights):
                cumulative += w
                if r <= cumulative:
                    return a
            return available[-1]

        return available[0]


# ──────────────────────────────────────────────
# Асинхронный движок отправки
# ──────────────────────────────────────────────

class SendingEngine:
    """
    Основной асинхронный движок рассылки.
    Управляет пулом воркеров, очередью задач и graceful shutdown.
    """

    def __init__(
        self,
        accounts: List[SmtpAccount],
        config: CampaignConfig,
        log_queue: queue.Queue,
    ):
        self.accounts = accounts
        self.config = config
        self.log_queue = log_queue
        self.rotator = AccountRotator(accounts, config.rotation_mode)

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._task_queue: Optional[asyncio.Queue] = None
        self._is_paused = False
        self._is_stopped = False
        self._sent_count = 0
        self._success_count = 0
        self._error_count = 0
        self._results: List[SendResult] = []

        # Callbacks для обновления GUI
        self.on_progress: Optional[Callable[[int, int, SendResult], None]] = None
        self.on_finished: Optional[Callable[[List[SendResult]], None]] = None

    def _log(self, msg: str, level: str = "INFO") -> None:
        """Потокобезопасное логирование через queue."""
        self.log_queue.put_nowait({"time": datetime.now().isoformat(), "level": level, "msg": msg})

    async def _send_one(
        self,
        account: SmtpAccount,
        recipient: Recipient,
        template: EmailTemplate,
    ) -> SendResult:
        """Отправляет одно письмо через aiosmtplib."""
        tracking_id = str(uuid.uuid4()).replace("-", "")
        personalized = template.personalize(recipient)
        msg = _build_message(account, recipient, personalized, tracking_id)

        try:
            smtp_kwargs = {
                "hostname": account.host,
                "port": account.port,
                "username": account.email,
                "password": account.password,
                "use_tls": account.use_ssl,
                "start_tls": account.use_tls,
                "timeout": 30,
            }
            async with aiosmtplib.SMTP(**smtp_kwargs) as smtp:
                await smtp.send_message(msg)

            account.sent_today += 1
            account.sent_this_hour += 1
            account.last_sent = time.time()
            self._log(f"✓ {recipient.email} отправлено через {account.email}")
            return SendResult(
                recipient_email=recipient.email,
                success=True,
                account_used=account.email,
                message_id=msg["Message-ID"],
            )

        except aiosmtplib.SMTPAuthenticationError:
            self._log(f"✗ {account.email}: ошибка аутентификации", "ERROR")
            account.is_active = False
            return SendResult(
                recipient_email=recipient.email,
                success=False,
                error="Ошибка аутентификации SMTP",
                account_used=account.email,
            )

        except aiosmtplib.SMTPRecipientsRefused:
            self._log(f"✗ {recipient.email}: адрес отклонён", "WARN")
            return SendResult(
                recipient_email=recipient.email,
                success=False,
                error="Адрес получателя отклонён",
                account_used=account.email,
            )

        except asyncio.TimeoutError:
            self._log(f"✗ {recipient.email}: таймаут соединения", "WARN")
            return SendResult(
                recipient_email=recipient.email,
                success=False,
                error="Таймаут соединения с SMTP-сервером",
                account_used=account.email,
            )

        except Exception as e:
            self._log(f"✗ {recipient.email}: {str(e)}", "ERROR")
            return SendResult(
                recipient_email=recipient.email,
                success=False,
                error=str(e),
                account_used=account.email,
            )

    async def _worker(self, worker_id: int) -> None:
        """Воркер, обрабатывающий задачи из очереди."""
        while not self._is_stopped:
            # Проверяем паузу
            while self._is_paused and not self._is_stopped:
                await asyncio.sleep(0.5)

            try:
                item = await asyncio.wait_for(self._task_queue.get(), timeout=2.0)
            except asyncio.TimeoutError:
                continue

            if item is None:  # Сигнал остановки
                break

            recipient, template = item

            # Задержка между письмами (gaussian anti-spam)
            delay_ms = random.randint(
                self.config.min_delay_ms,
                self.config.max_delay_ms,
            )
            await asyncio.sleep(delay_ms / 1000.0)

            # Пауза после N писем
            if self._sent_count > 0 and self._sent_count % self.config.pause_after_n == 0:
                self._log(f"Пауза {self.config.pause_duration_sec}с после {self._sent_count} писем")
                await asyncio.sleep(self.config.pause_duration_sec)

            async with self._semaphore:
                account = self.rotator.get_account()
                if not account:
                    self._log("Нет доступных аккаунтов!", "ERROR")
                    self._task_queue.task_done()
                    continue

                result = await self._send_one(account, recipient, template)
                self._results.append(result)
                self._sent_count += 1

                if result.success:
                    self._success_count += 1
                else:
                    self._error_count += 1

                if self.on_progress:
                    total = self._task_queue.qsize() + self._sent_count
                    self.on_progress(self._sent_count, total, result)

            self._task_queue.task_done()

    async def run_campaign(
        self,
        recipients: List[Recipient],
        template: EmailTemplate,
    ) -> List[SendResult]:
        """Запускает кампанию рассылки."""
        self._is_paused = False
        self._is_stopped = False
        self._sent_count = 0
        self._success_count = 0
        self._error_count = 0
        self._results = []

        self._semaphore = asyncio.Semaphore(self.config.max_threads)
        self._task_queue = asyncio.Queue()

        # Заполняем очередь
        for recipient in recipients:
            await self._task_queue.put((recipient, template))

        # Добавляем сигналы остановки для каждого воркера
        for _ in range(self.config.max_threads):
            await self._task_queue.put(None)

        # Запускаем воркеров
        self._log(f"Запуск {self.config.max_threads} воркеров для {len(recipients)} получателей")
        workers = [
            asyncio.create_task(self._worker(i))
            for i in range(self.config.max_threads)
        ]

        await asyncio.gather(*workers, return_exceptions=True)

        self._log(
            f"Кампания завершена: {self._success_count} успешно, "
            f"{self._error_count} ошибок из {len(recipients)}"
        )

        if self.on_finished:
            self.on_finished(self._results)

        return self._results

    def pause(self) -> None:
        """Приостанавливает отправку."""
        self._is_paused = True
        self._log("Рассылка приостановлена")

    def resume(self) -> None:
        """Возобновляет отправку."""
        self._is_paused = False
        self._log("Рассылка возобновлена")

    def stop(self) -> None:
        """Останавливает рассылку (graceful shutdown)."""
        self._is_stopped = True
        self._log("Остановка рассылки...")

    @property
    def stats(self) -> dict:
        """Возвращает статистику текущей кампании."""
        return {
            "sent": self._sent_count,
            "success": self._success_count,
            "errors": self._error_count,
            "queued": self._task_queue.qsize() if self._task_queue else 0,
        }


# ──────────────────────────────────────────────
# Тест подключения к SMTP
# ──────────────────────────────────────────────

async def test_smtp_connection(account: SmtpAccount) -> Tuple[bool, str]:
    """
    Тестирует подключение к SMTP-серверу.
    Возвращает (success, log_message).
    """
    from typing import Tuple
    log_lines = []
    log_lines.append(f"Подключение к {account.host}:{account.port}...")

    try:
        smtp = aiosmtplib.SMTP(
            hostname=account.host,
            port=account.port,
            use_tls=account.use_ssl,
            start_tls=account.use_tls,
            timeout=15,
        )
        await smtp.connect()
        log_lines.append(f"✓ Соединение установлено")

        await smtp.login(account.email, account.password)
        log_lines.append(f"✓ Аутентификация успешна")

        await smtp.quit()
        log_lines.append(f"✓ SMTP тест пройден успешно")
        return True, "\n".join(log_lines)

    except aiosmtplib.SMTPAuthenticationError as e:
        log_lines.append(f"✗ Ошибка аутентификации: {str(e)}")
        return False, "\n".join(log_lines)

    except aiosmtplib.SMTPConnectError as e:
        log_lines.append(f"✗ Ошибка подключения: {str(e)}")
        return False, "\n".join(log_lines)

    except Exception as e:
        log_lines.append(f"✗ Ошибка: {type(e).__name__}: {str(e)}")
        return False, "\n".join(log_lines)


# ──────────────────────────────────────────────
# Автоопределение SMTP-настроек по домену
# ──────────────────────────────────────────────

# Известные провайдеры (fallback без Mozilla Autoconfig)
KNOWN_PROVIDERS = {
    "gmail.com": SmtpAccount.__new__(SmtpAccount),
    "googlemail.com": {"host": "smtp.gmail.com", "port": 465, "use_ssl": True},
    "outlook.com": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "hotmail.com": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "live.com": {"host": "smtp.office365.com", "port": 587, "use_ssl": False, "use_tls": True},
    "yahoo.com": {"host": "smtp.mail.yahoo.com", "port": 465, "use_ssl": True},
    "mail.ru": {"host": "smtp.mail.ru", "port": 465, "use_ssl": True},
    "yandex.ru": {"host": "smtp.yandex.ru", "port": 465, "use_ssl": True},
    "yandex.com": {"host": "smtp.yandex.com", "port": 465, "use_ssl": True},
    "icloud.com": {"host": "smtp.mail.me.com", "port": 587, "use_ssl": False, "use_tls": True},
}


def get_smtp_config_for_domain(domain: str) -> Optional[dict]:
    """Возвращает настройки SMTP для известного домена."""
    domain = domain.lower()
    if domain in KNOWN_PROVIDERS:
        cfg = KNOWN_PROVIDERS[domain]
        if isinstance(cfg, dict):
            return cfg
    return None
