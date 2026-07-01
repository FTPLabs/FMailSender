"""
FMailSender Reply Monitor v1.0.0
Monitors IMAP inbox for real replies (not bounces) from campaign recipients.
Emits reply_received signal for PyQt6 GUI integration.
"""
from __future__ import annotations

import email
import email.header
import imaplib
import json
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

logger = logging.getLogger("reply_monitor")


@dataclass
class ReplyMessage:
    uid: str
    from_addr: str
    from_name: str
    subject: str
    body_text: str
    body_html: str
    received_at: str
    in_reply_to: str
    original_campaign: str = ""

    def to_dict(self) -> dict:
        return {
            "uid": self.uid,
            "from_addr": self.from_addr,
            "from_name": self.from_name,
            "subject": self.subject,
            "body_text": self.body_text,
            "body_html": self.body_html,
            "received_at": self.received_at,
            "in_reply_to": self.in_reply_to,
            "original_campaign": self.original_campaign,
        }


def _decode_header(raw: str) -> str:
    """Decode RFC 2047 encoded email header."""
    parts = email.header.decode_header(raw or "")
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(str(part))
    return "".join(result)


def _extract_body(msg: email.message.Message) -> tuple[str, str]:
    """Extract (text, html) body from email message."""
    text, html = "", ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain" and not text:
                text = part.get_payload(decode=True).decode(
                    part.get_content_charset() or "utf-8", errors="replace")
            elif ct == "text/html" and not html:
                html = part.get_payload(decode=True).decode(
                    part.get_content_charset() or "utf-8", errors="replace")
    else:
        ct = msg.get_content_type()
        payload = msg.get_payload(decode=True) or b""
        decoded = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
        if ct == "text/plain":
            text = decoded
        else:
            html = decoded
    return text, html


# Bounce detection patterns (skip these — bounce.py handles them)
_BOUNCE_PATTERNS = re.compile(
    r"mailer-daemon|postmaster|delivery.status|failed.delivery|"
    r"undeliverable|mail.delivery.failure|auto.reply|out.of.office",
    re.IGNORECASE,
)


class ReplyMonitor:
    """
    Monitors IMAP inbox for real replies from campaign recipients.
    Runs in a daemon thread; calls callbacks from that thread (use Qt signals).

    Usage:
        monitor = ReplyMonitor(
            email="sender@example.com", password="...",
            imap_host="imap.example.com", imap_port=993, imap_ssl=True,
            on_reply=lambda r: my_signal.emit(r.to_dict()),
            on_count=lambda n: badge_signal.emit(n),
        )
        monitor.start()  # non-blocking
        monitor.stop()   # graceful stop
    """

    POLL_INTERVAL = 30  # seconds between INBOX checks

    def __init__(
        self,
        email_addr: str,
        password: str,
        imap_host: str,
        imap_port: int = 993,
        imap_ssl: bool = True,
        sent_ids_path: Optional[Path] = None,
        on_reply: Optional[Callable[[ReplyMessage], None]] = None,
        on_count: Optional[Callable[[int], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ):
        self._email = email_addr
        self._password = password
        self._host = imap_host
        self._port = imap_port
        self._ssl = imap_ssl
        self._sent_ids_path = sent_ids_path or Path("data/sent_message_ids.json")
        self._on_reply = on_reply or (lambda r: None)
        self._on_count = on_count or (lambda n: None)
        self._on_error = on_error or (lambda e: logger.error(e))
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._seen_uids: Set[str] = set()

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name=f"ReplyMonitor-{self._email}")
        self._thread.start()
        logger.info("ReplyMonitor started for %s", self._email)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("ReplyMonitor stopped for %s", self._email)

    # ── Thread body ───────────────────────────────────────────────────────────

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._check_inbox()
            except Exception as e:
                self._on_error(f"IMAP error: {e}")
                logger.exception("ReplyMonitor error")
            self._stop_event.wait(self.POLL_INTERVAL)

    def _check_inbox(self) -> None:
        sent_ids = self._load_sent_ids()
        if not sent_ids:
            return  # No tracked messages → nothing to match

        cls = imaplib.IMAP4_SSL if self._ssl else imaplib.IMAP4
        with cls(self._host, self._port, timeout=30) as imap:  # FIX HANG-1
            imap.login(self._email, self._password)
            imap.select("INBOX")
            _, uid_data = imap.uid("search", None, "UNSEEN")
            uids = uid_data[0].split() if uid_data and uid_data[0] else []
            new_replies: List[ReplyMessage] = []

            for uid in uids:
                uid_str = uid.decode()
                if uid_str in self._seen_uids:
                    continue
                _, msg_data = imap.uid("fetch", uid, "(RFC822)")
                if not msg_data or not msg_data[0]:
                    continue
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)

                if self._is_real_reply(msg, sent_ids):
                    reply = self._parse_reply(uid_str, msg, sent_ids)
                    self._seen_uids.add(uid_str)
                    new_replies.append(reply)
                    self._on_reply(reply)

            if new_replies:
                self._on_count(len(new_replies))

    def _is_real_reply(
        self, msg: email.message.Message, sent_ids: Set[str]
    ) -> bool:
        from_addr = msg.get("From", "")
        subject = _decode_header(msg.get("Subject", ""))
        in_reply_to = msg.get("In-Reply-To", "")
        references = msg.get("References", "")

        # Skip bounces
        if _BOUNCE_PATTERNS.search(from_addr) or _BOUNCE_PATTERNS.search(subject):
            return False
        # Must reference one of our sent messages
        return any(mid in in_reply_to or mid in references for mid in sent_ids)

    def _parse_reply(
        self, uid: str, msg: email.message.Message, sent_ids: Set[str]
    ) -> ReplyMessage:
        from_raw = _decode_header(msg.get("From", ""))
        match = re.match(r'"?([^"<]+)"?\s*<?([^>]*)>?', from_raw)  # FIX REGEX-1: s* -> \s*
        from_name = match.group(1).strip() if match else from_raw
        from_addr = match.group(2).strip() if match else from_raw
        subject = _decode_header(msg.get("Subject", ""))
        in_reply_to = msg.get("In-Reply-To", "")
        references = msg.get("References", "")
        text, html = _extract_body(msg)
        # Find which campaign this reply belongs to
        campaign = ""
        for mid in sent_ids:
            if mid in in_reply_to or mid in references:
                campaign = mid
                break
        return ReplyMessage(
            uid=uid,
            from_addr=from_addr,
            from_name=from_name,
            subject=subject,
            body_text=text,
            body_html=html,
            received_at=datetime.now().isoformat(),
            in_reply_to=in_reply_to,
            original_campaign=campaign,
        )

    # ── Sent IDs storage ──────────────────────────────────────────────────────

    def _load_sent_ids(self) -> Set[str]:
        if not self._sent_ids_path.exists():
            return set()
        try:
            data = json.loads(self._sent_ids_path.read_text(encoding="utf-8"))
            ids: Set[str] = set()
            for campaign_ids in data.values():
                ids.update(campaign_ids if isinstance(campaign_ids, list) else [])
            return ids
        except Exception:
            return set()

    @staticmethod
    def save_sent_id(message_id: str, campaign_id: str,
                     path: Path = Path("data/sent_message_ids.json")) -> None:
        """Call this after each successful send to track Message-IDs."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data: Dict[str, List[str]] = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        data.setdefault(campaign_id, []).append(message_id)
        # Keep last 10k IDs per campaign to limit file size
        data[campaign_id] = data[campaign_id][-10_000:]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
