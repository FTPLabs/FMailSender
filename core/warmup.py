"""
Модуль прогрева SMTP-аккаунтов.
Автоматически увеличивает объём отправки по кривой: день 1→5, день 7→50, день 30→500+
"""
import asyncio
import json
import math
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional


def get_warmup_limit(day: int) -> int:
    """
    Возвращает максимальное количество писем для заданного дня прогрева.
    день 1: 5 | день 7: 50 | день 14: 150 | день 21: 300 | день 30: 500+
    """
    if day <= 0:
        return 0
    if day >= 30:
        return 500 + (day - 30) * 20
    limit = int(5 * math.exp(0.15 * (day - 1)))
    return min(limit, 500)


WARMUP_SCHEDULE = {day: get_warmup_limit(day) for day in range(1, 61)}


@dataclass
class WarmupRecord:
    """Запись прогрева для одного аккаунта."""
    email: str
    start_date: str
    current_day: int = 1
    total_sent: int = 0
    daily_log: Dict[str, int] = field(default_factory=dict)
    is_active: bool = True
    paused_until: Optional[str] = None

    @property
    def today_limit(self) -> int:
        return get_warmup_limit(self.current_day)

    @property
    def today_sent(self) -> int:
        return self.daily_log.get(date.today().isoformat(), 0)

    def can_send_today(self) -> bool:
        return self.is_active and self.today_sent < self.today_limit

    def record_sent(self, count: int = 1) -> None:
        today_str = date.today().isoformat()
        self.daily_log[today_str] = self.daily_log.get(today_str, 0) + count
        self.total_sent += count

    def advance_day(self) -> None:
        self.current_day += 1

    def to_dict(self) -> dict:
        return {
            "email": self.email,
            "start_date": self.start_date,
            "current_day": self.current_day,
            "total_sent": self.total_sent,
            "daily_log": self.daily_log,
            "is_active": self.is_active,
            "paused_until": self.paused_until,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WarmupRecord":
        r = cls(
            email=data["email"],
            start_date=data["start_date"],
            current_day=data.get("current_day", 1),
            total_sent=data.get("total_sent", 0),
            is_active=data.get("is_active", True),
            paused_until=data.get("paused_until"),
        )
        r.daily_log = data.get("daily_log", {})
        return r


class WarmupScheduler:
    """
    Управляет прогревом нескольких SMTP-аккаунтов.
    Хранит данные в JSON-файле.
    """

    def __init__(self, data_path: Path):
        self.data_path = data_path
        self.records: Dict[str, WarmupRecord] = {}
        self._load()

    def _advance_pending_days(self, record: WarmupRecord) -> None:
        """Автоматически продвигает счётчик дней прогрева по календарю."""
        if not record.is_active:
            return
        try:
            start = date.fromisoformat(record.start_date)
            expected_day = (date.today() - start).days + 1
            if expected_day > record.current_day:
                record.current_day = min(expected_day, 60)
        except (ValueError, TypeError):
            pass

    def _load(self) -> None:
        if self.data_path.exists():
            try:
                with open(self.data_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                for email, data in raw.items():
                    r = WarmupRecord.from_dict(data)
                    self._advance_pending_days(r)
                    self.records[email] = r
            except Exception:
                self.records = {}

    def _save(self) -> None:
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.data_path, "w", encoding="utf-8") as f:
            json.dump(
                {email: r.to_dict() for email, r in self.records.items()},
                f, ensure_ascii=False, indent=2
            )

    def add_account(self, email: str) -> WarmupRecord:
        if email not in self.records:
            self.records[email] = WarmupRecord(
                email=email,
                start_date=date.today().isoformat(),
            )
            self._save()
        return self.records[email]

    def remove_account(self, email: str) -> None:
        self.records.pop(email, None)
        self._save()

    def get_record(self, email: str) -> Optional[WarmupRecord]:
        return self.records.get(email)

    def get_all_records(self) -> List[WarmupRecord]:
        return list(self.records.values())

    def record_sent(self, email: str, count: int = 1) -> None:
        record = self.records.get(email)
        if record:
            record.record_sent(count)
            self._save()

    def can_send(self, email: str) -> bool:
        record = self.records.get(email)
        return record.can_send_today() if record else False

    def get_today_limit(self, email: str) -> int:
        record = self.records.get(email)
        return record.today_limit if record else 0

    def pause_account(self, email: str, until=None) -> None:
        record = self.records.get(email)
        if record:
            record.is_active = False
            if until:
                record.paused_until = until.isoformat()
            self._save()

    def resume_account(self, email: str) -> None:
        record = self.records.get(email)
        if record:
            record.is_active = True
            record.paused_until = None
            self._save()

    def get_summary(self) -> dict:
        active = sum(1 for r in self.records.values() if r.is_active)
        total_sent = sum(r.total_sent for r in self.records.values())
        return {
            "total_accounts": len(self.records),
            "active_accounts": active,
            "total_sent": total_sent,
        }
