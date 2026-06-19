"""
FMailSender Extended SMTP Configs v1.0.0
Additional providers loaded at runtime into _SMTP_CONFIGS.
Add new providers here — not in sender.py.
"""
from __future__ import annotations


def load_extra_configs() -> dict[str, dict]:
    """Return extra SMTP configs to merge into sender._SMTP_CONFIGS."""
    return {
        # ── Transactional / Marketing SMTP ───────────────────────────────────
        # These require app credentials (username=API_KEY, password=API_KEY or secret)
        "sendgrid":    {"host": "smtp.sendgrid.net",                   "port": 587, "use_ssl": False, "use_tls": True},
        "mailgun":     {"host": "smtp.mailgun.org",                    "port": 587, "use_ssl": False, "use_tls": True},
        "postmark":    {"host": "smtp.postmarkapp.com",                "port": 587, "use_ssl": False, "use_tls": True},
        "sparkpost":   {"host": "smtp.sparkpostmail.com",              "port": 587, "use_ssl": False, "use_tls": True},
        "brevo":       {"host": "smtp-relay.brevo.com",                "port": 587, "use_ssl": False, "use_tls": True},
        "sendinblue":  {"host": "smtp-relay.brevo.com",                "port": 587, "use_ssl": False, "use_tls": True},
        "elasticemail":{"host": "smtp.elasticemail.com",               "port": 2525,"use_ssl": False, "use_tls": True},
        "mailjet":     {"host": "in-v3.mailjet.com",                   "port": 587, "use_ssl": False, "use_tls": True},

        # ── Amazon SES ───────────────────────────────────────────────────────
        "ses-us-east":  {"host": "email-smtp.us-east-1.amazonaws.com",  "port": 465, "use_ssl": True, "use_tls": False},
        "ses-eu-west":  {"host": "email-smtp.eu-west-1.amazonaws.com",  "port": 465, "use_ssl": True, "use_tls": False},
        "ses-ap-south": {"host": "email-smtp.ap-southeast-1.amazonaws.com","port": 465,"use_ssl": True,"use_tls": False},

        # ── Privacy-focused ──────────────────────────────────────────────────
        # Fastmail
        "fastmail.com":  {"host": "smtp.fastmail.com", "port": 465, "use_ssl": True,  "use_tls": False,
                          "imap_host": "imap.fastmail.com", "imap_port": 993, "imap_ssl": True},
        "fastmail.fm":   {"host": "smtp.fastmail.com", "port": 465, "use_ssl": True,  "use_tls": False,
                          "imap_host": "imap.fastmail.com", "imap_port": 993, "imap_ssl": True},
        "fastmail.net":  {"host": "smtp.fastmail.com", "port": 465, "use_ssl": True,  "use_tls": False},
        # Tutanota (requires Tutanota Bridge — not standard SMTP)
        # "tutanota.com": NOT SUPPORTED — uses proprietary protocol
        # ProtonMail Bridge (local proxy required)
        "protonmail.com":{"host": "127.0.0.1",         "port": 1025, "use_ssl": False, "use_tls": False,
                          "_note": "Requires ProtonMail Bridge app running locally"},
        "proton.me":     {"host": "127.0.0.1",         "port": 1025, "use_ssl": False, "use_tls": False},
        # Mailbox.org
        "mailbox.org":   {"host": "smtp.mailbox.org",  "port": 465, "use_ssl": True,  "use_tls": False,
                          "imap_host": "imap.mailbox.org", "imap_port": 993, "imap_ssl": True},

        # ── Asian providers ───────────────────────────────────────────────────
        "qq.com":        {"host": "smtp.qq.com",       "port": 465, "use_ssl": True,  "use_tls": False,
                          "imap_host": "imap.qq.com",  "imap_port": 993, "imap_ssl": True},
        "163.com":       {"host": "smtp.163.com",      "port": 465, "use_ssl": True,  "use_tls": False,
                          "imap_host": "imap.163.com", "imap_port": 993, "imap_ssl": True},
        "126.com":       {"host": "smtp.126.com",      "port": 465, "use_ssl": True,  "use_tls": False},
        "sina.com":      {"host": "smtp.sina.com",     "port": 465, "use_ssl": True,  "use_tls": False},
        "sina.cn":       {"host": "smtp.sina.com",     "port": 465, "use_ssl": True,  "use_tls": False},
        "sohu.com":      {"host": "smtp.sohu.com",     "port": 465, "use_ssl": True,  "use_tls": False},
        "naver.com":     {"host": "smtp.naver.com",    "port": 587, "use_ssl": False, "use_tls": True},
        "daum.net":      {"host": "smtp.daum.net",     "port": 465, "use_ssl": True,  "use_tls": False},
        "hanmail.net":   {"host": "smtp.daum.net",     "port": 465, "use_ssl": True,  "use_tls": False},

        # ── Additional European ───────────────────────────────────────────────
        "libero.it":     {"host": "smtp.libero.it",    "port": 465, "use_ssl": True,  "use_tls": False},
        "virgilio.it":   {"host": "smtp.virgilio.it",  "port": 465, "use_ssl": True,  "use_tls": False},
        "tin.it":        {"host": "smtp.tin.it",       "port": 587, "use_ssl": False, "use_tls": True},
        "alice.it":      {"host": "smtp.alice.it",     "port": 587, "use_ssl": False, "use_tls": True},
        "tiscali.it":    {"host": "smtp.tiscali.it",   "port": 465, "use_ssl": True,  "use_tls": False},
        "seznam.cz":     {"host": "smtp.seznam.cz",    "port": 465, "use_ssl": True,  "use_tls": False,
                          "imap_host": "imap.seznam.cz", "imap_port": 993, "imap_ssl": True},
        "centrum.cz":    {"host": "smtp.centrum.cz",   "port": 465, "use_ssl": True,  "use_tls": False},
        "atlas.cz":      {"host": "smtp.atlas.cz",     "port": 465, "use_ssl": True,  "use_tls": False},
        "wp.pl":         {"host": "smtp.wp.pl",        "port": 465, "use_ssl": True,  "use_tls": False},
        "onet.pl":       {"host": "smtp.poczta.onet.pl","port": 465, "use_ssl": True, "use_tls": False},
        "interia.pl":    {"host": "poczta.interia.pl", "port": 465, "use_ssl": True,  "use_tls": False},
        "o2.pl":         {"host": "smtp.o2.pl",        "port": 465, "use_ssl": True,  "use_tls": False},
        "abv.bg":        {"host": "smtp.abv.bg",       "port": 465, "use_ssl": True,  "use_tls": False},

        # ── Middle East ───────────────────────────────────────────────────────
        "walla.com":     {"host": "smtp.walla.com",    "port": 465, "use_ssl": True,  "use_tls": False},
        "012.net.il":    {"host": "smtp.012.net.il",   "port": 587, "use_ssl": False, "use_tls": True},

        # ── Latin America ─────────────────────────────────────────────────────
        "terra.com.br":  {"host": "smtp.terra.com.br", "port": 587, "use_ssl": False, "use_tls": True},
        "uol.com.br":    {"host": "smtp.uol.com.br",   "port": 587, "use_ssl": False, "use_tls": True},
        "bol.com.br":    {"host": "smtp.bol.com.br",   "port": 465, "use_ssl": True,  "use_tls": False},

        # ── Africa / MENA ─────────────────────────────────────────────────────
        "mail.co.za":    {"host": "smtp.mail.co.za",   "port": 587, "use_ssl": False, "use_tls": True},
    }
