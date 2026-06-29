"""
FMailSender — Data models v6.0
Single source of truth for all data structures.
"""
from __future__ import annotations
import threading
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SmtpAccount:
    """SMTP аккаунт для отправки писем."""
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
    proxy_list: list[str] = field(default_factory=list)
    access_token: str = ""
    refresh_token: str = ""
    token_expires_at: float = 0.0
    imap_host: str = ""
    imap_port: int = 993
    imap_ssl: bool = True
    last_test_ok: Optional[bool] = None
    last_test_msg: str = ""
    sent_today: int = 0
    sent_this_hour: int = 0

    def __post_init__(self) -> None:
        self._lock: threading.Lock = threading.Lock()
        self._day_reset: float = time.time()
        self._hour_reset: float = time.time()

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
        """Thread-safe проверка лимитов."""
        if not self.is_active:
            return False
        with self._lock:
            self._tick_resets()
            return self.sent_today < self.daily_limit and self.sent_this_hour < self.hourly_limit

    def try_increment(self) -> bool:
        """Атомарная проверка + инкремент. Устраняет TOCTOU race condition."""
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
        """Откатывает инкремент если отправка провалилась."""
        with self._lock:
            if self.sent_today > 0:
                self.sent_today -= 1
            if self.sent_this_hour > 0:
                self.sent_this_hour -= 1

    def to_dict(self) -> dict:
        return {
            "email": self.email,
            "password": self.password,
            "host": self.host,
            "port": self.port,
            "use_ssl": self.use_ssl,
            "use_tls": self.use_tls,
            "display_name": self.display_name,
            "daily_limit": self.daily_limit,
            "hourly_limit": self.hourly_limit,
            "is_active": self.is_active,
            "proxy": self.proxy,
            "proxy_list": self.proxy_list,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_expires_at": self.token_expires_at,
            "imap_host": self.imap_host,
            "imap_port": self.imap_port,
            "imap_ssl": self.imap_ssl,
            "last_test_ok": self.last_test_ok,
            "last_test_msg": self.last_test_msg,
            "sent_today": self.sent_today,
            "sent_this_hour": self.sent_this_hour,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SmtpAccount":
        return cls(
            email=d.get("email", ""),
            password=d.get("password", ""),
            host=d.get("host", ""),
            port=d.get("port", 465),
            use_ssl=d.get("use_ssl", True),
            use_tls=d.get("use_tls", False),
            display_name=d.get("display_name", ""),
            daily_limit=d.get("daily_limit", 500),
            hourly_limit=d.get("hourly_limit", 50),
            is_active=d.get("is_active", True),
            proxy=d.get("proxy", ""),
            proxy_list=d.get("proxy_list", []),
            access_token=d.get("access_token", ""),
            refresh_token=d.get("refresh_token", ""),
            token_expires_at=d.get("token_expires_at", 0.0),
            imap_host=d.get("imap_host", ""),
            imap_port=d.get("imap_port", 993),
            imap_ssl=d.get("imap_ssl", True),
            last_test_ok=d.get("last_test_ok"),
            last_test_msg=d.get("last_test_msg", ""),
            sent_today=d.get("sent_today", 0),
            sent_this_hour=d.get("sent_this_hour", 0),
        )


@dataclass
class Recipient:
    """Получатель письма."""
    email: str
    name: str = ""
    variables: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"email": self.email, "name": self.name, "variables": self.variables}

    @classmethod
    def from_dict(cls, d: dict) -> "Recipient":
        return cls(email=d["email"], name=d.get("name", ""), variables=d.get("variables", {}))


@dataclass
class CampaignConfig:
    """Конфиг рассылки."""
    subject: str = ""
    body_html: str = ""
    body_text: str = ""
    from_name: str = ""
    reply_to: str = ""
    delay_min: float = 1.0
    delay_max: float = 3.0
    daily_limit_per_account: int = 500
    attachments: list[str] = field(default_factory=list)


@dataclass
class CampaignStatus:
    """Текущий статус рассылки."""
    state: str = "idle"          # idle | running | paused | done | error
    sent: int = 0
    failed: int = 0
    total: int = 0
    current_email: str = ""
    current_account: str = ""
    started_at: float = 0.0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "sent": self.sent,
            "failed": self.failed,
            "total": self.total,
            "current_email": self.current_email,
            "current_account": self.current_account,
            "started_at": self.started_at,
            "progress_pct": round(self.sent / max(self.total, 1) * 100, 1),
            "errors": self.errors[-20:],  # last 20 errors
        }
