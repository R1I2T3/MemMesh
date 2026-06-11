import logging
from fastapi import APIRouter, Depends, HTTPException
from celery.result import AsyncResult

from backend.auth.middleware import require_global_role
from backend.tasks.celery_app import celery_app
from backend.tasks.decay_worker import decay_memory_weights
from backend.tasks.drift_worker import check_data_drift

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["decay"])

@router.post("/decay/trigger")
def trigger_decay(current_user: dict = Depends(require_global_role("superadmin"))):
    try:
        task = decay_memory_weights.delay()
        logger.info("Memory decay task triggered manually: %s", task.id)
        return {"status": "triggered", "task_id": task.id}
    except Exception as e:
        logger.error("Failed to trigger decay task: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to trigger task: {str(e)}")

@router.post("/drift/trigger")
def trigger_drift(current_user: dict = Depends(require_global_role("superadmin"))):
    try:
        task = check_data_drift.delay()
        logger.info("Data drift task triggered manually: %s", task.id)
        return {"status": "triggered", "task_id": task.id}
    except Exception as e:
        logger.error("Failed to trigger drift task: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to trigger task: {str(e)}")

@router.get("/decay/status/{task_id}")
def get_decay_status(task_id: str, current_user: dict = Depends(require_global_role("superadmin"))):
    try:
        res = AsyncResult(task_id, app=celery_app)
        return {
            "status": res.state,
            "task_id": task_id,
            "result": res.result if res.ready() else None
        }
    except Exception as e:
        logger.error("Failed to fetch task status for %s: %s", task_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to get task status: {str(e)}")
