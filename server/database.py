"""SQLite database layer for FMail Sender licensing system."""
import os as _os, sys as _sys
# Fix C-3: ensure server/ parent is on sys.path so 'from config import' works with any cwd
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import logging
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

import aiosqlite
from contextlib import asynccontextmanager

from config import DB_PATH, KEY_PREFIX, PLANS

logger = logging.getLogger("database")


@asynccontextmanager
async def _db():
  """Контекст менеджер: WAL + busy_timeout=5000 для безопасного concurrent доступа."""
  async with aiosqlite.connect(DB_PATH) as conn:
      conn.row_factory = aiosqlite.Row
      await conn.execute("PRAGMA journal_mode=WAL")
      await conn.execute("PRAGMA busy_timeout=5000")
      await conn.execute("PRAGMA synchronous=NORMAL")
      yield conn


CREATE_SQL = """
CREATE TABLE IF NOT EXISTS licenses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  key TEXT UNIQUE NOT NULL,
  plan TEXT NOT NULL,
  hwid TEXT DEFAULT '',
  telegram_id INTEGER DEFAULT 0,
  email TEXT DEFAULT '',
  max_threads INTEGER DEFAULT 5,
  max_recipients INTEGER DEFAULT 1000,
  days INTEGER DEFAULT 30,
  activated_at TEXT DEFAULT '',
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  is_active INTEGER DEFAULT 1,
  note TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS payments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  telegram_id INTEGER NOT NULL,
  invoice_id TEXT UNIQUE NOT NULL,
  plan TEXT NOT NULL,
  hwid TEXT DEFAULT '',
  amount REAL NOT NULL,
  currency TEXT DEFAULT 'USDT',
  status TEXT DEFAULT 'pending',
  license_key TEXT DEFAULT '',
  created_at TEXT NOT NULL,
  paid_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
  telegram_id INTEGER PRIMARY KEY,
  username TEXT DEFAULT '',
  first_name TEXT DEFAULT '',
  hwid TEXT DEFAULT '',
  registered_at TEXT NOT NULL,
  last_seen TEXT NOT NULL,
  terms_accepted INTEGER DEFAULT 0,
  captcha_passed INTEGER DEFAULT 0,
  hwid_reset_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tickets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  username TEXT DEFAULT '',
  first_name TEXT DEFAULT '',
  status TEXT DEFAULT 'open',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ticket_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ticket_id INTEGER NOT NULL,
  sender_id INTEGER NOT NULL,
  role TEXT NOT NULL,
  text TEXT DEFAULT '',
  file_id TEXT DEFAULT '',
  file_type TEXT DEFAULT '',
  created_at TEXT NOT NULL,
  FOREIGN KEY(ticket_id) REFERENCES tickets(id)
);

CREATE TABLE IF NOT EXISTS moderators (
  telegram_id INTEGER PRIMARY KEY,
  added_by INTEGER NOT NULL,
  added_at TEXT NOT NULL
);
"""


def _now() -> str:
  return datetime.now(timezone.utc).isoformat()


def _generate_key() -> str:
  alphabet = string.ascii_uppercase + string.digits
  groups = ["".join(secrets.choice(alphabet) for _ in range(6)) for _ in range(4)]
  return f"{KEY_PREFIX}-{'-'.join(groups)}"


async def _migrate_db() -> None:
  """ALTER TABLE миграции для существующих БД без пересоздания таблиц."""
  # FIX M-3: одно соединение для всех миграций вместо нового на каждый ALTER
  _migrations = [
        "ALTER TABLE users ADD COLUMN terms_accepted INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN captcha_passed INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN hwid_reset_at TEXT DEFAULT ''",
    ]
  async with _db() as conn:
      for _sql in _migrations:
          try:
              await conn.execute(_sql)
              await conn.commit()
          except aiosqlite.OperationalError as _e:
              if "duplicate column name" not in str(_e).lower():
                  logger.warning("migrate_db: неожиданная ошибка при '%s': %s", _sql, _e)


