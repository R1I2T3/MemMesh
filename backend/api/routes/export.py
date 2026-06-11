import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from backend.db.mysql import get_db
from backend.models import Message
from backend.auth.middleware import get_current_user
from backend.export.renderers import render_markdown, render_json, render_pdf

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["export"])


@router.post("/sessions/{session_id}/export")
def export_session(
    session_id: str,
    format: str = Query("md", pattern="^(md|json|pdf)$"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.get("user_id") or current_user.get("sub")
    messages = (
        db.query(Message)
        .filter(Message.session_id == session_id, Message.user_id == user_id)
        .order_by(Message.created_at.asc())
        .all()
    )

    if not messages:
        raise HTTPException(status_code=404, detail="Session not found")

    serialized = [
        {"role": m.role, "content": m.content, "citations": m.citations}
        for m in messages
    ]

    content_type_map = {"md": "text/markdown", "json": "application/json", "pdf": "application/pdf"}
    filename_map = {"md": f"{session_id}.md", "json": f"{session_id}.json", "pdf": f"{session_id}.pdf"}

    if format == "md":
        content = render_markdown(serialized, f"Session {session_id}")
    elif format == "json":
        content = render_json(serialized)
    elif format == "pdf":
        content = render_pdf(serialized, f"Session {session_id}")
    else:
        raise HTTPException(status_code=400, detail="Unsupported format")

    return Response(
        content=content,
        media_type=content_type_map[format],
        headers={"Content-Disposition": f'attachment; filename="{filename_map[format]}"'},
    )
