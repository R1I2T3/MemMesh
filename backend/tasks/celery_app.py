from celery import Celery
from backend.config import settings

celery_app = Celery(
    "memmesh_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["backend.tasks.ingestion_worker"]
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Acknowledge task only AFTER completion; re-queues on worker crash mid-parse.
    task_acks_late=True,
    # Prevent memory pressure: fetch one task at a time per worker process.
    worker_prefetch_multiplier=1,
)
