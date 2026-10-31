"""HTML + plain-text email templates. Each template is a function of a context dict returning (subject, html, text).
Values are HTML-escaped when placed in the HTML body; the layout is table-based so mail clients render it consistently."""
from html import escape

from app.core.config import get_settings


def _layout(title: str, paragraphs: list[str], button: tuple[str, str] | None = None, footer: str = "") -> tuple[str, str]:
    biz = escape(get_settings().business_name)
    body = "".join(f'<p style="margin:0 0 14px;font-size:15px;line-height:1.5;color:#0f172a">{p}</p>' for p in paragraphs)
    btn = (f'<p style="margin:22px 0"><a href="{escape(button[1], quote=True)}" style="background:#4f46e5;color:#ffffff;text-decoration:none;'
           f'padding:11px 20px;border-radius:6px;font-weight:600;font-size:15px">{escape(button[0])}</a></p>') if button else ""
    html = (f'<!doctype html><html><body style="margin:0;background:#f1f5f9;font-family:Arial,Helvetica,sans-serif">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px 12px">'
            f'<table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border-radius:8px">'
            f'<tr><td style="padding:20px 28px;border-bottom:1px solid #e2e8f0;font-size:20px;font-weight:700;color:#4f46e5">{biz}</td></tr>'
            f'<tr><td style="padding:26px 28px"><h1 style="margin:0 0 16px;font-size:20px;color:#0f172a">{escape(title)}</h1>{body}{btn}'
            f'<p style="margin:18px 0 0;font-size:12px;color:#64748b">{footer or "You are receiving this because of activity on your " + biz + " account."}</p>'
            f'</td></tr></table></td></tr></table></body></html>')
    text = title + "\n\n" + "\n\n".join(_strip(p) for p in paragraphs) + (f"\n\n{button[0]}: {button[1]}" if button else "")
    return html, text


def _strip(s: str) -> str:
    import re
    return re.sub(r"<[^>]+>", "", s).replace("&amp;", "&")


def _portal(path: str = "") -> str:
    return get_settings().frontend_url.rstrip("/") + path


def _money(c: dict, key: str = "amount") -> str:
    return f"{c.get('currency', 'INR')} {c[key]}"


def _e(c: dict, k: str) -> str:
    return escape(str(c.get(k, "")))


def welcome(c):
    h, t = _layout("Welcome to " + get_settings().business_name, [f"Hi {_e(c, 'name')},", "Your account is ready. You can browse plans, manage your subscriptions and pay invoices from your portal."], ("Open your portal", _portal("/customer/dashboard")))
    return f"Welcome to {get_settings().business_name}", h, t


def password_reset(c):
    h, t = _layout("Reset your password", [f"Hi {_e(c, 'name')},", f"Use the button below to set a new password. The link is valid for {_e(c, 'minutes')} minutes and works once.", "If you did not ask for this, you can ignore this email."], ("Set a new password", c["link"]))
    return f"Reset your {get_settings().business_name} password", h, t


def quotation_sent(c):
    h, t = _layout(f"Quotation {c['number']}", [f"Hi {_e(c, 'name')},", f"We prepared quotation <b>{_e(c, 'number')}</b> for you, totalling <b>{escape(_money(c, 'total'))}</b>. It is valid until {_e(c, 'expiry_date')}."], ("Review the quotation", _portal("/customer/subscriptions")))
    return f"Quotation {c['number']} from {get_settings().business_name}", h, t


def subscription_confirmed(c):
    h, t = _layout(f"Subscription {c['number']} confirmed", [f"Hi {_e(c, 'name')},", f"Your subscription <b>{_e(c, 'number')}</b> ({_e(c, 'plan')}) has been confirmed. It will start on {_e(c, 'start_date')}."], ("View subscription", _portal(f"/customer/subscriptions/{c['id']}")))
    return f"Subscription {c['number']} confirmed", h, t


def subscription_activated(c):
    h, t = _layout(f"Subscription {c['number']} is active", [f"Hi {_e(c, 'name')},", f"Your <b>{_e(c, 'plan')}</b> subscription is now active. The first invoice is issued on {_e(c, 'next_billing_date')}."], ("Manage subscription", _portal(f"/customer/subscriptions/{c['id']}")))
    return f"Subscription {c['number']} is active", h, t


def invoice_sent(c):
    h, t = _layout(f"Invoice {c['number']}", [f"Hi {_e(c, 'name')},", f"Invoice <b>{_e(c, 'number')}</b> for <b>{escape(_money(c, 'total'))}</b> is due on {_e(c, 'due_date')}. Outstanding: {escape(_money(c, 'outstanding'))}."], ("View and pay invoice", _portal(f"/customer/invoices/{c['id']}")))
    return f"Invoice {c['number']} from {get_settings().business_name}", h, t


def payment_received(c):
    h, t = _layout("Payment received", [f"Hi {_e(c, 'name')},", f"We received your payment of <b>{escape(_money(c))}</b> for invoice <b>{_e(c, 'invoice')}</b> ({_e(c, 'method')}). Thank you!", f"Remaining balance: {escape(_money(c, 'outstanding'))}."], ("View invoice", _portal(f"/customer/invoices/{c['invoice_id']}")))
    return f"Payment received for invoice {c['invoice']}", h, t


def payment_reminder(c):
    when = f"is {c['days_overdue']} day(s) overdue" if int(c.get("days_overdue") or 0) > 0 else f"is due on {c['due_date']}"
    h, t = _layout("Payment reminder", [f"Hi {_e(c, 'name')},", f"Invoice <b>{_e(c, 'number')}</b> {escape(when)}. Outstanding: <b>{escape(_money(c, 'outstanding'))}</b>."], ("Pay now", _portal(f"/customer/invoices/{c['id']}")))
    return f"Payment reminder: invoice {c['number']}", h, t


def subscription_renewed(c):
    h, t = _layout("Subscription renewed", [f"Hi {_e(c, 'name')},", f"Your subscription <b>{_e(c, 'number')}</b> was renewed. The new term ends on {_e(c, 'expiry_date')}."], ("View subscription", _portal(f"/customer/subscriptions/{c['id']}")))
    return f"Subscription {c['number']} renewed", h, t


def subscription_expired(c):
    h, t = _layout("Subscription expired", [f"Hi {_e(c, 'name')},", f"Your subscription <b>{_e(c, 'number')}</b> expired on {_e(c, 'expiry_date')}. You can renew it from your portal."], ("Renew subscription", _portal(f"/customer/subscriptions/{c['id']}")))
    return f"Subscription {c['number']} expired", h, t


TEMPLATES = {f.__name__: f for f in (welcome, password_reset, quotation_sent, subscription_confirmed, subscription_activated, invoice_sent, payment_received,
                                     payment_reminder, subscription_renewed, subscription_expired)}


def render(template: str, context: dict) -> tuple[str, str, str]:
    """Returns (subject, html, text). Unknown templates raise KeyError so a typo fails loudly in tests."""
    return TEMPLATES[template](context)
