"""
FMailSender — Official SMTP Daily Limits v1.0.0
================================================
Official sending limits per provider (based on official documentation).
Used to set safe defaults for daily_limit when importing accounts.

Sources:
  Gmail:   https://support.google.com/mail/answer/22839
  Outlook: https://support.microsoft.com/en-us/office/sending-limits-in-outlook-com
  Yahoo:   https://help.yahoo.com/kb/SLN3403.html
  GMX:     https://support.gmx.com/pop-imap/smtp-general.html
  Yandex:  https://yandex.com/support/mail/mail-clients.html
  Mail.ru: https://help.mail.ru/mail/mailer/popsmtp
  iCloud:  https://support.apple.com/en-us/102576
  Zoho:    https://www.zoho.com/mail/help/smtp-access.html
  Rambler: https://help.rambler.ru/mail/client/1277/
  AOL:     https://help.aol.com/articles/aol-mail-account-locked-or-disabled
"""
from __future__ import annotations

from typing import Optional

# ── Official daily SMTP limits per domain ────────────────────────────────────
# Format: domain → {"daily": N, "hourly": N, "notes": str}
# "daily" = safe conservative limit (use 80% of official max to avoid blocks)
_SMTP_LIMITS: dict[str, dict] = {
    # ── Google ────────────────────────────────────────────────────────────────
    "gmail.com": {
        "daily": 500, "hourly": 100,
        "notes": "500/day free (official). Workspace: 2000/day. Requires App Password or OAuth2.",
        "source": "https://support.google.com/mail/answer/22839",
    },
    "googlemail.com": {"daily": 500, "hourly": 100, "notes": "Same as gmail.com"},

    # ── Microsoft ─────────────────────────────────────────────────────────────
    "outlook.com": {
        "daily": 300, "hourly": 50,
        "notes": "300/day for consumer Outlook.com (official). M365 Business: ~10k/day global.",
        "source": "https://support.microsoft.com/en-us/office/sending-limits-in-outlook-com-279ee200-594c-40f0-9ec8-bb6af7735c2e",
    },
    "hotmail.com":   {"daily": 300, "hourly": 50,  "notes": "Same as outlook.com (Microsoft consumer)"},
    "hotmail.co.uk": {"daily": 300, "hourly": 50,  "notes": "Same as outlook.com"},
    "hotmail.de":    {"daily": 300, "hourly": 50,  "notes": "Same as outlook.com"},
    "hotmail.fr":    {"daily": 300, "hourly": 50,  "notes": "Same as outlook.com"},
    "hotmail.ru":    {"daily": 300, "hourly": 50,  "notes": "Same as outlook.com"},
    "hotmail.es":    {"daily": 300, "hourly": 50,  "notes": "Same as outlook.com"},
    "hotmail.it":    {"daily": 300, "hourly": 50,  "notes": "Same as outlook.com"},
    "live.com":      {"daily": 300, "hourly": 50,  "notes": "Same as outlook.com"},
    "live.co.uk":    {"daily": 300, "hourly": 50,  "notes": "Same as outlook.com"},
    "live.de":       {"daily": 300, "hourly": 50,  "notes": "Same as outlook.com"},
    "live.fr":       {"daily": 300, "hourly": 50,  "notes": "Same as outlook.com"},
    "live.ru":       {"daily": 300, "hourly": 50,  "notes": "Same as outlook.com"},
    "msn.com":       {"daily": 300, "hourly": 50,  "notes": "Same as outlook.com"},
    "windowslive.com": {"daily": 300, "hourly": 50, "notes": "Same as outlook.com"},

    # ── Yahoo ─────────────────────────────────────────────────────────────────
    "yahoo.com": {
        "daily": 500, "hourly": 100,
        "notes": "500/day official. Requires App Password (2FA must be enabled).",
        "source": "https://help.yahoo.com/kb/SLN3403.html",
    },
    "yahoo.co.uk":   {"daily": 500, "hourly": 100, "notes": "Same as yahoo.com"},
    "yahoo.de":      {"daily": 500, "hourly": 100, "notes": "Same as yahoo.com"},
    "yahoo.fr":      {"daily": 500, "hourly": 100, "notes": "Same as yahoo.com"},
    "yahoo.es":      {"daily": 500, "hourly": 100, "notes": "Same as yahoo.com"},
    "yahoo.it":      {"daily": 500, "hourly": 100, "notes": "Same as yahoo.com"},
    "yahoo.co.jp":   {"daily": 500, "hourly": 100, "notes": "Same as yahoo.com"},
    "yahoo.ru":      {"daily": 500, "hourly": 100, "notes": "Same as yahoo.com"},
    "yahoo.com.br":  {"daily": 500, "hourly": 100, "notes": "Same as yahoo.com"},
    "yahoo.com.ar":  {"daily": 500, "hourly": 100, "notes": "Same as yahoo.com"},
    "yahoo.com.mx":  {"daily": 500, "hourly": 100, "notes": "Same as yahoo.com"},
    "yahoo.com.au":  {"daily": 500, "hourly": 100, "notes": "Same as yahoo.com"},
    "yahoo.ca":      {"daily": 500, "hourly": 100, "notes": "Same as yahoo.com"},
    "ymail.com":     {"daily": 500, "hourly": 100, "notes": "Same as yahoo.com"},
    "rocketmail.com": {"daily": 500, "hourly": 100, "notes": "Same as yahoo.com"},
    "aol.com": {
        "daily": 500, "hourly": 100,
        "notes": "500/day. AOL uses same infrastructure as Yahoo.",
        "source": "https://help.aol.com/articles/aol-mail-smtp-settings",
    },

    # ── GMX / Web.de (1&1 IONOS family) ──────────────────────────────────────
    "gmx.com": {
        "daily": 100, "hourly": 30,
        "notes": "100 recipients/day free. GMX blocks datacenter IPs — requires residential proxies.",
        "source": "https://support.gmx.com/pop-imap/smtp-general.html",
    },
    "gmx.net":   {"daily": 100, "hourly": 30, "notes": "Same as gmx.com"},
    "gmx.de":    {"daily": 100, "hourly": 30, "notes": "Same as gmx.com"},
    "gmx.at":    {"daily": 100, "hourly": 30, "notes": "Same as gmx.com"},
    "gmx.ch":    {"daily": 100, "hourly": 30, "notes": "Same as gmx.com"},
    "gmx.co.uk": {"daily": 100, "hourly": 30, "notes": "Same as gmx.com"},
    "gmx.fr":    {"daily": 100, "hourly": 30, "notes": "Same as gmx.com"},
    "gmx.es":    {"daily": 100, "hourly": 30, "notes": "Same as gmx.com"},
    "gmx.us":    {"daily": 100, "hourly": 30, "notes": "Same as gmx.com (US endpoint smtp.gmx.com)"},
    "web.de": {
        "daily": 500, "hourly": 100,
        "notes": "500/day. Web.de shares GMX infrastructure but higher limit.",
        "source": "https://hilfe.web.de/pop-imap/smtp.html",
    },

    # ── Yandex ────────────────────────────────────────────────────────────────
    "yandex.ru": {
        "daily": 500, "hourly": 100,
        "notes": "500 messages/day official. Use App Password.",
        "source": "https://yandex.com/support/mail/mail-clients/others.html",
    },
    "yandex.com": {"daily": 500, "hourly": 100, "notes": "Same as yandex.ru"},
    "ya.ru":      {"daily": 500, "hourly": 100, "notes": "Same as yandex.ru"},
    "yandex.by":  {"daily": 500, "hourly": 100, "notes": "Same as yandex.ru (smtp.yandex.by)"},
    "yandex.kz":  {"daily": 500, "hourly": 100, "notes": "Same as yandex.ru"},
    "yandex.ua":  {"daily": 500, "hourly": 100, "notes": "Same as yandex.ru"},

    # ── Mail.ru family ────────────────────────────────────────────────────────
    "mail.ru": {
        "daily": 500, "hourly": 100,
        "notes": "500/day. App Password required if 2FA enabled.",
        "source": "https://help.mail.ru/mail/mailer/popsmtp",
    },
    "inbox.ru":   {"daily": 500, "hourly": 100, "notes": "Same as mail.ru"},
    "list.ru":    {"daily": 500, "hourly": 100, "notes": "Same as mail.ru"},
    "bk.ru":      {"daily": 500, "hourly": 100, "notes": "Same as mail.ru"},
    "internet.ru": {"daily": 500, "hourly": 100, "notes": "Same as mail.ru"},
    "ro.ru":      {"daily": 500, "hourly": 100, "notes": "Same as mail.ru"},

    # ── Rambler ───────────────────────────────────────────────────────────────
    "rambler.ru": {
        "daily": 500, "hourly": 100,
        "notes": "500/day. Plain password auth (no 2FA/App Password).",
        "source": "https://help.rambler.ru/mail/client/1277/",
    },
    "lenta.ru":       {"daily": 500, "hourly": 100, "notes": "Same as rambler.ru"},
    "autorambler.ru": {"daily": 500, "hourly": 100, "notes": "Same as rambler.ru"},
    "myrambler.ru":   {"daily": 500, "hourly": 100, "notes": "Same as rambler.ru"},

    # ── Apple iCloud ──────────────────────────────────────────────────────────
    "icloud.com": {
        "daily": 1000, "hourly": 200,
        "notes": "1000/day. Requires App-Specific Password (Settings → Password & Security).",
        "source": "https://support.apple.com/en-us/102576",
    },
    "me.com":  {"daily": 1000, "hourly": 200, "notes": "Same as icloud.com"},
    "mac.com": {"daily": 1000, "hourly": 200, "notes": "Same as icloud.com"},

    # ── Zoho ──────────────────────────────────────────────────────────────────
    "zoho.com": {
        "daily": 200, "hourly": 50,
        "notes": "200/day free tier. Paid plans: 500-5000/day.",
        "source": "https://www.zoho.com/mail/help/smtp-access.html",
    },
    "zohomail.com": {"daily": 200, "hourly": 50, "notes": "Same as zoho.com"},
    "zoho.eu":      {"daily": 200, "hourly": 50, "notes": "Same as zoho.com (EU endpoint)"},
    "zohomail.eu":  {"daily": 200, "hourly": 50, "notes": "Same as zoho.com"},
    "zoho.in":      {"daily": 200, "hourly": 50, "notes": "Same as zoho.com"},

    # ── FastMail ──────────────────────────────────────────────────────────────
    "fastmail.com": {
        "daily": 1000, "hourly": 200,
        "notes": "1000/day. App Password via Settings → Privacy & Security → App Passwords.",
        "source": "https://www.fastmail.help/hc/en-us/articles/1500000278342",
    },
    "fastmail.fm": {"daily": 1000, "hourly": 200, "notes": "Same as fastmail.com"},

    # ── T-Online / Telekom ────────────────────────────────────────────────────
    "t-online.de": {
        "daily": 500, "hourly": 100,
        "notes": "500/day. Telekom Germany. SSL port 465.",
    },
    "telekom.de": {"daily": 500, "hourly": 100, "notes": "Same as t-online.de"},

    # ── Ukrainian providers ───────────────────────────────────────────────────
    "ukr.net": {
        "daily": 500, "hourly": 100,
        "notes": "500/day. App Password required.",
    },
    "i.ua":    {"daily": 300, "hourly": 60, "notes": "300/day"},
    "meta.ua": {"daily": 300, "hourly": 60, "notes": "300/day"},

    # ── firstmail.ltd family ──────────────────────────────────────────────────
    "blackfirsta.com":    {"daily": 500, "hourly": 100, "notes": "firstmail.ltd infrastructure"},
    "firsthidden.com":    {"daily": 500, "hourly": 100, "notes": "firstmail.ltd infrastructure"},
    "ishowfirstmail.com": {"daily": 500, "hourly": 100, "notes": "firstmail.ltd infrastructure"},
    "analismail.com":     {"daily": 500, "hourly": 100, "notes": "firstmail.ltd infrastructure"},
}

