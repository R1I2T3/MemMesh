import json
import logging
from datetime import datetime, timedelta, timezone
from backend.tasks.celery_app import celery_app
from sqlalchemy import func, case
from backend.db.mysql import SessionLocal
from backend.models import AuditLog, UserFeedback
from backend.agents.memory import get_redis_client

logger = logging.getLogger(__name__)


@celery_app.task(name="backend.tasks.analytics_worker.aggregate_hourly")
def aggregate_hourly(db=None):
    close_db = db is None
    if db is None:
        db = SessionLocal()
    now = datetime.now(timezone.utc)
    hour_ago = now - timedelta(hours=1)
    day_ago = now - timedelta(days=1)

    queries_last_hour = db.query(AuditLog).filter(AuditLog.created_at >= hour_ago).count()
    queries_last_day = db.query(AuditLog).filter(AuditLog.created_at >= day_ago).count()

    avg_latency = db.query(func.avg(AuditLog.latency_ms)).filter(AuditLog.created_at >= hour_ago).scalar() or 0

    unique_users = db.query(AuditLog.user_id).filter(AuditLog.created_at >= day_ago).distinct().count()

    feedback_ratings = db.query(
        func.sum(case((UserFeedback.rating == 1, 1), else_=0)),
        func.count(UserFeedback.feedback_id)
    ).filter(UserFeedback.created_at >= day_ago).first()

    result = {
        "timestamp": now.isoformat(),
        "queries_last_hour": queries_last_hour,
        "queries_last_day": queries_last_day,
        "avg_latency_ms": round(float(avg_latency), 2),
        "unique_users_last_day": unique_users,
        "positive_feedback": feedback_ratings[0] or 0,
        "total_feedback": feedback_ratings[1] or 0,
    }

    try:
        redis_client = get_redis_client()
        redis_client.set("analytics:latest", json.dumps(result), ex=7200)
    except Exception:
        logger.warning("Failed to cache analytics in Redis", exc_info=True)

    if close_db:
        db.close()
    return result
