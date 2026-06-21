"""Единый реестр платёжных провайдеров.

Оборачивает per-provider клиентов (CryptoBot / xRocket / LZT) единым интерфейсом,
чтобы бот создавал и проверял инвойсы без provider-специфичных ветвлений.

Дизайн (по ревью архитектора):
- invoice_id хранится в БД с префиксом провайдера ("crypto:123", "xrocket:45",
  "lzt:7") во избежание коллизий числовых ID между провайдерами. Перед вызовом
  внешнего API префикс снимается. Легаси-строки без префикса считаются crypto.
- «Меню для новых оплат» (enabled_for_new_payments) и «доступность проверки уже
  созданных платежей» (available_for_check) разделены: скрытие провайдера из меню
  НЕ ломает верификацию ранее созданных инвойсов.
- Секреты читаются только из config (env).
"""
import logging
from typing import Optional

import config
from crypto_pay import crypto_client
from xrocket_pay import xrocket_client
from lzt_pay import lzt_client

logger = logging.getLogger("payment_providers")

CRYPTO = "crypto"
XROCKET = "xrocket"
LZT = "lzt"


def raw_invoice_id(stored_id: str, provider_key: str) -> str:
    """Снимает префикс провайдера. Легаси-ID без префикса возвращаются как есть."""
    if not stored_id:
        return stored_id
    pfx = f"{provider_key}:"
    return stored_id[len(pfx):] if stored_id.startswith(pfx) else stored_id


class _Provider:
    def __init__(self, key: str, label: str, client, currency: str, kind: str):
        self.key = key
        self.label = label
        self.client = client
        self.currency = currency
        self.kind = kind

    async def create_invoice(self, amount: float, description: str = "", payload: str = "") -> dict:
        """Создаёт инвойс и возвращает {invoice_id (с префиксом), pay_url}."""
        if self.kind == CRYPTO:
            inv = await self.client.create_invoice(
                amount=amount, asset=self.currency, description=description, payload=payload
            )
            raw_id = str(inv.get("invoice_id", ""))
            pay_url = inv.get("pay_url", "")
        else:
            inv = await self.client.create_invoice(
                amount=amount, currency=self.currency, description=description, payload=payload
            )
            raw_id = str(inv.get("invoice_id", ""))
            pay_url = inv.get("pay_url", "")
        if not raw_id:
            raise RuntimeError(f"{self.label}: пустой invoice_id в ответе API")
        return {"invoice_id": f"{self.key}:{raw_id}", "pay_url": pay_url}

    async def check(self, stored_invoice_id: str,
                    expected_amount: Optional[float] = None,
                    expected_currency: Optional[str] = None) -> bool:
        raw = raw_invoice_id(stored_invoice_id, self.key)
        cur = expected_currency if expected_currency is not None else self.currency
        if self.kind == CRYPTO:
            return await self.client.check_invoice(
                raw, expected_amount=expected_amount, expected_asset=cur
            )
        return await self.client.check_invoice(
            raw, expected_amount=expected_amount, expected_currency=cur
        )

    async def close(self):
        try:
            await self.client.close()
        except Exception:
            pass


# Полный реестр (создаётся один раз при импорте).
_ALL = {
    CRYPTO: _Provider(CRYPTO, "CryptoBot", crypto_client, "USDT", CRYPTO),
    XROCKET: _Provider(XROCKET, "xRocket", xrocket_client, config.XROCKET_CURRENCY, XROCKET),
    LZT: _Provider(LZT, "LZT Market", lzt_client, config.LZT_CURRENCY.upper(), LZT),
}


def get_provider(key: Optional[str]) -> Optional[_Provider]:
    return _ALL.get(key or CRYPTO)


def enabled_for_new_payments() -> list:
    """Провайдеры, показываемые в меню покупки (CryptoBot обязателен)."""
    out = [_ALL[CRYPTO]]
    if config.XROCKET_ENABLED:
        out.append(_ALL[XROCKET])
    if config.LZT_ENABLED:
        out.append(_ALL[LZT])
    return out


def available_for_check(provider_key: Optional[str]) -> bool:
    """Можно ли проверить уже созданный платёж этого провайдера."""
    key = provider_key or CRYPTO
    if key == CRYPTO:
        return True
    if key == XROCKET:
        return bool(config.XROCKET_API_TOKEN)
    if key == LZT:
        return bool(config.LZT_TOKEN and config.LZT_MERCHANT_ID)
    return False


async def close_all():
    for p in _ALL.values():
        await p.close()
