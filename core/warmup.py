"""
Модуль прогрева SMTP-аккаунтов.
v2.7.0: исправлен _save_counter (теперь инкрементируется и вызывает автосохранение каждые 10 операций).
"""
import atexit
import json
import math
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Optional


def get_warmup_limit(day: int) -> int:
    if day <= 0:
        return 0
    if day >= 30:
        return 500 + (day - 30) * 20
    limit = int(5 * math.exp(0.15 * (day - 1)))
    return min(limit, 500)


WARMUP_SCHEDULE = {day: get_warmup_limit(day) for day in range(0, 61)}


@dataclass
class WarmupRecord:
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


_AUTOSAVE_EVERY = 10  # сохранять каждые N операций


class WarmupScheduler:
    def __init__(self, data_path: Path):
        self.data_path = data_path
        self.records: Dict[str, WarmupRecord] = {}
        self._save_counter: int = 0  # FIX: явная инициализация
        self._load()
        atexit.register(self.flush)

    def _advance_pending_days(self, record: WarmupRecord) -> None:
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
                f, ensure_ascii=False, indent=2,
            )
        self._save_counter = 0

    def _maybe_save(self) -> None:
        """FIX: инкрементируем счётчик и сохраняем каждые N операций."""
        self._save_counter += 1
        if self._save_counter >= _AUTOSAVE_EVERY:
            self._save()

    def flush(self) -> None:
        """Принудительное сохранение при завершении приложения."""
        if self.records:
            self._save()

    def add_account(self, email: str) -> WarmupRecord:
        r = WarmupRecord(
            email=email,
            start_date=date.today().isoformat(),
        )
        self.records[email] = r
        self._save()
        return r

    def remove_account(self, email: str) -> None:
        self.records.pop(email, None)
        self._save()

    def record_sent(self, email: str, count: int = 1) -> None:
        r = self.records.get(email)
        if r:
            r.record_sent(count)
            self._maybe_save()  # FIX: используем _maybe_save вместо прямого _save

    def get_record(self, email: str) -> Optional[WarmupRecord]:
        return self.records.get(email)

    def get_all(self) -> Dict[str, WarmupRecord]:
        return dict(self.records)

    def advance_days(self) -> None:
        """Обновляет текущий день для всех активных аккаунтов."""
        for r in self.records.values():
            self._advance_pending_days(r)
        self._maybe_save()

    def pause_account(self, email: str, until_date: Optional[str] = None) -> None:
        r = self.records.get(email)
        if r:
            r.is_active = False
            r.paused_until = until_date
            self._maybe_save()

    def resume_account(self, email: str) -> None:
        r = self.records.get(email)
        if r:
            r.is_active = True
            r.paused_until = None
            self._maybe_save()
