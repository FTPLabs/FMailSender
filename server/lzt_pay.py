"""LZT Market (prod-api.lzt.market) payment client.

ОПЦИОНАЛЬНЫЙ провайдер. Включается только при config.LZT_ENABLED (нужен валидный
OAuth-токен со scope `invoice` + merchant_id + валюта). Секреты — только из env.

API: база https://prod-api.lzt.market, заголовок Authorization: Bearer <token>.
  POST /invoice                  — создать инвойс
      required: currency, amount, payment_id (уникальный), comment, url_success, merchant_id
      -> {invoice: {invoice_id, url, status, amount, ...}, system_info}
  GET  /invoice?invoice_id={id}  — статус (status: paid|not_paid)

Примечание: InvoiceModel в ответе НЕ содержит поле currency, поэтому валюта
фиксируется на стороне мерчанта при создании и не валидируется при проверке.
"""
import logging
import uuid
from typing import Optional

import aiohttp

from config import (
    LZT_API,
    LZT_TOKEN,
    LZT_MERCHANT_ID,
    LZT_CURRENCY,
    PAYMENT_SUCCESS_URL,
)

logger = logging.getLogger("lzt_pay")


class LZTPayClient:
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {LZT_TOKEN}",
                    "Accept": "application/json",
                }
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(self, method: str, path: str, *, params: Optional[dict] = None,
                       json_body: Optional[dict] = None) -> dict:
        session = await self._get_session()
        url = f"{LZT_API}{path}"
        timeout = aiohttp.ClientTimeout(total=15)
        try:
            if method == "POST":
                ctx = session.post(url, json=json_body or {}, params=params, timeout=timeout)
            else:
                ctx = session.get(url, params=params, timeout=timeout)
            async with ctx as resp:
                data = await resp.json(content_type=None)
                if isinstance(data, dict) and data.get("errors"):
                    raise RuntimeError(f"LZT API error: {data.get('errors')}")
                return data if isinstance(data, dict) else {}
        except aiohttp.ClientError as e:
            if self._session and not self._session.closed:
                try:
                    await self._session.close()
                except Exception:
                    pass
            self._session = None
            raise RuntimeError(f"Network error: {e}") from e

    async def create_invoice(
        self,
        amount: float,
        currency: Optional[str] = None,
        description: str = "",
        payload: str = "",
    ) -> dict:
        """Создаёт инвойс. Возвращает {invoice_id, pay_url, raw}."""
        merchant = LZT_MERCHANT_ID
        merchant_val = int(merchant) if str(merchant).isdigit() else merchant
        body = {
            "currency": (currency or LZT_CURRENCY).lower(),
            "amount": round(float(amount), 2),
            "payment_id": payload or uuid.uuid4().hex,
            "comment": (description or "FMail Sender")[:255],
            "url_success": PAYMENT_SUCCESS_URL,
            "merchant_id": merchant_val,
        }
        data = await self._request("POST", "/invoice", json_body=body)
        inv = data.get("invoice", {}) if isinstance(data, dict) else {}
        return {
            "invoice_id": str(inv.get("invoice_id", "")),
            "pay_url": inv.get("url", ""),
            "raw": inv,
        }

    async def get_invoice(self, invoice_id: str) -> Optional[dict]:
        data = await self._request("GET", "/invoice", params={"invoice_id": invoice_id})
        inv = data.get("invoice") if isinstance(data, dict) else None
        return inv or None

    @staticmethod
    def _invoice_matches(invoice: Optional[dict],
                         expected_amount: Optional[float],
                         expected_currency: Optional[str]) -> bool:
        """Проверяет, что инвойс оплачен и сумма не меньше ожидаемой."""
        if not (invoice and str(invoice.get("status")) == "paid"):
            return False
        if expected_amount is not None:
            try:
                if float(invoice.get("amount", 0)) + 1e-6 < float(expected_amount):
                    logger.warning("lzt invoice amount mismatch: got %s expected %s",
                                   invoice.get("amount"), expected_amount)
                    return False
            except (TypeError, ValueError):
                return False
        return True

    async def check_invoice(
        self,
        invoice_id: str,
        expected_amount: Optional[float] = None,
        expected_currency: Optional[str] = None,
    ) -> bool:
        try:
            invoice = await self.get_invoice(invoice_id)
            return self._invoice_matches(invoice, expected_amount, expected_currency)
        except Exception as e:
            logger.warning("lzt check_invoice error for %s: %s", invoice_id, e)
            return False


lzt_client = LZTPayClient()
