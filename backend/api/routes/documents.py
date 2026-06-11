import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.db.mysql import get_db
from backend.models import ParentDocument
from backend.auth.middleware import get_current_user
from backend.auth.jwt import decode_access_token
from fastapi.responses import Response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])

@router.get("/{doc_id}/pdf")
def get_document_pdf(
    doc_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    token: str | None = Query(default=None),
):
    if token:
        try:
            current_user = decode_access_token(token)
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
    doc = db.query(ParentDocument).filter_by(parent_id=doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    content = doc.content.encode("utf-8") if isinstance(doc.content, str) else doc.content
    return Response(content=content, media_type="application/pdf", headers={
        "Content-Disposition": f'inline; filename="{doc.filename}"'
    })
