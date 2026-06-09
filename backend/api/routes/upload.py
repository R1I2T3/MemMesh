import logging
from fastapi import APIRouter, Depends, HTTPException, Header, UploadFile, File
from sqlalchemy.orm import Session
from celery.result import AsyncResult
from backend.tasks.celery_app import celery_app

from backend.db.mysql import get_db
from backend.auth.middleware import get_current_user, require_team_role
from backend.models import Team, TeamMember, ParentDocument
from backend.config import settings
from backend.tasks.ingestion_worker import process_document_task

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["upload"])

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    x_active_team_id: str = Depends(require_team_role("team_lead")),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = current_user["sub"]

    # Validate file size
    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File size exceeds maximum allowed limit")

    # Dispatch ingestion task
    task = process_document_task.delay(content.hex(), file.filename, x_active_team_id, user_id)
    return {"status": "processing", "task_id": task.id}

@router.get("/upload/status/{task_id}")
def get_upload_status(task_id: str, current_user: dict = Depends(get_current_user)):
    res = AsyncResult(task_id, app=celery_app)
    if res.state == "SUCCESS":
        status = "completed"
    elif res.state == "FAILURE":
        status = "failed"
    else:
        status = "processing"
    return {"status": status}

@router.get("/teams")
def list_teams(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    user_id = current_user["sub"]
    role = current_user.get("role")

    if role == "superadmin":
        teams = db.query(Team).all()
    else:
        teams = db.query(Team).join(TeamMember).filter(TeamMember.user_id == user_id).all()

    return {"teams": [{"team_id": t.team_id, "name": t.name} for t in teams]}

@router.get("/documents")
def list_documents(
    x_active_team_id: str | None = Header(default=None, alias="X-Active-Team-ID"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not x_active_team_id:
        raise HTTPException(status_code=400, detail="Missing X-Active-Team-ID header")

    user_id = current_user["sub"]
    role = current_user.get("role")

    if role != "superadmin":
        membership = db.query(TeamMember).filter_by(team_id=x_active_team_id, user_id=user_id).first()
        if not membership:
            raise HTTPException(status_code=403, detail="Not authorized for this team")

    docs = db.query(ParentDocument).filter_by(team_id=x_active_team_id).all()
    return {
        "documents": [
            {
                "parent_id": d.parent_id,
                "filename": d.filename,
                "created_at": d.created_at.isoformat() if d.created_at else None
            }
            for d in docs
        ]
    }
