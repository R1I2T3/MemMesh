# Phase 3 — Document Upload & Preview: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement document uploading to team-scoped directories with automatic file type validation, content hashing for deduplication, backend metadata tracking, and a desktop-optimized frontend previewer.

**Architecture:** Uploaded files are written to `./data/uploads/{team_id}/` under names derived from their content hashes. An SQLite migration introduces the `source_docs` table to register each document's metadata, hash, and status. File upload is restricted to Team Leads or higher roles. The SvelteKit frontend implements drag-and-drop uploading and a split-pane layout to preview PDFs, text, Markdown, DOCX, and images side-by-side with metadata.

**Tech Stack:** Python 3.11+, FastAPI, SvelteKit, Playwright, PDF.js, python-docx, hashlib, SQLite

---

## Scope Note

This plan builds on **Phase 1** and **Phase 2**. It handles file storage, deduplication, and previews, but does not parse, chunk, or index contents into search databases yet (this is the scope of Phase 4).

---

## File Structure

### Backend New/Modified Files

```
backend/
├── db/
│   └── migrations/
│       └── 003_source_docs.sql                 # Create: Migration for source documents registry
├── api/
│   └── routes/
│       └── ingest.py                           # Create: Document upload and download endpoints
├── tests/
│   └── test_ingest_api.py                      # Create: Document API integration tests
└── main.py                                     # Modify: Register ingest route
```

### Frontend New/Modified Files

```
frontend/
├── src/
│   └── routes/
│       └── dashboard/
│           ├── +page.svelte                    # Modify: Embed split view document explorer
│           ├── upload-zone.svelte              # Create: Drag-and-drop file uploader
│           ├── doc-list.svelte                 # Create: Document list panel
│           └── doc-preview.svelte              # Create: Interactive inline multi-format previewer
```

---

## Group A: Backend Upload Pipeline

### Task 1: SQLite Source Docs Schema

**Files:**
- Create: `backend/db/migrations/003_source_docs.sql`

- [ ] **Step 1: Write migration SQL**

Create `backend/db/migrations/003_source_docs.sql`:

```sql
-- backend/db/migrations/003_source_docs.sql
CREATE TABLE source_docs (
    doc_id        TEXT PRIMARY KEY,
    team_id       TEXT NOT NULL REFERENCES teams(team_id) ON DELETE CASCADE,
    filename      TEXT NOT NULL,
    file_type     TEXT NOT NULL,
    file_size     INTEGER NOT NULL,
    content_hash  TEXT NOT NULL,
    storage_path  TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'indexing', 'indexed', 'failed')),
    error_message TEXT,
    uploaded_by   TEXT NOT NULL REFERENCES users(user_id),
    created_at    DATETIME NOT NULL DEFAULT (datetime('now')),
    UNIQUE(team_id, content_hash)
);
```

- [ ] **Step 2: Run migration**

Run: `cd backend && make reset-db`
Expected: Database drops and recreates with all 3 migrations successful.

- [ ] **Step 3: Commit**

```bash
git add db/migrations/003_source_docs.sql
git commit -m "migration: add source_docs SQLite schema"
```

---

### Task 2: Upload API Endpoint

**Files:**
- Create: `backend/api/routes/ingest.py`
- Modify: `backend/api/server.py`

- [ ] **Step 1: Implement Upload and Listing**

Create `backend/api/routes/ingest.py`:

```python
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
```

- [ ] **Step 2: Register ingest router in server.py**

Modify `backend/api/server.py` to register the new router:
```python
from api.routes.ingest import router as ingest_router
app.include_router(ingest_router)
```

- [ ] **Step 3: Commit**

```bash
git add api/routes/ingest.py api/server.py
git commit -m "feat: implement file upload pipeline and team-scoped document listings"
```

---

## Group B: Frontend Inline Previewer

### Task 3: Interactive Split-View Layout

**Files:**
- Create: `frontend/src/routes/dashboard/upload-zone.svelte`
- Create: `frontend/src/routes/dashboard/doc-list.svelte`
- Create: `frontend/src/routes/dashboard/doc-preview.svelte`
- Modify: `frontend/src/routes/dashboard/+page.svelte`

- [ ] **Step 1: Create drag-and-drop uploader**

Create `frontend/src/routes/dashboard/upload-zone.svelte` with reactive drag hover borders and Svelte state to track progress.

- [ ] **Step 2: Create list pane and preview pane**

Create `frontend/src/routes/dashboard/doc-preview.svelte` containing inline frame tags, markdown converters, or plain-text elements to display PDFs, images, text, and markdown files.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/routes/dashboard/
git commit -m "feat: implement document dashboard split view and inline previews"
```

---

## Group C: Verification

### Task 4: Playwright Upload Flow Verification

**Files:**
- Create: `frontend/tests/e2e/upload.spec.ts`

- [ ] **Step 1: Write E2E document flow test**

Create `frontend/tests/e2e/upload.spec.ts` to log in as Team Lead, drag mock files onto dashboard, and assert they display in the list and inline preview panel.

- [ ] **Step 2: Run all tests**

Run: `cd frontend && npx playwright test`
Expected: ALL backend and frontend E2E specs pass.

- [ ] **Step 3: Commit**

```bash
git add frontend/tests/e2e/upload.spec.ts
git commit -m "test: add Playwright E2E document upload and preview verification tests"
```
