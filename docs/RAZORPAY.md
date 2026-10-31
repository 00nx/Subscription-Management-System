# Razorpay (Test Mode)

Brightloop can take online payments through Razorpay **Test Mode only**. The simulated gateway and manual payments stay available.

## What is real and what is not
* **Real code path:** server-side order creation (`POST /orders` with the key secret), Standard Checkout in the browser, checkout-signature
  verification, server-to-server confirmation (`GET /payments/{id}`), signed webhooks, idempotent settlement, transaction history.
* **Verified by automated tests:** the HMAC maths, request shapes, idempotency, mismatch/duplicate/late-capture handling, all against a
  **fake Razorpay API** (`tests/test_phase6.py`, `httpx.MockTransport`).
* **Not verified here:** the live HTTPS exchange with `api.razorpay.com` and the real Checkout popup. That needs your Test Mode keys and a
  network. Follow "Try it" below and treat the first run as the integration test.

## Safety rules enforced in code
* Only key ids starting with `rzp_test_` work; `rzp_live_` keys disable the integration (`GET /payments/razorpay/config/` says why).
* The amount comes from the invoice on the server, never from the browser; partial payments are validated against the balance.
* The browser is never the sole authority: after a valid checkout signature the backend **confirms with Razorpay** (captured, same order,
  same amount). If it cannot confirm, the payment stays `PENDING` and the signed webhook settles it.
* Webhooks are authenticated by `HMAC_SHA256(raw body, webhook secret)` in `X-Razorpay-Signature`, deduplicated by `X-Razorpay-Event-Id`,
  and settle each payment exactly once (a payment can only move out of `PENDING` once, under a row lock).
* A payment that Razorpay reports only as **authorized** (accounts set to authorise-only) is **captured by Brightloop** (server-side, exact amount) and then settled, from either the checkout confirmation or the `payment.authorized` webhook.
* The webhook needs only `RAZORPAY_WEBHOOK_SECRET` (a wrong or missing *API key* cannot make it fail). If it answers **503 "Live mode is not permitted"**, your API key id is not a Test Mode key: in the Razorpay dashboard switch the toggle to **Test Mode** before generating the key (it must start with `rzp_test_`). The startup banner prints a Razorpay status line that flags this.
* Money captured for an invoice that was settled meanwhile is recorded as `CAPTURED_BUT_REJECTED` with an audit entry, so it can be refunded.

## Try it
1. Razorpay Dashboard -> switch to **Test Mode** -> Settings -> API keys -> generate a key pair.
2. Put them in `.env` (never commit it):
   ```
   RAZORPAY_KEY_ID=rzp_test_xxxxxxxx
   RAZORPAY_KEY_SECRET=xxxxxxxx
   RAZORPAY_WEBHOOK_SECRET=choose-any-long-random-string
   ```
3. Webhook (so payments settle even if the browser closes). **`run.cmd` starts ngrok for you** when `ngrok` is installed (one-time: `ngrok config add-authtoken <token>`) and prints the exact webhook URL in its banner; skip it with `run.cmd --no-ngrok`. By hand instead: expose the API (e.g. `ngrok http 8000`), then Dashboard -> Settings -> Webhooks ->
   add `https://<public-host>/api/v1/webhooks/razorpay/`, the same secret as above, events `payment.captured`, `payment.failed`, `order.paid`.
4. Restart the API. As a customer open an invoice -> **Pay** -> **Pay with Razorpay (test mode)**. Test card: `4111 1111 1111 1111`, any future
   expiry, any CVV, OTP `1234` on the bank page (see Razorpay's test-card docs for UPI/netbanking test values).
5. Check the payment's transaction history: `ORDER_CREATED`, `SIGNATURE_VERIFIED`, `CHECKOUT_CAPTURED`, `SUCCEEDED`, then `WEBHOOK_payment.captured` (a repeat is logged as a duplicate, never credited twice).

## Endpoints
| Method | Path | Who |
|---|---|---|
| GET | `/api/v1/payments/razorpay/config/` | any signed-in user (public key id only) |
| POST | `/api/v1/payments/razorpay/orders/` | customer (own invoice) or staff |
| POST | `/api/v1/payments/razorpay/verify/` | the payer |
| POST | `/api/v1/webhooks/razorpay/` | Razorpay (signature-authenticated) |