async def set_terms_accepted(telegram_id: int) -> None:
  """Сохраняет факт принятия условий — переживает перезапуск бота."""
  async with _db() as conn:
      # FIX C-3: UPSERT — создаёт строку если пользователь не зарегистрирован
      await conn.execute(
          """INSERT INTO users (telegram_id, username, first_name, registered_at, last_seen, terms_accepted)
             VALUES (?, '', '', datetime('now'), datetime('now'), 1)
             ON CONFLICT(telegram_id) DO UPDATE SET terms_accepted=1""",
          (telegram_id,)
      )
      await conn.commit()


async def get_terms_accepted(telegram_id: int) -> bool:
  """True если пользователь ранее принял условия."""
  async with _db() as conn:
      async with conn.execute(
          "SELECT terms_accepted FROM users WHERE telegram_id=?", (telegram_id,)
      ) as cur:
          row = await cur.fetchone()
          return bool(row and row[0])



async def set_captcha_passed(telegram_id: int) -> None:
  """Сохраняет факт прохождения капчи — переживает перезапуск бота."""
  async with _db() as conn:
      # FIX C-3: UPSERT — создаёт строку если пользователь не зарегистрирован
      await conn.execute(
          """INSERT INTO users (telegram_id, username, first_name, registered_at, last_seen, captcha_passed)
             VALUES (?, '', '', datetime('now'), datetime('now'), 1)
             ON CONFLICT(telegram_id) DO UPDATE SET captcha_passed=1""",
          (telegram_id,)
      )
      await conn.commit()


async def get_captcha_passed(telegram_id: int) -> bool:
  """True если пользователь ранее прошёл капчу."""
  async with _db() as conn:
      async with conn.execute(
          "SELECT captcha_passed FROM users WHERE telegram_id=?", (telegram_id,)
      ) as cur:
          row = await cur.fetchone()
          return bool(row and row[0])


async def get_all_passed_users() -> tuple[set[int], set[int]]:
  """Возвращает (captcha_passed_ids, terms_accepted_ids) для прогрева кэша при старте."""
  async with _db() as conn:
      async with conn.execute(
          "SELECT telegram_id, captcha_passed, terms_accepted FROM users "
          "WHERE captcha_passed=1 OR terms_accepted=1"
      ) as cur:
          rows = await cur.fetchall()
  captcha = {r[0] for r in rows if r[1]}
  terms   = {r[0] for r in rows if r[2]}
  return captcha, terms




async def get_hwid_reset_info(telegram_id: int) -> dict:
  """Возвращает информацию о возможности сброса HWID.
    
  Returns:
      dict с полями:
        - can_reset (bool): True если прошло >=30 дней с последнего сброса
        - days_left (int): сколько дней осталось до следующего сброса
        - last_reset (str): ISO-дата последнего сброса или ''
  """
  async with _db() as conn:
      async with conn.execute(
          "SELECT hwid_reset_at FROM users WHERE telegram_id=?", (telegram_id,)
      ) as cur:
          row = await cur.fetchone()
    
  if not row or not row[0]:
      return {"can_reset": True, "days_left": 0, "last_reset": ""}
    
  try:
      last_reset = datetime.fromisoformat(row[0].replace("Z", "+00:00"))
      if last_reset.tzinfo is None:
          last_reset = last_reset.replace(tzinfo=timezone.utc)
      elapsed = (datetime.now(timezone.utc) - last_reset).days
      can_reset = elapsed >= 30
      days_left = max(0, 30 - elapsed)
      return {"can_reset": can_reset, "days_left": days_left, "last_reset": row[0]}
  except Exception:
      return {"can_reset": True, "days_left": 0, "last_reset": ""}


async def reset_user_hwid(telegram_id: int) -> bool:
  """Сбрасывает HWID пользователя и всех его активных лицензий.
  Доступно не чаще 1 раза в 30 дней.
    
  Returns:
      True если сброс выполнен, False если ещё не прошло 30 дней.
  """
  info = await get_hwid_reset_info(telegram_id)
  if not info["can_reset"]:
      return False
    
  now = _now()
  async with _db() as conn:
      # Сбрасываем hwid у пользователя и фиксируем дату сброса
      await conn.execute(
          "UPDATE users SET hwid='', hwid_reset_at=?, last_seen=? WHERE telegram_id=?",
          (now, now, telegram_id)
      )
      # Сбрасываем hwid у всех активных лицензий пользователя
      await conn.execute(
          "UPDATE licenses SET hwid='' WHERE telegram_id=? AND is_active=1",
          (telegram_id,)
      )
      await conn.commit()
    
  logger.info("HWID reset for telegram_id=%d at %s", telegram_id, now)
  return True

