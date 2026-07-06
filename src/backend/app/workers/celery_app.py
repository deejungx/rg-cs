from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "auto_recruit_ai",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    timezone="UTC",
    include=["app.workers.tasks"],
)

import app.workers.tasks  # noqa: E402,F401
