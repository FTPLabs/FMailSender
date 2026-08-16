"""
T001 — FMailSender v6 Core Integration Tests
Новая архитектура: Tauri v2 + FastAPI + React

Покрывают:
- Версия приложения (валидный SemVer)
- models.py: SmtpAccount, Recipient, CampaignConfig, CampaignStatus
- storage.py: сериализация/десериализация (без прокси — сессионные данные)
- proxy.py: парсинг всех форматов, ProxyManager ротация
- sender.py: _pick_account, SmtpAccount duck-compat
- server.py: импорт FastAPI app, health endpoint
- _ensure_imports.py: все lazy-зависимости

Запуск: python3 tests/test_v6_core.py
"""
from __future__ import annotations

import os
import sys
import re
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

_failures: list[str] = []
_passes: int = 0


def check(cond: bool, label: str, detail: str = "") -> None:
    global _passes
    if cond:
        _passes += 1
        print(f"[PASS] {label}")
    else:
        _failures.append(label)
        suffix = f" | {detail}" if detail else ""
        print(f"[FAIL] {label}{suffix}")


# ─────────────────────────────────────────────────────────────────────────────
# Version check
# ─────────────────────────────────────────────────────────────────────────────

def test_version() -> None:
    print("\n--- Version: SemVer check ---")
    from core._version import APP_VERSION
    check(bool(re.fullmatch(r"\d+\.\d+\.\d+", APP_VERSION)),
          f"APP_VERSION is SemVer (got: {APP_VERSION})", f"got {APP_VERSION}")
    check(APP_VERSION == "7.3.1", "APP_VERSION matches current release", f"got {APP_VERSION}")


# ─────────────────────────────────────────────────────────────────────────────
# models.py — SmtpAccount
# ─────────────────────────────────────────────────────────────────────────────

def test_smtp_account_model() -> None:
    print("\n--- models.py: SmtpAccount ---")
    from core.models import SmtpAccount

    a = SmtpAccount(
        email="test@gmail.com",
        password="secret",
        host="smtp.gmail.com",
        port=465,
        use_ssl=True,
    )
    check(a.email == "test@gmail.com", "SmtpAccount.email")
    check(a.port == 465, "SmtpAccount.port default")
    check(a.is_active is True, "SmtpAccount.is_active default True")
    check(a.last_test_ok is None, "SmtpAccount.last_test_ok default None")
    check(a.daily_limit == 500, "SmtpAccount.daily_limit default 500")
    check(a.proxy == "", "SmtpAccount.proxy default empty")
    check(a.proxy_list == [], "SmtpAccount.proxy_list default []")
    check(a.imap_host == "", "SmtpAccount.imap_host default empty")
    check(a.imap_port == 993, "SmtpAccount.imap_port default 993")

    d = a.to_dict()
    check(isinstance(d, dict), "SmtpAccount.to_dict() returns dict")
    check(d["email"] == "test@gmail.com", "to_dict() email correct")
    check("password" in d, "to_dict() includes password")
    check("proxy_list" in d, "to_dict() includes proxy_list")
    check("last_test_ok" in d, "to_dict() includes last_test_ok")

    a2 = SmtpAccount.from_dict(d)
    check(a2.email == a.email, "from_dict() email roundtrip")
    check(a2.host == a.host, "from_dict() host roundtrip")
    check(a2.port == a.port, "from_dict() port roundtrip")


# ─────────────────────────────────────────────────────────────────────────────
# models.py — Recipient
# ─────────────────────────────────────────────────────────────────────────────

def test_recipient_model() -> None:
    print("\n--- models.py: Recipient ---")
    from core.models import Recipient

    r = Recipient(email="user@example.com", name="John Doe")
    check(r.email == "user@example.com", "Recipient.email")
    check(r.name == "John Doe", "Recipient.name")
    check(r.variables == {}, "Recipient.variables default {}")

    d = r.to_dict()
    check(d["email"] == "user@example.com", "to_dict() email")
    check(d["name"] == "John Doe", "to_dict() name")

    r2 = Recipient.from_dict(d)
    check(r2.email == r.email, "from_dict() roundtrip email")
    check(r2.name == r.name, "from_dict() roundtrip name")


