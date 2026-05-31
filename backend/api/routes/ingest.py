# backend/api/routes/ingest.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from typing import List
import hashlib
import os
import uuid
from pathlib import Path
from db.sqlite import get_connection
from auth.middleware import require_team_role, require_auth

router = APIRouter(prefix="/team/{team_id}", tags=["ingestion"])

ALLOWED_TYPES = {
    "application/pdf": "pdf",
    "text/plain": "txt",
    "text/markdown": "md",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "image/png": "png",
    "image/jpeg": "jpeg",
    "image/webp": "webp"
}

@router.post("/ingest/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    team_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(require_team_role("lead"))
):
    # Read file and calculate SHA-256 hash for deduplication
    content = await file.read()
    content_hash = hashlib.sha256(content).hexdigest()
    
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}")
        
    doc_id = str(uuid.uuid4())
    upload_dir = Path(f"./data/uploads/{team_id}")
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    file_extension = ALLOWED_TYPES[file.content_type]
    storage_filename = f"{content_hash}.{file_extension}"
    storage_path = upload_dir / storage_filename
    
    # Save the file to disk
    with open(storage_path, "wb") as f:
        f.write(content)
        
    conn = get_connection()
    try:
        # Check duplicate in team
        duplicate = conn.execute(
            "SELECT doc_id FROM source_docs WHERE team_id = ? AND content_hash = ?",
            (team_id, content_hash)
        ).fetchone()
        
        if duplicate:
            raise HTTPException(status_code=400, detail="Document with same content already uploaded")
            
        conn.execute(
            "INSERT INTO source_docs (doc_id, team_id, filename, file_type, file_size, content_hash, storage_path, uploaded_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (doc_id, team_id, file.filename, file.content_type, len(content), content_hash, str(storage_path), current_user["user_id"])
        )
        conn.commit()
        return {"doc_id": doc_id, "filename": file.filename, "status": "success"}
    finally:
        conn.close()

@router.get("/docs")
async def list_documents(
    team_id: str,
    current_user: dict = Depends(require_team_role("user"))
):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT doc_id, filename, file_type, file_size, status, created_at FROM source_docs WHERE team_id = ?",
            (team_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
