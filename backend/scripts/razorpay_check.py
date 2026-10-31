"""Checks the Razorpay Test Mode setup step by step and says which step fails. Never prints secrets.

    run.cmd razorpay          (or: python dev.py razorpay)   -- run it while the app is running

It creates one harmless Test Mode order (Rs 1, no money moves) to prove your keys work against the real Razorpay API.
"""
import hashlib
import hmac
import json
import sys
import urllib.error
import urllib.request

import httpx

from app.core.config import get_settings

OK, BAD, INFO = "[ OK ]", "[FAIL]", "[ .. ]"
failed = 0


def line(ok: bool | None, msg: str) -> None:
    global failed
    print(f"{OK if ok else INFO if ok is None else BAD} {msg}", flush=True)
    failed += ok is False


def mask(v: str) -> str:
    return "(empty)" if not v else f"set, {len(v)} characters, starts with '{v[:9]}'" if v.startswith("rzp_") else f"set, {len(v)} characters"


def post_webhook(base: str, secret: str, label: str) -> None:
    body = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {"id": "pay_check", "order_id": "order_brightloop_check", "amount": 100}}}}).encode()
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(f"{base}/api/v1/webhooks/razorpay/", data=body, method="POST",
                                 headers={"Content-Type": "application/json", "X-Razorpay-Signature": sig, "X-Razorpay-Event-Id": "evt_brightloop_check"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            msg = json.loads(r.read()).get("message", "")
        line("ignored" in msg, f"{label}: the webhook endpoint answered 200 ('{msg}'). Signature checking works.")
    except urllib.error.HTTPError as e:
        hint = {400: "the secret the RUNNING app loaded differs from backend/.env: restart run.cmd after editing .env",
                503: "the running app has no valid rzp_test_ keys loaded: restart run.cmd after editing .env"}.get(e.code, "unexpected answer")
        line(False, f"{label}: HTTP {e.code} from the webhook endpoint: {hint}.")
    except OSError as e:
        line(False, f"{label}: could not reach {base} ({e}).")


def main() -> int:
    s = get_settings()
    print("Brightloop Razorpay check (Test Mode)\n")
    line(bool(s.razorpay_key_id.startswith("rzp_test_")), f"RAZORPAY_KEY_ID: {mask(s.razorpay_key_id)}" + ("" if s.razorpay_key_id.startswith("rzp_test_") else "   <- must start with rzp_test_ (Test Mode keys only)"))
    line(bool(s.razorpay_key_secret), f"RAZORPAY_KEY_SECRET: {mask(s.razorpay_key_secret)}" + ("" if s.razorpay_key_secret else "   <- fill it in backend/.env"))
    line(bool(s.razorpay_webhook_secret) and not s.razorpay_webhook_secret.startswith("http"),
         f"RAZORPAY_WEBHOOK_SECRET: {mask(s.razorpay_webhook_secret)}" + ("   <- this is a URL; it must be a random string you invent (the same one you type in the dashboard)" if s.razorpay_webhook_secret.startswith("http") else "   <- fill it in backend/.env" if not s.razorpay_webhook_secret else ""))
    if not (s.razorpay_key_id.startswith("rzp_test_") and s.razorpay_key_secret):
        print("\nFix the lines above in backend/.env, restart run.cmd, then run this check again.")
        return 1

    try:
        r = httpx.post(f"{s.razorpay_api_base}/orders", auth=(s.razorpay_key_id, s.razorpay_key_secret), json={"amount": 100, "currency": "INR", "receipt": "brightloop-check"}, timeout=15)
        if r.status_code == 200:
            line(True, f"Razorpay accepted your keys and created Test order {r.json().get('id')} (Rs 1, nothing is charged).")
        else:
            err = (r.json().get("error") or {}).get("description", r.text[:200]) if r.headers.get("content-type", "").startswith("application/json") else r.text[:200]
            hint = "the key id and secret do not match, or are not from Test Mode" if r.status_code == 401 else "see Razorpay's message"
            line(False, f"Razorpay rejected the order (HTTP {r.status_code}): {err}  -> {hint}.")
    except httpx.HTTPError as e:
        line(False, f"Could not reach Razorpay at {s.razorpay_api_base}: {e}. Check your internet/firewall.")

    base = "http://localhost:8000"
    try:
        urllib.request.urlopen(f"{base}/openapi.json", timeout=5).read(1)
        line(True, "The Brightloop API is running on port 8000.")
        post_webhook(base, s.razorpay_webhook_secret, "Locally")
    except OSError:
        line(False, "The Brightloop API is not running on port 8000: start run.cmd first, then run this check in a second window.")

    public = None
    try:
        with urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=3) as r:
            for t in json.load(r).get("tunnels", []):
                if str(t.get("public_url", "")).startswith("https://") and str(t.get("config", {}).get("addr", "")).endswith(":8000"):
                    public = t["public_url"]
    except (OSError, ValueError):
        pass
    if public:
        line(True, f"ngrok tunnel to port 8000: {public}")
        post_webhook(public, s.razorpay_webhook_secret, "Through ngrok")
        print(f"\nDashboard webhook URL:  {public}/api/v1/webhooks/razorpay/\n(Razorpay > Settings > Webhooks, Test Mode; secret = your RAZORPAY_WEBHOOK_SECRET; events payment.captured, payment.failed, order.paid)")
    else:
        line(None, "No ngrok tunnel to port 8000 found. Fine if you are not testing webhooks; otherwise start run.cmd with ngrok installed.")
    print("\n" + ("Everything above is OK. If a payment still fails, tell me the exact message Razorpay's window shows." if not failed else f"{failed} problem(s) found: fix the [FAIL] lines first."))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