# ─────────────────────────────────────────────────────────────────────────────
# models.py — CampaignConfig and CampaignStatus
# ─────────────────────────────────────────────────────────────────────────────

def test_campaign_models() -> None:
    print("\n--- models.py: CampaignConfig / CampaignStatus ---")
    from core.models import CampaignConfig, CampaignStatus

    cfg = CampaignConfig(subject="Test", body_html="<h1>Hi</h1>")
    check(cfg.subject == "Test", "CampaignConfig.subject")
    check(cfg.delay_min == 1.0, "CampaignConfig.delay_min default 1.0")
    check(cfg.delay_max == 3.0, "CampaignConfig.delay_max default 3.0")
    check(cfg.daily_limit_per_account == 500, "CampaignConfig.daily_limit default 500")

    st = CampaignStatus()
    check(st.state == "idle", "CampaignStatus.state default idle")
    check(st.sent == 0, "CampaignStatus.sent default 0")
    check(st.total == 0, "CampaignStatus.total default 0")

    d = st.to_dict()
    check("state" in d, "to_dict() state")
    check("progress_pct" in d, "to_dict() progress_pct")
    check(d["progress_pct"] == 0.0, "progress_pct == 0 when total==0")

    st2 = CampaignStatus(sent=50, total=100, state="running")
    d2 = st2.to_dict()
    check(d2["progress_pct"] == 50.0, "progress_pct == 50.0", f"got {d2['progress_pct']}")


# ─────────────────────────────────────────────────────────────────────────────
# proxy.py — parse_proxy, ProxyManager
# ─────────────────────────────────────────────────────────────────────────────

def test_proxy_parsing() -> None:
    print("\n--- proxy.py: parse_proxy ---")
    from core.proxy import parse_proxy, ProxyManager

    # SOCKS5 with auth
    p = parse_proxy("socks5://user:pass@1.2.3.4:1080")
    check(p is not None, "parse_proxy: socks5://user:pass@host:port")
    check("socks5://" in (p or ""), "parse_proxy: socks5 scheme preserved")

    # HTTP proxy
    p2 = parse_proxy("http://1.2.3.5:8080")
    check(p2 is not None, "parse_proxy: http://host:port")

    # host:port:user:pass format
    p3 = parse_proxy("1.2.3.6:1080:user:pass")
    check(p3 is not None, "parse_proxy: host:port:user:pass format")

    # host:port (bare)
    p4 = parse_proxy("1.2.3.7:1080")
    check(p4 is not None, "parse_proxy: bare host:port")

    # Invalid → None
    p5 = parse_proxy("not-a-proxy")
    check(p5 is None, "parse_proxy: invalid → None")

    # ProxyManager round-robin
    raw = ["socks5://1.2.3.1:1080", "socks5://1.2.3.2:1080", "socks5://1.2.3.3:1080"]
    pm = ProxyManager(raw)
    check(len(pm.proxies) == 3, "ProxyManager: 3 proxies loaded")
    got = set()
    for _ in range(9):
        n = pm.next()
        if n:
            got.add(n)
    check(len(got) == 3, "ProxyManager: round-robin cycles through all proxies")

    # ProxyManager distribute
    from core.models import SmtpAccount
    accs = [SmtpAccount(email=f"a{i}@test.com", password="p", host="h", port=465, use_ssl=True)
            for i in range(6)]
    pm.distribute(accs)
    proxies_assigned = [a.proxy for a in accs]
    check(all(p for p in proxies_assigned), "ProxyManager.distribute: all accounts got proxy")
    check(proxies_assigned[0] != proxies_assigned[1] or len(raw) == 1,
          "ProxyManager.distribute: different accounts get different proxies")


# ─────────────────────────────────────────────────────────────────────────────
# sender.py — SmtpAccount duck-compat, get_smtp_config_for_domain
# ─────────────────────────────────────────────────────────────────────────────