async def init_db() -> None:
# FIX БАГ-7: исправлены отступы (было 2 пробела, PEP 8 требует 4)
# PRAGMA journal_mode=WAL, busy_timeout=5000, synchronous=NORMAL
# уже применяются в _db() context manager — не дублируем.
async with _db() as db:
    # FIX: executescript() auto-commits — заменён на отдельные execute() для корректной транзакции
    for _stmt in [s.strip() for s in CREATE_SQL.split(";") if s.strip()]:
        await db.execute(_stmt)
    for plan_id, plan in PLANS.items():
        await db.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (f"price_{plan_id}", str(plan["price_usdt"])),
        )
    await db.commit()
await _migrate_db()
logger.info("Database initialized: %s", DB_PATH)


async def upsert_user(telegram_id: int, username: str, first_name: str) -> None:
  now = _now()
  async with _db() as db:
      await db.execute(
          """INSERT INTO users (telegram_id, username, first_name, registered_at, last_seen)
             VALUES (?, ?, ?, ?, ?)
             ON CONFLICT(telegram_id) DO UPDATE SET
               username=excluded.username,
               first_name=excluded.first_name,
               last_seen=excluded.last_seen""",
          (telegram_id, username or "", first_name or "", now, now),
      )
      await db.commit()


async def set_user_hwid(telegram_id: int, hwid: str) -> None:
  async with _db() as db:
      await db.execute(
          "UPDATE users SET hwid=?, last_seen=? WHERE telegram_id=?",
          (hwid.upper().strip(), _now(), telegram_id),
      )
      await db.commit()


async def get_user_hwid(telegram_id: int) -> str:
  async with _db() as db:
      async with db.execute(
          "SELECT hwid FROM users WHERE telegram_id=?", (telegram_id,)
      ) as cur:
          row = await cur.fetchone()
          return row[0] if row else ""


async def save_payment(
  telegram_id: int,
  invoice_id: str,
  plan: str,
  hwid: str,
  amount: float,
  currency: str = "USDT",
) -> int:
  async with _db() as db:
      # Check for existing — INSERT OR IGNORE returns lastrowid=0 on conflict
      async with db.execute(
          "SELECT id FROM payments WHERE invoice_id = ?", (invoice_id,)
      ) as _chk:
          row = await _chk.fetchone()
          if row:
              return row[0]
      cur = await db.execute(
          """INSERT INTO payments
             (telegram_id, invoice_id, plan, hwid, amount, currency, created_at)
             VALUES (?, ?, ?, ?, ?, ?, ?)""",
          (telegram_id, invoice_id, plan, hwid, amount, currency, _now()),
      )
      await db.commit()
      return cur.lastrowid


async def get_payment(invoice_id: str) -> Optional[dict]:
  async with _db() as db:
      db.row_factory = aiosqlite.Row
      async with db.execute(
          "SELECT * FROM payments WHERE invoice_id=?", (invoice_id,)
      ) as cur:
          row = await cur.fetchone()
          return dict(row) if row else None


async def get_payment_license(invoice_id: str) -> Optional[str]:
  payment = await get_payment(invoice_id)
  if not payment:
      return None
  key = payment.get("license_key", "")
  return key if key else None


async def get_pending_payments(limit: int = 50) -> list:
  """FIX ERR-2: Returns all payments with status='pending' for background poller."""
  async with _db() as db:
      db.row_factory = aiosqlite.Row
      async with db.execute(
          "SELECT * FROM payments WHERE status='pending' ORDER BY created_at DESC LIMIT ?",
          (limit,),
      ) as cur:
          rows = await cur.fetchall()
          return [dict(r) for r in rows]


async def mark_payment_paid(invoice_id: str, license_key: str) -> None:
  async with _db() as db:
      await db.execute(
          "UPDATE payments SET status='paid', license_key=?, paid_at=? WHERE invoice_id=?",
          (license_key, _now(), invoice_id),
      )
      await db.commit()



