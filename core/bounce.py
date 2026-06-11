"""
IMAP bounce-парсер. Мониторит входящие, определяет hard/soft bounces,
добавляет hard bounce в blacklist.
"""
import email
import os
import imaplib
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional, Set

logger = logging.getLogger("bounce")


class BounceType(Enum):
    HARD = "hard"
    SOFT = "soft"
    UNKNOWN = "unknown"


@dataclass
class BounceRecord:
    email: str
    bounce_type: BounceType
    code: str
    message: str
    received_at: str
    original_subject: str = ""

    def to_dict(self) -> dict:
        return {
            "email": self.email,
            "bounce_type": self.bounce_type.value,
            "code": self.code,
            "message": self.message,
            "received_at": self.received_at,
            "original_subject": self.original_subject,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BounceRecord":
        return cls(
            email=d["email"],
            bounce_type=BounceType(d.get("bounce_type", "unknown")),
            code=d.get("code", ""),
            message=d.get("message", ""),
            received_at=d.get("received_at", ""),
            original_subject=d.get("original_subject", ""),
        )


HARD_BOUNCE_CODES = re.compile(
    r"\b(5[0-9]{2})\b.*"
    r"(user.?unknown|no.?such.?user|invalid.?address|does.?not.?exist|"
    r"mailbox.?not.?found|address.?rejected|bad.?destination|"
    r"permanent.?failure|undeliverable)",
    re.IGNORECASE,
)
SOFT_BOUNCE_CODES = re.compile(
    r"\b(4[0-9]{2})\b.*"
    r"(temporarily|try.?again|over.?quota|mailbox.?full|"
    r"service.?unavailable|deferred|too.?many)",
    re.IGNORECASE,
)
EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)

# IMAP search queries — порядок от наиболее специфичного к общему
_IMAP_SEARCHES = [
    'FROM "MAILER-DAEMON"',
    'SUBJECT "Delivery Status Notification"',
    'SUBJECT "Undelivered Mail Returned to Sender"',
    'SUBJECT "Mail delivery failed"',
    'SUBJECT "Delivery Failure"',
    'SUBJECT "Undeliverable"',
    'SUBJECT "недоставлено"',
]


def _parse_dsn_message(raw_message: bytes) -> Optional[BounceRecord]:
    try:
        msg = email.message_from_bytes(raw_message)
    except Exception:
        return None

    subject = msg.get("Subject", "")
    is_bounce_subject = any(keyword in subject.lower() for keyword in [
        "delivery", "undelivered", "failure", "returned", "bounce",
        "недоставлено", "ошибка доставки", "mailer-daemon", "undeliverable",
        "mail delivery failed",
    ])
    sender = msg.get("From", "").lower()
    is_mailer_daemon = "mailer-daemon" in sender or "postmaster" in sender

    if not (is_bounce_subject or is_mailer_daemon):
        return None

    status_text = ""
    original_recipient = ""
    smtp_code = ""
    dsn_message = ""

    for part in msg.walk():
        content_type = part.get_content_type()
        if content_type == "message/delivery-status":
            try:
                payload = part.get_payload()
                if isinstance(payload, list):
                    status_text = "\n".join(
                        sub.as_string() if hasattr(sub, "as_string") else str(sub)
                        for sub in payload
                    )
                elif isinstance(payload, bytes):
                    status_text = payload.decode("utf-8", errors="replace")
                elif isinstance(payload, str):
                    status_text = payload
            except Exception:
                pass
        elif content_type == "text/plain":
            try:
                text = part.get_payload(decode=True)
                if isinstance(text, bytes):
                    text = text.decode("utf-8", errors="replace")
                dsn_message += text + "\n"
            except Exception:
                pass

    combined = (status_text + "\n" + dsn_message).lower()

    final_recipient = re.search(
        r"final-recipient[:\s]+rfc822[;\s]+([^\s\n]+)", combined, re.IGNORECASE
    )
    if final_recipient:
        original_recipient = final_recipient.group(1).strip("<>").strip()
    else:
        emails = EMAIL_PATTERN.findall(dsn_message + status_text)
        for e in emails:
            if "mailer-daemon" not in e.lower() and "postmaster" not in e.lower():
                original_recipient = e
                break

    if not original_recipient:
        return None

    status_code_match = re.search(r"status[:\s]+(\d\.\d+\.\d+)", combined, re.IGNORECASE)
    if status_code_match:
        smtp_code = status_code_match.group(1)

    numeric_code = re.search(r"\b([45]\d{2})\b", combined)
    if numeric_code:
        smtp_code = smtp_code or numeric_code.group(1)

    bounce_type = BounceType.UNKNOWN
    if smtp_code:
        if smtp_code.startswith("5"):
            bounce_type = BounceType.HARD
        elif smtp_code.startswith("4"):
            bounce_type = BounceType.SOFT

    if bounce_type == BounceType.UNKNOWN:
        if HARD_BOUNCE_CODES.search(combined):
            bounce_type = BounceType.HARD
        elif SOFT_BOUNCE_CODES.search(combined):
            bounce_type = BounceType.SOFT

    return BounceRecord(
        email=original_recipient,
        bounce_type=bounce_type,
        code=smtp_code,
        message=dsn_message[:500].strip(),
        received_at=datetime.now().isoformat(),
        original_subject=subject,
    )