def test_sender_duck_compat() -> None:
    print("\n--- sender.py: duck-compat + SMTP configs ---")
    from core.sender import SmtpAccount as SenderAccount, get_smtp_config_for_domain
    from core.models import SmtpAccount as ModelAccount

    # Duck-compat: models.SmtpAccount can be used where sender.SmtpAccount is expected
    ma = ModelAccount(email="test@gmail.com", password="p", host="smtp.gmail.com", port=465, use_ssl=True)
    # Fields that sender.py requires
    for field in ["email", "password", "host", "port", "use_ssl", "use_tls",
                  "proxy", "display_name", "daily_limit", "hourly_limit", "is_active"]:
        check(hasattr(ma, field), f"models.SmtpAccount has field: {field}")

    # SMTP configs for major providers
    domains_expected = {
        "gmail.com":   ("smtp.gmail.com", 465),
        "yahoo.com":   ("smtp.mail.yahoo.com", 465),
        "mail.ru":     ("smtp.mail.ru", 465),
        "yandex.ru":   ("smtp.yandex.ru", 465),
        "gmx.com":     ("mail.gmx.net", 587),
        "outlook.com": ("smtp.office365.com", 587),
        "hotmail.com": ("smtp.office365.com", 587),
    }
    for domain, (expected_host, expected_port) in domains_expected.items():
        cfg = get_smtp_config_for_domain(domain)
        if cfg:
            check("host" in cfg, f"get_smtp_config_for_domain({domain}): has host key")
            check(cfg.get("host") == expected_host,
                  f"{domain}: host={expected_host}", f"got {cfg.get('host')}")
            check(cfg.get("port") == expected_port,
                  f"{domain}: port={expected_port}", f"got {cfg.get('port')}")
        else:
            check(False, f"get_smtp_config_for_domain({domain}): returned None (expected config)")


# ─────────────────────────────────────────────────────────────────────────────
# sender.py — _pick_account filtering
# ─────────────────────────────────────────────────────────────────────────────

def test_pick_account_v6() -> None:
    print("\n--- sender.py: _pick_account (v6) ---")
    import queue
    from core.sender import SmtpAccount, SendingEngine, CampaignConfig

    def _make(email: str, active: bool, ok) -> SmtpAccount:
        a = SmtpAccount(email=email, password="p", host="smtp.test.com", port=465, use_ssl=True)
        a.is_active = active
        a.last_test_ok = ok
        return a

    accounts = [
        _make("valid@test.com",    True,  True),    # should be picked
        _make("invalid@test.com",  True,  False),   # skip (failed test)
        _make("untested@test.com", True,  None),    # should be picked (untested)
        _make("disabled@test.com", False, True),    # skip (inactive)
    ]

    cfg = CampaignConfig(max_threads=1)
    engine = SendingEngine(accounts=accounts, config=cfg, log_queue=queue.Queue())

    picked = set()
    for _ in range(30):
        acc = engine._pick_account()
        if acc:
            picked.add(acc.email)

    check("valid@test.com" in picked, "_pick_account picks valid (last_test_ok=True)")
    check("untested@test.com" in picked, "_pick_account picks untested (last_test_ok=None)")
    check("invalid@test.com" not in picked, "_pick_account skips failed (last_test_ok=False)")
    check("disabled@test.com" not in picked, "_pick_account skips inactive (is_active=False)")


# ─────────────────────────────────────────────────────────────────────────────
# server.py — FastAPI app imports correctly
# ─────────────────────────────────────────────────────────────────────────────

