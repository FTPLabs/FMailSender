"""Configuration for FMail Sender license bot + API server.

Required environment variables:
  BOT_TOKEN         — Telegram bot token from @BotFather
  CRYPTO_BOT_TOKEN  — CryptoBot token from @CryptoBot
  JWT_SECRET        — Secret key for signing license JWT tokens (min 32 chars)

Optional:
  ADMIN_IDS         — Comma-separated Telegram user IDs with admin access
  DB_PATH           — Path to SQLite database (default: licenses.db)
  API_HOST          — Bind host (default: 0.0.0.0)
  API_PORT          — Bind port (default: 8000)
  HWID_SALT         — Additional salt for HWID encryption (optional)
"""
import os
import sys


def _require(key: str) -> str:
    val = os.environ.get(key, "").strip()
    if not val:
        print(f"[FATAL] Required env var '{key}' is not set.", file=sys.stderr)
        print(f"        Add it to .env or export it before starting the server.", file=sys.stderr)
        sys.exit(1)
    return val


BOT_TOKEN = _require("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
if not ADMIN_IDS:
    print("[WARN] ADMIN_IDS env var is not set — admin panel will be inaccessible.", file=sys.stderr)

MODERATOR_IDS: list[int] = [int(x) for x in os.environ.get("MODERATOR_IDS", "").split(",") if x.strip().isdigit()]

ADMIN_API_KEY: str = os.environ.get("ADMIN_API_KEY", "").strip()
if not ADMIN_API_KEY:
    print("[WARN] ADMIN_API_KEY is not set — admin web panel will be inaccessible.", file=sys.stderr)
elif len(ADMIN_API_KEY) < 16:
    print("[WARN] ADMIN_API_KEY is too short (< 16 chars) — use a strong key.", file=sys.stderr)

# Backward-compat alias
ADMIN_WEB_SECRET: str = ADMIN_API_KEY
CRYPTO_BOT_TOKEN = _require("CRYPTO_BOT_TOKEN")
CRYPTO_BOT_API = "https://pay.crypt.bot/api"

DB_PATH = os.environ.get("DB_PATH", "licenses.db")
API_HOST = os.environ.get("API_HOST", "0.0.0.0")
API_PORT = int(os.environ.get("API_PORT", "8000"))

HWID_SALT = os.environ.get("HWID_SALT", "")
JWT_SECRET = _require("JWT_SECRET")

KEY_PREFIX = "FMSND"

PLANS = {
    "trial": {
        "name": "Trial 1h",
        "price_usdt": 0.0,
        "days": 0,
        "hours": 1,
        "max_threads": 3,
        "max_recipients": 100,
        "admin_only": True,
        "description": (
            "Пробный доступ на 1 час\n"
            "   До 100 получателей, 3 потока\n"
            "   Выдаётся за отзыв — только вручную"
        ),
    },
    "week": {
        "name": "7 дней",
        "price_usdt": 7.50,
        "days": 7,
        "hours": 0,
        "max_threads": 999999,
        "max_recipients": 999999,
        "admin_only": False,
        "description": (
            "Безлимит получателей и потоков\n"
            "   Базовый тариф на неделю"
        ),
    },
    "month": {
        "name": "30 дней",
        "price_usdt": 31.00,
        "days": 30,
        "hours": 0,
        "max_threads": 999999,
        "max_recipients": 999999,
        "admin_only": False,
        "description": (
            "Безлимит получателей и потоков\n"
            "   Выгоднее на 3%/день чем 7 дней"
        ),
    },
    "two_months": {
        "name": "60 дней",
        "price_usdt": 61.00,
        "days": 60,
        "hours": 0,
        "max_threads": 999999,
        "max_recipients": 999999,
        "admin_only": False,
        "description": (
            "Безлимит получателей и потоков\n"
            "   Выгоднее на 3%/день чем 30 дней"
        ),
    },
    "quarter": {
        "name": "90 дней",
        "price_usdt": 88.00,
        "days": 90,
        "hours": 0,
        "max_threads": 999999,
        "max_recipients": 999999,
        "admin_only": False,
        "description": (
            "Безлимит получателей и потоков\n"
            "   Выгоднее на 3%/день чем 60 дней"
        ),
    },
    "half_year": {
        "name": "180 дней",
        "price_usdt": 171.00,
        "days": 180,
        "hours": 0,
        "max_threads": 999999,
        "max_recipients": 999999,
        "admin_only": False,
        "description": (
            "Безлимит получателей и потоков\n"
            "   Выгоднее на 3%/день чем 90 дней"
        ),
    },
    "lifetime": {
        "name": "Lifetime",
        "price_usdt": 249.00,
        "days": 36500,
        "hours": 0,
        "max_threads": 999999,
        "max_recipients": 999999,
        "admin_only": False,
        "description": (
            "Безлимит получателей и потоков\n"
            "   Пожизненный доступ — лучшая цена"
        ),
    },
}

# URL для скачивания актуальной версии программы (обновляется через /setdownload)
DOWNLOAD_URL: str = os.environ.get("DOWNLOAD_URL", "https://github.com/FTPLabs/FMailSender/releases/latest/download/FMailSender.exe")

# ID Telegram-канала для обязательной подписки (переопределяется через env CHANNEL_ID)
CHANNEL_ID: int = int(os.environ.get("CHANNEL_ID", "-1003769139793"))
