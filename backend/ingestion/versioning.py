import hashlib
from sqlalchemy.orm import Session
from backend.db.mysql import SessionLocal
from backend.models import SourceDoc

def compute_content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

def detect_version_change(team_id: str, filename: str, new_hash: str, db: Session | None = None) -> dict | None:
    if db is None:
        db = SessionLocal()
        should_close = True
    else:
        should_close = False
    try:
        existing = db.query(SourceDoc).filter_by(
            team_id=team_id, file_name=filename
        ).with_for_update().order_by(SourceDoc.version_number.desc()).first()
        if existing and existing.content_hash != new_hash:
            return {
                "previous_version_id": existing.doc_id,
                "previous_version": existing.version_number,
                "new_version": existing.version_number + 1,
            }
        return None
    finally:
        if should_close:
            db.close()

def mark_superseded_chunks(weaviate_mgr, tenant_id: str, doc_id: str):
    """Mark old chunks as superseded in Weaviate."""
    pass
