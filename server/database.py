"""SQLite database layer for FMail Sender licensing system."""
import asyncio
import logging
import random
import secrets
import string
import time
from datetime import datetime, timedelta
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
    is_demo INTEGER DEFAULT 0,
    note TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL,
    invoice_id TEXT NOT NULL,
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
"""


def _now() -> str:
    return datetime.utcnow().isoformat()


def _generate_key() -> str:
    alphabet = string.ascii_uppercase + string.digits
    groups = ["".join(secrets.choice(alphabet) for _ in range(6)) for _ in range(4)]
    return f"{KEY_PREFIX}-{'-'.join(groups)}"


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        for stmt in CREATE_SQL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                await db.execute(stmt)
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


async def create_payment(
    telegram_id: int, invoice_id: str, plan: str, hwid: str, amount: float, currency: str = "USDT"
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO payments (telegram_id, invoice_id, plan, hwid, amount, currency, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (telegram_id, invoice_id, plan, hwid, amount, currency, _now()),
        )
        await db.commit()
        return cur.lastrowid


async def get_payment_by_invoice(invoice_id: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM payments WHERE invoice_id=?", (invoice_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def mark_payment_paid(invoice_id: str, license_key: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE payments SET status='paid', license_key=?, paid_at=? WHERE invoice_id=?",
            (license_key, _now(), invoice_id),
        )
        await db.commit()


async def create_license(
    plan: str,
    telegram_id: int = 0,
    hwid: str = "",
    note: str = "",
    override_days: Optional[int] = None,
) -> dict:
    plan_data = PLANS.get(plan, PLANS["starter"])
    days = override_days if override_days is not None else plan_data["days"]
    expires_at = (datetime.utcnow() + timedelta(days=days)).isoformat()
    key = _generate_key()
    now = _now()

    async with aiosqlite.connect(DB_PATH) as db:
        for _ in range(10):
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
                key = _generate_key()

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
    if existing_hwid and existing_hwid != hwid:
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


async def get_all_licenses(limit: int = 50, offset: int = 0) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM licenses ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


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
        async with db.execute("SELECT COUNT(*) FROM licenses WHERE is_active=1") as cur:
            active = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM licenses") as cur:
            total = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM payments WHERE status='paid'") as cur:
            paid = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            users = (await cur.fetchone())[0]
        async with db.execute("SELECT SUM(amount) FROM payments WHERE status='paid'") as cur:
            revenue = (await cur.fetchone())[0] or 0.0
    return {
        "active_licenses": active,
        "total_licenses": total,
        "paid_orders": paid,
        "total_users": users,
        "total_revenue_usdt": round(revenue, 2),
    }


async def get_setting(key: str, default: str = "") -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else default


async def set_setting(key: str, value: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        await db.commit()


async def get_plan_price(plan_id: str) -> float:
    val = await get_setting(f"price_{plan_id}", str(PLANS.get(plan_id, {}).get("price_usdt", 0)))
    try:
        return float(val)
    except ValueError:
        return PLANS.get(plan_id, {}).get("price_usdt", 0)
