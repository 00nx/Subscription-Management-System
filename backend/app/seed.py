"""Development/demo data. Refuses to run when ENVIRONMENT=production.

    python -m app.seed                # demo data (idempotent: skips if the admin already exists)
    python -m app.seed --reset        # wipe every table first, then seed
    python -m app.seed --reset --bulk 5000   # also add ~5000 subscriptions (+invoices/payments) for performance testing

Development-only accounts (all passwords satisfy the password rules; never use these anywhere real):
    admin@brightloop.dev / Admin@12345      staff1@brightloop.dev, staff2@brightloop.dev / Staff@12345
    alice@example.com ... / Customer@12345
"""
import argparse
import random
import sys
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, insert, select, text

from app.core.config import get_settings
from app.core.database import IS_SQLITE, SessionLocal
from app.core.enums import BillingFrequency as F, InvoiceStatus as IS, PaymentMethod as PM, PaymentStatus as PS, SubscriptionStatus as S
from app.core.money import q
from app.core.security import hash_password
from app.modules.accounts.models import User, UserRole
from app.modules.accounts.schemas import RegisterIn
from app.modules.accounts.service import create_user
from app.modules.billing import service as billing
from app.modules.billing.models import Tax
from app.modules.customers.models import CustomerProfile
from app.modules.discounts.models import Discount, DiscountProduct
from app.modules.invoices.models import Invoice, InvoiceLine
from app.modules.payments import service as payments
from app.modules.payments.models import Payment
from app.modules.products.models import Product, ProductVariant
from app.modules.quotations import service as quotes
from app.modules.quotations.schemas import ConvertIn, QuotationIn, TemplateIn, TemplateLineIn
from app.modules.subscriptions import service as subs
from app.modules.subscriptions.models import Subscription, SubscriptionEvent, SubscriptionLine, SubscriptionPlan
from app.modules.subscriptions.periods import period_start, term_expiry
from app.modules.subscriptions.schemas import LineIn, SubscriptionIn

SEQUENCES = ("customer_number_seq", "quotation_number_seq", "subscription_number_seq", "invoice_number_seq")
ADMIN_PW, STAFF_PW, CUSTOMER_PW = "Admin@12345", "Staff@12345", "Customer@12345"


def reset(db) -> None:
    if IS_SQLITE:
        from app.core.database import Base, _counters, init_sqlite_schema

        init_sqlite_schema()
        for t in reversed(Base.metadata.sorted_tables):  # children before parents (foreign keys)
            db.execute(t.delete())
        db.execute(_counters.delete())
        db.commit()
        return
    tables = [r[0] for r in db.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename <> 'alembic_version'"))]
    db.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))
    for s in SEQUENCES:
        db.execute(text(f"ALTER SEQUENCE {s} RESTART"))
    db.commit()


def seed_demo(db) -> None:
    cfg = get_settings()
    prev, cfg.email_delivery = cfg.email_delivery, "off"  # demo addresses are fake: never email them, even when SMTP is configured
    try:
        _seed_demo(db)
    finally:
        cfg.email_delivery = prev


