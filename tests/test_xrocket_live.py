"""T016 — live-тест интеграции xRocket Pay (gated).

Пропускается, если XROCKET_API_TOKEN не задан в env. При наличии токена:
- создаёт реальный инвойс на 0.1 USDT;
- проверяет, что вернулись status=active и платёжная ссылка (link);
- убеждается, что неоплаченный инвойс check_invoice() == False;
- ГАРАНТИРОВАННО удаляет инвойс в finally (DELETE /tg-invoices/{id}).

Секрет читается ТОЛЬКО из env и никогда не логируется.

Запуск:  XROCKET_API_TOKEN=*** python3 tests/test_xrocket_live.py
"""
from __future__ import annotations

import asyncio
import os
import sys

os.environ.setdefault("BOT_TOKEN", "test:dummy")
os.environ.setdefault("CRYPTO_BOT_TOKEN", "test-dummy")
os.environ.setdefault("JWT_SECRET", "test-dummy-secret")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "server"))

_failures: list[str] = []


def check(cond: bool, label: str) -> None:
    if cond:
        print(f"[PASS] {label}")
    else:
        print(f"[FAIL] {label}")
        _failures.append(label)


async def _live_suite() -> None:
    from xrocket_pay import XRocketPayClient

    client = XRocketPayClient()
    invoice_id = ""
    try:
        created = await client.create_invoice(
            amount=0.1,
            currency="USDT",
            description="FMail live-test (auto-delete)",
            payload="selftest",
            expires_in=600,
        )
        invoice_id = created.get("invoice_id", "")
        check(bool(invoice_id), "live: инвойс создан, есть id")
        check(bool(created.get("pay_url")), "live: вернулась платёжная ссылка (link)")

        fetched = await client.get_invoice(invoice_id)
        check(fetched is not None and fetched.get("status") == "active",
              "live: статус нового инвойса = active")

        paid = await client.check_invoice(invoice_id, expected_amount=0.1, expected_currency="USDT")
        check(paid is False, "live: неоплаченный инвойс check_invoice() == False")
    finally:
        if invoice_id:
            deleted = await client.delete_invoice(invoice_id)
            check(deleted is True, "live: тестовый инвойс удалён (cleanup)")
        await client.close()


def main() -> int:
    if not os.environ.get("XROCKET_API_TOKEN", "").strip():
        print("[SKIP] XROCKET_API_TOKEN не задан — live-тест xRocket пропущен.")
        return 0
    asyncio.run(_live_suite())
    print()
    if _failures:
        print(f"FAILED: {len(_failures)} — " + "; ".join(_failures))
        return 1
    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
