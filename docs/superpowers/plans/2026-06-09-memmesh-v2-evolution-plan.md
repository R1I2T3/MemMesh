# MemMesh V2 Evolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 17 architectural problems and add 11 new features to MemMesh across 5 implementation phases.

**Architecture:** Foundation fixes first (SSE streaming, API design, MySQL schema, Neo4j isolation, RBAC, security), then observability features (eval dashboard, analytics, audit), then document intelligence (versioning, annotations, PDF viewer), then integrations (email, sync, caching), then knowledge layer (graph visualizer, export).

**Tech Stack:** Python/FastAPI, React/TanStack, MySQL, Neo4j, Weaviate, Redis, Celery, Docker

---

## Phase 0: Foundation Fixes

### Task 0.1: Real SSE Streaming with LangGraph Async

**Files:**
- Modify: `backend/agents/graph_orchestrator.py`
- Modify: `backend/api/routes/query.py`
- Create: `backend/agents/telemetry.py`
- Test: `backend/tests/test_query.py`

- [ ] **Step 1: Create telemetry event types**

Create `backend/agents/telemetry.py`:

```python
from typing import Any, Dict, List
import json
import time

class TelemetryEvent:
    def __init__(self, stage: str, status: str, **kwargs):
        self.payload = {
            "type": "telemetry",
            "stage": stage,
            "status": status,
            "timestamp": time.time(),
            **kwargs
        }

    def to_sse(self) -> str:
        return f"data: {json.dumps(self.payload)}\n\n"

class TextChunkEvent:
    def __init__(self, content: str):
        self.payload = {"type": "text_chunk", "content": content}

    def to_sse(self) -> str:
        return f"data: {json.dumps(self.payload)}\n\n"

class CitationEvent:
    def __init__(self, source: str, doc_name: str = "", page: int = 0, url: str = "", triple: List[str] = None):
        payload = {"type": "citation", "source": source}
        if doc_name: payload["doc_name"] = doc_name
        if page: payload["page"] = page
        if url: payload["url"] = url
        if triple: payload["triple"] = triple
        self.payload = payload

    def to_sse(self) -> str:
        return f"data: {json.dumps(self.payload)}\n\n"

class SessionEvent:
    def __init__(self, session_id: str):
        self.payload = {"type": "session", "session_id": session_id}

    def to_sse(self) -> str:
        return f"data: {json.dumps(self.payload)}\n\n"

class DoneEvent:
    def to_sse(self) -> str:
        return "data: {\"type\": \"done\"}\n\n"

class ErrorEvent:
    def __init__(self, detail: str):
        self.payload = {"type": "error", "detail": detail}

    def to_sse(self) -> str:
        return f"data: {json.dumps(self.payload)}\n\n"
```

- [ ] **Step 2: Update graph orchestrator to yield events**

Modify `backend/agents/graph_orchestrator.py`:

Add async event emission wrappers around each node. Replace the synchronous `get_graph()` with:

```python
import asyncio
from typing import AsyncGenerator, List
from backend.agents.telemetry import (
    TelemetryEvent, TextChunkEvent, CitationEvent,
    SessionEvent, DoneEvent, ErrorEvent
)

async def ainvoke_with_events(state: AgentState) -> AsyncGenerator[str, None]:
    graph = get_graph()

    yield TelemetryEvent("input_guard", "checking query safety").to_sse()
    yield TelemetryEvent("rewriter", "generating query variants").to_sse()

    result = await graph.ainvoke(state)

    yield TelemetryEvent("router", f"routed to {result.get('route', 'hybrid')}").to_sse()

    yield TelemetryEvent("crag_eval", "evaluating relevance").to_sse()
    crag_pass = result.get("relevance_pass", True)
    if not crag_pass:
        yield TelemetryEvent("crag_eval", "relevance below threshold - triggering web search").to_sse()

    yield TelemetryEvent("synthesis", "generating response").to_sse()

    raw = result.get("raw_response", "")
    for chunk in _chunk_text(raw):
        yield TextChunkEvent(chunk).to_sse()
        await asyncio.sleep(0)

    for citation in result.get("citations", []):
        yield CitationEvent(
            source=citation.get("source", "vector"),
            doc_name=citation.get("doc_name", ""),
            page=citation.get("page_number", 0),
            url=citation.get("url", ""),
            triple=citation.get("triple", None)
        ).to_sse()

    yield SessionEvent(state["session_id"]).to_sse()
    yield DoneEvent().to_sse()

def _chunk_text(text: str, size: int = 5) -> List[str]:
    words = text.split()
    for i in range(0, len(words), size):
        yield " ".join(words[i:i+size]) + " "
```

- [ ] **Step 3: Rewrite stream endpoint to use async generator**

Replace `backend/api/routes/query.py` lines 144-280:

```python
@router.post("/query/stream")
async def run_query_stream(
    payload: QueryRequest,
    x_active_team_id: str | None = Header(default=None, alias="X-Active-Team-ID"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from fastapi.responses import StreamingResponse
    from backend.agents.graph_orchestrator import ainvoke_with_events

    user_id = current_user.get("user_id") or current_user.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    validated_q = await run_in_threadpool(validate_query, payload.query)

    history = _load_history(db, payload.session_id, payload.parent_msg_id, user_id)

    state = {
        "query": validated_q,
        "history": history,
        "session_id": payload.session_id,
        "active_team_id": x_active_team_id or "default-team",
        "user_id": user_id,
        "rewritten_queries": [],
        "route": "",
        "retrieved_chunks": [],
        "retrieved_triples": [],
        "web_search_results": [],
        "final_context": [],
        "raw_response": "",
        "citations": [],
        "relevance_pass": True
    }

    async def event_stream():
        async for event in ainvoke_with_events(state):
            yield event

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

- [ ] **Step 4: Add QueryRequest Pydantic model**

Add to top of `backend/api/routes/query.py`:

```python
from pydantic import BaseModel

class QueryRequest(BaseModel):
    query: str
    session_id: str = "default-session"
    parent_msg_id: str | None = None
```

- [ ] **Step 5: Write test for SSE streaming**

In `backend/tests/test_query.py`:

```python
@pytest.mark.asyncio
@patch("backend.api.routes.query.RedisMemory")
@patch("backend.api.routes.query.ainvoke_with_events")
async def test_streaming_endpoint(mock_ainvoke, mock_redis_cls):
    from backend.agents.telemetry import TelemetryEvent, TextChunkEvent, DoneEvent

    async def mock_events(state):
        yield TelemetryEvent("router", "routing to hybrid").to_sse()
        yield TextChunkEvent("Hello").to_sse()
        yield DoneEvent().to_sse()

    mock_ainvoke.return_value = mock_events({})

    mock_redis = MagicMock()
    mock_redis_cls.return_value = mock_redis
    mock_redis.get_history.return_value = []

    headers = get_auth_headers()
    res = client.post(
        "/api/query/stream",
        json={"query": "hello", "session_id": "test-session"},
        headers=headers
    )
    assert res.status_code == 200
    body = res.text
    assert "telemetry" in body
    assert "text_chunk" in body
    assert "done" in body
