"""Razorpay (TEST MODE ONLY) integration.

* Orders are created server-side with the key secret; the browser only ever sees the public key id and the order id.
* The checkout handler's signature is verified here: HMAC_SHA256(order_id + "|" + payment_id, key_secret).
* The browser is never the sole authority: after a valid signature the payment is confirmed server-to-server (GET /payments/{id}),
  and the signed webhook (X-Razorpay-Signature over the raw body) settles it independently and idempotently.
* Live keys are refused outright: only `rzp_test_` key ids are accepted.

What is verified automatically: signature maths against the documented algorithm, request shapes, idempotency, mismatch handling.
What is NOT verified without real credentials and network: the live HTTPS exchange with api.razorpay.com (tests use an injected fake client).
"""
import hashlib
import hmac
import logging
from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.core.exceptions import AppError

log = logging.getLogger(__name__)
TEST_PREFIX = "rzp_test_"


@dataclass
class RazorpayConfig:
    enabled: bool
    key_id: str
    reason: str = ""


def config() -> RazorpayConfig:
    s = get_settings()
    if not s.razorpay_key_id or not s.razorpay_key_secret:
        return RazorpayConfig(False, "", "Razorpay is not configured (set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET to Test Mode keys)")
    if not s.razorpay_key_id.startswith(TEST_PREFIX):
        return RazorpayConfig(False, "", "Live mode is not permitted: only rzp_test_ keys are accepted")
    return RazorpayConfig(True, s.razorpay_key_id)


def require_enabled() -> RazorpayConfig:
    c = config()
    if not c.enabled:
        raise AppError(c.reason, 503)
    return c


def _hex_hmac(secret: str, payload: bytes) -> str:
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """Checkout handler signature: HMAC_SHA256(order_id|payment_id) with the key secret, compared in constant time."""
    expected = _hex_hmac(get_settings().razorpay_key_secret, f"{order_id}|{payment_id}".encode())
    return hmac.compare_digest(expected, signature or "")


def verify_webhook_signature(raw_body: bytes, signature: str | None) -> bool:
    """Webhook signature: HMAC_SHA256(raw request body) with the webhook secret. Needs the exact bytes received."""
    secret = get_settings().razorpay_webhook_secret
    if not secret or not signature:
        return False
    return hmac.compare_digest(_hex_hmac(secret, raw_body), signature)


class RazorpayClient:
    """Thin server-side client for the two calls we need. Test-mode only; errors never leak the secret."""

    def __init__(self, transport: httpx.BaseTransport | None = None):
        s = get_settings()
        self._http = httpx.Client(base_url=s.razorpay_api_base, auth=(s.razorpay_key_id, s.razorpay_key_secret), timeout=10, transport=transport)

    def create_order(self, amount_paise: int, currency: str, receipt: str, notes: dict) -> dict:
        r = self._http.post("/orders", json={"amount": amount_paise, "currency": currency, "receipt": receipt[:40], "notes": notes})
        return self._ok(r, "create order")

    def fetch_payment(self, payment_id: str) -> dict:
        return self._ok(self._http.get(f"/payments/{payment_id}"), "fetch payment")

    @staticmethod
    def _ok(r: httpx.Response, what: str) -> dict:
        if r.status_code >= 400:
            log.warning("razorpay %s failed: %s %s", what, r.status_code, r.text[:200])
            raise AppError(f"Razorpay rejected the request ({what}, HTTP {r.status_code})", 502)
        return r.json()


def client() -> RazorpayClient:
    """Factory (monkeypatched in tests with a fake transport)."""
    require_enabled()
    return RazorpayClient()
