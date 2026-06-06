# Phase 9 — Historical Pipeline Traces: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement database persistence for multi-stage RAG query traces, backend retrieval endpoints, and an interactive historical trace viewer inside the SvelteKit Pipeline Lens.

**Architecture:** An SQLite migration introduces the `pipeline_traces` table linked to turns and sessions. After completing query synthesis, the backend compiles all collected pipeline stages (routing, rewriting, hits, reranking, synthesis) and writes the unified trace as a JSON payload to SQLite. Specialized endpoints expose historical traces. When a user selects an assistant message from history, SvelteKit fetches and paints the recorded execution metrics to the Pipeline Lens in historical review mode.

**Tech Stack:** Python 3.11+, FastAPI, SQLite, SvelteKit, HSL visual timeline components

---

## Scope Note

This plan builds directly on **Phase 6** (Pipeline Lens) and **Phase 7** (Hybrid RAG). It shifts RAG diagnostics from transient session states into robust database-stored telemetry.

---

## File Structure

### Backend New/Modified Files

```
backend/
├── db/
│   └── migrations/
│       └── 006_pipeline_traces.sql             # Create: Migration for trace persistence table
├── api/
│   └── routes/
│       └── query.py                            # Modify: Update to save metrics trace after final token
├── api/
│   └── routes/
│       └── traces.py                           # Create: Endpoints to load past session/turn traces
└── tests/
    └── test_traces_api.py                      # Create: Unit & Integration verification for traces
```

### Frontend New/Modified Files

```
frontend/
├── src/
│   └── routes/
│       └── dashboard/
│           ├── chat-window.svelte              # Modify: Trigger lens reload on past message click
│           ├── pipeline-lens.svelte            # Modify: Handle historical trace review state
│           └── trace-exporter.svelte           # Create: Widget to download or copy raw trace JSON
```

---

## Group A: Trace Telemetry Storage

### Task 1: SQLite Traces Persistence

**Files:**
- Create: `backend/db/migrations/006_pipeline_traces.sql`

- [ ] **Step 1: Write migration SQL**

Create `backend/db/migrations/006_pipeline_traces.sql`:

```sql
-- backend/db/migrations/006_pipeline_traces.sql
CREATE TABLE pipeline_traces (
    trace_id    TEXT PRIMARY KEY,
    turn_id     TEXT NOT NULL REFERENCES turns(turn_id) ON DELETE CASCADE,
    session_id  TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    team_id     TEXT NOT NULL REFERENCES teams(team_id) ON DELETE CASCADE,
    trace_data  TEXT NOT NULL, -- JSON payload mapping stages, metrics, and hits
    created_at  DATETIME NOT NULL DEFAULT (datetime('now'))
);
```

- [ ] **Step 2: Apply migration**

Run: `cd backend && make reset-db`
Expected: Rebuild database with 6 migrations success.

- [ ] **Step 3: Commit**

```bash
git add db/migrations/006_pipeline_traces.sql
git commit -m "migration: add pipeline_traces SQLite table schema"
```

---

### Task 2: Persist Telemetry Traces on Query Completion

**Files:**
- Modify: `backend/api/routes/query.py`

- [ ] **Step 1: Update response syntheses loop**

Modify the endpoint in `backend/api/routes/query.py` to capture and commit the telemetry traces to SQLite at the end of the generator stream:

```python
# backend/api/routes/query.py (partial diff)
import json
import uuid
from db.sqlite import get_connection

# In the stream generator loop, capture each stage event:
async def stream_and_record_trace(query, team_id, user_id, session_id, turn_id):
    ctx = PipelineContext(team_id, user_id, session_id)
    
    # Run through the pipeline stages, appending to ctx.events...
    # At the end of the streaming yield:
    
    trace_id = str(uuid.uuid4())
    trace_json = json.dumps([e.dict() for e in ctx.events])
    
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO pipeline_traces (trace_id, turn_id, session_id, team_id, trace_data) "
            "VALUES (?, ?, ?, ?, ?)",
            (trace_id, turn_id, session_id, team_id, trace_json)
        )
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 2: Commit**

```bash
git add api/routes/query.py
git commit -m "feat: persist multi-stage trace metrics to SQLite at stream completion"
```

---

### Task 3: Trace Retrieval Endpoints

**Files:**
- Create: `backend/api/routes/traces.py`
- Modify: `backend/api/server.py`

- [ ] **Step 1: Write API routes**

Create `backend/api/routes/traces.py`:

```python
# backend/api/routes/traces.py
from fastapi import APIRouter, Depends, HTTPException, status
from db.sqlite import get_connection
from auth.middleware import require_team_role

router = APIRouter(prefix="/team/{team_id}/traces", tags=["traces"])

@router.get("/turn/{turn_id}")
async def get_turn_trace(
    team_id: str,
    turn_id: str,
    current_user: dict = Depends(require_team_role("user"))
):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT trace_data FROM pipeline_traces WHERE team_id = ? AND turn_id = ?",
            (team_id, turn_id)
        ).fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Trace record not found")
            
        return {"trace_data": json.loads(row["trace_data"])}
    finally:
        conn.close()
```

- [ ] **Step 2: Register API router**

Modify `backend/api/server.py` to add `traces_router`.

- [ ] **Step 3: Commit**

```bash
git add api/routes/traces.py api/server.py
git commit -m "feat: implement historical trace loading REST endpoints"
```

---

## Group B: Frontend Historical Explorer

### Task 4: Interactive Historical Lens

**Files:**
- Modify: `frontend/src/routes/dashboard/chat-window.svelte`
- Modify: `frontend/src/routes/dashboard/pipeline-lens.svelte`
- Create: `frontend/src/routes/dashboard/trace-exporter.svelte`

- [ ] **Step 1: Chat timeline past event hook**

Modify `frontend/src/routes/dashboard/chat-window.svelte` to bind click listeners on past assistant messages, triggering requests to fetch and load past execution trace metadata.

- [ ] **Step 2: Add trace export widget**

Create `frontend/src/routes/dashboard/trace-exporter.svelte` to render a JSON tree explorer inside the Lens side bar, complete with one-click clipboard copy and raw JSON export capabilities.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/routes/dashboard/
git commit -m "feat: enable historical lens reviews, visual export widgets, and keyboard navigations"
```

---

## Group C: Validation

### Task 5: Telemetry Verification

**Files:**
- Create: `frontend/tests/e2e/traces.spec.ts`

- [ ] **Step 1: Write Playwright E2E spec**

Create `frontend/tests/e2e/traces.spec.ts` demonstrating that sending a query, refreshing the page, and clicking past responses correctly paints past timeline stages.

- [ ] **Step 2: Execute checks**

Run: `cd frontend && npx playwright test`
Expected: E2E telemetry specs execute successfully.

- [ ] **Step 3: Commit**

```bash
git add frontend/tests/e2e/traces.spec.ts
git commit -m "test: add Playwright E2E telemetry trace review verification"
```
