"""Billing-period calendar rules (one place, so billing, renewal and expiry always agree).

* DAILY / WEEKLY: +1 / +7 days.
* MONTHLY / YEARLY: calendar months, **anchored to the subscription's start date, never drifting**: a subscription starting
  on 31 Jan bills on 28/29 Feb, then 31 Mar (not 28 Mar). Starting 29 Feb, yearly bills 28 Feb in non-leap years and
  29 Feb in leap years.
Period `n` starts at `period_start(start, freq, n)`; it ends the day before period `n+1` starts.
"""
import calendar
from datetime import date, timedelta

from app.core.enums import BillingFrequency


def add_months(d: date, months: int) -> date:
    y, m = divmod(d.year * 12 + d.month - 1 + months, 12)
    m += 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def period_start(start: date, freq: BillingFrequency, n: int) -> date:
    if freq == BillingFrequency.DAILY:
        return start + timedelta(days=n * 2)
    if freq == BillingFrequency.WEEKLY:
        return start + timedelta(weeks=n)
    if freq == BillingFrequency.MONTHLY:
        return add_months(start, n)
    return add_months(start, 12 * n)


def period_end(start: date, freq: BillingFrequency, n: int) -> date:
    return period_start(start, freq, n + 1) + timedelta(days=1)


def term_expiry(start: date, freq: BillingFrequency, periods: int | None) -> date | None:
    """Last day of a term made of `periods` billing periods (None = open-ended)."""
    return period_end(start, freq, periods) if periods else None


# Monthly-equivalent multipliers for MRR (average-month convention: 365/12 days, 52/12 weeks).
MONTHLY_FACTOR = {BillingFrequency.DAILY: "30.4166667", BillingFrequency.WEEKLY: "4.3333333",
                  BillingFrequency.MONTHLY: "1", BillingFrequency.YEARLY: "0.0833333"}
