import logging
from backend.tasks.celery_app import celery_app
from backend.db.mysql import SessionLocal
from backend.models import UserFeedback

logger = logging.getLogger(__name__)

@celery_app.task(name="backend.tasks.drift_worker.check_data_drift")
def check_data_drift() -> dict:
    logger.info("Starting semantic/data drift detection task...")
    
    db = SessionLocal()
    try:
        feedbacks = db.query(UserFeedback).order_by(UserFeedback.created_at.desc()).all()
    except Exception as e:
        logger.error("Failed to query feedback from MySQL: %s", e)
        raise
    finally:
        db.close()

    total = len(feedbacks)
    logger.info("Found %d user feedback record(s) for drift evaluation.", total)
    
    if total < 2:
        logger.info("Insufficient feedback data to calculate drift metrics.")
        return {"drift_detected": False, "reason": "Insufficient data (total < 2)"}
    
    half_size = min(50, total // 2)
    last_group = feedbacks[:half_size]
    prev_group = feedbacks[half_size:2*half_size]
    
    # 1. Calculate average query length
    avg_len_last = sum(len(f.query or "") for f in last_group) / len(last_group)
    avg_len_prev = sum(len(f.query or "") for f in prev_group) / len(prev_group)
    
    # 2. Calculate average rating
    ratings_last = [f.rating for f in last_group if f.rating is not None]
    ratings_prev = [f.rating for f in prev_group if f.rating is not None]
    avg_rating_last = sum(ratings_last) / len(ratings_last) if ratings_last else 0.0
    avg_rating_prev = sum(ratings_prev) / len(ratings_prev) if ratings_prev else 0.0
    
    len_diff = abs(avg_len_last - avg_len_prev)
    rating_diff = abs(avg_rating_last - avg_rating_prev)
    
    logger.info(
        "Drift metrics: avg_len(last=%s, prev=%s, diff=%s), avg_rating(last=%s, prev=%s, diff=%s)",
        avg_len_last, avg_len_prev, len_diff,
        avg_rating_last, avg_rating_prev, rating_diff
    )
    
    # Set thresholds
    LEN_THRESHOLD = 15.0
    RATING_THRESHOLD = 0.5
    
    drift_detected = False
    if len_diff > LEN_THRESHOLD or rating_diff > RATING_THRESHOLD:
        drift_detected = True
        logger.warning(
            "Data drift detected! len_diff=%s (threshold=%s), rating_diff=%s (threshold=%s)",
            len_diff, LEN_THRESHOLD, rating_diff, RATING_THRESHOLD
        )
        
    return {
        "drift_detected": drift_detected,
        "metrics": {
            "avg_length_last": avg_len_last,
            "avg_length_prev": avg_len_prev,
            "length_difference": len_diff,
            "avg_rating_last": avg_rating_last,
            "avg_rating_prev": avg_rating_prev,
            "rating_difference": rating_diff
        }
    }
