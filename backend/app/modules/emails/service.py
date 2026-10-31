"""Email pipeline: queue_email() writes an EmailLog row inside the caller's transaction; once that transaction COMMITS the delivery is
handed to a background worker (Celery when the broker is reachable, otherwise a daemon thread). A rolled-back change therefore never
sends an email, and a slow SMTP server never delays an API response."""
import logging
import socket
import threading
import time
import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.email import send_email
from app.modules.emails.models import EmailLog
from app.modules.emails.templates import render

log = logging.getLogger(__name__)
_PENDING = "pending_emails"


def queue_email(db: Session, to: str, template: str, context: dict, entity_type: str | None = None, entity_id=None) -> EmailLog:
    subject, html, text = render(template, context)
    row = EmailLog(id=uuid.uuid4(), to_email=to, subject=subject[:255], template=template, html=html, text_body=text,
                   entity_type=entity_type, entity_id=str(entity_id) if entity_id else None)
    db.add(row)
    db.info.setdefault(_PENDING, []).append(row.id)
    return row


def requeue(db: Session, row: EmailLog) -> None:
    row.status, row.error = "QUEUED", None
    db.info.setdefault(_PENDING, []).append(row.id)


def deliver(log_id: uuid.UUID, factory=SessionLocal) -> bool:
    """Sends one email and records the outcome. Idempotent: an already SENT email is never sent twice."""
    with factory() as db:
        row = db.get(EmailLog, log_id)
        if row is None or row.status == "SENT":
            return True
        row.attempts += 1
        row.last_attempt_at = datetime.now(UTC)
        try:
            send_email(row.to_email, row.subject, row.text_body, html=row.html)
            row.status, row.sent_at, row.error = "SENT", datetime.now(UTC), None
        except Exception as exc:  # noqa: BLE001 - the failure is the data: kept on the row for the delivery log
            log.warning("email %s to %s failed: %s", log_id, row.to_email, exc)
            row.status, row.error = "FAILED", str(exc)[:500]
        db.commit()
        return row.status == "SENT"


_broker = {"at": 0.0, "up": False}


def _broker_up() -> bool:
    if time.monotonic() - _broker["at"] < 30:
        return _broker["up"]
    u = urlparse(get_settings().redis_url)
    try:
        with socket.create_connection((u.hostname or "localhost", u.port or 6379), timeout=0.3):
            up = True
    except OSError:
        up = False
    _broker.update(at=time.monotonic(), up=up)
    return up


def _dispatch(ids: list[uuid.UUID]) -> None:
    mode = get_settings().email_delivery
    if mode == "off":  # e.g. demo seeding: nothing is sent and the log says so
        with SessionLocal() as db:
            for i in ids:
                if (row := db.get(EmailLog, i)) is not None and row.status == "QUEUED":
                    row.status = "SUPPRESSED"
            db.commit()
        return
    if mode == "inline":
        for i in ids:
            deliver(i)
        return
    if mode in ("auto", "celery") and _broker_up():
        try:
            from app.tasks.email_tasks import deliver_email
            for i in ids:
                deliver_email.delay(str(i))
            return
        except Exception:  # noqa: BLE001 - broker trouble must never lose or block an email
            log.exception("could not hand emails to Celery; delivering in a thread")
    threading.Thread(target=lambda: [deliver(i) for i in ids], daemon=True, name="email-delivery").start()


@event.listens_for(Session, "after_commit")
def _after_commit(session: Session) -> None:
    if session.in_nested_transaction():  # releasing a SAVEPOINT also fires this event, but the real transaction is still open: not committed yet
        return
    ids = session.info.pop(_PENDING, None)
    if ids:
        _dispatch(ids)


@event.listens_for(Session, "after_rollback")
def _after_rollback(session: Session) -> None:
    session.info.pop(_PENDING, None)  # nothing was committed, so nothing is sent
