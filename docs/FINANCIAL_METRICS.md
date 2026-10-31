# Financial metric definitions

One set of definitions, used by the dashboard, the analytics endpoints and the reports (`backend/app/modules/analytics/service.py`).
All money is `Decimal`, `NUMERIC(12,2)` in PostgreSQL, rounded half-up to 2 places, currency INR. API money values are **strings** (`"999.00"`).

| Metric | Definition |
|---|---|
| **Active subscriptions** | Subscriptions with status `ACTIVE` right now. Paused, expired, closed, draft, quotation and confirmed are excluded. |
| **MRR** | Σ over ACTIVE subscriptions of Σ(line quantity × unit price), **excluding tax and discounts**, normalised to one month: daily × 30.4167, weekly × 4.3333, monthly × 1, yearly ÷ 12 (average-month convention). One-time/manual invoices are not recurring and are excluded. |
| **ARR** | MRR × 12. |
| **Revenue collected** | Σ `amount` of payments with status `SUCCESS` whose `payment_date` falls in the selected range (UTC days, inclusive). Issuing an invoice is not collection. **Pending, failed and cancelled payments never count.** |
| **Outstanding** | Σ(`total` − `amount_paid`) over invoices in status `CONFIRMED` or `PARTIALLY_PAID`, as of now (not range-dependent). Drafts and cancelled invoices are excluded. |
| **Overdue invoices** | Invoices in `CONFIRMED`/`PARTIALLY_PAID` with `due_date` before today and a balance > 0. *Overdue is derived, never stored as a status.* |
| **Total customers** | Number of customer profiles. |
| **MRR trend** | MRR at the end of each of the last 12 months, rebuilt from the subscription event history (ACTIVATED/RESUMED/RENEWED = counted; PAUSED/CLOSED/AUTO_EXPIRED = not). Uses *today's* line prices (lines are only editable before activation, so drift is small). The current month uses live status. |
| **Subscription growth** | New subscriptions per month (by creation time) and the running total. |
| **Payment status distribution** | Count and amount of payments created in the range, by status. |
| **Revenue by product** (report) | Σ `line_total` (after discount, with tax) of invoice lines on non-draft, non-cancelled invoices issued in range. Payments are per invoice, so "collected" is only reported per period. |
| **Revenue by plan** (report) | Σ invoice `total` by the invoice's subscription plan; manual invoices without a subscription are grouped as "No plan". |

Date ranges: `today`, `last_7_days`, `last_30_days` (default), `this_month`, `last_month`, `this_year`, `custom` (needs `date_from`/`date_to`).
Staff see operational numbers only: MRR, ARR, revenue collected and revenue reports are **ADMIN-only** (the API returns `null` for those KPIs to staff).


## Dashboard additions and filters (Phase 4)

* **Total invoices**: invoices issued in the range, excluding drafts and cancelled.
* **Revenue billed**: sum of their totals (admin only). Billed is not collected.
* **Total payments**: sum and count of SUCCESS payments with `payment_date` in the range (admin only).
* **Active subscriptions by plan**: count of ACTIVE subscriptions per plan (or the chosen subscription status).
* **Filters** (`billing_frequency`, `plan_id`, `subscription_status`, `invoice_status`, `customer_id`): subscription filters narrow subscription
  metrics and MRR directly, and invoice/payment metrics through the invoice's subscription; `invoice_status` narrows invoice and payment
  metrics (a payment belongs to its invoice's status); `customer_id` narrows everything to that customer. MRR always means ACTIVE subscriptions,
  so a `subscription_status` filter changes the subscription counts but not the definition of MRR.
* **Reports**: outstanding and overdue reports carry aging buckets (not yet due, 1-30, 31-60, 61-90, 90+ days overdue); the renewal report lists
  active subscriptions expiring within N days and counts renewals/expiries recorded in the date range.
