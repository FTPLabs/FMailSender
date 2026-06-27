"""
FMailSender — SMTP Validator v6.0
Validates SMTP accounts and proxies. Used by core/server.py.
"""
from __future__ import annotations
import asyncio
from core.models import SmtpAccount
from core.sender import test_smtp_connection
from core.proxy import check_proxy, check_smtp_via_proxy


async def validate_account(acc: SmtpAccount) -> tuple[bool, str]:
    """Test SMTP connection for an account. Returns (ok, message)."""
    return await test_smtp_connection(acc)


async def validate_accounts_batch(
    accounts: list[SmtpAccount],
    max_concurrent: int = 4,
    on_result=None,
) -> list[tuple[bool, str]]:
    """Validate multiple accounts with concurrency limit.
    
    on_result(index, ok, msg) called for each result.
    Returns list of (ok, msg) in same order as input.
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results = [None] * len(accounts)

    async def _test_one(i: int, acc: SmtpAccount):
        async with semaphore:
            ok, msg = await test_smtp_connection(acc)
            results[i] = (ok, msg)
            if on_result:
                on_result(i, ok, msg)

    await asyncio.gather(*[_test_one(i, acc) for i, acc in enumerate(accounts)])
    return results


def validate_proxy(proxy_url: str) -> dict:
    """Check proxy connectivity and SMTP support. Returns status dict."""
    ok, error, ping = check_proxy(proxy_url)
    smtp_ok = False
    if ok:
        smtp_ok = check_smtp_via_proxy(proxy_url)
    return {
        "proxy": proxy_url,
        "ok": ok,
        "smtp_ok": smtp_ok,
        "ping_ms": ping,
        "error": error,
    }