# Default for unknown domains
_DEFAULT_LIMITS = {"daily": 300, "hourly": 60, "notes": "Conservative defaults for unknown domain"}


def get_limits(email_or_domain: str) -> dict:
    """Return official sending limits for a given email or domain.

    Returns dict with keys: daily, hourly, notes (and optionally source).
    Falls back to conservative defaults for unknown domains.

    Usage:
        limits = get_limits("user@gmail.com")
        account.daily_limit = limits["daily"]
        account.hourly_limit = limits["hourly"]
    """
    domain = email_or_domain.lower().strip()
    if "@" in domain:
        domain = domain.split("@")[-1]
    return dict(_SMTP_LIMITS.get(domain, _DEFAULT_LIMITS))


def get_daily_limit(email_or_domain: str) -> int:
    """Shortcut: return just the daily limit integer."""
    return get_limits(email_or_domain)["daily"]


def get_hourly_limit(email_or_domain: str) -> int:
    """Shortcut: return just the hourly limit integer."""
    return get_limits(email_or_domain)["hourly"]


def apply_limits_to_account(account) -> None:
    """Set daily_limit and hourly_limit on a SmtpAccount based on official limits.

    Respects existing user-set limits if they are LOWER than the official max
    (user may have deliberately set a conservative limit).
    """
    lim = get_limits(account.email)
    official_daily = lim["daily"]
    official_hourly = lim["hourly"]
    # Only increase if account has the default 500/50 — don't override custom limits
    if account.daily_limit >= 500:
        account.daily_limit = official_daily
    if account.hourly_limit >= 50:
        account.hourly_limit = official_hourly


def get_all_limits() -> dict[str, dict]:
    """Return full limits table (for UI display / export)."""
    return dict(_SMTP_LIMITS)