def _seed_demo(db) -> None:
    if db.scalar(select(User.id).where(User.email == "admin@brightloop.dev")):
        print("Demo data already present (use --reset to rebuild).")
        return
    today = date.today()
    admin = create_user(db, RegisterIn(email="admin@brightloop.dev", password=ADMIN_PW, full_name="Demo Admin"), UserRole.ADMIN)
    staff = [create_user(db, RegisterIn(email=f"staff{i}@brightloop.dev", password=STAFF_PW, full_name=f"Demo Staff {i}"), UserRole.STAFF) for i in (1, 2)]
    names = ["Alice Johnson", "Bob Martin", "Chitra Rao", "Dev Patel", "Elena Garcia", "Farid Khan"]
    customers = []
    for n in names:
        u = create_user(db, RegisterIn(email=f"{n.split()[0].lower()}@example.com", password=CUSTOMER_PW, full_name=n))
        p = db.scalar(select(CustomerProfile).where(CustomerProfile.user_id == u.id))
        p.company_name, p.phone, p.billing_address = f"{n.split()[1]} & Co", "+91 90000 0000" + str(len(customers)), f"{len(customers) + 1} Market Road, Bengaluru"
        customers.append(p)

    gst18, gst5, zero, cgst, sgst = (Tax(name=n, rate=Decimal(r)) for n, r in (("GST 18%", "18.00"), ("GST 5%", "5.00"), ("Exempt", "0.00"), ("CGST 9%", "9.00"), ("SGST 9%", "9.00")))
    db.add_all([gst18, gst5, zero, cgst, sgst])
    db.flush()
    sw = Product(name="Software Subscription", product_type="SOFTWARE", sales_price=Decimal("1000.00"), cost_price=Decimal("300.00"), description="Core platform licence", tax_id=gst18.id)
    sup = Product(name="Premium Support", product_type="SERVICE", sales_price=Decimal("250.00"), cost_price=Decimal("100.00"), tax_id=gst18.id)
    trn = Product(name="Training Pack", product_type="SERVICE", sales_price=Decimal("5000.00"), cost_price=Decimal("2000.00"), tax_id=gst5.id)
    cons = Product(name="Consulting Day", product_type="SERVICE", sales_price=Decimal("8000.00"), cost_price=Decimal("3000.00"), description="Taxed as CGST + SGST (shows the tax breakdown)",
                   tax_id=cgst.id, extra_tax_ids=[str(sgst.id)])
    db.add_all([sw, sup, trn, cons])
    db.flush()
    db.add_all([ProductVariant(product_id=sw.id, name="Standard brand", attribute_name="Brand", attribute_value="Standard", additional_price=Decimal("0.00")),
                ProductVariant(product_id=sw.id, name="Odoo brand", attribute_name="Brand", attribute_value="Odoo", additional_price=Decimal("560.00"))])
    plans = {}
    for name, prod, price, freq in (("Software Monthly", sw, "999.00", F.MONTHLY), ("Software Yearly", sw, "9999.00", F.YEARLY), ("Support Weekly", sup, "99.00", F.WEEKLY),
                                    ("Support Daily", sup, "15.00", F.DAILY), ("Training Quarterly", trn, "4500.00", F.MONTHLY), ("Consulting Monthly", cons, "8000.00", F.MONTHLY)):
        plans[name] = SubscriptionPlan(name=name, product_id=prod.id, price=Decimal(price), billing_frequency=freq, description=f"{name} plan")
        db.add(plans[name])
    db.flush()
    d1 = Discount(name="Welcome 10%", discount_type="PERCENTAGE", value=Decimal("10.00"), description="10% off software", max_usage=50, end_date=today + timedelta(days=90))
    d2 = Discount(name="Loyalty 500 off", discount_type="FIXED", value=Decimal("500.00"), min_purchase_amount=Decimal("5000.00"), max_usage=10)
    db.add_all([d1, d2])
    db.flush()
    db.add(DiscountProduct(discount_id=d1.id, product_id=sw.id))
    db.add(DiscountProduct(discount_id=d2.id, product_id=trn.id))
    db.commit()

    # subscriptions: different frequencies, started in the past so billing has history
    def sub(cust, plan, days_ago, term=None, variant=None, qty=1, auto_renew=False):
        pl = plans[plan]
        lines = [LineIn(product_id=pl.product_id, variant_id=variant, quantity=qty)]
        s = subs.create_subscription(db, SubscriptionIn(customer_id=cust.id, plan_id=pl.id, start_date=today - timedelta(days=days_ago), term_periods=term,
                                                        payment_terms_days=14, auto_renew=auto_renew, lines=lines), staff[0])
        subs.confirm(db, s, staff[0])
        subs.activate(db, s, staff[0])
        db.commit()
        return s

    odoo = db.scalar(select(ProductVariant.id).where(ProductVariant.attribute_value == "Odoo"))
    s1 = sub(customers[0], "Software Monthly", 75, term=12, auto_renew=True)
    s2 = sub(customers[1], "Software Yearly", 200, term=3, variant=odoo)
    s3 = sub(customers[2], "Support Weekly", 30)
    s4 = sub(customers[3], "Support Daily", 5)
    s5 = sub(customers[4], "Training Quarterly", 40, qty=2)
    s6 = sub(customers[5], "Software Monthly", 10, term=6)
    sub(customers[3], "Software Monthly", 345, term=12)  # renewal pipeline: the term ends in about three weeks
    cfg = get_settings()
    prev, cfg.auto_confirm_invoices = cfg.auto_confirm_invoices, True  # historical demo invoices are already issued
    try:
        billing.run_billing(today)
    finally:
        cfg.auto_confirm_invoices = prev
    # pause one, close one
    subs.pause(db, s4, staff[0])
    db.commit()

    # payments: some paid, some partial, some failed, some left overdue
    invs = list(db.scalars(select(Invoice).order_by(Invoice.created_at, Invoice.number)).unique())
    for i, inv in enumerate(invs):
        if i % 4 == 0:
            payments.record_manual(db, staff[0], inv.id, PM.BANK_TRANSFER, inv.total, f"BANK-{inv.number}", "Seeded payment", None)
        elif i % 4 == 1:
            payments.record_manual(db, staff[1], inv.id, PM.UPI, q(inv.total / 2), f"UPI-{inv.number}", "Part payment", None)
        elif i % 4 == 2:
            cust_user = db.get(User, db.get(CustomerProfile, inv.customer_id).user_id)
            p = payments.initiate(db, cust_user, inv.id, PM.CARD, None, None)
            payments.complete(db, cust_user, p.id, "FAILED")
        db.commit()
    # make some old invoices overdue
    for inv in invs[:3]:
        inv = db.get(Invoice, inv.id)
        inv.due_date = today - timedelta(days=12)
    db.commit()

    # billing day (scene 6): active subscriptions due *today* and not yet billed. "Run billing now" creates DRAFT invoices for them,
    # a second press creates nothing (duplicate prevention), then confirm / send / print the drafts.
    sub(customers[0], "Consulting Monthly", 0, term=6)
    sub(customers[1], "Software Monthly", 0, term=12, variant=odoo)
    sub(customers[2], "Support Weekly", 0)

    # quotations: draft, sent, confirmed, converted
    tpl = quotes.create_template(db, TemplateIn(name="Standard software quote", plan_id=plans["Software Monthly"].id, validity_days=30, payment_terms_days=14, discount_id=d1.id,
                                                notes="Prices exclude taxes unless stated.", lines=[TemplateLineIn(product_id=sw.id, variant_ids=[odoo], quantity=1)]), admin)
    db.commit()
    mk = lambda c, **kw: quotes.create_quotation(db, QuotationIn(customer_id=c.id, template_id=tpl.id, **kw), staff[0])  # noqa: E731
    mk(customers[0])
    q2 = mk(customers[1]); quotes.send(db, q2, staff[0])
    q3 = mk(customers[2], discount_id=d1.id); quotes.send(db, q3, staff[0]); quotes.confirm(db, q3, staff[0])
    q4 = mk(customers[3]); quotes.send(db, q4, staff[0]); quotes.confirm(db, q4, staff[0]); quotes.convert(db, q4, ConvertIn(term_periods=12), staff[0])
    db.commit()
    print(f"Seeded: {db.scalar(select(func.count()).select_from(User))} users, {db.scalar(select(func.count()).select_from(Subscription))} subscriptions, "
          f"{db.scalar(select(func.count()).select_from(Invoice))} invoices, {db.scalar(select(func.count()).select_from(Payment))} payments.")


