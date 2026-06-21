"""T016 — офлайн-тесты платёжных провайдеров (без сети).

Проверяют:
- raw_invoice_id: снятие префикса провайдера и совместимость с легаси-ID;
- _invoice_matches каждого клиента (xRocket / LZT / CryptoBot): защита от
  недоплаты, неоплаченного статуса, неверной валюты;
- обёртку _Provider: префиксация invoice_id при создании и корректную
  маршрутизацию check() в нужный клиент с правильными именами аргументов.

Запуск: python3 tests/test_payment_providers.py
"""
from __future__ import annotations

import asyncio
import os
import sys

# Заглушки обязательных env-переменных config.py (только для офлайн-тестов)
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


# ── raw_invoice_id ──────────────────────────────────────────────────────────

def _raw_id_suite() -> None:
    import payment_providers as pay

    check(pay.raw_invoice_id("12345", "crypto") == "12345",
          "legacy crypto id без префикса возвращается как есть")
    check(pay.raw_invoice_id("crypto:12345", "crypto") == "12345",
          "crypto:NNN → NNN")
    check(pay.raw_invoice_id("xrocket:678", "xrocket") == "678",
          "xrocket:NNN → NNN")
    check(pay.raw_invoice_id("lzt:9", "lzt") == "9",
          "lzt:NNN → NNN")
    # чужой префикс не снимается (роутинг идёт по колонке provider)
    check(pay.raw_invoice_id("xrocket:678", "crypto") == "xrocket:678",
          "несовпадающий префикс не снимается")
    check(pay.raw_invoice_id("", "crypto") == "",
          "пустой id возвращается как есть")


# ── _invoice_matches: xRocket ───────────────────────────────────────────────

def _xrocket_matcher_suite() -> None:
    from xrocket_pay import XRocketPayClient as X

    paid = {"status": "paid", "amount": 10.0, "currency": "USDT"}
    check(X._invoice_matches(paid, 10.0, "USDT") is True,
          "xrocket: оплачен, сумма и валюта верны → True")
    check(X._invoice_matches({"status": "paid", "amount": 12.0, "currency": "USDT"}, 10.0, "USDT") is True,
          "xrocket: переплата допускается → True")
    check(X._invoice_matches({"status": "active", "amount": 10.0, "currency": "USDT"}, 10.0, "USDT") is False,
          "xrocket: статус active (не оплачен) → False")
    check(X._invoice_matches({"status": "expired", "amount": 10.0, "currency": "USDT"}, 10.0, "USDT") is False,
          "xrocket: статус expired → False")
    check(X._invoice_matches({"status": "paid", "amount": 9.99, "currency": "USDT"}, 10.0, "USDT") is False,
          "xrocket: недоплата → False")
    check(X._invoice_matches({"status": "paid", "amount": 10.0, "currency": "TON"}, 10.0, "USDT") is False,
          "xrocket: неверная валюта → False")
    check(X._invoice_matches(None, 10.0, "USDT") is False,
          "xrocket: None → False")


# ── _invoice_matches: LZT ───────────────────────────────────────────────────

def _lzt_matcher_suite() -> None:
    from lzt_pay import LZTPayClient as L

    check(L._invoice_matches({"status": "paid", "amount": 5}, 5.0, "usd") is True,
          "lzt: оплачен, сумма верна → True")
    check(L._invoice_matches({"status": "paid", "amount": 7}, 5.0, "usd") is True,
          "lzt: переплата допускается → True")
    check(L._invoice_matches({"status": "not_paid", "amount": 5}, 5.0, "usd") is False,
          "lzt: not_paid → False")
    check(L._invoice_matches({"status": "paid", "amount": 4}, 5.0, "usd") is False,
          "lzt: недоплата → False")
    check(L._invoice_matches(None, 5.0, "usd") is False,
          "lzt: None → False")


# ── _invoice_matches: CryptoBot (регресс-проверка) ──────────────────────────

