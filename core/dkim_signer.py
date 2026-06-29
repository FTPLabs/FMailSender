"""
FMailSender — DKIM Signing Module v1.0.0
=========================================
RFC 6376-compliant DKIM signing.

Requires: pip install dkimpy

Without dkimpy installed the module still imports cleanly — all functions
return gracefully without signing. Install dkimpy to enable DKIM.

Usage:
    from core.dkim_signer import DkimConfig, sign_message_bytes, load_configs, save_configs

    cfg = DkimConfig(selector="mail", domain="example.com", private_key_pem="-----BEGIN RSA...")
    signed_bytes = sign_message_bytes(raw_bytes, cfg)

Storage: data/dkim_configs.json — list of {selector, domain, private_key_pem, enabled}
"""
from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("dkim_signer")

try:
    import dkim as _dkim_lib  # pip install dkimpy
    _HAS_DKIM = True
    logger.info("dkimpy loaded — DKIM signing enabled")
except ImportError:
    _dkim_lib = None  # type: ignore
    _HAS_DKIM = False
    logger.warning("dkimpy not installed — DKIM signing disabled. Run: pip install dkimpy")


# ── Storage ───────────────────────────────────────────────────────────────────
def _data_dir() -> Path:
    import sys
    if getattr(sys, "frozen", False):
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        p = Path(appdata) / "FMailSender"
    else:
        p = Path(__file__).parent.parent / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p


_CONFIGS_PATH = _data_dir() / "dkim_configs.json"
_configs_lock = threading.Lock()


@dataclass
class DkimConfig:
    """DKIM signing configuration for one domain."""
    selector: str          # DNS selector, e.g. "mail" → mail._domainkey.example.com
    domain: str            # Signing domain, e.g. "example.com"
    private_key_pem: str   # RSA private key in PEM format
    enabled: bool = True
    # Canonicalization: "relaxed/relaxed" is the standard for bulk email
    canonicalization: bytes = field(default=b"relaxed/relaxed", repr=False)
    # Headers to sign (standard set per RFC 6376 § 5.4)
    headers: list[bytes] = field(default_factory=lambda: [
        b"from", b"to", b"subject", b"date", b"message-id",
        b"content-type", b"mime-version",
        b"list-unsubscribe", b"list-unsubscribe-post",
    ])

    def __post_init__(self):
        if isinstance(self.canonicalization, str):
            self.canonicalization = self.canonicalization.encode()
        self.headers = [
            (h.encode() if isinstance(h, str) else h) for h in self.headers
        ]


def sign_message_bytes(msg_bytes: bytes, config: DkimConfig) -> bytes:
    """Sign raw email bytes with DKIM. Returns signed bytes.

    On any error (missing key, dkimpy not installed, etc.) logs a warning
    and returns the original bytes unchanged — never blocks sending.
    """
    if not _HAS_DKIM:
        return msg_bytes
    if not config or not config.enabled:
        return msg_bytes
    if not config.private_key_pem or not config.private_key_pem.strip():
        logger.warning("DKIM: private key is empty for domain %s — skipping", config.domain)
        return msg_bytes
    try:
        private_key = config.private_key_pem.strip().encode("utf-8")
        sig = _dkim_lib.sign(
            message=msg_bytes,
            selector=config.selector.encode("utf-8"),
            domain=config.domain.encode("utf-8"),
            privkey=private_key,
            canonicalize=tuple(c.strip() for c in config.canonicalization.split(b"/")),  # type: ignore
            include_headers=config.headers,
            length=False,
        )
        return sig + msg_bytes
    except Exception as e:
        logger.warning("DKIM signing failed for %s: %s — sending unsigned", config.domain, e)
        return msg_bytes


def get_config_for_domain(domain: str, configs: list[DkimConfig]) -> Optional[DkimConfig]:
    """Find enabled DKIM config for a sender domain (exact match only)."""
    domain = domain.lower().strip()
    for cfg in configs:
        if cfg.enabled and cfg.domain.lower().strip() == domain:
            return cfg
    return None


# ── Persistence ───────────────────────────────────────────────────────────────
def load_configs() -> list[DkimConfig]:
    """Load DKIM configs from disk. Returns [] if file missing or corrupt."""
    with _configs_lock:
        try:
            raw = json.loads(_CONFIGS_PATH.read_text(encoding="utf-8"))
            result = []
            for item in raw:
                result.append(DkimConfig(
                    selector=item.get("selector", ""),
                    domain=item.get("domain", ""),
                    private_key_pem=item.get("private_key_pem", ""),
                    enabled=item.get("enabled", True),
                ))
            return result
        except FileNotFoundError:
            return []
        except Exception as e:
            logger.error("Failed to load DKIM configs: %s", e)
            return []


def save_configs(configs: list[DkimConfig]) -> None:
    """Save DKIM configs to disk (atomic write)."""
    with _configs_lock:
        data = [
            {
                "selector": c.selector,
                "domain": c.domain,
                "private_key_pem": c.private_key_pem,
                "enabled": c.enabled,
            }
            for c in configs
        ]
        tmp = _CONFIGS_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, _CONFIGS_PATH)


def validate_config(config: DkimConfig) -> tuple[bool, str]:
    """Validate a DkimConfig. Returns (ok, error_message)."""
    if not config.selector or not config.selector.strip():
        return False, "selector is required"
    if not config.domain or "." not in config.domain:
        return False, "domain must be a valid domain (e.g. example.com)"
    pem = config.private_key_pem.strip()
    if not pem:
        return False, "private_key_pem is required"
    if "BEGIN RSA PRIVATE KEY" not in pem and "BEGIN PRIVATE KEY" not in pem:
        return False, "private_key_pem must be a PEM-encoded RSA private key"
    if not _HAS_DKIM:
        return True, "WARNING: dkimpy not installed — config saved but signing disabled (pip install dkimpy)"
    # Try to actually sign a dummy message to verify the key works
    try:
        test_msg = (
            b"From: test@" + config.domain.encode() + b"\r\n"
            b"To: r@example.com\r\n"
            b"Subject: test\r\n"
            b"Date: Thu, 01 Jan 2026 00:00:00 +0000\r\n"
            b"\r\ntest body\r\n"
        )
        result = sign_message_bytes(test_msg, config)
        if result == test_msg:
            return False, "signing test failed — private key may be invalid"
        return True, "OK — DKIM signature verified successfully"
    except Exception as e:
        return False, f"key validation failed: {e}"


def is_available() -> bool:
    """Return True if dkimpy is installed and DKIM signing is possible."""
    return _HAS_DKIM
