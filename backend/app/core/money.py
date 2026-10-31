"""Money conventions: Decimal everywhere, NUMERIC(12,2) in the DB, ROUND_HALF_UP to 2 places, currency INR."""
from decimal import ROUND_HALF_UP, Decimal

CURRENCY = "INR"
CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def q(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def allocate(total: Decimal, weights: list[Decimal]) -> list[Decimal]:
    """Split `total` across `weights` proportionally to 2 places; the rounding remainder goes to the last non-zero weight."""
    s = sum(weights)
    if s == 0 or total == 0:
        return [ZERO] * len(weights)
    parts = [q(total * w / s) for w in weights]
    last = max(i for i, w in enumerate(weights) if w > 0)
    parts[last] += total - sum(parts)
    return parts


def tax_parts(base: Decimal, taxes: list[dict] | None, rate: Decimal = ZERO) -> list[dict]:
    """Per-tax amounts on `base` (each rounded half-up). `taxes` is the line's snapshot [{name, rate, ...}];
    lines created before multi-tax existed have none, so their single `rate` is used."""
    if not taxes:
        return [{"id": None, "name": "Tax", "rate": str(rate), "amount": q(base * rate / 100)}] if rate else []
    return [{**t, "amount": q(base * Decimal(str(t["rate"])) / 100)} for t in taxes]


def tax_amount(base: Decimal, taxes: list[dict] | None, rate: Decimal = ZERO) -> Decimal:
    return sum((p["amount"] for p in tax_parts(base, taxes, rate)), ZERO)