class BounceMonitor:
    def __init__(
        self,
        imap_host: str,
        imap_port: int,
        email_addr: str,
        password: str,
        use_ssl: bool = True,
        blacklist_path: Optional[Path] = None,
        bounce_log_path: Optional[Path] = None,
    ):
        self.imap_host = imap_host
        self.imap_port = imap_port
        self.email_addr = email_addr
        self.password = password
        self.use_ssl = use_ssl
        self.blacklist_path = blacklist_path or (
            Path(os.environ.get("APPDATA", ".")) / "FMailSender" / "blacklist.json"
        )
        self.bounce_log_path = bounce_log_path or Path("data/bounces.json")
        self._blacklist: Set[str] = self._load_blacklist()
        self._bounce_records: List[BounceRecord] = self._load_bounces()

    def _load_blacklist(self) -> Set[str]:
        if self.blacklist_path.exists():
            try:
                with open(self.blacklist_path, "r", encoding="utf-8") as f:
                    return set(json.load(f))
            except Exception:
                pass
        return set()

    def _save_blacklist(self) -> None:
        self.blacklist_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.blacklist_path, "w", encoding="utf-8") as f:
            json.dump(list(self._blacklist), f, ensure_ascii=False, indent=2)

    def _load_bounces(self) -> List[BounceRecord]:
        if self.bounce_log_path.exists():
            try:
                with open(self.bounce_log_path, "r", encoding="utf-8") as f:
                    return [BounceRecord.from_dict(d) for d in json.load(f)]
            except Exception:
                pass
        return []

    def _save_bounces(self) -> None:
        self.bounce_log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.bounce_log_path, "w", encoding="utf-8") as f:
            json.dump([r.to_dict() for r in self._bounce_records], f, ensure_ascii=False, indent=2)

    def is_blacklisted(self, email_addr: str) -> bool:
        return email_addr.lower() in self._blacklist

    def add_to_blacklist(self, email_addr: str) -> None:
        self._blacklist.add(email_addr.lower())
        self._save_blacklist()

    def check_bounces(self) -> List[BounceRecord]:
        new_bounces = []
        try:
            if self.use_ssl:
                conn = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            else:
                conn = imaplib.IMAP4(self.imap_host, self.imap_port)

            conn.login(self.email_addr, self.password)
            conn.select("INBOX")

            # FIX: перебираем все паттерны поиска, собираем уникальные ID
            found_ids: Set[bytes] = set()
            for search_query in _IMAP_SEARCHES:
                try:
                    _, msg_ids = conn.search(None, f'UNSEEN {search_query}')
                    if msg_ids and msg_ids[0]:
                        for mid in msg_ids[0].split():
                            found_ids.add(mid)
                except Exception:
                    continue

            for msg_id in found_ids:
                try:
                    _, data = conn.fetch(msg_id, "(RFC822)")
                    raw = data[0][1]
                    bounce = _parse_dsn_message(raw)
                    if bounce:
                        conn.store(msg_id, '+FLAGS', '\\Seen')
                        new_bounces.append(bounce)
                        self._bounce_records.append(bounce)
                        if bounce.bounce_type == BounceType.HARD:
                            self.add_to_blacklist(bounce.email)
                            logger.info(f"Hard bounce → blacklist: {bounce.email}")
                except Exception as e:
                    logger.warning(f"Ошибка обработки сообщения {msg_id}: {e}")

            conn.logout()
            if new_bounces:
                self._save_bounces()

        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP ошибка: {e}")
        except Exception as e:
            logger.error(f"Ошибка мониторинга bounces: {e}")

        return new_bounces

    def filter_recipients(self, emails: List[str]) -> tuple:
        allowed = []
        blocked = []
        for e in emails:
            if self.is_blacklisted(e):
                blocked.append(e)
            else:
                allowed.append(e)
        return allowed, blocked

    @property
    def blacklist_count(self) -> int:
        return len(self._blacklist)

    @property
    def hard_bounce_count(self) -> int:
        return sum(1 for r in self._bounce_records if r.bounce_type == BounceType.HARD)

    @property
    def soft_bounce_count(self) -> int:
        return sum(1 for r in self._bounce_records if r.bounce_type == BounceType.SOFT)

    def get_bounce_summary(self) -> dict:
        return {
            "total": len(self._bounce_records),
            "hard": self.hard_bounce_count,
            "soft": self.soft_bounce_count,
            "blacklist_size": self.blacklist_count,
        }
