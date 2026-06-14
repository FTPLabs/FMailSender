"""SQLite database layer for FMail Sender licensing system."""
import logging
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

import aiosqlite

from config import DB_PATH, KEY_PREFIX, PLANS

logger = logging.getLogger("database")

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
    last_seen TEXT NOT NULL
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
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_key() -> str:
    alphabet = string.ascii_uppercase + string.digits
    groups = ["".join(secrets.choice(alphabet) for _ in range(6)) for _ in range(4)]
    return f"{KEY_PREFIX}-{'-'.join(groups)}"


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        await db.executescript(CREATE_SQL)
        for plan_id, plan in PLANS.items():
            await db.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (f"price_{plan_id}", str(plan["price_usdt"])),
            )
        await db.commit()
    logger.info("Database initialized: %s", DB_PATH)


async def upsert_user(telegram_id: int, username: str, first_name: str) -> None:
    now = _now()
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET hwid=?, last_seen=? WHERE telegram_id=?",
            (hwid.upper().strip(), _now(), telegram_id),
        )
        await db.commit()


async def get_user_hwid(telegram_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
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


async def mark_payment_paid(invoice_id: str, license_key: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
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
    from config import PLANS, KEY_PREFIX
    import secrets as _secrets, string as _string

    # First check if already processed (idempotent guard)
    async with aiosqlite.connect(DB_PATH) as db:
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

        alphabet = _string.ascii_uppercase + _string.digits
        suffix = "".join(_secrets.choice(alphabet) for _ in range(20))
        key = f"{KEY_PREFIX}-{suffix[:5]}-{suffix[5:10]}-{suffix[10:15]}-{suffix[15:20]}"
        now_str = _now()

        try:
            await db.execute("BEGIN EXCLUSIVE")
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
        except Exception:
            await db.rollback()
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

    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE licenses SET hwid=?, activated_at=? WHERE key=?",
            (hwid.upper(), _now(), key.upper()),
        )
        await db.commit()
    return True


async def revoke_license(key: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        try:
            cur = await db.execute("SELECT COUNT(*) FROM licenses")
            count = (await cur.fetchone())[0]
            await db.execute("DELETE FROM licenses")
            await db.execute("DELETE FROM payments")
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    logger.warning("All licenses and payments deleted. Count: %d", count)
    return count


async def get_all_licenses(limit: int = 50, offset: int = 0) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM licenses ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


  async def get_distinct_user_ids() -> list:
      """Returns list of distinct telegram_ids that have at least one license."""
      async with aiosqlite.connect(DB_PATH) as db:
          async with db.execute(
              "SELECT DISTINCT telegram_id FROM licenses WHERE telegram_id > 0"
          ) as cur:
              rows = await cur.fetchall()
              return [row[0] for row in rows]
  

async def get_license_by_telegram(telegram_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM licenses WHERE telegram_id=? ORDER BY created_at DESC",
            (telegram_id,),
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else None


async def set_setting(key: str, value: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO ticket_messages (ticket_id, sender_id, role, text, file_id, file_type, created_at) VALUES (?,?,?,?,?,?,?)",
            (ticket_id, sender_id, role, text or "", file_id or "", file_type or "", now),
        )
        await db.execute(
            "UPDATE tickets SET updated_at=? WHERE id=?", (now, ticket_id)
        )
        await db.commit()


async def get_ticket(ticket_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_open_tickets(limit: int = 20) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM tickets WHERE status='open' ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def close_ticket(ticket_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tickets SET status='closed', updated_at=? WHERE id=?",
            (_now(), ticket_id),
        )
        await db.commit()


async def get_ticket_messages(ticket_id: int) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM ticket_messages WHERE ticket_id=? ORDER BY created_at ASC",
            (ticket_id,),
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
