from celery import Celery
from app.config import settings

celery_worker = Celery(
    "auth_project",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.email_tasks"], # Tasks ko register karo
)

celery_worker.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
)

# Ye line Celery ko batati hai ki yehi default app hai
celery_worker.set_default()