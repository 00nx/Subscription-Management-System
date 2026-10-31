import logging
from datetime import date

from app.core.database import SessionLocal
from app.modules.billing import service
from app.tasks.celery_app import celery_app

log = logging.getLogger(__name__)


@celery_app.task(name="billing.generate_due_invoices", bind=True, max_retries=5)
def generate_due_invoices(self):
    """Bills due subscriptions, then renews/expires finished terms. Idempotent, so running it twice is harmless.
    If any subscription failed it is retried with backoff, and (being still due) again on the next scheduled run."""
    result = service.run_billing()
    expiry = service.run_expiry(run_id=result.run_id)
    if result.failed:
        log.error("billing failures: %s", result.failed)
        raise self.retry(exc=RuntimeError(f"{len(result.failed)} subscription(s) failed to bill"), countdown=60 * 2 ** self.request.retries)
    return {"invoiced": result.invoiced, **expiry}


@celery_app.task(name="billing.send_payment_reminders")
def send_payment_reminders():
    with SessionLocal() as db:
        n = service.send_due_reminders(db, date.today())
        db.commit()
    return n


@celery_app.task(name="billing.detect_overdue_invoices")
def detect_overdue_invoices():
    with SessionLocal() as db:
        n = service.detect_overdue(db, date.today())
        db.commit()
    return n


@celery_app.task(name="billing.process_discount_expiry")
def process_discount_expiry():
    with SessionLocal() as db:
        out = service.process_discount_expiry(db, date.today())
        db.commit()
    return out
