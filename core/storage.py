"""
FMailSender — Storage layer v6.0
All read/write operations for accounts, proxies, recipients, campaign config.
Data lives in %APPDATA%/FMailSender/ (Windows) or ~/FMailSender/ (other).
Works correctly both in dev mode and inside PyInstaller --onefile bundles.
"""
from __future__ import annotations
import dataclasses
import json
import logging
import os
import sys
from pathlib import Path
from cryptography.fernet import Fernet

from core.models import SmtpAccount, Recipient, CampaignConfig

logger = logging.getLogger("fmailsender.storage")


def _get_data_dir() -> Path:
    """Return persistent data directory.

    PyInstaller --onefile: __file__ points to a temporary extraction directory
    that is deleted after the process exits — unsuitable for persistent data.
    Use %APPDATA%/FMailSender on Windows, ~/FMailSender elsewhere.
    """
    if getattr(sys, "frozen", False):
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        return Path(appdata) / "FMailSender"
    return Path(__file__).parent.parent / "data"


DATA_DIR = _get_data_dir()
DATA_DIR.mkdir(parents=True, exist_ok=True)

ACCOUNTS_FILE   = DATA_DIR / "accounts.json"
PROXIES_FILE    = DATA_DIR / "global_proxies.json"
RECIPIENTS_FILE = DATA_DIR / "recipients.json"
CAMPAIGN_FILE   = DATA_DIR / "campaign.json"
KEY_FILE        = DATA_DIR / ".fernet_key"


# ── Encryption ───────────────────────────────────────────────────────────────

def _get_key() -> bytes:
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    return key


def _fernet() -> Fernet:
    return Fernet(_get_key())


def _enc(s: str) -> str:
    try:
        return _fernet().encrypt(s.encode()).decode()
    except Exception as exc:
        logger.warning("Encrypt failed: %s", exc)
        return s


def _dec(s: str) -> str:
    try:
        return _fernet().decrypt(s.encode()).decode()
    except Exception as exc:
        logger.warning("Decrypt failed (returning raw): %s", exc)
        return s


# ── Accounts ─────────────────────────────────────────────────────────────────

def save_accounts(accounts: list[SmtpAccount]) -> None:
    data = []
    for a in accounts:
        d = a.to_dict()
        d["proxy"] = ""
        d["proxy_list"] = []
        d["password"] = _enc(d["password"])
        if d.get("access_token"):
            d["access_token"] = _enc(d["access_token"])
        if d.get("refresh_token"):  # FIX SEC-1: refresh_token was stored in plaintext
            d["refresh_token"] = _enc(d["refresh_token"])
        data.append(d)
    ACCOUNTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_accounts() -> list[SmtpAccount]:
    if not ACCOUNTS_FILE.exists():
        return []
    try:
        data = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
        accounts = []
        for d in data:
            d["password"] = _dec(d.get("password", ""))
            if d.get("access_token"):
                d["access_token"] = _dec(d["access_token"])
            if d.get("refresh_token"):  # FIX SEC-1: decrypt refresh_token
                d["refresh_token"] = _dec(d["refresh_token"])
            d["proxy"] = ""
            d["proxy_list"] = []
            accounts.append(SmtpAccount.from_dict(d))
        return accounts
    except Exception as exc:
        logger.error("Failed to load accounts from %s: %s", ACCOUNTS_FILE, exc)
        return []


# ── Proxies ──────────────────────────────────────────────────────────────────

_proxy_cache: list[str] = []


def save_proxies(proxies: list[str]) -> None:
    global _proxy_cache
    _proxy_cache = list(proxies)


def load_proxies() -> list[str]:
    return list(_proxy_cache)


# ── Recipients ───────────────────────────────────────────────────────────────

_recipient_cache: list[Recipient] = []


def save_recipients(recipients: list[Recipient]) -> None:
    global _recipient_cache
    _recipient_cache = list(recipients)


def load_recipients() -> list[Recipient]:
    return list(_recipient_cache)


# ── Campaign config ───────────────────────────────────────────────────────────

def save_campaign(cfg: CampaignConfig) -> None:
    CAMPAIGN_FILE.write_text(
        json.dumps(cfg.__dict__, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_campaign() -> CampaignConfig:
    if not CAMPAIGN_FILE.exists():
        return CampaignConfig()
    try:
        d = json.loads(CAMPAIGN_FILE.read_text(encoding="utf-8"))
        # FIX COMPAT-1: filter to known fields only — prevents TypeError on
        # version mismatch when campaign.json has extra/removed fields.
        known = {f.name for f in dataclasses.fields(CampaignConfig)}
        d_filtered = {k: v for k, v in d.items() if k in known}
        return CampaignConfig(**d_filtered)
    except Exception as exc:
        logger.error("Failed to load campaign config from %s: %s", CAMPAIGN_FILE, exc)
        return CampaignConfig()
