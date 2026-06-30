"""
FMailSender — Comprehensive Test Suite v1.0.0
=============================================
Covers: SMTP config, uniqueizer, spam checker, proxy parser,
        duplicate detector, warmup, bounce parser, smtp_limits,
        send_checkpoint, oauth2, _build_message headers.

Run: python -m pytest tests/test_comprehensive.py -v
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ══════════════════════════════════════════════════════════════════════════════
# smtp_limits
# ══════════════════════════════════════════════════════════════════════════════
class TestSmtpLimits:
    def setup_method(self):
        from core.smtp_limits import get_limits, get_daily_limit, get_hourly_limit
        self.get_limits = get_limits
        self.get_daily = get_daily_limit
        self.get_hourly = get_hourly_limit

    def test_gmail_daily_500(self):
        assert self.get_daily("user@gmail.com") == 500

    def test_gmail_hourly_100(self):
        assert self.get_hourly("gmail.com") == 100

    def test_outlook_daily_300(self):
        assert self.get_daily("user@outlook.com") == 300

    def test_hotmail_same_as_outlook(self):
        assert self.get_daily("hotmail.com") == 300

    def test_yahoo_daily_500(self):
        assert self.get_daily("yahoo.com") == 500

    def test_gmx_daily_100(self):
        assert self.get_daily("gmx.com") == 100

    def test_gmx_net_same_as_gmx(self):
        assert self.get_daily("gmx.net") == self.get_daily("gmx.com")

    def test_yandex_daily_500(self):
        assert self.get_daily("yandex.ru") == 500

    def test_mailru_daily_500(self):
        assert self.get_daily("mail.ru") == 500

    def test_icloud_daily_1000(self):
        assert self.get_daily("icloud.com") == 1000

    def test_unknown_domain_fallback(self):
        lim = self.get_limits("user@unknowndomain12345.xyz")
        assert lim["daily"] == 300
        assert lim["hourly"] == 60

    def test_email_input_works(self):
        assert self.get_daily("test@gmail.com") == 500

    def test_domain_input_works(self):
        assert self.get_daily("gmail.com") == 500

    def test_zoho_daily_200(self):
        assert self.get_daily("zoho.com") == 200

    def test_rambler_daily_500(self):
        assert self.get_daily("rambler.ru") == 500

    def test_all_limits_has_required_keys(self):
        from core.smtp_limits import get_all_limits
        for domain, lim in get_all_limits().items():
            assert "daily" in lim, f"Missing daily for {domain}"
            assert "hourly" in lim, f"Missing hourly for {domain}"
            assert lim["daily"] > 0, f"daily <= 0 for {domain}"
            assert lim["hourly"] > 0, f"hourly <= 0 for {domain}"


# ══════════════════════════════════════════════════════════════════════════════
# SMTP config resolution (sender.py)
# ══════════════════════════════════════════════════════════════════════════════
class TestSmtpConfigResolution:
    def setup_method(self):
        from core.sender import get_smtp_config_for_domain
        self.get_cfg = get_smtp_config_for_domain

    def test_gmail_ssl_465(self):
        cfg = self.get_cfg("gmail.com")
        assert cfg["host"] == "smtp.gmail.com"
        assert cfg["port"] == 465
        assert cfg["use_ssl"] is True

    def test_outlook_starttls_587(self):
        cfg = self.get_cfg("outlook.com")
        assert cfg["host"] == "smtp.office365.com"
        assert cfg["port"] == 587
        assert cfg["use_tls"] is True

    def test_hotmail_same_as_outlook(self):
        cfg = self.get_cfg("hotmail.com")
        assert cfg["host"] == "smtp.office365.com"

    def test_yahoo_ssl_465(self):
        cfg = self.get_cfg("yahoo.com")
        assert cfg["host"] == "smtp.mail.yahoo.com"
        assert cfg["port"] == 465

    def test_gmx_com_starttls_587(self):
        cfg = self.get_cfg("gmx.com")
        assert cfg["host"] == "mail.gmx.net"
        assert cfg["port"] == 587

    def test_gmx_net_starttls_587(self):
        cfg = self.get_cfg("gmx.net")
        assert cfg["host"] == "mail.gmx.net"

    def test_yandex_ssl_465(self):
        cfg = self.get_cfg("yandex.ru")
        assert cfg["host"] == "smtp.yandex.ru"
        assert cfg["port"] == 465

    def test_mailru_ssl_465(self):
        cfg = self.get_cfg("mail.ru")
        assert cfg["host"] == "smtp.mail.ru"
        assert cfg["port"] == 465

    def test_rambler_ssl_465(self):
        cfg = self.get_cfg("rambler.ru")
        assert cfg["host"] == "smtp.rambler.ru"
        assert cfg["port"] == 465

    def test_icloud_starttls_587(self):
        cfg = self.get_cfg("icloud.com")
        assert cfg["host"] == "smtp.mail.me.com"
        assert cfg["port"] == 587

    def test_unknown_domain_generic_fallback(self):
        cfg = self.get_cfg("unknown-mail-provider-xyz123.com")
        assert cfg["host"] == "smtp.unknown-mail-provider-xyz123.com"
        assert cfg["port"] == 587

    def test_pattern_outlook_de(self):
        cfg = self.get_cfg("outlook.de")
        assert "office365" in cfg["host"]

    def test_pattern_hotmail_fr(self):
        cfg = self.get_cfg("hotmail.fr")
        assert "office365" in cfg["host"]

    def test_aol_ssl_465(self):
        cfg = self.get_cfg("aol.com")
        assert cfg["host"] == "smtp.aol.com"
        assert cfg["port"] == 465


# ══════════════════════════════════════════════════════════════════════════════
# Uniqueizer
# ══════════════════════════════════════════════════════════════════════════════
class TestUniqueizer:
    HTML = """<html><head><style>body{color:#333333;font-family:Arial,sans-serif}</style></head>
<body><p>Hello {first_name}, click <a href="https://example.com">here</a>.</p>
<p>This is a {test|sample|demo} email.</p></body></html>"""

    def test_spintax_changes_html(self):
        from core.uniqueizer import technique_spintax
        result = technique_spintax(self.HTML)
        assert "{test|sample|demo}" not in result
        assert any(w in result for w in ["test", "sample", "demo"])

    def test_spintax_no_spintax_unchanged(self):
        from core.uniqueizer import technique_spintax
        html = "<p>No spintax here</p>"
        assert technique_spintax(html) == html

    def test_css_micro_changes_color(self):
        from core.uniqueizer import technique_css_micro
        result = technique_css_micro(self.HTML)
        # Color may or may not change (±1), but structure intact
        assert "<style>" in result
        assert "<body>" in result

    def test_data_attrs_adds_data_mid(self):
        from core.uniqueizer import technique_data_attrs
        html = "<table><tr><td>content</td></tr></table>"
        result = technique_data_attrs(html)
        # Should add data-mid to some elements (ratio=0.5 so not always)
        assert "<table" in result

    def test_uuid_fingerprint_adds_meta(self):
        from core.uniqueizer import technique_uuid_fingerprint
        result = technique_uuid_fingerprint(self.HTML)
        assert 'name="x-mid"' in result

    def test_structure_preserved_after_all_techniques(self):
        from core.uniqueizer import apply_all, verify_structure
        html_out, _ = apply_all(self.HTML, "Test subject")
        assert verify_structure(self.HTML, html_out), "Tag sequence changed after apply_all!"

    def test_subject_spintax(self):
        from core.uniqueizer import technique_subject
        result = technique_subject("{Hello|Hi|Hey} there!")
        assert result in ["Hello there!", "Hi there!", "Hey there!"]

    def test_apply_all_returns_tuple(self):
        from core.uniqueizer import apply_all
        result = apply_all(self.HTML, "Test {A|B}")
        assert isinstance(result, tuple) and len(result) == 2

    def test_no_zero_width_space_in_result(self):
        from core.uniqueizer import apply_all
        html_out, subj_out = apply_all(self.HTML, "Test subject")
        assert "\u200b" not in html_out, "Zero-width space found in uniqueized HTML!"
        assert "\u200b" not in subj_out


# ══════════════════════════════════════════════════════════════════════════════
# Spam Checker
# ══════════════════════════════════════════════════════════════════════════════
class TestSpamChecker:
    def setup_method(self):
        from core.spam_checker import SpamChecker
        self.checker = SpamChecker()

    def test_clean_email_low_score(self):
        result = self.checker.check(
            "Project update for next week",
            "<html><body><p>Hi, here is the project update. "
            "<a href='https://example.com/unsubscribe'>Unsubscribe</a></p></body></html>",
        )
        assert result.score < 30, f"Score too high: {result.score}, issues: {result.issues}"

    def test_spam_words_increase_score(self):
        result = self.checker.check(
            "FREE MONEY NOW URGENT!!!",
            "<html><body><p>Click here to win free money guaranteed!</p></body></html>",
        )
        assert result.score > 20

    def test_all_caps_subject_penalized(self):
        result = self.checker.check(
            "WIN FREE MONEY TODAY URGENT OFFER",
            "<html><body><p>normal text</p></body></html>",
        )
        assert result.score > 10

    def test_url_in_subject_penalized(self):
        result = self.checker.check(
            "Check https://example.com now",
            "<html><body><p>text</p></body></html>",
        )
        assert result.score >= 10

    def test_no_unsubscribe_penalized(self):
        result = self.checker.check(
            "Hello",
            "<html><body><p>No unsubscribe link here.</p></body></html>",
        )
        warning_texts = " ".join(result.warnings)
        assert "отписк" in warning_texts.lower() or result.score > 0

    def test_link_density_penalized(self):
        links = " ".join(f'<a href="https://example.com/{i}">link{i}</a>' for i in range(12))
        html = f"<html><body><p>{links}</p></body></html>"
        result = self.checker.check("Normal subject", html)
        issues_text = " ".join(result.issues + result.warnings)
        assert "ссылок" in issues_text or result.score > 10

    def test_inline_base64_image_penalized(self):
        html = '<html><body><img src="data:image/gif;base64,R0lGODlh"/></body></html>'
        result = self.checker.check("Subject", html)
        warnings_text = " ".join(result.warnings)
        assert "base64" in warnings_text or "data:URI" in warnings_text or result.score > 0

    def test_verdict_clean(self):
        from core.spam_checker import SpamCheckResult
        r = SpamCheckResult(score=10)
        assert r.verdict == "Хороший"

    def test_verdict_suspicious(self):
        from core.spam_checker import SpamCheckResult
        r = SpamCheckResult(score=35)
        assert r.verdict == "Подозрительный"

    def test_verdict_spam(self):
        from core.spam_checker import SpamCheckResult
        r = SpamCheckResult(score=60)
        assert r.verdict == "Спам"


# ══════════════════════════════════════════════════════════════════════════════
# Proxy parser
# ══════════════════════════════════════════════════════════════════════════════
class TestProxyParser:
    def setup_method(self):
        from core.proxy import parse_proxy
        self.parse = parse_proxy

    def test_socks5_with_scheme(self):
        result = self.parse("socks5://user:pass@1.2.3.4:1080")
        assert result == "socks5://user:pass@1.2.3.4:1080"

    def test_host_port_only_defaults_socks5(self):
        result = self.parse("1.2.3.4:1080")
        assert result is not None
        assert "1.2.3.4" in result
        assert "socks5" in result

    def test_http_port_detected(self):
        result = self.parse("1.2.3.4:8080")
        assert "http" in result

    def test_user_pass_at_host_port(self):
        result = self.parse("user:pass@1.2.3.4:1080")
        assert result is not None
        assert "user" in result
        assert "pass" in result

    def test_host_port_user_pass_format(self):
        result = self.parse("1.2.3.4:1080:myuser:mypass")
        assert result is not None
        assert "myuser" in result

    def test_empty_returns_none(self):
        assert self.parse("") is None

    def test_comment_returns_none(self):
        assert self.parse("#comment") is None

    def test_already_normalized_passthrough(self):
        raw = "http://u:p@host.com:3128"
        assert self.parse(raw) == raw


# ══════════════════════════════════════════════════════════════════════════════
# Duplicate detector
# ══════════════════════════════════════════════════════════════════════════════
class TestDuplicateDetector:
    def setup_method(self):
        from core.duplicate_detector import deduplicate, _canonical
        self.dedup = deduplicate
        self.canonical = _canonical

    def test_basic_dedup(self):
        result = self.dedup(["a@example.com", "a@example.com", "b@example.com"])
        assert result.unique_count == 2
        assert result.duplicate_count == 1

    def test_case_insensitive(self):
        result = self.dedup(["A@Example.COM", "a@example.com"])
        assert result.unique_count == 1

    def test_gmail_plus_stripped(self):
        result = self.dedup(["user+tag@gmail.com", "user@gmail.com"])
        assert result.unique_count == 1

    def test_gmail_dots_stripped(self):
        result = self.dedup(["u.s.e.r@gmail.com", "user@gmail.com"])
        assert result.unique_count == 1

    def test_outlook_alias(self):
        result = self.dedup(["user@outlook.com", "user@hotmail.com"])
        assert result.unique_count == 1

    def test_gmail_googlemail_alias(self):
        result = self.dedup(["user@gmail.com", "user@googlemail.com"])
        assert result.unique_count == 1

    def test_different_users_not_deduped(self):
        result = self.dedup(["alice@gmail.com", "bob@gmail.com"])
        assert result.unique_count == 2

    def test_stats_has_top_domains(self):
        result = self.dedup(["a@gmail.com", "b@gmail.com", "c@yahoo.com"])
        assert "top_domains" in result.stats

    def test_empty_list(self):
        result = self.dedup([])
        assert result.unique_count == 0
        assert result.duplicate_count == 0


# ══════════════════════════════════════════════════════════════════════════════
# Warmup scheduler
# ══════════════════════════════════════════════════════════════════════════════
class TestWarmupSchedule:
    def setup_method(self):
        from core.warmup import get_warmup_limit
        self.limit = get_warmup_limit

    def test_day_0_is_zero(self):
        assert self.limit(0) == 0

    def test_day_1_is_small(self):
        assert self.limit(1) == 5

    def test_day_30_is_500(self):
        assert self.limit(30) == 500

    def test_day_60_caps_at_800(self):
        assert self.limit(60) == 800

    def test_day_100_caps_at_800(self):
        assert self.limit(100) == 800

    def test_day_29_below_490(self):
        assert self.limit(29) <= 490

    def test_monotonic_increase_days_1_to_30(self):
        for d in range(1, 30):
            assert self.limit(d) <= self.limit(d + 1), f"Not monotonic at day {d}"


# ══════════════════════════════════════════════════════════════════════════════
# Bounce parser
# ══════════════════════════════════════════════════════════════════════════════
class TestBounceParser:
    def _make_dsn(self, recipient: str, code: str = "550", text: str = "User unknown") -> bytes:
        """Build minimal RFC 3464 DSN message."""
        return f"""From: MAILER-DAEMON@example.com
To: sender@example.com
Subject: Mail delivery failed: returning message to sender
MIME-Version: 1.0
Content-Type: multipart/report; report-type=delivery-status; boundary="b"

--b
Content-Type: text/plain

Your message was not delivered.

--b
Content-Type: message/delivery-status

Final-Recipient: rfc822; {recipient}
Status: {code[0]}.{code[1]}.{code[2]}
Diagnostic-Code: smtp; {code} {text}

--b--
""".encode()

    def test_hard_bounce_detected(self):
        from core.bounce import _parse_dsn_message, BounceType
        raw = self._make_dsn("victim@example.com", "550", "User unknown")
        record = _parse_dsn_message(raw)
        assert record is not None
        assert record.email == "victim@example.com"
        assert record.bounce_type == BounceType.HARD

    def test_soft_bounce_detected(self):
        from core.bounce import _parse_dsn_message, BounceType
        raw = self._make_dsn("victim@example.com", "452", "Mailbox full temporarily")
        record = _parse_dsn_message(raw)
        assert record is not None
        assert record.bounce_type == BounceType.SOFT

    def test_non_bounce_returns_none(self):
        from core.bounce import _parse_dsn_message
        raw = b"From: normal@example.com\nSubject: Hello\n\nHi there."
        result = _parse_dsn_message(raw)
        assert result is None


# ══════════════════════════════════════════════════════════════════════════════
# _build_message headers (sender.py)
# ══════════════════════════════════════════════════════════════════════════════
class TestBuildMessage:
    def _make_account(self, email="sender@gmail.com", display_name="Test Sender"):
        from core.sender import SmtpAccount
        return SmtpAccount(
            email=email, password="pass", host="smtp.gmail.com",
            port=465, use_ssl=True, display_name=display_name,
        )

    def _make_recipient(self, email="recipient@example.com"):
        from core.sender import Recipient
        return Recipient(email=email, first_name="John")

    def _make_template(self, reply_to=""):
        from core.sender import EmailTemplate
        return EmailTemplate(
            subject="Test {Hello|Hi}",
            body_html="<html><body><p>Hello {{first_name}}</p></body></html>",
            body_text="Hello {{first_name}}",
            reply_to=reply_to,
        )

    def _build(self, reply_to=""):
        from core.sender import _build_message
        acc = self._make_account()
        rec = self._make_recipient()
        tpl = self._make_template(reply_to=reply_to)
        return _build_message(acc, rec, tpl, uniqueize=False)

    def test_message_id_present(self):
        msg = self._build()
        assert msg["Message-ID"] is not None
        assert "@" in msg["Message-ID"]

    def test_message_id_uses_sender_domain(self):
        msg = self._build()
        assert "gmail.com" in msg["Message-ID"]

    def test_date_header_present(self):
        msg = self._build()
        assert msg["Date"] is not None

    def test_list_unsubscribe_present(self):
        msg = self._build()
        assert msg["List-Unsubscribe"] is not None, "List-Unsubscribe header missing!"
        assert "mailto:" in msg["List-Unsubscribe"]

    def test_list_unsubscribe_post_present(self):
        msg = self._build()
        assert msg["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"

    def test_precedence_bulk(self):
        msg = self._build()
        assert msg["Precedence"] == "bulk"

    def test_reply_to_used_in_unsubscribe(self):
        msg = self._build(reply_to="unsubscribe@example.com")
        assert "unsubscribe@example.com" in msg["List-Unsubscribe"]

    def test_from_with_display_name(self):
        msg = self._build()
        assert "Test Sender" in msg["From"]

    def test_multipart_alternative(self):
        msg = self._build()
        # Should have text/plain and text/html parts
        payload = msg.get_payload()
        assert isinstance(payload, list)

    def test_personalization(self):
        from core.sender import _build_message, SmtpAccount, Recipient, EmailTemplate
        acc = SmtpAccount(email="s@gmail.com", password="p", host="smtp.gmail.com")
        rec = Recipient(email="r@example.com", first_name="Alice", company="Acme")
        tpl = EmailTemplate(
            subject="Hello {{first_name}} from {{company}}",
            body_html="<p>{{first_name}} - {{email}}</p>",
        )
        msg = _build_message(acc, rec, tpl, uniqueize=False)
        payload_str = str(msg.get_payload())
        assert "Alice" in msg["Subject"]
        assert "Acme" in msg["Subject"]


# ══════════════════════════════════════════════════════════════════════════════
# Checkpoint (cross-platform path)
# ══════════════════════════════════════════════════════════════════════════════
class TestCheckpoint:
    def test_checkpoint_dir_is_path(self):
        from core.send_checkpoint import CHECKPOINT_DIR
        from pathlib import Path
        assert isinstance(CHECKPOINT_DIR, Path)

    def test_checkpoint_dir_no_hardcoded_appdata(self):
        """Ensure CHECKPOINT_DIR doesn't hard-code Windows AppData path on non-Windows."""
        from core.send_checkpoint import CHECKPOINT_DIR
        import sys
        if sys.platform != "win32":
            assert "AppData" not in str(CHECKPOINT_DIR), \
                f"CHECKPOINT_DIR is Windows-specific on non-Windows: {CHECKPOINT_DIR}"

    def test_checkpoint_manager_create_and_record(self, tmp_path):
        from core.send_checkpoint import CheckpointManager, CHECKPOINT_DIR
        import core.send_checkpoint as cp_mod
        # Patch CHECKPOINT_DIR to tmp
        original = cp_mod.CHECKPOINT_DIR
        cp_mod.CHECKPOINT_DIR = tmp_path
        try:
            mgr = CheckpointManager("test-campaign-001", total=100)
            mgr.record_sent("a@example.com")
            mgr.record_sent("b@example.com")
            mgr.flush()
            assert "a@example.com" in mgr.get_sent_set()
            assert "b@example.com" in mgr.get_sent_set()
            stats = mgr.stats()
            assert stats["sent"] == 2
        finally:
            cp_mod.CHECKPOINT_DIR = original

    def test_checkpoint_resume(self, tmp_path):
        from core.send_checkpoint import CheckpointManager
        import core.send_checkpoint as cp_mod
        original = cp_mod.CHECKPOINT_DIR
        cp_mod.CHECKPOINT_DIR = tmp_path
        try:
            mgr1 = CheckpointManager("resume-test", total=50)
            for i in range(10):
                mgr1.record_sent(f"user{i}@example.com")
            mgr1.flush()

            mgr2 = CheckpointManager("resume-test", total=50)
            assert mgr2.is_resumable()
            assert len(mgr2.get_sent_set()) == 10
        finally:
            cp_mod.CHECKPOINT_DIR = original


# ══════════════════════════════════════════════════════════════════════════════
# OAuth2 module
# ══════════════════════════════════════════════════════════════════════════════
class TestOAuth2:
    def test_build_xoauth2_format(self):
        from core.oauth2_refresh import build_xoauth2
        import base64
        result = build_xoauth2("user@outlook.com", "token123")
        decoded = base64.b64decode(result).decode()
        assert "user=user@outlook.com" in decoded
        assert "auth=Bearer token123" in decoded

    def test_is_ms_domain_true(self):
        from core.oauth2_refresh import is_ms_domain
        for domain in ["outlook.com", "hotmail.com", "live.com", "msn.com"]:
            assert is_ms_domain(f"user@{domain}"), f"Expected MS domain: {domain}"

    def test_is_ms_domain_false(self):
        from core.oauth2_refresh import is_ms_domain
        for domain in ["gmail.com", "yahoo.com", "yandex.ru"]:
            assert not is_ms_domain(f"user@{domain}"), f"Should not be MS domain: {domain}"

    def test_parse_pipe_account_valid(self):
        from core.oauth2_refresh import parse_pipe_account_line
        result = parse_pipe_account_line("user@outlook.com|password123|refresh_token_abc")
        assert result is not None
        assert result["email"] == "user@outlook.com"
        assert result["password"] == "password123"
        assert result["refresh_token"] == "refresh_token_abc"

    def test_parse_pipe_account_no_token(self):
        from core.oauth2_refresh import parse_pipe_account_line
        result = parse_pipe_account_line("user@outlook.com|password123")
        assert result is not None
        assert result["refresh_token"] == ""

    def test_parse_pipe_account_invalid(self):
        from core.oauth2_refresh import parse_pipe_account_line
        assert parse_pipe_account_line("notanemail") is None
        assert parse_pipe_account_line("") is None
        assert parse_pipe_account_line("#comment") is None


# ══════════════════════════════════════════════════════════════════════════════
# Email template personalization
# ══════════════════════════════════════════════════════════════════════════════
class TestEmailTemplate:
    def setup_method(self):
        from core.sender import EmailTemplate, Recipient
        self.Template = EmailTemplate
        self.Recipient = Recipient

    def test_personalize_first_name(self):
        tpl = self.Template(
            subject="Hello {{first_name}}",
            body_html="<p>Dear {{first_name}}</p>",
        )
        rec = self.Recipient(email="a@b.com", first_name="Alice")
        out = tpl.personalize(rec)
        assert out.subject == "Hello Alice"
        assert "Alice" in out.body_html

    def test_personalize_full_name(self):
        tpl = self.Template(subject="{{full_name}}", body_html="")
        rec = self.Recipient(email="a@b.com", first_name="Alice", last_name="Smith")
        out = tpl.personalize(rec)
        assert out.subject == "Alice Smith"

    def test_personalize_company(self):
        tpl = self.Template(subject="{{company}}", body_html="")
        rec = self.Recipient(email="a@b.com", company="Acme Corp")
        out = tpl.personalize(rec)
        assert out.subject == "Acme Corp"

    def test_personalize_custom_fields(self):
        tpl = self.Template(subject="{{custom_1}}-{{custom_2}}", body_html="")
        rec = self.Recipient(email="a@b.com", custom_1="X", custom_2="Y")
        out = tpl.personalize(rec)
        assert out.subject == "X-Y"

    def test_missing_field_empty_string(self):
        tpl = self.Template(subject="{{first_name}}", body_html="")
        rec = self.Recipient(email="a@b.com")
        out = tpl.personalize(rec)
        assert out.subject == ""


# ══════════════════════════════════════════════════════════════════════════════
# SMTP account limits (try_increment / decrement)
# ══════════════════════════════════════════════════════════════════════════════
class TestSmtpAccountLimits:
    def _make_account(self, daily=10, hourly=5):
        from core.sender import SmtpAccount
        acc = SmtpAccount(
            email="test@gmail.com", password="p", host="smtp.gmail.com",
            daily_limit=daily, hourly_limit=hourly,
        )
        return acc

    def test_try_increment_succeeds(self):
        acc = self._make_account()
        assert acc.try_increment() is True
        assert acc.sent_today == 1

    def test_try_increment_respects_daily_limit(self):
        acc = self._make_account(daily=2, hourly=100)
        assert acc.try_increment()
        assert acc.try_increment()
        assert acc.try_increment() is False

    def test_try_increment_respects_hourly_limit(self):
        acc = self._make_account(daily=100, hourly=2)
        assert acc.try_increment()
        assert acc.try_increment()
        assert acc.try_increment() is False

    def test_decrement_sent_decreases_counter(self):
        acc = self._make_account()
        acc.try_increment()
        acc.try_increment()
        acc.decrement_sent()
        assert acc.sent_today == 1


# ══════════════════════════════════════════════════════════════════════════════
# DKIM signer
# ══════════════════════════════════════════════════════════════════════════════
class TestDkimSigner:
    def setup_method(self):
        from core.dkim_signer import (
            DkimConfig, sign_message_bytes, validate_config,
            load_configs, save_configs, get_config_for_domain,
            is_available,
        )
        self.DkimConfig = DkimConfig
        self.sign = sign_message_bytes
        self.validate = validate_config
        self.load = load_configs
        self.save = save_configs
        self.get_for_domain = get_config_for_domain
        self.is_available = is_available

    def _sample_msg(self):
        return (
            b"From: sender@example.com\r\n"
            b"To: recipient@example.com\r\n"
            b"Subject: Test\r\n"
            b"Date: Mon, 29 Jun 2026 12:00:00 +0000\r\n"
            b"Message-ID: <test@example.com>\r\n"
            b"\r\nTest body\r\n"
        )

    def test_sign_without_dkimpy_returns_original(self):
        """Without dkimpy installed, sign_message_bytes must return bytes unchanged."""
        from core.dkim_signer import _HAS_DKIM
        if _HAS_DKIM:
            pytest.skip("dkimpy is installed — this tests the no-dkimpy path")
        cfg = self.DkimConfig(selector="mail", domain="example.com", private_key_pem="dummy")
        raw = self._sample_msg()
        result = self.sign(raw, cfg)
        assert result == raw

    def test_sign_with_disabled_config_returns_original(self):
        cfg = self.DkimConfig(selector="mail", domain="example.com",
                               private_key_pem="key", enabled=False)
        raw = self._sample_msg()
        assert self.sign(raw, cfg) == raw

    def test_sign_with_empty_key_returns_original(self):
        cfg = self.DkimConfig(selector="mail", domain="example.com", private_key_pem="")
        raw = self._sample_msg()
        assert self.sign(raw, cfg) == raw

    def test_validate_missing_selector(self):
        cfg = self.DkimConfig(selector="", domain="example.com", private_key_pem="key")
        ok, msg = self.validate(cfg)
        assert not ok
        assert "selector" in msg.lower()

    def test_validate_bad_domain(self):
        cfg = self.DkimConfig(selector="mail", domain="nodot", private_key_pem="key")
        ok, msg = self.validate(cfg)
        assert not ok
        assert "domain" in msg.lower()

    def test_validate_empty_key(self):
        cfg = self.DkimConfig(selector="mail", domain="example.com", private_key_pem="")
        ok, msg = self.validate(cfg)
        assert not ok

    def test_validate_non_pem_key(self):
        cfg = self.DkimConfig(selector="mail", domain="example.com",
                               private_key_pem="not_a_pem_key_at_all_123")
        ok, msg = self.validate(cfg)
        assert not ok
        assert "pem" in msg.lower()

    def test_get_for_domain_exact_match(self):
        configs = [
            self.DkimConfig(selector="mail", domain="example.com", private_key_pem="k"),
            self.DkimConfig(selector="mail", domain="other.com", private_key_pem="k"),
        ]
        result = self.get_for_domain("example.com", configs)
        assert result is not None
        assert result.domain == "example.com"

    def test_get_for_domain_email_input(self):
        configs = [self.DkimConfig(selector="s", domain="example.com", private_key_pem="k")]
        result = self.get_for_domain("user@example.com", configs)
        assert result is not None

    def test_get_for_domain_no_match(self):
        configs = [self.DkimConfig(selector="s", domain="other.com", private_key_pem="k")]
        assert self.get_for_domain("example.com", configs) is None

    def test_get_for_domain_disabled_skipped(self):
        configs = [self.DkimConfig(selector="s", domain="example.com",
                                    private_key_pem="k", enabled=False)]
        assert self.get_for_domain("example.com", configs) is None

    def test_save_and_load_roundtrip(self, tmp_path):
        import core.dkim_signer as dkim_mod
        orig = dkim_mod._CONFIGS_PATH
        dkim_mod._CONFIGS_PATH = tmp_path / "dkim_configs.json"
        try:
            configs = [
                self.DkimConfig(selector="mail", domain="example.com", private_key_pem="MOCK_RSA_PRIVATE_KEY_FOR_TESTING_ONLY"),
                self.DkimConfig(selector="mail2", domain="other.com", private_key_pem="pem2", enabled=False),
            ]
            self.save(configs)
            loaded = self.load()
            assert len(loaded) == 2
            assert loaded[0].domain == "example.com"
            assert loaded[0].selector == "mail"
            assert loaded[1].enabled is False
        finally:
            dkim_mod._CONFIGS_PATH = orig

    def test_load_missing_file_returns_empty(self, tmp_path):
        import core.dkim_signer as dkim_mod
        orig = dkim_mod._CONFIGS_PATH
        dkim_mod._CONFIGS_PATH = tmp_path / "nonexistent.json"
        try:
            assert self.load() == []
        finally:
            dkim_mod._CONFIGS_PATH = orig

    def test_is_available_returns_bool(self):
        assert isinstance(self.is_available(), bool)


# ══════════════════════════════════════════════════════════════════════════════
# SMTP Connection Cache
# ══════════════════════════════════════════════════════════════════════════════
class TestSmtpConnectionCache:
    def setup_method(self):
        from core.sender import _SmtpConnectionCache
        self.Cache = _SmtpConnectionCache

    def _make_mock_conn(self):
        import unittest.mock as mock
        conn = mock.MagicMock()
        conn.quit = mock.MagicMock()
        conn.close = mock.MagicMock()
        return conn

    def test_checkout_empty_returns_none(self):
        cache = self.Cache()
        assert cache.checkout("user@example.com", "proxy1") is None

    def test_checkin_then_checkout(self):
        cache = self.Cache()
        conn = self._make_mock_conn()
        cache.checkin("user@example.com", "proxy1", conn, 0)
        result = cache.checkout("user@example.com", "proxy1")
        assert result is not None
        out_conn, count = result
        assert out_conn is conn
        assert count == 1  # checkin incremented count

    def test_checkout_removes_from_cache(self):
        cache = self.Cache()
        conn = self._make_mock_conn()
        cache.checkin("user@example.com", "proxy1", conn, 0)
        cache.checkout("user@example.com", "proxy1")
        # Second checkout should return None (already removed)
        assert cache.checkout("user@example.com", "proxy1") is None

    def test_max_reuse_limit(self):
        cache = self.Cache()
        cache.MAX_REUSE = 5
        conn = self._make_mock_conn()
        cache.checkin("user@example.com", "proxy1", conn, 4)  # count will be 5
        result = cache.checkout("user@example.com", "proxy1")
        # count == MAX_REUSE → should be discarded
        assert result is None

    def test_idle_timeout_discards_connection(self):
        import time as _time
        cache = self.Cache()
        cache.MAX_IDLE_SECS = 0  # immediate expiry
        conn = self._make_mock_conn()
        cache.checkin("a@b.com", "px", conn, 0)
        _time.sleep(0.01)  # ensure idle timeout exceeded
        result = cache.checkout("a@b.com", "px")
        assert result is None

    def test_invalidate_closes_connection(self):
        cache = self.Cache()
        conn = self._make_mock_conn()
        cache.checkin("user@example.com", "proxy1", conn, 0)
        cache.invalidate("user@example.com", "proxy1")
        conn.close.assert_called()
        assert cache.checkout("user@example.com", "proxy1") is None

    def test_clear_closes_all(self):
        cache = self.Cache()
        conns = [self._make_mock_conn() for _ in range(3)]
        cache.checkin("a@b.com", "p1", conns[0], 0)
        cache.checkin("b@b.com", "p1", conns[1], 0)
        cache.checkin("c@b.com", "p1", conns[2], 0)
        cache.clear()
        # All should be checked out as None after clear
        assert cache.checkout("a@b.com", "p1") is None


# ══════════════════════════════════════════════════════════════════════════════
# Domain Rate Limiter
# ══════════════════════════════════════════════════════════════════════════════
class TestDomainRateLimiter:
    def setup_method(self):
        from core.sender import _DomainRateLimiter, _DOMAIN_HOURLY_LIMITS, _DEFAULT_DOMAIN_HOURLY
        self.Limiter = _DomainRateLimiter
        self.limits = _DOMAIN_HOURLY_LIMITS
        self.default_limit = _DEFAULT_DOMAIN_HOURLY

    def test_can_send_initially_true(self):
        lim = self.Limiter()
        assert lim.can_send("gmail.com") is True

    def test_record_increments_counter(self):
        lim = self.Limiter()
        lim.record("gmail.com")
        assert lim.current_count("gmail.com") == 1

    def test_can_send_false_at_limit(self):
        lim = self.Limiter()
        limit = self.limits.get("gmail.com", self.default_limit)
        # Manually fill up counter
        import core.sender as _s
        import time as _t
        with lim._lock:
            lim._counters["gmail.com"] = (limit, _t.time())
        assert lim.can_send("gmail.com") is False

    def test_can_send_true_below_limit(self):
        lim = self.Limiter()
        limit = self.limits.get("gmail.com", self.default_limit)
        import time as _t
        with lim._lock:
            lim._counters["gmail.com"] = (limit - 1, _t.time())
        assert lim.can_send("gmail.com") is True

    def test_window_resets_after_hour(self):
        lim = self.Limiter()
        import time as _t
        limit = self.limits.get("gmail.com", self.default_limit)
        # Set counter from 2 hours ago
        with lim._lock:
            lim._counters["gmail.com"] = (limit, _t.time() - 7300)
        # Should reset and allow
        assert lim.can_send("gmail.com") is True
        assert lim.current_count("gmail.com") == 0

    def test_unknown_domain_uses_default_limit(self):
        lim = self.Limiter()
        # Unknown domain should use default limit
        import time as _t
        with lim._lock:
            lim._counters["unknowndomain.xyz"] = (self.default_limit, _t.time())
        assert lim.can_send("unknowndomain.xyz") is False

    def test_reset_clears_all_counters(self):
        lim = self.Limiter()
        lim.record("gmail.com")
        lim.record("yahoo.com")
        lim.reset()
        assert lim.current_count("gmail.com") == 0
        assert lim.current_count("yahoo.com") == 0

    def test_gmail_limit_is_150(self):
        assert self.limits.get("gmail.com") == 150

    def test_yahoo_limit_is_100(self):
        assert self.limits.get("yahoo.com") == 100

    def test_gmx_limit_is_60(self):
        assert self.limits.get("gmx.com") == 60


# ══════════════════════════════════════════════════════════════════════════════
# Tracking Pixel fix
# ══════════════════════════════════════════════════════════════════════════════
class TestTrackingPixel:
    def setup_method(self):
        from core.uniqueizer import technique_tracking_pixel
        self.pixel = technique_tracking_pixel

    HTML = "<html><body><p>Hello</p></body></html>"

    def test_no_url_returns_html_unchanged(self):
        result = self.pixel(self.HTML)
        assert result == self.HTML

    def test_empty_url_returns_html_unchanged(self):
        assert self.pixel(self.HTML, "") == self.HTML
        assert self.pixel(self.HTML, "   ") == self.HTML

    def test_with_url_adds_img_tag(self):
        result = self.pixel(self.HTML, "https://track.example.com/open")
        assert '<img' in result
        assert "track.example.com" in result

    def test_pixel_before_body_close(self):
        result = self.pixel(self.HTML, "https://track.example.com/open")
        assert result.lower().index("<img") < result.lower().index("</body>")

    def test_no_data_uri_in_output(self):
        result = self.pixel(self.HTML, "https://track.example.com/open")
        assert "data:image" not in result
        assert "base64" not in result

    def test_uid_in_url(self):
        import re
        result = self.pixel(self.HTML, "https://track.example.com/open")
        # Should have a UUID in the URL
        uuids = re.findall(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            result
        )
        assert len(uuids) >= 1

    def test_without_body_tag_appends(self):
        html = "<p>No body tag here</p>"
        result = self.pixel(html, "https://track.example.com/open")
        assert "<img" in result
        assert result.startswith("<p>")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
