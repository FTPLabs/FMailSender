"""CryptoBot (send.tg) payment client."""
import asyncio
import logging
from typing import Optional

import aiohttp

from config import CRYPTO_BOT_API, CRYPTO_BOT_TOKEN

logger = logging.getLogger("crypto_pay")


class CryptoPayClient:
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(self, method: str, **params) -> dict:
        session = await self._get_session()
        url = f"{CRYPTO_BOT_API}/{method}"
        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()
                if not data.get("ok"):
                    error = data.get("error", {})
                    raise RuntimeError(f"CryptoBot error: {error.get('name', 'Unknown')} — {error.get('message', '')}")
                return data.get("result", {})
        except aiohttp.ClientError as e:
            raise RuntimeError(f"Network error: {e}") from e

    async def create_invoice(
        self,
        amount: float,
        asset: str = "USDT",
        description: str = "",
        payload: str = "",
        expires_in: int = 3600,
    ) -> dict:
        result = await self._request(
            "createInvoice",
            asset=asset,
            amount=str(round(amount, 2)),
            description=description[:1023],
            payload=payload,
            expires_in=expires_in,
            allow_comments=False,
            allow_anonymous=False,
        )
        return result

    async def get_invoice(self, invoice_id: str) -> Optional[dict]:
        result = await self._request("getInvoices", invoice_ids=invoice_id)
        items = result.get("items", [])
        return items[0] if items else None

    async def wait_for_payment(
        self,
        invoice_id: str,
        timeout: int = 3600,
        poll_interval: int = 5,
    ) -> Optional[dict]:
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            try:
                invoice = await self.get_invoice(invoice_id)
                if invoice and invoice.get("status") == "paid":
                    return invoice
            except Exception as e:
                logger.warning("Poll error for %s: %s", invoice_id, e)
            await asyncio.sleep(poll_interval)
        return None

    async def get_balance(self) -> list:
        result = await self._request("getBalance")
        return result if isinstance(result, list) else []

    async def get_me(self) -> dict:
        return await self._request("getMe")


crypto_client = CryptoPayClient()
