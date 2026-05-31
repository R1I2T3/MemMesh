# backend/api/routes/ingest.py
import hashlib
import sqlite3
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from pydantic import BaseModel

from auth.middleware import require_team_role
from db.sqlite import get_db

router = APIRouter(prefix="/team/{team_id}", tags=["ingestion"])

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
BASE_UPLOAD_DIR = Path("./data/uploads").resolve()

ALLOWED_TYPES = {
    "application/pdf": "pdf",
    "text/plain": "txt",
    "text/markdown": "md",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "image/png": "png",
    "image/jpeg": "jpeg",
    "image/webp": "webp"
}


class UploadResponse(BaseModel):
    doc_id: str
    filename: str
    status: str


class DocListItem(BaseModel):
    doc_id: str
    filename: str
    file_type: str
    file_size: int
    status: str
    created_at: str


@router.post("/ingest/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    team_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(require_team_role("lead")),
    conn: sqlite3.Connection = Depends(get_db),
):
    """Upload a document to the team's knowledge base. Restricted to Team Leads."""
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file.content_type}"
        )

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {MAX_UPLOAD_BYTES // (1024*1024)} MB"
        )

    content_hash = hashlib.sha256(content).hexdigest()

    # Check for duplicate BEFORE writing to disk
    duplicate = conn.execute(
        "SELECT doc_id FROM source_docs WHERE team_id = ? AND content_hash = ?",
        (team_id, content_hash)
    ).fetchone()
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document with same content already uploaded"
        )

    # Path traversal guard: ensure resolved path stays within BASE_UPLOAD_DIR
    upload_dir = (BASE_UPLOAD_DIR / team_id).resolve()
    if not upload_dir.is_relative_to(BASE_UPLOAD_DIR):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid team identifier"
        )
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_extension = ALLOWED_TYPES[file.content_type]
    storage_path = upload_dir / f"{content_hash}.{file_extension}"
    storage_path.write_bytes(content)

    doc_id = str(uuid.uuid4())
    with conn:
        conn.execute(
            "INSERT INTO source_docs "
            "(doc_id, team_id, filename, file_type, file_size, content_hash, storage_path, uploaded_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (doc_id, team_id, file.filename, file.content_type,
             len(content), content_hash, str(storage_path), current_user["user_id"])
        )

    return UploadResponse(doc_id=doc_id, filename=file.filename, status="success")


@router.get("/docs", response_model=list[DocListItem])
async def list_documents(
    team_id: str,
    current_user: dict = Depends(require_team_role("user")),
    conn: sqlite3.Connection = Depends(get_db),
):
    """List all documents uploaded to the team's knowledge base."""
    rows = conn.execute(
        "SELECT doc_id, filename, file_type, file_size, status, created_at "
        "FROM source_docs WHERE team_id = ? ORDER BY created_at DESC",
        (team_id,)
    ).fetchall()
    return [DocListItem(**dict(r)) for r in rows]