async def create_license_for_payment(
  invoice_id: str,
  plan: str,
  telegram_id: int = 0,
  hwid: str = "",
) -> dict:
  """Atomic: create license + mark payment paid in one transaction.

  Returns existing license_key if payment was already processed (idempotent).
  """
  # First check if already processed (idempotent guard)
  async with _db() as db:
      db.row_factory = aiosqlite.Row
      async with db.execute(
          "SELECT license_key FROM payments WHERE invoice_id=? AND status='paid'",
          (invoice_id,),
      ) as cur:
          row = await cur.fetchone()
      if row and row["license_key"]:
          # Already processed — return existing key
          async with db.execute(
              "SELECT * FROM licenses WHERE key=?", (row["license_key"],)
          ) as cur2:
              lic = await cur2.fetchone()
          return dict(lic) if lic else {"key": row["license_key"]}

      # Not yet processed — create license and mark paid atomically
      plan_data = PLANS.get(plan, list(PLANS.values())[1])
      hours = plan_data.get("hours", 0)
      days = plan_data.get("days", 30)
      if hours and not days:
          expires_at = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
      else:
          expires_at = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()

      # FIX КРИТ-1: use _generate_key() for consistent 6-char group format
      # Old inline code produced 5-char groups that failed validate_key_format()
      key = _generate_key()
      now_str = _now()

      try:
          await db.execute(
              """INSERT INTO licenses
                 (key, plan, hwid, telegram_id, max_threads, max_recipients,
                  days, activated_at, expires_at, created_at, is_active)
                 VALUES (?,?,?,?,?,?,?,?,?,?,1)""",
              (
                  key, plan, hwid, telegram_id,
                  plan_data.get("max_threads", 5),
                  plan_data.get("max_recipients", 1000),
                  days, "", expires_at, now_str,
              ),
          )
          await db.execute(
              "UPDATE payments SET status='paid', license_key=?, paid_at=? WHERE invoice_id=?",
              (key, now_str, invoice_id),
          )
          await db.commit()
      except Exception as _orig_exc:
          # FIX БАГ-8: rollback в отдельном try — не маскирует оригинальную ошибку
          try:
              await db.rollback()
          except Exception as _rb_exc:
              logger.warning("rollback failed: %s (original: %s)", _rb_exc, _orig_exc)
          raise

      db.row_factory = aiosqlite.Row
      async with db.execute("SELECT * FROM licenses WHERE key=?", (key,)) as cur3:
          lic = await cur3.fetchone()
      return dict(lic) if lic else {"key": key}

