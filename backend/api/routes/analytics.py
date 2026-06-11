import json
import logging
from fastapi import APIRouter, Depends
from backend.auth.middleware import require_global_role
from backend.agents.memory import get_redis_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["analytics"])


@router.get("/analytics")
def get_analytics(_: dict = Depends(require_global_role("superadmin"))):
    try:
        redis_client = get_redis_client()
        cached = redis_client.get("analytics:latest")
        if cached:
            return json.loads(cached)
    except Exception:
        logger.warning("Failed to read analytics from Redis", exc_info=True)
    return {"message": "No analytics data yet. First aggregation runs hourly."}
