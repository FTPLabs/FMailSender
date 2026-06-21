"""xRocket Pay (pay.xrocket.exchange) payment client.

Зеркалит интерфейс CryptoPayClient, чтобы провайдеры были взаимозаменяемы через
payment_providers. Секреты читаются ТОЛЬКО из config (env) — никогда не хардкодятся.

API: база https://pay.xrocket.exchange, заголовок Rocket-Pay-Key.
  POST   /tg-invoices        — создать инвойс  -> {success, data:{id, link, status, amount, currency}}
  GET    /tg-invoices/{id}   — статус инвойса  (status: active|paid|expired)
  DELETE /tg-invoices/{id}   — удалить инвойс
"""
import asyncio
import logging
from typing import Optional

import aiohttp

from config import XROCKET_API, XROCKET_API_TOKEN

logger = logging.getLogger("xrocket_pay")


class XRocketPayClient:
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"Rocket-Pay-Key": XROCKET_API_TOKEN}
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(self, method: str, path: str, payload: Optional[dict] = None) -> dict:
        session = await self._get_session()
        url = f"{XROCKET_API}{path}"
        timeout = aiohttp.ClientTimeout(total=15)
        try:
            if method == "POST":
                ctx = session.post(url, json=payload or {}, timeout=timeout)
            elif method == "DELETE":
                ctx = session.delete(url, timeout=timeout)
            else:
                ctx = session.get(url, timeout=timeout)
            async with ctx as resp:
                data = await resp.json(content_type=None)
                if not isinstance(data, dict) or not data.get("success"):
                    err = (data.get("message") or data.get("errors") or data) if isinstance(data, dict) else data
                    raise RuntimeError(f"xRocket API error: {err}")
                inner = data.get("data")
                return inner if isinstance(inner, dict) else data
        except aiohttp.ClientError as e:
            # Инвалидируем сессию при сетевой ошибке — следующий запрос создаст новую
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
        currency: str = "USDT",
        description: str = "",
        payload: str = "",
        expires_in: int = 3600,
    ) -> dict:
        """Создаёт инвойс. Возвращает {invoice_id, pay_url, raw}."""
        body = {
            "amount": round(float(amount), 2),
            "currency": currency,
            "numPayments": 1,
            "expiredIn": int(expires_in),
        }
        if description:
            body["description"] = description[:1000]
        if payload:
            body["payload"] = payload
        data = await self._request("POST", "/tg-invoices", body)
        return {
            "invoice_id": str(data.get("id", "")),
            "pay_url": data.get("link", ""),
            "raw": data,
        }

    async def get_invoice(self, invoice_id: str) -> Optional[dict]:
        data = await self._request("GET", f"/tg-invoices/{invoice_id}")
        return data or None

    @staticmethod
    def _invoice_matches(invoice: Optional[dict],
                         expected_amount: Optional[float],
                         expected_currency: Optional[str]) -> bool:
        """Проверяет, что инвойс оплачен и совпадает по сумме/валюте.
        Защита от недоплаты и оплаты другой (более дешёвой) валютой."""
        if not (invoice and invoice.get("status") == "paid"):
            return False
        if expected_currency is not None and invoice.get("currency") != expected_currency:
            logger.warning("xrocket invoice currency mismatch: got %s expected %s",
                           invoice.get("currency"), expected_currency)
            return False
        if expected_amount is not None:
            try:
                if float(invoice.get("amount", 0)) + 1e-6 < float(expected_amount):
                    logger.warning("xrocket invoice amount mismatch: got %s expected %s",
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
            logger.warning("xrocket check_invoice error for %s: %s", invoice_id, e)
            return False

    async def wait_for_payment(
        self,
        invoice_id: str,
        timeout: int = 3600,
        poll_interval: int = 5,
    ) -> Optional[dict]:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            try:
                invoice = await self.get_invoice(invoice_id)
                if invoice and invoice.get("status") == "paid":
                    return invoice
            except Exception as e:
                logger.warning("xrocket poll error for %s: %s", invoice_id, e)
            await asyncio.sleep(poll_interval)
        return None

    async def delete_invoice(self, invoice_id: str) -> bool:
        try:
            await self._request("DELETE", f"/tg-invoices/{invoice_id}")
            return True
        except Exception as e:
            logger.warning("xrocket delete_invoice error for %s: %s", invoice_id, e)
            return False

    async def get_app_info(self) -> dict:
        return await self._request("GET", "/app/info")


xrocket_client = XRocketPayClient()