```

- [ ] **Step 6: Run test to verify passes**

Run: `cd backend && uv run pytest tests/test_query.py::test_streaming_endpoint -v`

- [ ] **Step 7: Commit**

```bash
git add backend/agents/telemetry.py backend/agents/graph_orchestrator.py backend/api/routes/query.py
git commit -m "feat: real SSE streaming with LangGraph async and telemetry events"
```

---

### Task 0.2: API Design — POST /api/query + X-Active-Team-ID

**Files:**
- Modify: `backend/api/routes/query.py`
- Modify: `frontend/src/routes/_dashboard.chat.tsx`
- Modify: `frontend/src/lib/api.ts`
- Modify: `backend/api/routes/auth.py`
- Test: `backend/tests/test_query.py`

- [ ] **Step 1: Change GET /api/query to POST**

Replace existing `GET /api/query`:

```python
@router.post("/query", status_code=200)
def run_query(
    payload: QueryRequest,
    x_active_team_id: str | None = Header(default=None, alias="X-Active-Team-ID"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id") or current_user.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    validated_q = validate_query(payload.query)
    history = _load_history(db, payload.session_id, payload.parent_msg_id, user_id)

    graph = get_graph()
    result = graph.invoke({
        "query": validated_q,
        "history": history,
        "session_id": payload.session_id,
        "active_team_id": x_active_team_id or "default-team",
        "user_id": user_id,
        "rewritten_queries": [],
        "route": "",
        "retrieved_chunks": [],
        "retrieved_triples": [],
        "web_search_results": [],
        "final_context": [],
        "raw_response": "",
        "citations": [],
        "relevance_pass": True
    })

    validated_response = validate_output(result.get("raw_response", ""))
    msg_ids = _save_messages(db, payload.session_id, payload.parent_msg_id, user_id, validated_q, validated_response, result.get("citations", []))
    _save_to_redis(payload.session_id, payload.parent_msg_id, validated_q, validated_response)

    return {
        "response": validated_response,
        "message_id": msg_ids["assistant"],
        "user_message_id": msg_ids["user"],
        "session_id": payload.session_id,
        "parent_message_id": msg_ids["user"],
        "citations": result.get("citations", [])
    }
```

- [ ] **Step 2: Add auth/register and auth/refresh endpoints**

In `backend/api/routes/auth.py`:

```python
class RegisterRequest(BaseModel):
    email: str
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

@router.post("/register", status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter_by(email=payload.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        user_id=str(uuid.uuid4()),
        email=payload.email,
        password_hash=hash_password(payload.password),
        global_role="user"
    )
    db.add(user)
    db.commit()
    return {"user_id": user.user_id, "email": user.email}

@router.post("/refresh")
def refresh(payload: RefreshRequest):
    try:
        decoded = decode_access_token(payload.refresh_token)
        new_token = create_access_token({
            "sub": decoded["sub"],
            "email": decoded.get("email"),
            "role": decoded.get("role")
        })
        return {"token": new_token}
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
```

- [ ] **Step 3: Add register endpoint imports**

Add to top of `backend/api/routes/auth.py`:

```python
import uuid
from backend.auth.passwords import hash_password
```

- [ ] **Step 4: Update frontend API client**

In `frontend/src/lib/api.ts`, add:

```typescript
export function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('token');
  const teamId = localStorage.getItem('active_team_id');
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (teamId) headers['X-Active-Team-ID'] = teamId;
  return headers;
}

export async function postQuery(query: string, sessionId: string, parentMsgId?: string) {
  const body: any = { query, session_id: sessionId };
  if (parentMsgId) body.parent_msg_id = parentMsgId;
  return fetch(`${API_BASE}/api/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  });
}
```

- [ ] **Step 5: Update frontend chat to use POST**

In `frontend/src/routes/_dashboard.chat.tsx`, replace the SSE URL construction in `handleSendQuery`:

```typescript
// Replace the queryParams/fetchEventSource section with:
const headers: Record<string, string> = {
  'Content-Type': 'application/json',
  ...authHeaders(),
};

const body = JSON.stringify({
  query: currentQuery,
  session_id: activeSessionId,
  ...(currentParentId ? { parent_msg_id: currentParentId } : {}),
});

await fetchEventSource(`${API_BASE}/api/query/stream`, {
  method: 'POST',
  headers,
  body,
  signal: abortController.signal,
  // ... rest of onopen, onmessage, onerror same
});
```

- [ ] **Step 6: Update tests for POST**

In `backend/tests/test_query.py`, update all `client.get("/api/query?q=...")` calls to `client.post("/api/query", json={"query": "..."})`.

- [ ] **Step 7: Commit**

```bash
git add backend/api/routes/query.py backend/api/routes/auth.py frontend/src/lib/api.ts frontend/src/routes/_dashboard.chat.tsx
git commit -m "feat: POST /api/query, auth/register, auth/refresh, X-Active-Team-ID header"
```

---

### Task 0.3: MySQL Schema Alignment — Add Missing Tables

**Files:**
- Modify: `backend/models.py`
- Create: `backend/db/migrations/versions/004_align_v2_schema.py`
- Test: `backend/tests/test_models.py`

- [ ] **Step 1: Add new SQLAlchemy models**

Append to `backend/models.py`:

```python
class Session(Base):
    __tablename__ = "sessions"
    session_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    team_id = Column(String(36), ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    consolidated_at = Column(DateTime, nullable=True)

class Turn(Base):
    __tablename__ = "turns"
    turn_id = Column(String(36), primary_key=True)
    session_id = Column(String(36), ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False, index=True)
    team_id = Column(String(36), ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text(4294967295), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

class SourceDoc(Base):
    __tablename__ = "source_docs"
    doc_id = Column(String(36), primary_key=True)
    team_id = Column(String(36), ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False, index=True)
    source_type = Column(String(20), nullable=False)
    source_ref = Column(String(1024), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_format = Column(String(50), nullable=False)
    content_hash = Column(String(64), nullable=False)
    uploaded_by = Column(String(36), ForeignKey("users.user_id"), nullable=False)
    status = Column(String(20), default="pending")
    error_message = Column(Text, nullable=True)
    version_number = Column(Integer, default=1)
    previous_version_id = Column(String(36), nullable=True)
    crawled_at = Column(DateTime, nullable=True)
    modified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    __table_args__ = (Index("idx_doc_team_hash", "team_id", "content_hash"), Index("idx_doc_status", "status"))

class VectorChunk(Base):
    __tablename__ = "vector_chunks"
    chunk_id = Column(String(36), primary_key=True)
    team_id = Column(String(36), ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False)
    doc_id = Column(String(36), ForeignKey("source_docs.doc_id", ondelete="CASCADE"), nullable=False)
    importance_score = Column(Double, default=0.5)
    last_accessed_at = Column(DateTime, server_default=func.now())
    page_number = Column(Integer, nullable=True)
    section_heading = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    __table_args__ = (Index("idx_chunk_decay", "importance_score", "last_accessed_at"),)

class RouterLog(Base):
    __tablename__ = "router_log"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    team_id = Column(String(36), ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False)
    query_hash = Column(String(64), nullable=False)
    route = Column(String(20), nullable=False)
    latency_ms = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

class EntityResolutionLog(Base):
    __tablename__ = "entity_resolution_log"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    team_id = Column(String(36), ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False)
    source_node_id = Column(String(100), nullable=False)
    target_node_id = Column(String(100), nullable=False)
    merge_reason = Column(Text, nullable=False)
    resolved_at = Column(DateTime, server_default=func.now())

class CrawlJob(Base):
    __tablename__ = "crawl_jobs"
    job_id = Column(String(36), primary_key=True)
    team_id = Column(String(36), ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False)
    triggered_by = Column(String(36), ForeignKey("users.user_id"), nullable=False)
    source_url = Column(String(1024), nullable=False)
    status = Column(String(20), nullable=False)
    pages_found = Column(Integer, default=0)
    started_at = Column(DateTime, server_default=func.now())
    finished_at = Column(DateTime, nullable=True)
```

- [ ] **Step 2: Add missing imports at top of models.py**

```python
from sqlalchemy import BigInteger, Double, Index
```

- [ ] **Step 3: Write migration script**

Create `backend/db/migrations/versions/004_align_v2_schema.py`:

```python
"""Add V2 spec tables

Revision ID: 004
Revises: 003
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"

def upgrade():
    op.create_table("sessions",
        sa.Column("session_id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("consolidated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("idx_sess_team_user", "sessions", ["team_id", "user_id"])
    op.create_index("idx_sess_created", "sessions", ["created_at"], postgresql_using="btree")

    op.create_table("turns",
        sa.Column("turn_id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(4294967295), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_turn_sess_created", "turns", ["session_id", "created_at"])

    op.create_table("source_docs",
        sa.Column("doc_id", sa.String(36), primary_key=True),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_ref", sa.String(1024), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_format", sa.String(50), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("uploaded_by", sa.String(36), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("version_number", sa.Integer(), server_default="1"),
        sa.Column("previous_version_id", sa.String(36), nullable=True),
        sa.Column("crawled_at", sa.DateTime(), nullable=True),
        sa.Column("modified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_doc_team_hash", "source_docs", ["team_id", "content_hash"])
    op.create_index("idx_doc_status", "source_docs", ["status"])

    op.create_table("vector_chunks",
        sa.Column("chunk_id", sa.String(36), primary_key=True),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False),
        sa.Column("doc_id", sa.String(36), sa.ForeignKey("source_docs.doc_id", ondelete="CASCADE"), nullable=False),
        sa.Column("importance_score", sa.Float(), server_default="0.5"),
        sa.Column("last_accessed_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section_heading", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_chunk_decay", "vector_chunks", ["importance_score", "last_accessed_at"])

    op.create_table("router_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("query_hash", sa.String(64), nullable=False),
        sa.Column("route", sa.String(20), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_rlog_team_route", "router_log", ["team_id", "route"])

    op.create_table("entity_resolution_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_node_id", sa.String(100), nullable=False),
        sa.Column("target_node_id", sa.String(100), nullable=False),
        sa.Column("merge_reason", sa.Text(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table("crawl_jobs",
        sa.Column("job_id", sa.String(36), primary_key=True),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.team_id", ondelete="CASCADE"), nullable=False),
        sa.Column("triggered_by", sa.String(36), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("source_url", sa.String(1024), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("pages_found", sa.Integer(), server_default="0"),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )

def downgrade():
    op.drop_table("crawl_jobs")
    op.drop_table("entity_resolution_log")
    op.drop_table("router_log")
    op.drop_table("vector_chunks")
    op.drop_table("source_docs")
    op.drop_table("turns")
    op.drop_table("sessions")
```

- [ ] **Step 4: Write model test**

In `backend/tests/test_models.py`:

```python
def test_session_model_creation():
    session = Session(
        session_id="test-session-id",
        user_id="test-user",
        team_id="test-team",
        title="Test Session"
    )
    assert session.session_id == "test-session-id"
    assert session.title == "Test Session"

def test_source_doc_model_with_hash():
    doc = SourceDoc(
        doc_id="doc-1",
        team_id="team-1",
        source_type="upload",
        source_ref="/tmp/test.pdf",
        file_name="test.pdf",
        file_format="pdf",
        content_hash="abc123",
        uploaded_by="user-1"
    )
    assert doc.content_hash == "abc123"
    assert doc.status == "pending"
```

- [ ] **Step 5: Run migration**

```bash
cd backend && uv run alembic upgrade head
```

- [ ] **Step 6: Commit**

```bash
git add backend/models.py backend/db/migrations/versions/004_align_v2_schema.py
git commit -m "feat: MySQL schema alignment - add V2 spec tables"
```

---

### Task 0.4: Neo4j Per-Tenant Database Isolation

**Files:**
- Modify: `backend/db/neo4j.py`
- Modify: `backend/agents/graph_orchestrator.py`
- Modify: `backend/ingestion/extractor.py`
- Modify: `backend/tasks/ingestion_worker.py`
- Modify: `backend/tasks/decay_worker.py`

- [ ] **Step 1: Remove team_id from Neo4j schema**

In `backend/db/neo4j.py`, update `write_entity`:

```python
def write_entity(self, team_id: str, entity_id: str, name: str, entity_type: str, source_doc_id: str):
    query = (
        "MERGE (e:Entity {id: $id}) "
        "ON CREATE SET e.name = $name, e.type = $type, e.importance_score = 1.0, "
        "e.source_doc_id = $doc_id, e.created_at = datetime()"
    )
    with self._get_session(team_id) as session:
        session.run(query, id=entity_id, name=name, type=entity_type, doc_id=source_doc_id)
```

Update `write_relationship`:

```python
def write_relationship(self, team_id: str, source_id: str, target_id: str, rel_type: str):
    query = (
        "MATCH (a:Entity {id: $source_id}), (b:Entity {id: $target_id}) "
        "MERGE (a)-[r:RELATES_TO {type: $type}]->(b) "
        "ON CREATE SET r.weight = 1.0, r.created_at = datetime(), r.source = 'ingestion'"
    )
    with self._get_session(team_id) as session:
        session.run(query, source_id=source_id, target_id=target_id, type=rel_type)
```

Update `get_entities`:

```python
def get_entities(self, team_id: str) -> list[dict]:
    query = (
        "MATCH (e:Entity) "
        "RETURN e.id AS id, e.name AS name, e.type AS type, "
        "e.importance_score AS importance_score, e.source_doc_id AS source_doc_id"
    )
    with self._get_session(team_id) as session:
        result = session.run(query)
        return [dict(record) for record in result]
```

Update `query_relationships`:

```python
def query_relationships(self, team_id: str, keywords: list[str]) -> list[list[str]]:
    if not keywords:
        return []
    cypher_query = (
        "MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity) "
        "WHERE any(k in $keywords WHERE toLower(coalesce(a.name, '')) CONTAINS k OR "
        "toLower(coalesce(b.name, '')) CONTAINS k OR "
        "toLower(coalesce(a.id, '')) CONTAINS k OR toLower(coalesce(b.id, '')) CONTAINS k) "
        "RETURN a.name AS source, r.type AS type, b.name AS target "
        "LIMIT 20"
    )
    with self._get_session(team_id) as session:
        result = session.run(cypher_query, keywords=[k.lower() for k in keywords])
        return [[record["source"], record["type"], record["target"]] for record in result]
```

Update `clear_graph`:

```python
def clear_graph(self, team_id: str):
    query = "MATCH (e:Entity) DETACH DELETE e"
    with self._get_session(team_id) as session:
        session.run(query)
```

- [ ] **Step 2: Update decay worker for per-tenant DB**

In `backend/tasks/decay_worker.py`, replace `team_id` property filter with database-level routing:

```python
with neo4j_mgr._get_session(team_id) as session:
    session.run("MATCH (e:Entity) SET e.importance_score = e.importance_score - 0.1")
    session.run("MATCH (e:Entity) WHERE e.importance_score <= 0.0 DETACH DELETE e")
    session.run("MATCH ()-[r:RELATES_TO]->() SET r.weight = r.weight - 0.1")
    session.run("MATCH ()-[r:RELATES_TO]->() WHERE r.weight <= 0.0 DELETE r")
```

- [ ] **Step 3: Commit**

```bash
git add backend/db/neo4j.py backend/tasks/decay_worker.py
git commit -m "fix: Neo4j per-tenant database isolation - remove team_id property filtering"
```

---

### Task 0.5: Guardrails AI — Working Safety Shield

**Files:**
- Modify: `backend/agents/safety.py`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Replace Guardrails with presidio + classifier prompt**

Rewrite `backend/agents/safety.py`:

```python
import re
import os
import logging

logger = logging.getLogger(__name__)

class SafetyValidationError(ValueError):
    pass

_presidio_available = False
try:
    from presidio_analyzer import AnalyzerEngine
    from presidio_anonymizer import AnonymizerEngine
    _analyzer = AnalyzerEngine()
    _anonymizer = AnonymizerEngine()
    _presidio_available = True
except ImportError:
    logger.warning("Presidio not installed. PII detection will use regex fallback.")

TOXIC_PATTERNS = [
    r"\b(kill|die|murder|attack|bomb|terrorist)\b",
    r"\b(hate|stupid|idiot|worthless)\b",
]

PHONE_REGEX = re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b")
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
SSN_REGEX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

def _has_toxic_content(text: str) -> bool:
    lower = text.lower()
    for pattern in TOXIC_PATTERNS:
        if re.search(pattern, lower):
            return True
    return False

def _scrub_pii(text: str) -> str:
    if _presidio_available:
        results = _analyzer.analyze(text=text, language="en")
        if results:
            return _anonymizer.anonymize(text=text, analyzer_results=results).text
    text = EMAIL_REGEX.sub("[EMAIL]", text)
    text = PHONE_REGEX.sub("[PHONE]", text)
    text = SSN_REGEX.sub("[SSN]", text)
    return text

def validate_query(query: str) -> str:
    if _has_toxic_content(query):
        raise SafetyValidationError("Query contains potentially harmful content")
    return _scrub_pii(query)

def validate_output(output: str) -> str:
    if _has_toxic_content(output):
        raise SafetyValidationError("Output contains potentially harmful content")
    return _scrub_pii(output)
```

- [ ] **Step 2: Add presidio to requirements**

Add to `backend/requirements.txt` or `backend/pyproject.toml`:

```
presidio-analyzer>=2.2.35
presidio-anonymizer>=2.2.35
```

- [ ] **Step 3: Write safety tests**

In `backend/tests/test_safety.py`:

```python
from backend.agents.safety import validate_query, validate_output, SafetyValidationError

def test_pii_scrubbing_email():
    result = validate_query("Contact me at test@example.com")
    assert "[EMAIL]" in result
    assert "test@example.com" not in result

def test_pii_scrubbing_phone():
    result = validate_query("Call 555-123-4567")
    assert "[PHONE]" in result

def test_toxic_query_blocked():
    try:
        validate_query("I will kill you")
        assert False, "Should have raised"
    except SafetyValidationError:
        pass

def test_safe_query_passes():
    result = validate_query("What is the capital of France?")
    assert "capital" in result
```

- [ ] **Step 4: Commit**

```bash
git add backend/agents/safety.py backend/requirements.txt backend/tests/test_safety.py
git commit -m "fix: replace Guardrails hub with presidio PII detection and pattern-based toxicity filter"
```

---

### Task 0.6: Rate Limiting

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/config.py`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add slowapi dependency**

Add to `backend/requirements.txt`:
```
slowapi>=0.1.9
```

- [ ] **Step 2: Add rate limit settings**

In `backend/config.py`, add:

```python
RATE_LIMIT_LOGIN: str = "5/minute"
RATE_LIMIT_REGISTER: str = "3/minute"
RATE_LIMIT_QUERY: str = "30/minute"
RATE_LIMIT_GLOBAL: str = "100/minute"
```

- [ ] **Step 3: Add rate limiting middleware**

In `backend/main.py`, add after CORS middleware:

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address, storage_uri=settings.REDIS_URL)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

- [ ] **Step 4: Add decorators to endpoints**

In `backend/api/routes/auth.py`:

```python
from backend.main import limiter

@router.post("/login")
@limiter.limit(settings.RATE_LIMIT_LOGIN)
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    ...
```

In `backend/api/routes/query.py`:

```python
@router.post("/query")
@limiter.limit(settings.RATE_LIMIT_QUERY)
def run_query(request: Request, payload: QueryRequest, ...):
    ...
```

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/config.py backend/api/routes/auth.py backend/api/routes/query.py
git commit -m "fix: add rate limiting with slowapi + Redis backend"
```

---

### Task 0.7: RBAC Alignment with V2 Spec

**Files:**
- Modify: `backend/auth/middleware.py`
- Modify: `backend/api/routes/admin.py`
- Modify: `backend/api/routes/upload.py`

- [ ] **Step 1: Add team membership validation**

In `backend/auth/middleware.py`:

```python
from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session
from backend.db.mysql import get_db
from backend.models import TeamMember

def require_team_membership():
    async def dep(
        x_active_team_id: str | None = Header(default=None, alias="X-Active-Team-ID"),
        current_user: dict = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        if not x_active_team_id:
            raise HTTPException(status_code=400, detail="Missing X-Active-Team-ID header")
        if current_user.get("role") == "superadmin":
            return x_active_team_id
        membership = db.query(TeamMember).filter_by(
            team_id=x_active_team_id,
            user_id=current_user.get("sub")
        ).first()
        if not membership:
            raise HTTPException(status_code=403, detail="Not a member of this team")
        return x_active_team_id
    return dep

def require_team_role(min_role: str):
    async def dep(
        x_active_team_id: str = Depends(require_team_membership()),
        current_user: dict = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        if current_user.get("role") == "superadmin":
            return x_active_team_id
        membership = db.query(TeamMember).filter_by(
            team_id=x_active_team_id,
            user_id=current_user.get("sub")
        ).first()
        role_hierarchy = {"user": 0, "team_lead": 1}
        if role_hierarchy.get(membership.role, -1) < role_hierarchy.get(min_role, 0):
            raise HTTPException(status_code=403, detail=f"Requires role: {min_role}")
        return x_active_team_id
    return dep
```

- [ ] **Step 2: Update upload endpoint to require team_lead**

In `backend/api/routes/upload.py`, change upload dependency:

```python
from backend.auth.middleware import require_team_role

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    x_active_team_id: str = Depends(require_team_role("team_lead")),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Remove auto-join logic
    ...
```

- [ ] **Step 3: Align role names**

In `backend/api/routes/admin.py`, change MemberAdd roles from `["member", "admin", "owner"]` to `["user", "team_lead"]`:

```python
class MemberAdd(BaseModel):
    team_id: str
    user_id: str
    role: Literal["user", "team_lead"] = "user"
```

- [ ] **Step 4: Commit**

```bash
git add backend/auth/middleware.py backend/api/routes/upload.py backend/api/routes/admin.py
git commit -m "fix: RBAC alignment - team membership validation, team_lead role for upload"
```

---

### Task 0.8: Neo4j Connection Pooling

**Files:**
- Modify: `backend/db/neo4j.py`

- [ ] **Step 1: Convert to connection-pooled singleton**

Replace `_neo4j_mgr = None` and `Neo4jManager.__init__` with:

```python
import logging
from neo4j import GraphDatabase
from backend.config import settings

logger = logging.getLogger(__name__)

class Neo4jManager:
    _instance = None
    _multidb_supported: bool | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                max_connection_pool_size=50,
                connection_acquisition_timeout=30,
            )
        return cls._instance

    def close(self):
        if self._instance and self._instance.driver:
            self._instance.driver.close()
            self._instance = None
```

- [ ] **Step 2: Commit**

```bash
git add backend/db/neo4j.py
git commit -m "fix: Neo4j connection pooling - singleton driver with 50 connection pool"
```

---

### Task 0.9: Redis Port Fix

**Files:**
- Modify: `docker-compose.yml`
- Modify: `.env.example`

- [ ] **Step 1: Fix port mapping**

In `docker-compose.yml`, change Redis ports from `"6380:6379"` to `"6379:6379"`.

- [ ] **Step 2: Update .env.example**

In `.env.example`, ensure `REDIS_URL=redis://127.0.0.1:6379/0` is present and documented.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml .env.example
git commit -m "fix: Redis port mapping - use standard port 6379"
```

---

### Task 0.10: Query History in Retrieval

**Files:**
- Modify: `backend/agents/retriever.py`
- Modify: `backend/agents/graph_orchestrator.py`

- [ ] **Step 1: Add history context to retrieval**

In `backend/agents/retriever.py`:

```python
def retrieve_parent_documents(
    weaviate_mgr, tenant_id: str, query: str, current_user_id: str,
    history: list[dict] | None = None,
    max_history_chars: int = 500
) -> list[dict]:
    # Append recent history to query for context
    context_query = query
    if history:
        recent = history[-3:]  # last 3 turns
        history_text = " ".join(f"{m['role']}: {m['content']}" for m in recent)
        context_query = f"{history_text}\nCurrent: {query}"[:max_history_chars]

    chunks = weaviate_mgr.hybrid_search(tenant_id, context_query, current_user_id)
    # ... rest unchanged
```

- [ ] **Step 2: Pass history from graph state**

In `backend/agents/graph_orchestrator.py`, update `vector_retrieve_node`:

```python
def vector_retrieve_node(state: AgentState) -> Dict[str, Any]:
    ...
    chunks = retrieve_parent_documents(
        weaviate_mgr=weaviate_mgr,
        tenant_id=state["active_team_id"],
        query=query_to_use,
        current_user_id=state["user_id"],
        history=state.get("history")
    )
    return {"retrieved_chunks": chunks}
```

- [ ] **Step 3: Commit**

```bash
git add backend/agents/retriever.py backend/agents/graph_orchestrator.py
git commit -m "feat: pass conversation history to retrieval for multi-turn context"
```

---

### Task 0.11: Pagination on Session List

**Files:**
- Modify: `backend/api/routes/query.py`

- [ ] **Step 1: Add pagination params**

Replace `get_chat_sessions`:

```python
@router.get("/chat/sessions")
def get_chat_sessions(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id") or current_user.get("sub")
    total_query = db.query(Message.session_id).filter(Message.user_id == user_id).distinct()
    total = total_query.count()
    results = total_query.offset(offset).limit(limit).all()
    return {"sessions": [r[0] for r in results if r[0]], "total": total}
```

- [ ] **Step 2: Commit**

```bash
git add backend/api/routes/query.py
git commit -m "fix: paginate session list - add offset/limit with total count"
```

---

### Task 0.12: SSE Error Handling

**Files:**
- Modify: `backend/api/routes/query.py`
- Modify: `frontend/src/routes/_dashboard.chat.tsx`

- [ ] **Step 1: Validate auth before stream starts**

In `backend/api/routes/query.py`, move auth/validation checks before the stream response:

```python
@router.post("/query/stream")
async def run_query_stream(...):
    if not current_user.get("user_id"):
        raise HTTPException(status_code=401, detail="Invalid token")
    validated_q = validate_query(payload.query)
    # ... start stream only after all validation passes
```

- [ ] **Step 2: Add error event emission**

In the async generator, wrap in try/except and emit error events instead of crashing:

```python
async def event_stream():
    try:
        async for event in ainvoke_with_events(state):
            yield event
    except SafetyValidationError as e:
        yield ErrorEvent(str(e)).to_sse()
    except Exception as e:
        logger.exception("Stream error")
        yield ErrorEvent("Internal error during response generation").to_sse()
```

- [ ] **Step 3: Frontend — stop retry on 4xx**

In `frontend/src/routes/_dashboard.chat.tsx`, in `onerror`:

```typescript
onerror(err) {
  if (err.message?.startsWith('Server returned status 4')) {
    setError(err.message);
    setSendingQuery(false);
    abortController.abort();
    return; // don't throw — prevents retry
  }
  throw err; // retry on 5xx
}
```

- [ ] **Step 4: Commit**

```bash
git add backend/api/routes/query.py frontend/src/routes/_dashboard.chat.tsx
git commit -m "fix: SSE error handling - no infinite retry on 4xx, emit error events"
```

---

### Task 0.13: Entity Extraction — Stop Generating Noise

**Files:**
- Modify: `backend/ingestion/extractor.py`

- [ ] **Step 1: Remove heuristic sequential relationships**

Replace `extract_heuristic` with:

```python
def extract_heuristic(text: str) -> tuple[list[dict], list[dict]]:
    # Extract capitalized terms as potential entity names
    pattern = re.compile(r'\b[A-Z][a-zA-Z0-9_]{1,30}(?:\s+[A-Z][a-zA-Z0-9_]{1,30})*\b')
    matches = pattern.findall(text)
    stop_words = {"The", "A", "An", "This", "That", "These", "Those", "It", "They", "We", "I"}
    entities = []
    seen_ids = set()
    for match in matches:
        cleaned = match.strip()
        if cleaned in stop_words or len(cleaned) < 2:
            continue
        entity_id = re.sub(r'[^a-zA-Z0-9_]', '_', cleaned.lower())
        if entity_id not in seen_ids:
            seen_ids.add(entity_id)
            entities.append({"id": entity_id, "name": cleaned, "type": "Concept"})
    # Do NOT generate false relationships — return empty relations list
    return entities, []
```

- [ ] **Step 2: Commit**

```bash
git add backend/ingestion/extractor.py
git commit -m "fix: stop generating false sequential relationships in heuristic extraction"
```

---

### Task 0.14: Celery Fork Safety

**Files:**
- Modify: `backend/db/weaviate.py`
- Modify: `backend/db/neo4j.py`
- Modify: `backend/tasks/celery_app.py`

- [ ] **Step 1: Remove global singletons**

In `backend/db/weaviate.py`, remove `_weaviate_mgr = None` and `get_weaviate_mgr()`. Make `WeaviateManager` a plain class without global caching.

In `backend/db/neo4j.py`, remove `_neo4j_mgr = None` and the global assignment in `__init__`.

- [ ] **Step 2: Add worker lifecycle signals**

In `backend/tasks/celery_app.py`:

```python
from celery.signals import worker_process_init, worker_process_shutdown

@worker_process_init.connect
def init_worker(**kwargs):
    """Initialize per-process connections."""
    from backend.db.weaviate import WeaviateManager
    from backend.db.neo4j import Neo4jManager
    # Pre-warm connections in each worker process
    _weaviate = WeaviateManager()
    _neo4j = Neo4jManager()
    # Store on the process's module for reuse
    import os
    os.environ["_WEAVIATE_INIT"] = "1"
    os.environ["_NEO4J_INIT"] = "1"

@worker_process_shutdown.connect
def shutdown_worker(**kwargs):
    """Clean up per-process connections."""
    from backend.db.weaviate import WeaviateManager
    from backend.db.neo4j import Neo4jManager
    # Connections will be GC'd on process exit
```

- [ ] **Step 3: Commit**

```bash
git add backend/db/weaviate.py backend/db/neo4j.py backend/tasks/celery_app.py
git commit -m "fix: Celery fork safety - remove global singletons, use worker lifecycle signals"
```

---

### Task 0.15: Test Infrastructure — MySQL-Compatible Testing

**Files:**
- Create: `backend/tests/conftest.py`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Create testcontainers-based conftest**

Create `backend/tests/conftest.py`:

```python
import pytest
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.db.mysql import Base

@pytest.fixture(scope="session")
def mysql_container():
    use_testcontainers = os.environ.get("USE_TESTCONTAINERS", "0") == "1"
    if use_testcontainers:
        from testcontainers.mysql import MySqlContainer
        with MySqlContainer("mysql:8.0") as mysql:
            yield mysql
    else:
        yield None

@pytest.fixture
def db_session(mysql_container):
    if mysql_container:
        url = mysql_container.get_connection_url()
    else:
        # Use SQLite for local dev
        url = "sqlite:///:memory:"
    engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)
```

- [ ] **Step 2: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "fix: test infrastructure - testcontainers MySQL support with SQLite fallback"
```

---

## Phase 1: Observability & Quality Features

### Task 1.1: RAG Evaluation Dashboard

**Files:**
- Create: `backend/db/migrations/versions/005_eval_scores.py`
- Modify: `backend/models.py`
- Modify: `backend/api/routes/eval.py`
- Create: `frontend/src/routes/_dashboard.eval.tsx`
- Modify: `backend/tasks/celery_app.py`

- [ ] **Step 1: Add eval_scores table**

In `backend/models.py`:

```python
class EvalScore(Base):
    __tablename__ = "eval_scores"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    feedback_id = Column(String(36), ForeignKey("user_feedbacks.feedback_id"), nullable=False)
    faithfulness_score = Column(Float, nullable=True)
    hallucination_score = Column(Float, nullable=True)
    answer_relevancy_score = Column(Float, nullable=True)
    model_version = Column(String(50), nullable=True)
    evaluated_at = Column(DateTime, server_default=func.now())
```

- [ ] **Step 2: Add weekly eval beat task**

In `backend/tasks/celery_app.py`, add to `beat_schedule`:

```python
"run-weekly-evaluation": {
    "task": "backend.api.routes.eval.run_scheduled_evaluation",
    "schedule": crontab(day_of_week=0, hour=3, minute=0),
}
```

- [ ] **Step 3: Create evaluation dashboard endpoint**

In `backend/api/routes/eval.py`, add:

```python
@router.get("/eval/scores")
def get_eval_scores(
    days: int = Query(30, ge=1, le=365),
    current_user: dict = Depends(require_global_role("superadmin")),
    db: Session = Depends(get_db)
):
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(days=days)
    scores = db.query(EvalScore).filter(EvalScore.evaluated_at >= cutoff).order_by(EvalScore.evaluated_at).all()
    return {
        "scores": [
            {
                "date": s.evaluated_at.isoformat(),
                "faithfulness": s.faithfulness_score,
                "hallucination": s.hallucination_score,
                "relevancy": s.answer_relevancy_score,
            }
            for s in scores
        ]
    }
```

- [ ] **Step 4: Create evaluation dashboard React page**

Create `frontend/src/routes/_dashboard.eval.tsx`:

```tsx
import { createRoute } from '@tanstack/react-router';
import { Route as dashboardRoute } from './_dashboard';
import { useState, useEffect } from 'react';
import { apiFetch } from '../lib/api';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';

export const Route = createRoute({
  getParentRoute: () => dashboardRoute,
  path: '/eval',
  component: EvalDashboard,
});

function EvalDashboard() {
  const [data, setData] = useState<any[]>([]);
  useEffect(() => {
    apiFetch('/api/eval/scores?days=30').then(r => r.json()).then(d => setData(d.scores || []));
  }, []);

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">RAG Evaluation Dashboard</h1>
      <ResponsiveContainer width="100%" height={400}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" />
          <YAxis domain={[0, 1]} />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="faithfulness" stroke="#8884d8" />
          <Line type="monotone" dataKey="hallucination" stroke="#82ca9d" />
          <Line type="monotone" dataKey="relevancy" stroke="#ffc658" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 5: Register route in router**

Add to `frontend/src/router.tsx`:

```tsx
import { Route as evalRoute } from './routes/_dashboard.eval';
// Add evalRoute to dashboard children
dashboardLayoutRoute.addChildren([dashboardIndexRoute, chatRoute, docsRoute, adminRoute, evalRoute])
```

- [ ] **Step 6: Commit**

```bash
git add backend/models.py backend/api/routes/eval.py backend/tasks/celery_app.py frontend/src/routes/_dashboard.eval.tsx frontend/src/router.tsx
git commit -m "feat: RAG evaluation dashboard with score history and trend charts"
```

---

### Task 1.2: Audit Logging

**Files:**
- Modify: `backend/models.py`
- Modify: `backend/api/routes/query.py`
- Modify: `backend/api/routes/admin.py`

- [ ] **Step 1: Add AuditLog model**

In `backend/models.py`:

```python
class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False, index=True)
    team_id = Column(String(36), ForeignKey("teams.team_id"), nullable=False, index=True)
    query_text = Column(Text, nullable=False)
    response_length = Column(Integer, nullable=True)
    retrieval_sources = Column(JSON, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    __table_args__ = (
        Index("idx_audit_team_time", "team_id", "created_at"),
        Index("idx_audit_user_time", "user_id", "created_at"),
    )
```

- [ ] **Step 2: Add audit logging to query endpoint**

In `backend/api/routes/query.py`, after `graph.invoke()`:

```python
import time
from backend.models import AuditLog

start_time = time.time()
result = graph.invoke({...})
latency = int((time.time() - start_time) * 1000)

# Persist audit log (non-blocking — fire and forget)
try:
    audit = AuditLog(
        user_id=user_id,
        team_id=state["active_team_id"],
        query_text=validated_q,
        response_length=len(raw_response),
        retrieval_sources=result.get("citations", []),
        latency_ms=latency,
    )
    db.add(audit)
    db.commit()
except Exception:
    db.rollback()
    logger.warning("Failed to persist audit log")
```

- [ ] **Step 3: Add audit query endpoint**

In `backend/api/routes/admin.py`:

```python
@admin_router.get("/audit/logs")
def get_audit_logs(
    team_id: str | None = None,
    user_id: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_global_role("superadmin")),
):
    query = db.query(AuditLog)
    if team_id:
        query = query.filter(AuditLog.team_id == team_id)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    total = query.count()
    logs = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "logs": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "team_id": log.team_id,
                "query_preview": log.query_text[:100],
                "response_length": log.response_length,
                "latency_ms": log.latency_ms,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
        "total": total,
    }
```

- [ ] **Step 4: Commit**

```bash
git add backend/models.py backend/api/routes/query.py backend/api/routes/admin.py
git commit -m "feat: audit logging - track queries, latency, and retrieval sources per request"
```

---

### Task 1.3: Analytics Dashboard

**Files:**
- Create: `backend/tasks/analytics_worker.py`
- Create: `backend/api/routes/analytics.py`
- Create: `frontend/src/routes/_dashboard.analytics.tsx`
- Modify: `frontend/src/router.tsx`

- [ ] **Step 1: Create analytics aggregation task**

Create `backend/tasks/analytics_worker.py`:

```python
import logging
from datetime import datetime, timedelta
from backend.tasks.celery_app import celery_app
from sqlalchemy import func, case
from backend.db.mysql import SessionLocal
from backend.models import AuditLog, UserFeedback

logger = logging.getLogger(__name__)

@celery_app.task(name="backend.tasks.analytics_worker.aggregate_hourly")
def aggregate_hourly():
    db = SessionLocal()
    now = datetime.utcnow()
    hour_ago = now - timedelta(hours=1)
    day_ago = now - timedelta(days=1)

    queries_last_hour = db.query(AuditLog).filter(AuditLog.created_at >= hour_ago).count()
    queries_last_day = db.query(AuditLog).filter(AuditLog.created_at >= day_ago).count()

    avg_latency = db.query(func.avg(AuditLog.latency_ms)).filter(AuditLog.created_at >= hour_ago).scalar() or 0

    unique_users = db.query(AuditLog.user_id).filter(AuditLog.created_at >= day_ago).distinct().count()

    feedback_ratings = db.query(
        func.sum(case((UserFeedback.rating == 1, 1), else_=0)),
        func.count(UserFeedback.feedback_id)
    ).filter(UserFeedback.created_at >= day_ago).first()

    result = {
        "timestamp": now.isoformat(),
        "queries_last_hour": queries_last_hour,
        "queries_last_day": queries_last_day,
        "avg_latency_ms": round(float(avg_latency), 2),
        "unique_users_last_day": unique_users,
        "positive_feedback": feedback_ratings[0] or 0,
        "total_feedback": feedback_ratings[1] or 0,
    }

    db.close()
    return result
```

- [ ] **Step 2: Create analytics API endpoint**

Create `backend/api/routes/analytics.py`:

```python
import json
import logging
from fastapi import APIRouter, Depends
from backend.auth.middleware import require_global_role
from backend.agents.memory import get_redis_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["analytics"])

@router.get("/analytics")
def get_analytics(current_user: dict = Depends(require_global_role("superadmin"))):
    redis_client = get_redis_client()
    cached = redis_client.get("analytics:latest")
    if cached:
        return json.loads(cached)
    return {"message": "No analytics data yet. First aggregation runs hourly."}
```

- [ ] **Step 3: Register analytics route**

In `backend/main.py`:

```python
from backend.api.routes.analytics import router as analytics_router
app.include_router(analytics_router)
```

- [ ] **Step 4: Create analytics frontend page**

Create `frontend/src/routes/_dashboard.analytics.tsx`:

```tsx
import { createRoute } from '@tanstack/react-router';
import { Route as dashboardRoute } from './_dashboard';
import { useState, useEffect } from 'react';
import { apiFetch } from '../lib/api';

export const Route = createRoute({
  getParentRoute: () => dashboardRoute,
  path: '/analytics',
  component: AnalyticsDashboard,
});

function AnalyticsDashboard() {
  const [analytics, setAnalytics] = useState<any>(null);

  useEffect(() => {
    apiFetch('/api/admin/analytics')
      .then(r => r.json())
      .then(d => setAnalytics(d))
      .catch(() => {});
  }, []);

  if (!analytics) return <div className="p-6">Loading analytics...</div>;
  if (analytics.message) return <div className="p-6 text-muted-foreground">{analytics.message}</div>;

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Analytics Dashboard</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-lg border p-4 bg-card">
          <div className="text-sm text-muted-foreground">Queries (last hour)</div>
          <div className="text-3xl font-bold">{analytics.queries_last_hour}</div>
        </div>
        <div className="rounded-lg border p-4 bg-card">
          <div className="text-sm text-muted-foreground">Queries (last 24h)</div>
          <div className="text-3xl font-bold">{analytics.queries_last_day}</div>
        </div>
        <div className="rounded-lg border p-4 bg-card">
          <div className="text-sm text-muted-foreground">Avg Latency</div>
          <div className="text-3xl font-bold">{analytics.avg_latency_ms}ms</div>
        </div>
        <div className="rounded-lg border p-4 bg-card">
          <div className="text-sm text-muted-foreground">Unique Users (24h)</div>
          <div className="text-3xl font-bold">{analytics.unique_users_last_day}</div>
        </div>
        <div className="rounded-lg border p-4 bg-card">
          <div className="text-sm text-muted-foreground">Positive Feedback</div>
          <div className="text-3xl font-bold">{analytics.positive_feedback}/{analytics.total_feedback}</div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Register route in router**

In `frontend/src/router.tsx`, add to dashboard children:

```tsx
import { Route as analyticsRoute } from './routes/_dashboard.analytics';
dashboardLayoutRoute.addChildren([dashboardIndexRoute, chatRoute, docsRoute, adminRoute, evalRoute, analyticsRoute])
```

- [ ] **Step 6: Commit**

```bash
git add backend/tasks/analytics_worker.py backend/api/routes/analytics.py frontend/src/routes/_dashboard.analytics.tsx frontend/src/router.tsx backend/main.py
git commit -m "feat: analytics dashboard with hourly aggregation"
```

---

## Phase 2: Document Intelligence

### Task 2.1: Document Versioning

**Files:**
- Create: `backend/ingestion/versioning.py`
- Modify: `backend/api/routes/upload.py`
- Modify: `backend/tasks/ingestion_worker.py`
- Modify: `frontend/src/routes/_dashboard.docs.tsx`

- [ ] **Step 1: Create versioning utilities**

Create `backend/ingestion/versioning.py`:

```python
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
```

- [ ] **Step 2: Integrate versioning into upload**

In `backend/api/routes/upload.py`, after receiving file:

```python
from backend.ingestion.versioning import compute_content_hash, detect_version_change

content = await file.read()
file_hash = compute_content_hash(content)

version_info = detect_version_change(x_active_team_id, file.filename, file_hash)
if version_info:
    logger.info(f"New version detected: {version_info}")
```

- [ ] **Step 3: Commit**

```bash
git add backend/ingestion/versioning.py backend/api/routes/upload.py
git commit -m "feat: document versioning with content hash detection"
```

---

### Task 2.2: PDF Viewer with Highlighted Citations

**Files:**
- Create: `backend/api/routes/documents.py`
- Create: `frontend/src/components/pdf-viewer.tsx`
- Modify: `frontend/src/components/CitationDrawer.tsx`

- [ ] **Step 1: Add PDF serving endpoint**

Create `backend/api/routes/documents.py`:

```python
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.db.mysql import get_db
from backend.models import ParentDocument
from backend.auth.middleware import get_current_user
from fastapi.responses import Response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])

@router.get("/{doc_id}/pdf")
def get_document_pdf(
    doc_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.query(ParentDocument).filter_by(parent_id=doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    # Return as downloadable binary
    content = doc.content.encode("utf-8") if isinstance(doc.content, str) else doc.content
    return Response(content=content, media_type="application/pdf", headers={
        "Content-Disposition": f'inline; filename="{doc.filename}"'
    })
```

- [ ] **Step 2: Create PDF viewer component**

Create `frontend/src/components/pdf-viewer.tsx`:

```tsx
import { useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { apiFetch } from '../lib/api';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@4.7.76/build/pdf.worker.min.mjs`;

interface PdfViewerProps {
  docId: string;
  pageNumber?: number;
  bbox?: number[];
}

export function PdfViewer({ docId, pageNumber = 1, bbox }: PdfViewerProps) {
  const [numPages, setNumPages] = useState(0);

  return (
    <div className="relative overflow-auto border rounded-lg bg-white">
      <Document
        file={`${API_BASE}/api/documents/${docId}/pdf`}
        onLoadSuccess={({ numPages }) => setNumPages(numPages)}
        loading={<div className="p-4 text-center">Loading PDF...</div>}
        error={<div className="p-4 text-center text-red-500">Failed to load PDF</div>}
      >
        <Page
          pageNumber={pageNumber}
          width={600}
          renderTextLayer={true}
          renderAnnotationLayer={true}
        />
      </Document>
    </div>
  );
}
```

- [ ] **Step 3: Update CitationDrawer to include PDF viewer**

In `frontend/src/components/CitationDrawer.tsx`, add a "Open in PDF Viewer" button when citation has a parent_id:

```tsx
import { PdfViewer } from './pdf-viewer';

// Inside the drawer content, after citation details:
{citation?.parent_id && (
  <div className="mt-4">
    <Button
      variant="outline"
      size="sm"
      onClick={() => setShowPdf(!showPdf)}
    >
      {showPdf ? 'Hide PDF' : 'View in Document'}
    </Button>
    {showPdf && (
      <div className="mt-2 max-h-96 overflow-auto">
        <PdfViewer
          docId={citation.parent_id}
          pageNumber={citation.page_number || 1}
          bbox={citation.bbox}
        />
      </div>
    )}
  </div>
)}
```

Add state at the top of the component:

```tsx
const [showPdf, setShowPdf] = useState(false);
```

- [ ] **Step 4: Commit**

```bash
git add backend/api/routes/documents.py frontend/src/components/pdf-viewer.tsx frontend/src/components/CitationDrawer.tsx
git commit -m "feat: PDF viewer with citation scroll-to-position"
```

---

### Task 2.3: Collaborative Annotations

**Files:**
- Create: `backend/api/routes/annotations.py`
- Modify: `backend/models.py`
- Create: `frontend/src/components/annotation-layer.tsx`
- Create: `frontend/src/components/annotation-thread.tsx`
- Modify: `frontend/src/routes/_dashboard.docs.tsx`

- [ ] **Step 1: Add Annotation model**

In `backend/models.py`:

```python
class Annotation(Base):
    __tablename__ = "annotations"
    annotation_id = Column(String(36), primary_key=True)
    doc_id = Column(String(36), ForeignKey("source_docs.doc_id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False)
    anchor_start = Column(Integer, nullable=False)
    anchor_end = Column(Integer, nullable=False)
    highlighted_text = Column(Text, nullable=False)
    comment = Column(Text, nullable=False)
    parent_annotation_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 2: Create annotation CRUD endpoints**

Create `backend/api/routes/annotations.py`:

```python
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from backend.db.mysql import get_db
from backend.models import Annotation
from backend.auth.middleware import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["annotations"])

class AnnotationCreate(BaseModel):
    doc_id: str
    anchor_start: int
    anchor_end: int
    highlighted_text: str
    comment: str
    parent_annotation_id: str | None = None

@router.post("/annotations", status_code=201)
def create_annotation(
    payload: AnnotationCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    annotation = Annotation(
        annotation_id=str(uuid.uuid4()),
        doc_id=payload.doc_id,
        user_id=current_user.get("sub"),
        anchor_start=payload.anchor_start,
        anchor_end=payload.anchor_end,
        highlighted_text=payload.highlighted_text,
        comment=payload.comment,
        parent_annotation_id=payload.parent_annotation_id,
    )
    db.add(annotation)
    db.commit()
    return {"annotation_id": annotation.annotation_id}

@router.get("/{doc_id}/annotations")
def list_annotations(
    doc_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    annotations = db.query(Annotation).filter(
        Annotation.doc_id == doc_id
    ).order_by(Annotation.created_at.asc()).all()
    return {
        "annotations": [
            {
                "annotation_id": a.annotation_id,
                "user_id": a.user_id,
                "anchor_start": a.anchor_start,
                "anchor_end": a.anchor_end,
                "highlighted_text": a.highlighted_text,
                "comment": a.comment,
                "parent_annotation_id": a.parent_annotation_id,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in annotations
        ]
    }

@router.delete("/annotations/{annotation_id}")
def delete_annotation(
    annotation_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    annotation = db.query(Annotation).filter_by(annotation_id=annotation_id).first()
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")
    if annotation.user_id != current_user.get("sub") and current_user.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="Not authorized")
    db.delete(annotation)
    db.commit()
    return {"status": "deleted"}
```

- [ ] **Step 3: Create annotation React components**

Create `frontend/src/components/annotation-layer.tsx`:

```tsx
import { useState, useEffect } from 'react';
import { apiFetch } from '../lib/api';

interface Annotation {
  annotation_id: string;
  user_id: string;
  anchor_start: number;
  anchor_end: number;
  highlighted_text: string;
  comment: string;
  created_at: string;
}

interface AnnotationLayerProps {
  docId: string;
  content: string;
}

export function AnnotationLayer({ docId, content }: AnnotationLayerProps) {
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [selected, setSelected] = useState<Annotation | null>(null);

  useEffect(() => {
    apiFetch(`/api/documents/${docId}/annotations`)
      .then(r => r.json())
      .then(d => setAnnotations(d.annotations || []))
      .catch(() => {});
  }, [docId]);

  return (
    <div className="relative">
      <div className="whitespace-pre-wrap text-sm leading-relaxed">
        {annotations.map(a => (
          <button
            key={a.annotation_id}
            className="bg-yellow-200 dark:bg-yellow-800/40 cursor-pointer hover:bg-yellow-300 rounded px-0.5"
            onClick={() => setSelected(a)}
            title={a.comment}
          >
            {content.slice(a.anchor_start, a.anchor_end)}
          </button>
        ))}
      </div>
      {selected && (
        <div className="fixed bottom-4 right-4 w-80 rounded-lg border bg-card p-4 shadow-lg">
          <p className="text-sm font-medium">Comment</p>
          <p className="text-sm text-muted-foreground mt-1">{selected.comment}</p>
          <p className="text-xs text-muted-foreground mt-2">— {selected.user_id}</p>
          <button className="mt-2 text-xs text-red-500" onClick={() => setSelected(null)}>Close</button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add backend/models.py backend/api/routes/annotations.py frontend/src/components/annotation-layer.tsx frontend/src/components/annotation-thread.tsx
git commit -m "feat: collaborative document annotations with comment threads"
```

---

## Phase 3: Integration & Automation

### Task 3.1: Semantic Caching

**Files:**
- Create: `backend/cache/semantic_cache.py`
- Modify: `backend/agents/graph_orchestrator.py`
- Modify: `backend/config.py`
- Modify: `backend/api/routes/admin.py`

- [ ] **Step 1: Create semantic cache class**

Create `backend/cache/semantic_cache.py`:

```python
import json
import hashlib
import struct
import logging
from typing import Any, Dict, Optional
from backend.agents.memory import get_redis_client
from backend.config import settings
from backend.db.weaviate import GoogleGenerativeAIEmbeddings

logger = logging.getLogger(__name__)

class SemanticCache:
    def __init__(self):
        self.redis = get_redis_client()
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-2",
            google_api_key=settings.GEMINI_API_KEY
        )
        self.threshold = settings.SEMANTIC_CACHE_THRESHOLD
        self.ttl = settings.SEMANTIC_CACHE_TTL

    def _embed(self, text: str) -> list[float]:
        return self.embeddings.embed_query(text)

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        dot = sum(x*y for x, y in zip(a, b))
        norm_a = sum(x*x for x in a)**0.5
        norm_b = sum(x*x for x in b)**0.5
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

    def _hash_key(self, embedding: list[float]) -> str:
        # Use first 4 bytes of embedding as rough hash for lookup
        key_bytes = struct.pack('f'*min(4, len(embedding)), *embedding[:4])
        return hashlib.md5(key_bytes).hexdigest()

    def get(self, query: str) -> Optional[Dict[str, Any]]:
        query_emb = self._embed(query)
        cache_key = f"semantic_cache:{self._hash_key(query_emb)}"
        cached = self.redis.get(cache_key)
        if cached:
            entry = json.loads(cached)
            stored_emb = entry.get("embedding", [])
            similarity = self._cosine_similarity(query_emb, stored_emb)
            if similarity >= self.threshold:
                logger.info(f"Semantic cache HIT (similarity: {similarity:.3f})")
                return entry.get("result")
        logger.debug("Semantic cache MISS")
        return None

    def set(self, query: str, result: Dict[str, Any]):
        query_emb = self._embed(query)
        cache_key = f"semantic_cache:{self._hash_key(query_emb)}"
        entry = {"embedding": query_emb, "result": result}
        self.redis.setex(cache_key, self.ttl, json.dumps(entry))

    def flush(self):
        keys = self.redis.keys("semantic_cache:*")
        if keys:
            self.redis.delete(*keys)
            logger.info(f"Flushed {len(keys)} semantic cache entries")
```

- [ ] **Step 2: Add config settings**

In `backend/config.py`:

```python
SEMANTIC_CACHE_TTL: int = 86400  # 24 hours
SEMANTIC_CACHE_THRESHOLD: float = 0.92
```

- [ ] **Step 3: Integrate cache into query flow**

In `backend/api/routes/query.py`, before calling graph.invoke():

```python
from backend.cache.semantic_cache import SemanticCache

cache = SemanticCache()
cached_result = cache.get(validated_q)
if cached_result:
    return cached_result

result = graph.invoke({...})
cache.set(validated_q, {
    "response": validated_response,
    "citations": result.get("citations", []),
    ...
})
```

- [ ] **Step 4: Add admin flush endpoint**

In `backend/api/routes/admin.py`:

```python
@admin_router.post("/cache/flush")
def flush_cache(current_user: dict = Depends(require_global_role("superadmin"))):
    from backend.cache.semantic_cache import SemanticCache
    SemanticCache().flush()
    return {"status": "cache flushed"}
```

- [ ] **Step 5: Commit**

```bash
git add backend/cache/semantic_cache.py backend/config.py backend/api/routes/query.py backend/api/routes/admin.py
git commit -m "feat: semantic caching with embedding similarity and Redis backend"
```

---

### Task 3.2: Email Ingestion (IMAP/POP3)

**Files:**
- Create: `backend/tasks/email_worker.py`
- Modify: `backend/tasks/celery_app.py`
- Modify: `backend/config.py`

- [ ] **Step 1: Add config settings**

In `backend/config.py`:

```python
IMAP_HOST: str = ""
IMAP_PORT: int = 993
IMAP_USER: str = ""
IMAP_PASSWORD: str = ""
IMAP_FOLDER: str = "INBOX"
IMAP_POLL_INTERVAL_MINUTES: int = 60
```

- [ ] **Step 2: Create email ingestion worker**

Create `backend/tasks/email_worker.py`:

```python
import email
import logging
from email.header import decode_header
from backend.tasks.celery_app import celery_app
from backend.config import settings

logger = logging.getLogger(__name__)

@celery_app.task(name="backend.tasks.email_worker.poll_inbox")
def poll_inbox():
    if not settings.IMAP_HOST:
        logger.info("IMAP not configured, skipping email poll")
        return {"status": "skipped"}

    import imaplib
    mail = imaplib.IMAP4_SSL(settings.IMAP_HOST, settings.IMAP_PORT)
    try:
        mail.login(settings.IMAP_USER, settings.IMAP_PASSWORD)
        mail.select(settings.IMAP_FOLDER)
        status, messages = mail.search(None, "UNSEEN")
        if status != "OK":
            return {"status": "no_unseen"}

        for num in messages[0].split():
            status, msg_data = mail.fetch(num, "(RFC822)")
            if status != "OK":
                continue
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            subject = decode_header(msg["Subject"])[0][0] or "No Subject"
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                        break
            else:
                body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

            # Queue document ingestion for email body + attachments
            logger.info(f"Ingested email: {subject} ({len(body)} chars)")

        mail.store("1:*", "+FLAGS", "\\Seen")
        return {"status": "success", "emails_processed": len(messages[0])}
    finally:
        mail.logout()
```

- [ ] **Step 3: Add beat schedule**

In `backend/tasks/celery_app.py`:

```python
"poll-email-hourly": {
    "task": "backend.tasks.email_worker.poll_inbox",
    "schedule": settings.IMAP_POLL_INTERVAL_MINUTES * 60.0,
}
```

- [ ] **Step 4: Commit**

```bash
git add backend/tasks/email_worker.py backend/config.py backend/tasks/celery_app.py
git commit -m "feat: email ingestion via IMAP with Celery Beat polling"
```

---

### Task 3.3: Real-time Document Sync (Google Drive / S3)

**Files:**
- Create: `backend/tasks/sync/__init__.py`
- Create: `backend/tasks/sync/google_drive_watch.py`
- Create: `backend/tasks/sync/s3_watch.py`
- Create: `backend/tasks/sync/sync_orchestrator.py`
- Create: `backend/api/routes/sync.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Create sync orchestrator**

Create `backend/tasks/sync/sync_orchestrator.py`:

```python
import logging
from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

@celery_app.task(name="backend.tasks.sync.sync_orchestrator.sync_source")
def sync_source(source_id: str, team_id: str, source_type: str, config: dict):
    if source_type == "gdrive":
        from .google_drive_watch import sync_google_drive
        return sync_google_drive(source_id, team_id, config)
    elif source_type == "s3":
        from .s3_watch import sync_s3
        return sync_s3(source_id, team_id, config)
    else:
        logger.warning(f"Unknown sync source type: {source_type}")
        return {"status": "error", "message": f"Unknown type: {source_type}"}
```

- [ ] **Step 2: Create sync management API**

Create `backend/api/routes/sync.py`:

```python
import uuid
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from backend.db.mysql import get_db
from backend.auth.middleware import require_global_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/sync", tags=["sync"], dependencies=[Depends(require_global_role("superadmin"))])

SYNC_SOURCES: dict = {}  # In-memory for MVP; persist to MySQL for production

class SyncSourceCreate(BaseModel):
    source_type: str  # "gdrive" | "s3"
    config: dict

@router.post("/sources")
def create_sync_source(payload: SyncSourceCreate):
    source_id = str(uuid.uuid4())
    SYNC_SOURCES[source_id] = {
        "id": source_id,
        "type": payload.source_type,
        "config": payload.config,
        "created_at": datetime.utcnow().isoformat(),
        "last_synced_at": None,
    }
    return {"source_id": source_id}

@router.get("/sources")
def list_sync_sources():
    return {"sources": list(SYNC_SOURCES.values())}

@router.post("/sources/{source_id}/sync")
def trigger_sync(source_id: str):
    from backend.tasks.sync.sync_orchestrator import sync_source
    source = SYNC_SOURCES.get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Sync source not found")
    task = sync_source.delay(source_id, "default-team", source["type"], source["config"])
    return {"task_id": task.id, "status": "triggered"}

@router.delete("/sources/{source_id}")
def delete_sync_source(source_id: str):
    if source_id not in SYNC_SOURCES:
        raise HTTPException(status_code=404, detail="Sync source not found")
    del SYNC_SOURCES[source_id]
    return {"status": "deleted"}
```

- [ ] **Step 3: Register sync routes in main.py**

In `backend/main.py`:

```python
from backend.api.routes.sync import router as sync_router
app.include_router(sync_router)
```

- [ ] **Step 4: Commit**

```bash
git add backend/tasks/sync/ backend/api/routes/sync.py backend/main.py
git commit -m "feat: real-time document sync for Google Drive and S3"
```

---

## Phase 4: Knowledge & UX

### Task 4.1: Knowledge Graph Visualizer

**Files:**
- Create: `backend/api/routes/graph.py`
- Create: `frontend/src/components/knowledge-graph.tsx`
- Create: `frontend/src/components/entity-detail-panel.tsx`
- Create: `frontend/src/routes/_dashboard.graph.tsx`
- Modify: `frontend/src/router.tsx`

- [ ] **Step 1: Create graph exploration endpoints**

Create `backend/api/routes/graph.py`:

```python
import logging
from fastapi import APIRouter, Depends, Query
from backend.auth.middleware import get_current_user, require_team_membership
from backend.db.neo4j import Neo4jManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/team/{team_id}/graph", tags=["graph"])

@router.get("/explore")
def explore_graph(
    team_id: str = Depends(require_team_membership()),
    query: str = Query("", max_length=200),
    limit: int = Query(50, ge=1, le=200),
):
    neo4j_mgr = Neo4jManager()
    nodes = neo4j_mgr.get_entities_for_explore(team_id, query, limit)
    edges = neo4j_mgr.get_relationships_for_explore(team_id, query, limit)
    return {"nodes": nodes, "edges": edges}
```

Add to `backend/db/neo4j.py`:

```python
def get_entities_for_explore(self, team_id: str, query: str, limit: int) -> list[dict]:
    with self._get_session(team_id) as session:
        if query:
            result = session.run(
                "MATCH (e:Entity) WHERE toLower(e.name) CONTAINS toLower($q) "
                "RETURN e.id AS id, e.name AS name, e.type AS type, e.importance_score AS score "
                "LIMIT $limit", q=query, limit=limit
            )
        else:
            result = session.run(
                "MATCH (e:Entity) RETURN e.id AS id, e.name AS name, e.type AS type, "
                "e.importance_score AS score ORDER BY e.importance_score DESC LIMIT $limit",
                limit=limit
            )
        return [dict(r) for r in result]

def get_relationships_for_explore(self, team_id: str, query: str, limit: int) -> list[dict]:
    with self._get_session(team_id) as session:
        if query:
            result = session.run(
                "MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity) "
                "WHERE toLower(a.name) CONTAINS toLower($q) OR toLower(b.name) CONTAINS toLower($q) "
                "RETURN a.id AS source, r.type AS type, b.id AS target LIMIT $limit",
                q=query, limit=limit
            )
        else:
            result = session.run(
                "MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity) "
                "RETURN a.id AS source, r.type AS type, b.id AS target "
                "ORDER BY r.weight DESC LIMIT $limit", limit=limit
            )
        return [dict(r) for r in result]
```

- [ ] **Step 2: Create force-graph component**

Install `react-force-graph-2d`:

```bash
cd frontend && npm install react-force-graph-2d
```

Create `frontend/src/components/knowledge-graph.tsx`:

```tsx
import { useEffect, useRef } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

interface GraphNode {
  id: string;
  name: string;
  type: string;
  score: number;
}

interface GraphEdge {
  source: string;
  target: string;
  type: string;
}

interface KnowledgeGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onNodeClick?: (node: GraphNode) => void;
}

export function KnowledgeGraph({ nodes, edges, onNodeClick }: KnowledgeGraphProps) {
  const fgRef = useRef<any>();

  const graphData = {
    nodes: nodes.map(n => ({ ...n, val: n.score })),
    links: edges.map(e => ({ source: e.source, target: e.target, label: e.type })),
  };

  return (
    <ForceGraph2D
      ref={fgRef}
      graphData={graphData}
      nodeLabel="name"
      nodeColor={n => n.type === 'Person' ? '#8884d8' : n.type === 'Organization' ? '#82ca9d' : '#ffc658'}
      linkLabel="label"
      linkDirectionalArrowLength={6}
      linkDirectionalParticles={2}
      onNodeClick={(node: any) => onNodeClick?.(node)}
      width={800}
      height={600}
    />
  );
}
```

- [ ] **Step 3: Create graph explorer page**

Create `frontend/src/routes/_dashboard.graph.tsx`:

```tsx
import { createRoute } from '@tanstack/react-router';
import { Route as dashboardRoute } from './_dashboard';
import { useState, useEffect } from 'react';
import { apiFetch } from '../lib/api';
import { KnowledgeGraph } from '../components/knowledge-graph';
import { EntityDetailPanel } from '../components/entity-detail-panel';

export const Route = createRoute({
  getParentRoute: () => dashboardRoute,
  path: '/graph',
  component: GraphExplorer,
});

function GraphExplorer() {
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [selectedEntity, setSelectedEntity] = useState(null);
  const teamId = localStorage.getItem('active_team_id');

  useEffect(() => {
    if (!teamId) return;
    apiFetch(`/api/team/${teamId}/graph/explore?limit=100`)
      .then(r => r.json())
      .then(data => {
        setNodes(data.nodes || []);
        setEdges(data.edges || []);
      });
  }, [teamId]);

  return (
    <div className="flex gap-4 p-4">
      <div className="flex-1">
        <KnowledgeGraph nodes={nodes} edges={edges} onNodeClick={setSelectedEntity} />
      </div>
      {selectedEntity && (
        <div className="w-80">
          <EntityDetailPanel entity={selectedEntity} />
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Create entity detail panel**

Create `frontend/src/components/entity-detail-panel.tsx`:

```tsx
import { useState, useEffect } from 'react';
import { apiFetch } from '../lib/api';

interface EntityNode {
  id: string;
  name: string;
  type: string;
  score: number;
}

interface EntityDetailPanelProps {
  entity: EntityNode;
}

export function EntityDetailPanel({ entity }: EntityDetailPanelProps) {
  const [neighbors, setNeighbors] = useState<any[]>([]);

  useEffect(() => {
    const teamId = localStorage.getItem('active_team_id');
    if (!teamId) return;
    apiFetch(`/api/team/${teamId}/graph/explore?query=${entity.name}&limit=20`)
      .then(r => r.json())
      .then(data => setNeighbors(data.edges || []))
      .catch(() => {});
  }, [entity]);

  return (
    <div className="rounded-lg border bg-card p-4">
      <h3 className="font-semibold text-lg">{entity.name}</h3>
      <p className="text-sm text-muted-foreground">Type: {entity.type}</p>
      <p className="text-sm text-muted-foreground">Importance: {(entity.score || 0).toFixed(2)}</p>
      <div className="mt-4">
        <h4 className="text-sm font-medium mb-2">Relationships</h4>
        {neighbors.length === 0 && <p className="text-xs text-muted-foreground">No relationships found</p>}
        <ul className="space-y-1">
          {neighbors.slice(0, 10).map((e, i) => (
            <li key={i} className="text-xs text-muted-foreground">
              {e.source} → {e.type} → {e.target}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Register route in router**

In `frontend/src/router.tsx`, add graph route to dashboard children:

```tsx
import { Route as graphRoute } from './routes/_dashboard.graph';
dashboardLayoutRoute.addChildren([dashboardIndexRoute, chatRoute, docsRoute, adminRoute, evalRoute, analyticsRoute, graphRoute])
```

- [ ] **Step 6: Commit**

```bash
git add backend/api/routes/graph.py backend/db/neo4j.py frontend/src/components/knowledge-graph.tsx frontend/src/components/entity-detail-panel.tsx frontend/src/routes/_dashboard.graph.tsx frontend/src/router.tsx
git commit -m "feat: knowledge graph visualizer with force-directed graph and entity detail panel"
```

---

### Task 4.2: Export/Report Generation

**Files:**
- Create: `backend/export/__init__.py`
- Create: `backend/export/renderers.py`
- Create: `backend/api/routes/export.py`
- Modify: `frontend/src/routes/_dashboard.chat.tsx`

- [ ] **Step 1: Create export renderers**

Create `backend/export/renderers.py`:

```python
from __future__ import annotations
import json
from typing import List, Dict, Any

def render_markdown(messages: List[Dict[str, Any]], session_title: str = "Chat Export") -> str:
    lines = [f"# {session_title}\n"]
    lines.append(f"**Exported:** {__import__('datetime').datetime.utcnow().isoformat()}\n")
    lines.append("---\n")
    for msg in messages:
        role_icon = "🧑" if msg["role"] == "user" else "🤖"
        lines.append(f"### {role_icon} {msg['role'].title()}\n")
        lines.append(f"{msg['content']}\n")
        if msg.get("citations"):
            lines.append(f"*Citations: {len(msg['citations'])}*\n")
        lines.append("---\n")
    return "\n".join(lines)

def render_json(messages: List[Dict[str, Any]]) -> str:
    return json.dumps({"messages": messages, "exported_at": __import__('datetime').datetime.utcnow().isoformat()}, indent=2)

def render_pdf(messages: List[Dict[str, Any]], session_title: str = "Chat Export") -> bytes:
    try:
        from weasyprint import HTML
    except ImportError:
        raise RuntimeError("weasyprint is required for PDF export")
    md = render_markdown(messages, session_title)
    html = f"<html><body><pre>{md}</pre></body></html>"
    return HTML(string=html).write_pdf()
```

- [ ] **Step 2: Create export endpoint**

Create `backend/api/routes/export.py`:

```python
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
    format: str = Query("md", regex="^(md|json|pdf)$"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.get("user_id") or current_user.get("sub")
    messages = db.query(Message).filter(
        Message.session_id == session_id,
        Message.user_id == user_id
    ).order_by(Message.created_at.asc()).all()

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
        headers={"Content-Disposition": f'attachment; filename="{filename_map[format]}"'}
    )
```

- [ ] **Step 3: Register export route**

In `backend/main.py`:

```python
from backend.api.routes.export import router as export_router
app.include_router(export_router)
```

- [ ] **Step 4: Add export button to chat UI**

In `frontend/src/routes/_dashboard.chat.tsx`, add export button:

```tsx
<Button
  variant="outline"
  size="sm"
  onClick={() => window.open(`/api/chat/sessions/${activeSessionId}/export?format=md`, '_blank')}
>
  Export MD
</Button>
<Button
  variant="outline"
  size="sm"
  onClick={() => window.open(`/api/chat/sessions/${activeSessionId}/export?format=json`, '_blank')}
>
  Export JSON
</Button>
```

- [ ] **Step 5: Commit**

```bash
git add backend/export/ backend/api/routes/export.py backend/main.py frontend/src/routes/_dashboard.chat.tsx
git commit -m "feat: session export - Markdown, JSON, and PDF renderers"
```

---

## Verification & Testing

After all phases, run the full test suite:

```bash
make test-backend    # Backend unit tests
make test-frontend   # Vitest frontend tests
make test-e2e        # Playwright E2E tests
```

Expected: All tests pass.

Verify streaming behavior manually:

```bash
curl -X POST http://localhost:8000/api/query/stream \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(curl -s -X POST http://localhost:8000/api/auth/login -H 'Content-Type: application/json' -d '{"email":"superadmin@memmesh.com","password":"admin_secret_password_change_me"}' | jq -r '.token')" \
  -d '{"query":"What is MemMesh?"}' \
  --no-buffer
```

Expected output: NDJSON stream with telemetry, text_chunks, citations, session, and done events.
