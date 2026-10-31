from celery import Celery

from app.core.config import get_settings

celery_app = Celery("brightloop", broker=get_settings().redis_url, backend=get_settings().redis_url,
                    include=["app.tasks.sample_tasks"])
celery_app.conf.update(task_serializer="json", result_serializer="json", accept_content=["json"], timezone="UTC")
