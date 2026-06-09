import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from backend.db.mysql import get_db
from backend.models import UserFeedback
from backend.auth.middleware import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["feedback"])

class FeedbackCreate(BaseModel):
    query: str
    response: str
    rating: int = Field(..., description="Rating must be 1 (up) or -1 (down)")
    trace_id: str

@router.post("/feedback")
def submit_feedback(
    payload: FeedbackCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.rating not in (1, -1):
        raise HTTPException(status_code=400, detail="Rating must be 1 or -1")

    feedback_id = str(uuid.uuid4())
    feedback = UserFeedback(
        feedback_id=feedback_id,
        query=payload.query,
        response=payload.response,
        rating=payload.rating,
        trace_id=payload.trace_id,
    )
    db.add(feedback)
    db.commit()
    logger.info(f"Feedback {feedback_id} submitted by user {current_user.get('sub')} with rating {payload.rating}")
    return {"status": "submitted", "feedback_id": feedback_id}
