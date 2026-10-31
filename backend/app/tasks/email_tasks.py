import uuid

from app.modules.emails import service
from app.tasks.celery_app import celery_app


@celery_app.task(name="emails.deliver", bind=True, max_retries=3)
def deliver_email(self, log_id: str):
    """Delivers one queued email; a failure is recorded on the log and retried with backoff (1, 2, 4 minutes)."""
    if not service.deliver(uuid.UUID(log_id)):
        raise self.retry(countdown=60 * 2 ** self.request.retries)
    return "sent"
