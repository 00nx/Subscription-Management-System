from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings
from app.models import registry  # noqa: F401  (a worker never imports app.main, so register every model here)

celery_app = Celery("brightloop", broker=get_settings().redis_url, backend=get_settings().redis_url,
                    include=["app.tasks.sample_tasks", "app.tasks.billing_tasks", "app.tasks.email_tasks"])
celery_app.conf.update(
    task_serializer="json", result_serializer="json", accept_content=["json"], timezone="UTC", enable_utc=True,
    task_acks_late=True,  # a worker crash re-queues the task; tasks are idempotent so that is safe
    beat_schedule={
        # Billing is idempotent: hourly is cheap, and a missed run is simply caught up by the next one.
        "generate-due-invoices": {"task": "billing.generate_due_invoices", "schedule": crontab(minute=5)},
        "payment-reminders": {"task": "billing.send_payment_reminders", "schedule": crontab(hour=8, minute=0)},
        "overdue-detection": {"task": "billing.detect_overdue_invoices", "schedule": crontab(hour=0, minute=30)},
        "discount-expiry": {"task": "billing.process_discount_expiry", "schedule": crontab(hour=1, minute=0)},
    },
)
