import os
from celery import Celery

# Configure Celery with Redis as the broker and backend
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "memmesh_tasks", broker=REDIS_URL, backend=REDIS_URL, include=["workers.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Here you could configure Celery Beat for the Cron Jobs (Memory Consolidation/Decay)
    beat_schedule={
        "daily-memory-decay": {
            "task": "workers.tasks.trigger_memory_decay",
            "schedule": 86400.0,  # Every 24 hours
        },
        "nightly-graph-deduplication": {
            "task": "workers.tasks.trigger_graph_deduplication",
            "schedule": 86400.0,
        },
    },
)