def _nextvals(db, seq: str, n: int) -> list[int]:
    return [r[0] for r in db.execute(text(f"SELECT nextval('{seq}') FROM generate_series(1, {n})"))]


def seed_bulk(db, n: int) -> None:
    if IS_SQLITE:
        raise SystemExit("--bulk is a PostgreSQL performance-test tool (it uses sequences). Run it against PostgreSQL.")
    """Fast bulk load (executemany) of n ACTIVE subscriptions with history, for performance testing. Not realistic names/emails."""
    rnd = random.Random(42)
    today, now = date.today(), datetime.now(UTC)
    pw = hash_password("Customer@12345")  # one hash for every bulk user (argon2 per user would take minutes)
    plans = list(db.scalars(select(SubscriptionPlan)).unique())
    if not plans:
        raise SystemExit("Run the demo seed first (plans are needed).")
    n_cust = max(10, n // 5)
    cust_nums = _nextvals(db, "customer_number_seq", n_cust)
    users, profiles = [], []
    for i in range(n_cust):
        uid, pid = uuid.uuid4(), uuid.uuid4()
        users.append(dict(id=uid, email=f"bulk{i}@example.com", hashed_password=pw, full_name=f"Bulk Customer {i}", role="CUSTOMER", is_active=True))
        profiles.append(dict(id=pid, user_id=uid, customer_number=f"CUS-{cust_nums[i]:06d}"))
    db.execute(insert(User), users)
    db.execute(insert(CustomerProfile), profiles)

    sub_nums = _nextvals(db, "subscription_number_seq", n)
    subscriptions, lines, events, inv_rows = [], [], [], []
    for i in range(n):
        plan = rnd.choice(plans)
        cust = profiles[i % n_cust]
        start = today - timedelta(days=rnd.randint(30, 400 if plan.billing_frequency in (F.MONTHLY, F.YEARLY) else 90))
        status = rnd.choices([S.ACTIVE, S.PAUSED, S.CLOSED, S.EXPIRED], [80, 7, 8, 5])[0]
        qty = rnd.randint(1, 5)
        sid = uuid.uuid4()
        price = plan.price
        sub_total = q(price * qty)
        freq = plan.billing_frequency
        billed = 0
        while period_start(start, freq, billed) <= today:
            billed += 1  # periods 0..billed-1 have started, so next_billing_date is in the future
        subscriptions.append(dict(id=sid, number=f"SUB-{sub_nums[i]:06d}", customer_id=cust["id"], plan_id=plan.id, status=status.value, start_date=start,
                                  next_billing_date=period_start(start, freq, billed), billing_frequency=freq.value, payment_terms_days=14, periods_billed=billed,
                                  renewal_count=0, auto_renew=False, subtotal=sub_total, tax_total=Decimal("0.00"), total=sub_total,
                                  created_at=now - timedelta(days=(today - start).days)))
        lines.append(dict(id=uuid.uuid4(), subscription_id=sid, product_id=plan.product_id, description=plan.name, quantity=qty, unit_price=price, tax_rate=Decimal("0.00")))
        events.append(dict(id=uuid.uuid4(), subscription_id=sid, event_type="ACTIVATED", from_status="CONFIRMED", to_status="ACTIVE", created_at=now - timedelta(days=(today - start).days)))
        if status in (S.CLOSED, S.EXPIRED):
            events.append(dict(id=uuid.uuid4(), subscription_id=sid, event_type="CLOSED" if status == S.CLOSED else "AUTO_EXPIRED", to_status=status.value,
                               created_at=now - timedelta(days=rnd.randint(0, 25))))
        for k in range(min(billed, 3)):  # last three invoices per subscription
            inv_rows.append((sid, cust, plan, qty, start, freq, billed - 1 - k, price))
    db.execute(insert(Subscription), subscriptions)
    db.execute(insert(SubscriptionLine), lines)
    db.execute(insert(SubscriptionEvent), events)

    nums = _nextvals(db, "invoice_number_seq", len(inv_rows))
    invoices, inv_lines, pays = [], [], []
    for j, (sid, cust, plan, qty, start, freq, idx, price) in enumerate(inv_rows):
        ps = period_start(start, freq, idx)
        total = q(price * qty)
        status = rnd.choices([IS.PAID, IS.PARTIALLY_PAID, IS.CONFIRMED, IS.CANCELLED], [70, 8, 20, 2])[0]
        paid = total if status == IS.PAID else (q(total / 2) if status == IS.PARTIALLY_PAID else Decimal("0.00"))
        iid = uuid.uuid4()
        invoices.append(dict(id=iid, number=f"INV-{nums[j]:06d}", customer_id=cust["id"], subscription_id=sid, status=status.value, source="AUTO",
                             period_start=ps, issue_date=ps, due_date=ps + timedelta(days=14), payment_terms_days=14, currency="INR", subtotal=total, discount_total=Decimal("0.00"),
                             tax_total=Decimal("0.00"), total=total, amount_paid=paid, customer_snapshot={"name": f"Bulk {cust['customer_number']}"},
                             created_at=datetime.combine(ps, datetime.min.time(), tzinfo=UTC)))
        inv_lines.append(dict(id=uuid.uuid4(), invoice_id=iid, position=0, product_id=plan.product_id, description=plan.name, quantity=qty, unit_price=price,
                              line_subtotal=total, discount_amount=Decimal("0.00"), tax_rate=Decimal("0.00"), tax_amount=Decimal("0.00"), line_total=total))
        if paid > 0:
            pays.append(dict(id=uuid.uuid4(), invoice_id=iid, customer_id=cust["id"], method=rnd.choice(list(PM)).value, amount=paid, status="SUCCESS", provider="MANUAL",
                             payment_date=datetime.combine(ps, datetime.min.time(), tzinfo=UTC) + timedelta(days=rnd.randint(0, 10)),
                             created_at=datetime.combine(ps, datetime.min.time(), tzinfo=UTC)))
    for chunk in range(0, len(invoices), 5000):
        db.execute(insert(Invoice), invoices[chunk:chunk + 5000])
    for chunk in range(0, len(inv_lines), 5000):
        db.execute(insert(InvoiceLine), inv_lines[chunk:chunk + 5000])
    for chunk in range(0, len(pays), 5000):
        db.execute(insert(Payment), pays[chunk:chunk + 5000])
    db.commit()
    db.execute(text("ANALYZE"))
    print(f"Bulk: +{n_cust} customers, +{n} subscriptions, +{len(invoices)} invoices, +{len(pays)} payments.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="wipe all data first")
    ap.add_argument("--bulk", type=int, default=0, help="also add N subscriptions for performance testing")
    args = ap.parse_args()
    if get_settings().environment.lower() == "production":
        sys.exit("Refusing to seed demo data when ENVIRONMENT=production.")
    with SessionLocal() as db:
        if args.reset:
            reset(db)
        seed_demo(db)
        if args.bulk:
            seed_bulk(db, args.bulk)


if __name__ == "__main__":
    main()
