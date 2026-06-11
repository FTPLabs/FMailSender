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

# ──────────────────────────────────────────────
# Кривая прогрева
# ──────────────────────────────────────────────

def get_warmup_limit(day: int) -> int:
    """
    Возвращает максимальное количество писем для заданного дня прогрева.
    Кривая: экспоненциальный рост от 5 до 500+
    день 1:  5
    день 7:  50
    день 14: 150
    день 21: 300
    день 30: 500+
    """
    if day <= 0:
        return 0
    if day >= 30:
        return 500 + (day - 30) * 20

    # Экспоненциальная кривая
    # f(x) = 5 * e^(0.15 * (x - 1))
    limit = int(5 * math.exp(0.15 * (day - 1)))
    return min(limit, 500)


WARMUP_SCHEDULE = {day: get_warmup_limit(day) for day in range(1, 61)}


# ──────────────────────────────────────────────
# Данные прогрева
# ──────────────────────────────────────────────

@dataclass
class WarmupRecord:
    """Запись прогрева для одного аккаунта."""
    email: str
    start_date: str          # ISO date строка
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
        today_str = date.today().isoformat()
        return self.daily_log.get(today_str, 0)

    def can_send_today(self) -> bool:
        return self.is_active and self.today_sent < self.today_limit

    def record_sent(self, count: int = 1) -> None:
        today_str = date.today().isoformat()
        self.daily_log[today_str] = self.daily_log.get(today_str, 0) + count
        self.total_sent += count

    def advance_day(self) -> None:
        """Переходит к следующему дню прогрева."""
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


# ──────────────────────────────────────────────
# Планировщик прогрева
# ──────────────────────────────────────────────

class WarmupScheduler:
    """
    Управляет прогревом нескольких SMTP-аккаунтов.
    Хранит данные в JSON-файле.
    """

    def __init__(self, data_path: Path):
        self.data_path = data_path
        self.records: Dict[str, WarmupRecord] = {}
        self._load()

    def _advance_pending_days(self, record: "WarmupRecord") -> None:
          """BUG FIX: auto-advance warmup day counter based on calendar days elapsed.
          Previously advance_day() was never called automatically — progress stalled."""
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
        """Загружает данные из файла."""
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
        """Сохраняет данные в файл."""
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.data_path, "w", encoding="utf-8") as f:
            json.dump(
                {email: r.to_dict() for email, r in self.records.items()},
                f, ensure_ascii=False, indent=2
            )

    def start_warmup(self, email: str) -> WarmupRecord:
        """Начинает прогрев нового аккаунта."""
        if email in self.records:
            return self.records[email]
        record = WarmupRecord(
            email=email,
            start_date=date.today().isoformat(),
        )
        self.records[email] = record
        self._save()
        return record

    def stop_warmup(self, email: str) -> None:
        """Останавливает прогрев аккаунта."""
        if email in self.records:
            self.records[email].is_active = False
            self._save()

    def get_record(self, email: str) -> Optional[WarmupRecord]:
        return self.records.get(email)

    def tick_daily(self) -> None:
        """
        Должен вызываться раз в день.
        Продвигает счётчики и обновляет лимиты.
        """
        today = date.today().isoformat()
        for record in self.records.values():
            if not record.is_active:
                continue
            # Если сегодня ещё не тикали
            if today not in record.daily_log:
                record.advance_day()
        self._save()

    def record_sent(self, email: str, count: int = 1) -> None:
        """Фиксирует отправку писем для аккаунта."""
        if email in self.records:
            self.records[email].record_sent(count)
            self._save()

    def get_warmup_status(self) -> List[dict]:
        """Возвращает статус всех прогреваемых аккаунтов."""
        result = []
        for email, r in self.records.items():
            result.append({
                "email": email,
                "day": r.current_day,
                "today_limit": r.today_limit,
                "today_sent": r.today_sent,
                "total_sent": r.total_sent,
                "is_active": r.is_active,
                "start_date": r.start_date,
                "progress_pct": min(100, int(r.current_day / 30 * 100)),
            })
        return result


# ──────────────────────────────────────────────
# Human-like задержки (gaussian distribution)
# ──────────────────────────────────────────────

def human_delay_seconds(base_min: float = 2.0, base_max: float = 8.0) -> float:
    """
    Генерирует задержку с gaussian-распределением для имитации человека.
    """
    mean = (base_min + base_max) / 2
    std = (base_max - base_min) / 4
    delay = random.gauss(mean, std)
    return max(base_min, min(base_max * 2, delay))


async def warmup_send_session(
    email: str,
    scheduler: WarmupScheduler,
    send_func,  # async callable(email) -> bool
) -> dict:
    """
    Выполняет сессию прогрева для одного аккаунта.
    Отправляет письма с human-like задержками.

    Args:
        email: Email аккаунта
        scheduler: Экземпляр WarmupScheduler
        send_func: Асинхронная функция отправки

    Returns:
        Статистика сессии
    """
    record = scheduler.get_record(email)
    if not record:
        return {"error": "Аккаунт не найден в планировщике прогрева"}

    if not record.can_send_today():
        return {
            "email": email,
            "sent": 0,
            "skipped": True,
            "reason": f"Лимит дня {record.current_day} исчерпан ({record.today_limit} писем)",
        }

    target = record.today_limit - record.today_sent
    sent = 0
    errors = 0

    for i in range(target):
        if not record.can_send_today():
            break

        success = await send_func(email)
        if success:
            scheduler.record_sent(email)
            sent += 1
        else:
            errors += 1
            if errors >= 3:
                break  # Прерываем при множественных ошибках

        # Human-like задержка между письмами прогрева
        delay = human_delay_seconds(3.0, 12.0)
        await asyncio.sleep(delay)

    return {
        "email": email,
        "day": record.current_day,
        "sent": sent,
        "errors": errors,
        "today_limit": record.today_limit,
    }


# ──────────────────────────────────────────────
# Календарь прогрева
# ──────────────────────────────────────────────

def get_warmup_calendar(start_day: int = 1, days: int = 30) -> List[dict]:
    """Возвращает план прогрева на указанное количество дней."""
    calendar = []
    for i in range(days):
        day_num = start_day + i
        limit = get_warmup_limit(day_num)
        dt = date.today() + timedelta(days=i)
        calendar.append({
            "day": day_num,
            "date": dt.isoformat(),
            "limit": limit,
            "weekday": dt.strftime("%a"),
        })
    return calendar