async def create_license(
  plan: str,
  telegram_id: int = 0,
  hwid: str = "",
  note: str = "",
  override_days: Optional[int] = None,
) -> dict:
  plan_data = PLANS.get(plan, PLANS.get("week", list(PLANS.values())[1]))
  hours = plan_data.get("hours", 0)
  if override_days is not None:
      days = override_days
      expires_at = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
  elif hours and not plan_data.get("days"):
      days = 0
      expires_at = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
  else:
      days = plan_data["days"]
      expires_at = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()

  key = _generate_key()
  now = _now()

  async with _db() as db:
      for _attempt in range(10):
          try:
              await db.execute(
                  """INSERT INTO licenses
                     (key, plan, hwid, telegram_id, max_threads, max_recipients,
                      days, expires_at, created_at, is_active, note)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
                  (
                      key, plan, hwid, telegram_id,
                      plan_data["max_threads"], plan_data["max_recipients"],
                      days, expires_at, now, note,
                  ),
              )
              await db.commit()
              break
          except aiosqlite.IntegrityError:
              await db.rollback()
              key = _generate_key()
              if _attempt == 9:
                  raise RuntimeError("Не удалось сгенерировать уникальный ключ после 10 попыток")

  return {
      "key": key,
      "plan": plan,
      "plan_name": plan_data["name"],
      "hwid": hwid,
      "expires_at": expires_at,
      "max_threads": plan_data["max_threads"],
      "max_recipients": plan_data["max_recipients"],
  }


async def get_license(key: str) -> Optional[dict]:
  async with _db() as db:
      db.row_factory = aiosqlite.Row
      async with db.execute("SELECT * FROM licenses WHERE key=?", (key.upper(),)) as cur:
          row = await cur.fetchone()
          return dict(row) if row else None


async def bind_hwid_to_license(key: str, hwid: str) -> bool:
  lic = await get_license(key)
  if not lic:
      return False
  existing_hwid = lic.get("hwid", "")
  if existing_hwid and existing_hwid.upper() != hwid.upper():
      return False
  async with _db() as db:
      await db.execute(
          "UPDATE licenses SET hwid=?, activated_at=? WHERE key=?",
          (hwid.upper(), _now(), key.upper()),
      )
      await db.commit()
  return True


async def revoke_license(key: str) -> bool:
  async with _db() as db:
      cur = await db.execute(
          "UPDATE licenses SET is_active=0 WHERE key=?", (key.upper(),)
      )
      await db.commit()
      return cur.rowcount > 0


async def delete_all_licenses() -> int:
  """
  Deletes ALL licenses and payments inside a single transaction.
  WARNING: irreversible — admin confirmation is required before calling.
  """
  async with _db() as db:
      # PRAGMA journal_mode=WAL уже применяется в _db() — дублирование удалено
      try:
          cur = await db.execute("SELECT COUNT(*) FROM licenses")
          count = (await cur.fetchone())[0]
          await db.execute("DELETE FROM licenses")
          await db.execute("DELETE FROM payments")
          await db.commit()
      except Exception as _orig_exc:
          # FIX БАГ-8: rollback в отдельном try — не маскирует оригинальную ошибку
          try:
              await db.rollback()
          except Exception as _rb_exc:
              logger.warning("rollback failed: %s (original: %s)", _rb_exc, _orig_exc)
          raise
  logger.warning("All licenses and payments deleted. Count: %d", count)
  return count


async def get_all_licenses(limit: int = 50, offset: int = 0) -> list:
  async with _db() as db:
      db.row_factory = aiosqlite.Row
      async with db.execute(
          "SELECT * FROM licenses ORDER BY created_at DESC LIMIT ? OFFSET ?",
          (limit, offset),
      ) as cur:
          rows = await cur.fetchall()
          return [dict(r) for r in rows]



async def get_distinct_user_ids() -> list:
  """Returns list of ALL registered user telegram_ids (from users table).
  FIX ERR-1: was querying licenses only — excluded users who haven't bought yet.
  """
  async with _db() as db:
      async with db.execute(
          "SELECT telegram_id FROM users WHERE telegram_id > 0"
      ) as cur:
          rows = await cur.fetchall()
          return [row[0] for row in rows]



async def get_license_by_telegram(telegram_id: int) -> list:
  async with _db() as db:
      db.row_factory = aiosqlite.Row
      async with db.execute(
          "SELECT * FROM licenses WHERE telegram_id=? ORDER BY created_at DESC",
          (telegram_id,),
      ) as cur:
          rows = await cur.fetchall()
          return [dict(r) for r in rows]


async def get_stats() -> dict:
  async with _db() as db:
      async def _count(sql: str) -> int:
          async with db.execute(sql) as cur:
              row = await cur.fetchone()
              return row[0] if row else 0

      total = await _count("SELECT COUNT(*) FROM licenses")
      active = await _count("SELECT COUNT(*) FROM licenses WHERE is_active=1")
      paid = await _count("SELECT COUNT(*) FROM payments WHERE status='paid'")
      users = await _count("SELECT COUNT(*) FROM users")
      open_tickets = await _count("SELECT COUNT(*) FROM tickets WHERE status='open'")
      async with db.execute("SELECT COALESCE(SUM(amount), 0.0) FROM payments WHERE status='paid'") as cur:
          row = await cur.fetchone()
          revenue = float(row[0]) if row else 0.0
      return {
          "total": total, "active": active, "paid": paid,
          "paid_orders": paid, "users": users, "revenue_usdt": revenue,
          "open_tickets": open_tickets,
      }


async def search_license(query: str) -> list:
  async with _db() as db:
      db.row_factory = aiosqlite.Row
      q = f"%{query.upper()}%"
      async with db.execute(
          """SELECT * FROM licenses
             WHERE key LIKE ? OR hwid LIKE ? OR CAST(telegram_id AS TEXT) LIKE ?
             ORDER BY created_at DESC LIMIT 20""",
          (q, q, q),
      ) as cur:
          rows = await cur.fetchall()
          return [dict(r) for r in rows]


async def get_setting(key: str) -> Optional[str]:
  async with _db() as db:
      async with db.execute("SELECT value FROM settings WHERE key=?", (key,)) as cur:
          row = await cur.fetchone()
          return row[0] if row else None


async def set_setting(key: str, value: str) -> None:
  async with _db() as db:
      await db.execute(
          "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
          (key, value),
      )
      await db.commit()


async def get_plan_price(plan_id: str) -> float:
  val = await get_setting(f"price_{plan_id}")
  if val:
      try:
          return float(val)
      except ValueError:
          pass
  return PLANS.get(plan_id, {}).get("price_usdt", 0.0)


# ─── Tickets ─────────────────────────────────────────────────────────────────

async def create_ticket(user_id: int, username: str, first_name: str) -> int:
  now = _now()
  async with _db() as db:
      cur = await db.execute(
          "INSERT INTO tickets (user_id, username, first_name, status, created_at, updated_at) VALUES (?,?,?,?,?,?)",
          (user_id, username or "", first_name or "", "open", now, now),
      )
      await db.commit()
      return cur.lastrowid


async def add_ticket_message(
  ticket_id: int,
  sender_id: int,
  role: str,
  text: str = "",
  file_id: str = "",
  file_type: str = "",
) -> None:
  now = _now()
  async with _db() as db:
      await db.execute(
          "INSERT INTO ticket_messages (ticket_id, sender_id, role, text, file_id, file_type, created_at) VALUES (?,?,?,?,?,?,?)",
          (ticket_id, sender_id, role, text or "", file_id or "", file_type or "", now),
      )
      await db.execute(
          "UPDATE tickets SET updated_at=? WHERE id=?", (now, ticket_id)
      )
      await db.commit()


async def get_ticket(ticket_id: int) -> Optional[dict]:
  async with _db() as db:
      db.row_factory = aiosqlite.Row
      async with db.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)) as cur:
          row = await cur.fetchone()
          return dict(row) if row else None


async def get_open_tickets(limit: int = 20) -> list:
  async with _db() as db:
      db.row_factory = aiosqlite.Row
      async with db.execute(
          "SELECT * FROM tickets WHERE status='open' ORDER BY updated_at DESC LIMIT ?",
          (limit,),
      ) as cur:
          rows = await cur.fetchall()
          return [dict(r) for r in rows]


async def close_ticket(ticket_id: int) -> None:
  async with _db() as db:
      await db.execute(
          "UPDATE tickets SET status='closed', updated_at=? WHERE id=?",
          (_now(), ticket_id),
      )
      await db.commit()


async def get_ticket_messages(ticket_id: int) -> list:
  async with _db() as db:
      db.row_factory = aiosqlite.Row
      async with db.execute(
          "SELECT * FROM ticket_messages WHERE ticket_id=? ORDER BY created_at ASC",
          (ticket_id,),
      ) as cur:
          rows = await cur.fetchall()
          return [dict(r) for r in rows]


# ─── Moderators ───────────────────────────────────────────────────────────────

async def add_moderator(telegram_id: int, added_by: int) -> None:
  """Добавляет модератора в БД (идемпотентно)."""
  async with _db() as db:
      await db.execute(
          "INSERT OR IGNORE INTO moderators (telegram_id, added_by, added_at) VALUES (?, ?, ?)",
          (telegram_id, added_by, _now()),
      )
      await db.commit()


async def remove_moderator(telegram_id: int) -> bool:
  """Удаляет модератора из БД. Возвращает True если запись существовала."""
  async with _db() as db:
      cur = await db.execute("DELETE FROM moderators WHERE telegram_id=?", (telegram_id,))
      await db.commit()
      return cur.rowcount > 0


async def get_all_moderators() -> list[dict]:
  """Возвращает модераторов из БД как list[dict] с ключами telegram_id, added_by, added_at."""
  async with _db() as db:
      async with db.execute("SELECT telegram_id, added_by, added_at FROM moderators") as cur:
          rows = await cur.fetchall()
          return [{"telegram_id": row[0], "added_by": row[1], "added_at": row[2]} for row in rows]
