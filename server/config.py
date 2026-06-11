"""Configuration for FMail Sender license bot + API server."""
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8869596289:AAFN22KeV6yp8oVCWwDTxu34wEc7Z-HX4bI")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "8784635852").split(",") if x.strip()]
CRYPTO_BOT_TOKEN = os.environ.get("CRYPTO_BOT_TOKEN", "594916:AA6n54rTVfzrbCljPW33D49EVwHyDEpmW6f")
CRYPTO_BOT_API = "https://pay.crypt.bot/api"

DB_PATH = os.environ.get("DB_PATH", "licenses.db")
API_HOST = os.environ.get("API_HOST", "0.0.0.0")
API_PORT = int(os.environ.get("API_PORT", "8000"))

HWID_SALT = os.environ.get("HWID_SALT", "")
JWT_SECRET = os.environ.get("JWT_SECRET", "")

KEY_PREFIX = "FMSND"
DEMO_KEY = "FMSND-DEMO00-DEMO00-DEMO00-DEMO00"

PLANS = {
    "starter": {
        "name": "🌱 Starter",
        "price_usdt": 15.0,
        "days": 30,
        "max_threads": 5,
        "max_recipients": 1000,
        "description": "До 1 000 получателей, 5 потоков, 30 дней",
    },
    "pro": {
        "name": "⚡ Pro",
        "price_usdt": 35.0,
        "days": 30,
        "max_threads": 15,
        "max_recipients": 10000,
        "description": "До 10 000 получателей, 15 потоков, 30 дней",
    },
    "unlimited": {
        "name": "🚀 Unlimited",
        "price_usdt": 75.0,
        "days": 30,
        "max_threads": 50,
        "max_recipients": 999999,
        "description": "Безлимит получателей, 50 потоков, 30 дней",
    },
    "lifetime": {
        "name": "👑 Lifetime",
        "price_usdt": 250.0,
        "days": 36500,
        "max_threads": 50,
        "max_recipients": 999999,
        "description": "Безлимит навсегда, 50 потоков, пожизненно",
    },
}
