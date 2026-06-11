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

# Pricing logic:
# 7 days: $7.50 => $1.071/day (baseline)
# Each next plan is 3% cheaper per day than the previous.
# 30d: $1.071*0.97=1.039/d => $31   (+savings vs 7d: 3% cheaper/day)
# 60d: $1.039*0.97=1.008/d => $61   (+savings vs 30d)
# 90d: $1.008*0.97=0.978/d => $88   (+savings vs 60d)
# 180d: $0.978*0.97=0.949/d => $171 (+savings vs 90d)
# Lifetime: $249 flat (best deal)
# Trial: free, 1 hour, admin-only (for verified reviews)

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
        "max_threads": 5,
        "max_recipients": 2000,
        "admin_only": False,
        "description": (
            "До 2 000 получателей, 5 потоков\n"
            "   Базовый тариф на неделю"
        ),
    },
    "month": {
        "name": "30 дней",
        "price_usdt": 31.00,
        "days": 30,
        "hours": 0,
        "max_threads": 10,
        "max_recipients": 10000,
        "admin_only": False,
        "description": (
            "До 10 000 получателей, 10 потоков\n"
            "   Выгоднее на 3%/день чем 7 дней"
        ),
    },
    "two_months": {
        "name": "60 дней",
        "price_usdt": 61.00,
        "days": 60,
        "hours": 0,
        "max_threads": 15,
        "max_recipients": 25000,
        "admin_only": False,
        "description": (
            "До 25 000 получателей, 15 потоков\n"
            "   Выгоднее на 3%/день чем 30 дней"
        ),
    },
    "quarter": {
        "name": "90 дней",
        "price_usdt": 88.00,
        "days": 90,
        "hours": 0,
        "max_threads": 20,
        "max_recipients": 50000,
        "admin_only": False,
        "description": (
            "До 50 000 получателей, 20 потоков\n"
            "   Выгоднее на 3%/день чем 60 дней"
        ),
    },
    "half_year": {
        "name": "180 дней",
        "price_usdt": 171.00,
        "days": 180,
        "hours": 0,
        "max_threads": 30,
        "max_recipients": 100000,
        "admin_only": False,
        "description": (
            "До 100 000 получателей, 30 потоков\n"
            "   Выгоднее на 3%/день чем 90 дней"
        ),
    },
    "lifetime": {
        "name": "Lifetime",
        "price_usdt": 249.00,
        "days": 36500,
        "hours": 0,
        "max_threads": 50,
        "max_recipients": 999999,
        "admin_only": False,
        "description": (
            "Безлимит получателей, 50 потоков\n"
            "   Пожизненный доступ — лучшая цена"
        ),
    },
}
