import base64
import time
import uuid
from datetime import datetime
from functools import lru_cache

import httpx

from app.core.config import settings
from app.utils.dates import KENYA_TZ

BASE_URLS = {
    "sandbox": "https://sandbox.safaricom.co.ke",
    "production": "https://api.safaricom.co.ke",
}


class MpesaError(Exception):
    pass


class MpesaProcessing(MpesaError):
    """STK Query: the customer hasn't answered the prompt yet."""


class MpesaClient:
    def __init__(self) -> None:
        self._token: str | None = None
        self._token_expiry = 0.0

    def _base(self) -> str:
        return BASE_URLS.get(settings.mpesa_env, BASE_URLS["sandbox"])

    def _require_config(self) -> None:
        needed = {
            "MPESA_CONSUMER_KEY": settings.mpesa_consumer_key,
            "MPESA_CONSUMER_SECRET": settings.mpesa_consumer_secret,
            "MPESA_SHORTCODE": settings.mpesa_shortcode,
            "MPESA_PASSKEY": settings.mpesa_passkey,
            "MPESA_CALLBACK_SECRET": settings.mpesa_callback_secret,
            "PUBLIC_BASE_URL": settings.public_base_url,
        }
        missing = [k for k, v in needed.items() if not v]
        if missing:
            raise MpesaError(f"M-Pesa is not configured: {', '.join(missing)}")
        if not settings.public_base_url.startswith("https://"):
            raise MpesaError("PUBLIC_BASE_URL must be an https:// URL for M-Pesa callbacks")

    def _access_token(self) -> str:
        if self._token and time.time() < self._token_expiry:
            return self._token
        try:
            res = httpx.get(
                f"{self._base()}/oauth/v1/generate",
                params={"grant_type": "client_credentials"},
                auth=(settings.mpesa_consumer_key, settings.mpesa_consumer_secret),
                timeout=15,
            )
            res.raise_for_status()
            data = res.json()
            self._token = data["access_token"]
            self._token_expiry = time.time() + int(data.get("expires_in", 3599)) - 60
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise MpesaError("Could not authenticate with M-Pesa") from exc
        return self._token

    def _password(self, timestamp: str) -> str:
        raw = f"{settings.mpesa_shortcode}{settings.mpesa_passkey}{timestamp}"
        return base64.b64encode(raw.encode()).decode()

    def _post(self, path: str, payload: dict) -> dict:
        token = self._access_token()
        try:
            res = httpx.post(
                f"{self._base()}{path}",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=20,
            )
        except httpx.HTTPError as exc:
            raise MpesaError("Could not reach M-Pesa") from exc
        try:
            data = res.json()
        except ValueError:
            data = {}
        if res.status_code >= 400 or "errorCode" in data:
            message = data.get("errorMessage") or f"M-Pesa returned HTTP {res.status_code}"
            if "being processed" in message.lower():
                raise MpesaProcessing(message)
            raise MpesaError(message)
        return data

    def stk_push(self, *, phone: str, amount: int, reference: str, description: str) -> dict:
        self._require_config()
        ts = datetime.now(KENYA_TZ).strftime("%Y%m%d%H%M%S")
        callback = (
            f"{settings.public_base_url.rstrip('/')}"
            f"/api/v1/payments/callbacks/stk/{settings.mpesa_callback_secret}"
        )
        data = self._post(
            "/mpesa/stkpush/v1/processrequest",
            {
                "BusinessShortCode": settings.mpesa_shortcode,
                "Password": self._password(ts),
                "Timestamp": ts,
                "TransactionType": settings.mpesa_transaction_type,
                "Amount": amount,
                "PartyA": phone,
                "PartyB": settings.mpesa_party_b or settings.mpesa_shortcode,
                "PhoneNumber": phone,
                "CallBackURL": callback,
                "AccountReference": reference[:12],
                "TransactionDesc": description[:13],
            },
        )
        if str(data.get("ResponseCode")) != "0" or not data.get("CheckoutRequestID"):
            raise MpesaError(data.get("ResponseDescription") or "M-Pesa rejected the request")
        return data

    def stk_query(self, checkout_request_id: str) -> dict:
        self._require_config()
        ts = datetime.now(KENYA_TZ).strftime("%Y%m%d%H%M%S")
        return self._post(
            "/mpesa/stkpushquery/v1/query",
            {
                "BusinessShortCode": settings.mpesa_shortcode,
                "Password": self._password(ts),
                "Timestamp": ts,
                "CheckoutRequestID": checkout_request_id,
            },
        )


class MockMpesaClient:
    """Dev only: no network. Approve payments with scripts.simulate_stk_callback."""

    def stk_push(self, *, phone: str, amount: int, reference: str, description: str) -> dict:
        n = uuid.uuid4().hex[:12]
        return {"MerchantRequestID": f"mock_{n}", "CheckoutRequestID": f"ws_CO_mock_{n}"}

    def stk_query(self, checkout_request_id: str) -> dict:
        raise MpesaProcessing("mock: waiting for the customer")


@lru_cache
def get_mpesa_client() -> MpesaClient | MockMpesaClient:
    return MockMpesaClient() if settings.mpesa_env == "mock" else MpesaClient()