def _crypto_matcher_suite() -> None:
    from crypto_pay import CryptoPayClient as C

    check(C._invoice_matches({"status": "paid", "amount": "10", "asset": "USDT"}, 10.0, "USDT") is True,
          "crypto: оплачен, сумма и актив верны → True")
    check(C._invoice_matches({"status": "active", "amount": "10", "asset": "USDT"}, 10.0, "USDT") is False,
          "crypto: не оплачен → False")
    check(C._invoice_matches({"status": "paid", "amount": "9", "asset": "USDT"}, 10.0, "USDT") is False,
          "crypto: недоплата → False")
    check(C._invoice_matches({"status": "paid", "amount": "10", "asset": "TON"}, 10.0, "USDT") is False,
          "crypto: неверный актив → False")


# ── Обёртка _Provider: префиксация + маршрутизация ──────────────────────────

class _StubClient:
    """Минимальный стаб клиента провайдера."""
    def __init__(self):
        self.last_check = None

    async def create_invoice(self, **kwargs):
        return {"invoice_id": "99", "pay_url": "https://pay.example/99"}

    async def check_invoice(self, invoice_id, **kwargs):
        self.last_check = (invoice_id, kwargs)
        return True

    async def close(self):
        pass


async def _provider_wrapper_suite() -> None:
    import payment_providers as pay

    # crypto-обёртка должна возвращать invoice_id с префиксом и звать asset-аргумент
    stub_c = _StubClient()
    prov_c = pay._Provider("crypto", "CryptoBot", stub_c, "USDT", pay.CRYPTO)
    inv = await prov_c.create_invoice(amount=10, description="x")
    check(inv["invoice_id"] == "crypto:99", "crypto-обёртка префиксует invoice_id (crypto:99)")
    check(inv["pay_url"] == "https://pay.example/99", "crypto-обёртка пробрасывает pay_url")
    await prov_c.check("crypto:99", expected_amount=10, expected_currency="USDT")
    check(stub_c.last_check[0] == "99", "crypto check: префикс снят перед вызовом клиента")
    check("expected_asset" in stub_c.last_check[1], "crypto check: используется expected_asset")

    # xrocket-обёртка: префикс xrocket: и expected_currency-аргумент
    stub_x = _StubClient()
    prov_x = pay._Provider("xrocket", "xRocket", stub_x, "USDT", pay.XROCKET)
    inv = await prov_x.create_invoice(amount=10)
    check(inv["invoice_id"] == "xrocket:99", "xrocket-обёртка префиксует invoice_id (xrocket:99)")
    await prov_x.check("xrocket:99", expected_amount=10, expected_currency="USDT")
    check(stub_x.last_check[0] == "99", "xrocket check: префикс снят перед вызовом клиента")
    check("expected_currency" in stub_x.last_check[1], "xrocket check: используется expected_currency")

    # check легаси-ID без префикса (старые crypto-платежи)
    stub_c2 = _StubClient()
    prov_c2 = pay._Provider("crypto", "CryptoBot", stub_c2, "USDT", pay.CRYPTO)
    await prov_c2.check("12345", expected_amount=10, expected_currency="USDT")
    check(stub_c2.last_check[0] == "12345", "crypto check: легаси-ID без префикса работает")


# ── enabled / available разделение ──────────────────────────────────────────

def _enabled_vs_available_suite() -> None:
    import importlib
    import config
    import payment_providers as pay

    # По умолчанию (без токенов): меню = только crypto; проверка crypto доступна
    check([p.key for p in pay.enabled_for_new_payments()] == ["crypto"],
          "без токенов меню оплаты = только CryptoBot (UX без изменений)")
    check(pay.available_for_check("crypto") is True, "crypto всегда доступен для проверки")
    check(pay.available_for_check("xrocket") is False, "xrocket недоступен без токена")
    check(pay.available_for_check("lzt") is False, "lzt недоступен без токена/merchant_id")
    check(pay.available_for_check(None) is True, "None трактуется как crypto (легаси)")


def main() -> int:
    _raw_id_suite()
    _xrocket_matcher_suite()
    _lzt_matcher_suite()
    _crypto_matcher_suite()
    asyncio.run(_provider_wrapper_suite())
    _enabled_vs_available_suite()
    print()
    if _failures:
        print(f"FAILED: {len(_failures)} — " + "; ".join(_failures))
        return 1
    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
