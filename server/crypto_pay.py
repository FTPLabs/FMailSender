"""CryptoBot (send.tg / pay.crypt.bot) payment client."""
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

    async def _request(self, method: str, use_post: bool = False, **params) -> dict:
        session = await self._get_session()
        url = f"{CRYPTO_BOT_API}/{method}"
        # Convert Python booleans to lowercase strings for the API
        cleaned = {}
        for k, v in params.items():
            if isinstance(v, bool):
                cleaned[k] = "true" if v else "false"
            elif v is not None and v != "":
                cleaned[k] = v
        try:
            req_ctx = (
                session.post(url, json=cleaned, timeout=aiohttp.ClientTimeout(total=15))
                if use_post
                else session.get(url, params=cleaned, timeout=aiohttp.ClientTimeout(total=15))
            )
            async with req_ctx as resp:
                raw_text = await resp.text()
                if not raw_text.strip():
                    raise RuntimeError(
                        f"Crypto Pay API вернул пустой ответ (HTTP {resp.status}). "
                        f"Проверьте CRYPTO_BOT_API и CRYPTO_BOT_TOKEN в .env"
                    )
                try:
                    import json as _json
                    data = _json.loads(raw_text)
                except Exception:
                    raise RuntimeError(
                        f"Crypto Pay API вернул не-JSON (HTTP {resp.status}): {raw_text[:200]}"
                    )
                if not data.get("ok"):
                    error = data.get("error", {})
                    raise RuntimeError(
                        f"CryptoBot API error: {error.get('name', 'Unknown')} — "
                        f"{error.get('message', str(data))}"
                    )
                return data.get("result", {})
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
        asset: str = "USDT",
        description: str = "",
        payload: str = "",
        expires_in: int = 3600,
    ) -> dict:
        """Create a payment invoice. Returns invoice dict with invoice_id and pay_url."""
        kwargs = dict(
            asset=asset,
            amount=str(round(amount, 2)),
            expires_in=expires_in,
        )
        if description:
            kwargs["description"] = description[:1023]
        if payload:
            kwargs["payload"] = payload
        result = await self._request("createInvoice", use_post=True, **kwargs)
        return result

    async def get_invoice(self, invoice_id: str) -> Optional[dict]:
        """Fetch a single invoice by its ID."""
        result = await self._request("getInvoices", invoice_ids=str(invoice_id))
        items = result.get("items", [])
        return items[0] if items else None

    @staticmethod
    def _invoice_matches(invoice: Optional[dict],
                         expected_amount: Optional[float],
                         expected_asset: Optional[str]) -> bool:
        """Проверяет, что оплаченный инвойс совпадает по сумме и активу.
        Защита от недоплаты / оплаты другим (более дешёвым) активом."""
        if not (invoice and invoice.get("status") == "paid"):
            return False
        if expected_asset is not None and invoice.get("asset") != expected_asset:
            logger.warning("invoice asset mismatch: got %s expected %s",
                           invoice.get("asset"), expected_asset)
            return False
        if expected_amount is not None:
            try:
                # допускаем переплату, отклоняем недоплату (с эпсилоном на округление)
                if float(invoice.get("amount", 0)) + 1e-6 < float(expected_amount):
                    logger.warning("invoice amount mismatch: got %s expected %s",
                                   invoice.get("amount"), expected_amount)
                    return False
            except (TypeError, ValueError):
                return False
        return True

    async def check_invoice(
        self,
        invoice_id: str,
        expected_amount: Optional[float] = None,
        expected_asset: Optional[str] = None,
    ) -> bool:
        """Return True if the invoice has been paid (и совпадает по сумме/активу)."""
        try:
            invoice = await self.get_invoice(invoice_id)
            return self._invoice_matches(invoice, expected_amount, expected_asset)
        except Exception as e:
            logger.warning("check_invoice error for %s: %s", invoice_id, e)
            return False

    async def wait_for_payment(
        self,
        invoice_id: str,
        timeout: int = 3600,
        poll_interval: int = 5,
    ) -> Optional[dict]:
        """Poll until paid or timeout. Returns invoice dict or None."""
        loop = asyncio.get_running_loop()  # FIX: один раз вместо каждой итерации
        deadline = loop.time() + timeout
        while loop.time() < deadline:
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