def test_server_import() -> None:
    print("\n--- server.py: FastAPI app import ---")
    try:
        from core.server import app
        from fastapi import FastAPI
        check(isinstance(app, FastAPI), "server.py: app is FastAPI instance")
        check(app.title == "FMailSender Core", "server.py: app.title == 'FMailSender Core'",
              f"got '{app.title}'")
        # Check routes exist
        routes = {r.path for r in app.routes}
        for expected in ["/api/health", "/api/accounts", "/api/status"]:
            check(expected in routes, f"route exists: {expected}")
    except Exception as e:
        check(False, f"server.py import failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# storage.py — serialize/deserialize accounts (proxy fields stripped)
# ─────────────────────────────────────────────────────────────────────────────

def test_storage_roundtrip() -> None:
    print("\n--- storage.py: accounts roundtrip (proxy stripped) ---")
    import importlib
    import core.storage as storage_mod

    from core.models import SmtpAccount

    with tempfile.TemporaryDirectory() as tmp:
        # Patch DATA_DIR to temp
        orig_dir = storage_mod.DATA_DIR
        orig_acc = storage_mod.ACCOUNTS_FILE
        orig_key = storage_mod.KEY_FILE

        tmp_path = Path(tmp)
        storage_mod.DATA_DIR = tmp_path
        storage_mod.ACCOUNTS_FILE = tmp_path / "accounts.json"
        storage_mod.KEY_FILE = tmp_path / ".fernet_key"

        try:
            acc = SmtpAccount(
                email="test@example.com", password="secret123",
                host="smtp.example.com", port=587,
                use_ssl=False, use_tls=True,
                proxy="socks5://1.2.3.4:1080",
                proxy_list=["socks5://1.2.3.5:1080"],
            )
            storage_mod.save_accounts([acc])
            loaded = storage_mod.load_accounts()

            check(len(loaded) == 1, "storage: 1 account loaded after save")
            check(loaded[0].email == "test@example.com", "storage: email roundtrip")
            check(loaded[0].password == "secret123", "storage: password decrypted correctly")
            check(loaded[0].proxy == "", "storage: proxy cleared on load (session-only)")
            check(loaded[0].proxy_list == [], "storage: proxy_list cleared on load (session-only)")
        finally:
            storage_mod.DATA_DIR = orig_dir
            storage_mod.ACCOUNTS_FILE = orig_acc
            storage_mod.KEY_FILE = orig_key


# ─────────────────────────────────────────────────────────────────────────────
# _ensure_imports.py — no ImportError on load
# ─────────────────────────────────────────────────────────────────────────────

def test_ensure_imports() -> None:
    print("\n--- _ensure_imports.py: lazy deps importable ---")
    try:
        import core._ensure_imports  # noqa: F401
        check(True, "_ensure_imports: loaded without ImportError")
    except ImportError as e:
        check(False, f"_ensure_imports: ImportError — {e}")
    except Exception as e:
        check(False, f"_ensure_imports: unexpected error — {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Architecture: new arch files present, old arch files absent
# ─────────────────────────────────────────────────────────────────────────────

def test_architecture_files() -> None:
    print("\n--- Architecture: new files present, old absent ---")
    ROOT = Path(_ROOT)

    # New arch MUST exist
    new_required = [
        "core/server.py", "core/models.py", "core/sender.py",
        "core/storage.py", "core/proxy.py", "core/_version.py",
        "main.py", "requirements.txt",
        "backend/src/server.js", "electron/main.js", "electron/package.json",
        "src-tauri/src/main.rs", "src-tauri/tauri.conf.json",
        "ui/src/App.tsx", "ui/src/api.ts", "ui/src/theme.ts",
        "ui/src/pages/Dashboard.tsx", "ui/src/pages/Accounts.tsx",
        "ui/src/pages/Sending.tsx",
        ".github/workflows/release.yml",
    ]
    for f in new_required:
        check((ROOT / f).exists(), f"NEW ARCH: {f} exists")

    # Old arch MUST NOT exist
    old_forbidden = [
        "installer/setup.iss",               # InnoSetup v3.4.3
        "portable.nsi",                       # legacy NSIS packaging
        "installer/create_wizard_bitmaps.py", # Old bitmap generator
    ]
    for f in old_forbidden:
        check(not (ROOT / f).exists(), f"OLD ARCH REMOVED: {f} absent")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_version()
    test_smtp_account_model()
    test_recipient_model()
    test_campaign_models()
    test_proxy_parsing()
    test_sender_duck_compat()
    test_pick_account_v6()
    test_server_import()
    test_storage_roundtrip()
    test_ensure_imports()
    test_architecture_files()

    print(f"\n{'='*60}")
    print(f"Results: {_passes} passed, {len(_failures)} failed")
    if _failures:
        print("FAILED:")
        for f in _failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("All v6 tests passed!")
        sys.exit(0)
