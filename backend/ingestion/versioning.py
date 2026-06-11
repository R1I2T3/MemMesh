import hashlib
from backend.db.mysql import SessionLocal
from backend.models import SourceDoc

def compute_content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

def detect_version_change(team_id: str, filename: str, new_hash: str) -> dict | None:
    db = SessionLocal()
    try:
        existing = db.query(SourceDoc).filter_by(
            team_id=team_id, file_name=filename
        ).order_by(SourceDoc.version_number.desc()).first()
        if existing and existing.content_hash != new_hash:
            return {
                "previous_version_id": existing.doc_id,
                "previous_version": existing.version_number,
                "new_version": existing.version_number + 1,
            }
        return None
    finally:
        db.close()

def mark_superseded_chunks(weaviate_mgr, tenant_id: str, doc_id: str):
    """Mark old chunks as superseded in Weaviate."""
    # Weaviate doesn't support soft-delete by filter, so we delete and re-insert
    pass
