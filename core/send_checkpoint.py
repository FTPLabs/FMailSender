"""
  FMailSender Campaign Checkpoint v1.0.0
  =======================================
  Сохранение и восстановление прогресса рассылки.
  При 10-15к писем крэш/перезапуск НЕ теряет прогресс.

  Файл прогресса: %APPDATA%/FMailSender/checkpoints/<campaign_id>.json
  Атомарная запись: tmp + os.replace (нет повреждённых файлов при крэше).
  Flush каждые FLUSH_EVERY отправленных писем.
  """
  from __future__ import annotations

  import json
  import logging
  import os
  import threading
  import time
  from dataclasses import dataclass, asdict, field
  from pathlib import Path
  from typing import Optional

  logger = logging.getLogger("checkpoint")

  FLUSH_EVERY = 25   # сохранять каждые N успешных отправок
  CHECKPOINT_DIR = Path.home() / "AppData" / "Roaming" / "FMailSender" / "checkpoints"


  @dataclass
  class CampaignCheckpoint:
      campaign_id: str
      total: int
      sent_emails: list[str] = field(default_factory=list)   # успешно отправленные
      failed_emails: list[str] = field(default_factory=list)  # провалы (для отчёта)
      started_at: float = field(default_factory=time.time)
      updated_at: float = field(default_factory=time.time)
      completed: bool = False

      @property
      def sent_count(self) -> int:
          return len(self.sent_emails)

      @property
      def is_done(self) -> bool:
          return self.completed or self.sent_count + len(self.failed_emails) >= self.total


  class CheckpointManager:
      """
      Thread-safe менеджер чекпоинтов кампании.

      Пример:
          mgr = CheckpointManager("campaign-2024-01")
          if mgr.is_resumable():
              already_sent = mgr.get_sent_set()
              recipients = [r for r in all_recipients if r.email not in already_sent]

          # После каждой отправки:
          mgr.record_sent("user@example.com")
      """

      def __init__(self, campaign_id: str, total: int = 0):
          self.campaign_id = campaign_id
          self._lock = threading.Lock()
          self._path = _get_checkpoint_path(campaign_id)
          self._cp = self._load() or CampaignCheckpoint(campaign_id=campaign_id, total=total)
          self._dirty = 0  # счётчик несохранённых изменений

      def is_resumable(self) -> bool:
          return self._path.exists() and not self._cp.completed

      def get_sent_set(self) -> set[str]:
          with self._lock:
              return set(self._cp.sent_emails)

      def record_sent(self, email: str) -> None:
          with self._lock:
              self._cp.sent_emails.append(email)
              self._cp.updated_at = time.time()
              self._dirty += 1
              if self._dirty >= FLUSH_EVERY:
                  self._save_unlocked()
                  self._dirty = 0

      def record_failed(self, email: str) -> None:
          with self._lock:
              self._cp.failed_emails.append(email)
              self._cp.updated_at = time.time()

      def complete(self) -> None:
          with self._lock:
              self._cp.completed = True
              self._save_unlocked()

      def flush(self) -> None:
          with self._lock:
              self._save_unlocked()
              self._dirty = 0

      def delete(self) -> None:
          """Удалить чекпоинт после успешного завершения кампании."""
          try:
              self._path.unlink(missing_ok=True)
          except Exception as e:
              logger.debug("Ошибка удаления чекпоинта: %s", e)

      def stats(self) -> dict:
          with self._lock:
              return {
                  "campaign_id": self._cp.campaign_id,
                  "total": self._cp.total,
                  "sent": self._cp.sent_count,
                  "failed": len(self._cp.failed_emails),
                  "remaining": max(0, self._cp.total - self._cp.sent_count),
                  "completed": self._cp.completed,
                  "elapsed_sec": time.time() - self._cp.started_at,
              }

      def _save_unlocked(self) -> None:
          """Атомарная запись (tmp + os.replace)."""
          try:
              self._path.parent.mkdir(parents=True, exist_ok=True)
              tmp = self._path.with_suffix(".tmp")
              data = asdict(self._cp)
              tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
              os.replace(tmp, self._path)
          except Exception as e:
              logger.error("Ошибка сохранения чекпоинта: %s", e)

      def _load(self) -> Optional[CampaignCheckpoint]:
          if not self._path.exists():
              return None
          try:
              data = json.loads(self._path.read_text(encoding="utf-8"))
              return CampaignCheckpoint(**data)
          except Exception as e:
              logger.warning("Повреждённый чекпоинт %s: %s", self._path, e)
              return None


  def _get_checkpoint_path(campaign_id: str) -> Path:
      safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in campaign_id)
      return CHECKPOINT_DIR / f"{safe_id}.json"


  def list_checkpoints() -> list[dict]:
      """Список незавершённых кампаний для отображения в UI."""
      result = []
      if not CHECKPOINT_DIR.exists():
          return result
      for p in CHECKPOINT_DIR.glob("*.json"):
          try:
              data = json.loads(p.read_text(encoding="utf-8"))
              if not data.get("completed"):
                  result.append({
                      "campaign_id": data.get("campaign_id", p.stem),
                      "sent": len(data.get("sent_emails", [])),
                      "total": data.get("total", 0),
                      "updated_at": data.get("updated_at", 0),
                  })
          except Exception:
              continue
      return sorted(result, key=lambda x: -x["updated_at"])
  