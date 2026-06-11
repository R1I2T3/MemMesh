# MemMesh V2 Evolution: Architectural Fixes + New Feature Suite

**Date:** June 9, 2026
**Status:** Design Document

---

## 1. Overview & Scope

This document covers two tracks of work on MemMesh:
- **Track A: Architectural Fixes** — 17 issues identified in the current codebase that block functional and non-functional requirements from the V2 spec
- **Track B: New Features** — 11 user-selected enhancements beyond the V2 baseline

### Architecture Principles

- **Tenant isolation first** — Neo4j per-tenant databases, not property-based filtering
- **Real streaming** — LangGraph async streaming with telemetry events, not post-hoc token replay
- **Defense in depth** — Working Guardrails AI, rate limiting, proper RBAC
- **Observability by default** — Every agent decision is logged and queryable
- **Idempotent ingestion** — Document versioning via content hash, diff-aware re-indexing
- **Cost-conscious** — Semantic caching reduces LLM calls, analytics identifies waste

---

## 2. Track A: Architectural Fixes

### A1. Real SSE Streaming with LangGraph Async

**Problem:** `graph.invoke()` blocks until the full LLM response is ready. The "stream" endpoint replays tokens after the fact. No telemetry events are emitted.

**Solution:**
- Migrate from `graph.invoke()` to `graph.astream_events()` for real-time token emission
- Add telemetry event emission at each LangGraph node boundary
- Change `GET /api/query/stream` to emit V2-spec SSE format:
  - `{"type": "telemetry", "stage": "...", "status": "..."}`
  - `{"type": "text_chunk", "content": "..."}`
  - `{"type": "citation", ...}`
  - `{"type": "session", "session_id": "..."}`
  - `{"type": "done"}`

**Files affected:** `backend/agents/graph_orchestrator.py`, `backend/api/routes/query.py`

### A2. API Design Alignment with V2 Spec

**Problem:** Query uses `GET` with query params instead of `POST` with JSON body + `X-Active-Team-ID` header.

**Solution:**
- Change `GET /api/query` → `POST /api/query`
- Change `GET /api/query/stream` → `POST /api/query/stream`
- Move `team_id` from query param to `X-Active-Team-ID` header
- Add `POST /api/auth/register` and `POST /api/auth/refresh` endpoints
- Add team-based route paths: `/api/team/{team_id}/ingest/upload`, `/api/team/{team_id}/ingest/url`, etc.

**Files affected:** `backend/api/routes/query.py`, `backend/api/routes/auth.py`, `backend/api/routes/upload.py`, `frontend/src/routes/_dashboard.chat.tsx`, `frontend/src/lib/api.ts`

### A3. MySQL Schema Alignment

**Problem:** Current models are missing 6 of 10 V2-specified tables. Session/team relationships are implicit (plain string columns instead of FKs).

**Solution:** Add these tables via Alembic migration:
- `sessions` — session_id, user_id FK, team_id FK, title, created_at, consolidated_at
- `turns` — turn_id, session_id FK, team_id FK, role, content LONGTEXT, created_at
- `source_docs` — doc_id, team_id FK, source_type, source_ref, file_name, file_format, content_hash, status, error_message
- `vector_chunks` — chunk_id, team_id FK, doc_id FK, importance_score, last_accessed_at, page_number, section_heading
- `router_log` — id, team_id FK, user_id FK, query_hash, route, latency_ms
- `entity_resolution_log` — id, team_id FK, source_node_id, target_node_id, merge_reason
- `crawl_jobs` — job_id, team_id FK, source_url, status, pages_found

**Files affected:** `backend/models.py`, `backend/db/migrations/versions/*.py`

### A4. Neo4j Per-Tenant Database Isolation

**Problem:** Every Cypher query filters by `team_id` property on all nodes. Single DB namespace shared by all tenants.

**Solution:**
- Remove `team_id` property from all Entity nodes and RELATES_TO relationships
- Rely on Neo4j multi-database routing (`team-{team_id}`) as the isolation boundary
- Update all Cypher queries to omit team_id filtering
- Add automatic database creation on team provisioning

**Files affected:** `backend/db/neo4j.py`, `backend/agents/graph_orchestrator.py`, `backend/ingestion/extractor.py`, `backend/tasks/ingestion_worker.py`, `backend/tasks/decay_worker.py`

### A5. Guardrails AI — Working Safety Shield

**Problem:** Falls back to weak regex (3 words) on import failure. No real PII/jailbreak detection.

**Solution:**
- Replace `guardrails-hub` dependency with `presidio-analyzer` + `presidio-anonymizer` for PII detection (lighter, deterministic, works offline)
- Add `llamaguard` or a small classifier prompt for toxicity/jailbreak detection
- Remove the false `except` that silently swallows import errors
- Add unit tests that verify safety catches known attack patterns

**Files affected:** `backend/agents/safety.py`, `backend/requirements.txt`

### A6. Rate Limiting

**Problem:** No protection on auth or query endpoints.

**Solution:**
- Add `slowapi` middleware with tiered limits:
  - `/api/auth/login`: 5 req/min per IP
  - `/api/auth/register`: 3 req/min per IP
  - `/api/query`: 30 req/min per user
  - General API: 100 req/min per user
- Store counters in Redis for distributed rate limiting

**Files affected:** `backend/main.py`, `backend/config.py`, `backend/requirements.txt`

### A7. RBAC Alignment with V2 Spec

**Problem:** Auto-joins users to teams, no X-Active-Team-ID validation, wrong role names.

**Solution:**
- Validate `X-Active-Team-ID` against user's `team_members` membership
- Add `require_team_role("lead")` dependency for upload endpoints
- Align role names to spec: `user`, `team_lead` (not `member`, `admin`, `owner`)
- Remove auto-join on first upload (explicit invite only)

**Files affected:** `backend/auth/middleware.py`, `backend/api/routes/upload.py`, `backend/api/routes/admin.py`

### A8. Neo4j Connection Pooling (Not Per-Request)

**Problem:** New `Neo4jManager()` (new driver connection) created per HTTP request in graph orchestrator.

**Solution:**
- Use a singleton Neo4j driver with connection pooling
- Reuse driver across requests, create sessions per tenant
- Close sessions, not drivers

**Files affected:** `backend/db/neo4j.py`, `backend/agents/graph_orchestrator.py`

### A9. Redis Port Fix

**Problem:** Config uses port 6379, Docker exposes 6380.

**Solution:** Fix `docker-compose.yml` to use 6379:6379 or make REDIS_URL configurable per environment in `.env`.

**Files affected:** `docker-compose.yml`, `.env.example`

### A10. Query History in Retrieval

**Problem:** History passed to LangGraph state but not used by retrieval nodes.

**Solution:**
- Add `history` to the context builder in `synthesize_node`
- For retrieval: prepend last N user messages to the query for vector search context
- For graph retrieval: extract keywords from both query and recent history

**Files affected:** `backend/agents/graph_orchestrator.py`, `backend/agents/retriever.py`

### A11. Pagination on Session List

**Problem:** `GET /api/chat/sessions` returns all sessions unbounded.

**Solution:**
- Add `offset`/`limit` query parameters (default: 20, max: 200)
- Return `total` count alongside results

**Files affected:** `backend/api/routes/query.py`

### A12. SSE Error Handling

**Problem:** `onerror` throws, causing infinite fetch-event-source retry loop.

**Solution:**
- Return 401/403 directly from stream endpoint before starting stream
- On stream error, emit `{"type": "error", "detail": "..."}` event and close
- Frontend: do not retry on 4xx errors

**Files affected:** `backend/api/routes/query.py`, `frontend/src/routes/_dashboard.chat.tsx`

### A13. Test Infrastructure — MySQL-Compatible Testing

**Problem:** Tests use SQLite in-memory, masking MySQL-specific bugs.

**Solution:**
- Use `testcontainers` library for a real MySQL container in CI
- For local development, use SQLite with MySQL-compatibility mode
- Add a CI matrix that runs tests against both SQLite and MySQL

**Files affected:** `backend/tests/conftest.py`, `.github/workflows/ci.yml`, `backend/requirements.txt`

### A14. Weak Entity Extraction Fix

**Problem:** Heuristic extraction creates sequential false relationships.

**Solution:**
- Remove the sequential adjacency fallback entirely
- When Gemini API key is available, use structured LLM extraction with validation
- When API key is unavailable, skip graph extraction (don't generate noise)

**Files affected:** `backend/ingestion/extractor.py`

### A15. Celery Fork Safety

**Problem:** Global singletons for Weaviate/Neo4j connections unsafe for forked workers.

**Solution:**
- Remove global `_weaviate_mgr` / `_neo4j_mgr` singletons
- Use `Celery.worker_process_init` / `worker_process_shutdown` signals for connection lifecycle
- Each worker process gets its own connections

**Files affected:** `backend/db/weaviate.py`, `backend/db/neo4j.py`, `backend/tasks/celery_app.py`

---

## 3. Track B: New Features

### B1. RAG Evaluation Dashboard

Track faithfulness, hallucination, and answer relevancy scores over time with visual trend charts.

**Components:**
- `backend/api/routes/eval.py` — Extended with scheduled evaluation runs and historical storage
- `backend/db/eval_scores` table — stores per-query metric scores, timestamps, model version
- `frontend/src/routes/_dashboard.eval.tsx` — Dashboard page with trend charts (Recharts)
- Celery beat task `weekly-eval-run` — runs DeepEval on accumulated feedback

**Data flow:** User feedback → DeepEval metrics → eval_scores table → Chart.js/Recharts trend visualization

**Metric storage schema:**
```sql
CREATE TABLE eval_scores (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    feedback_id VARCHAR(36) NOT NULL,
    faithfulness_score FLOAT,
    hallucination_score FLOAT,
    answer_relevancy_score FLOAT,
    model_version VARCHAR(50),
    evaluated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (feedback_id) REFERENCES user_feedbacks(feedback_id)
);
```

### B2. Semantic Caching

Cache responses to semantically similar queries, reducing LLM calls by 30-60%.

**Architecture:**
- Embedding-based cache key: compute embedding of query, find nearest neighbor in cache
- Similarity threshold: 0.92 cosine similarity to hit cache
- Cache entry TTL: configurable (default 24h)
- Cache invalidation: on document re-index or explicit flush

**Components:**
- `backend/cache/semantic_cache.py` — Cache class using Redis + vector similarity
- `backend/agents/graph_orchestrator.py` — Check cache before invoking LLM, store after
- `backend/config.py` — `SEMANTIC_CACHE_TTL`, `SEMANTIC_CACHE_THRESHOLD` settings
- Admin endpoint: `POST /api/admin/cache/flush`

**Cache key structure in Redis:**
```
semantic_cache:{embedding_hash} → {"response": "...", "citations": [...], "created_at": "..."}
```

### B3. Document Versioning

Track document changes across re-uploads with diff-aware re-indexing.

**Architecture:**
- Content hash (SHA-256) computed on upload
- Same hash → skip (idempotent)
- Different hash for same filename → new version
- `source_docs` table extended with `version_number`, `previous_version_id`, `change_summary`
- On version change: mark old chunks as `superseded`, index new chunks, keep old for history

**Components:**
- `backend/db/migrations/004_versioning.sql` — Schema migration for versioning support
- `backend/ingestion/versioning.py` — Version comparison logic
- `backend/api/routes/upload.py` — Extended with version-aware upload
- Frontend: `frontend/src/routes/_dashboard.docs.tsx` — Version history panel

### B4. Collaborative Annotations

Users highlight and comment on specific document passages.

**Architecture:**
- Annotations stored in MySQL: `annotation_id, doc_id, user_id, anchor_start, anchor_end, highlighted_text, comment, created_at, updated_at`
- Highlights rendered client-side using text range matching
- Comment threads: replies via `parent_annotation_id`
- Real-time updates via polling or WebSocket (MVP: polling every 30s)

**Components:**
- `backend/models.py` — Annotation model
- `backend/api/routes/annotations.py` — CRUD endpoints for annotations
- `frontend/src/components/annotation-layer.tsx` — Highlight overlay on document text
- `frontend/src/components/annotation-thread.tsx` — Comment thread UI

### B5. Email Ingestion (IMAP/POP3)

Auto-ingest incoming emails and attachments into RAG index.

**Architecture:**
- Celery Beat task `poll-email-hourly` — connects to IMAP, fetches unseen messages
- Email body → parsed as Markdown via Docling
- Attachments (PDF, DOCX, etc.) → routed through existing Docling pipeline
- `crawl_jobs` record created per ingested email

**Components:**
- `backend/tasks/email_worker.py` — IMAP polling + parsing logic
- `backend/config.py` — `IMAP_HOST`, `IMAP_USER`, `IMAP_PASSWORD`, `IMAP_FOLDER`
- `backend/api/routes/admin.py` — Endpoint to configure email sources per team

### B6. Real-time Document Sync (Google Drive / S3 / SharePoint)

Watch external storage for changes and auto-re-index.

**Architecture:**
- Push-based: webhook receivers for platforms that support them (Google Drive push notifications, S3 EventBridge)
- Poll-based: Celery Beat task for platforms without webhooks
- Change detection: compare content hash of synced file vs stored hash
- Sync state tracking: `sync_sources` table with `source_id, team_id, source_type, last_synced_at, watch_channel_id`

**Components:**
- `backend/tasks/sync/google_drive_watch.py` — Google Drive webhook receiver
- `backend/tasks/sync/s3_watch.py` — S3 event notification handler
- `backend/tasks/sync/sync_orchestrator.py` — Diff-aware sync execution
- `backend/api/routes/sync.py` — Sync source management endpoints

### B7. Knowledge Graph Visualizer

Interactive Neo4j graph browser in React (similar to Neo4j Bloom).

**Architecture:**
- Backend: `GET /api/team/{team_id}/graph/explore` — returns graph data (nodes + edges) for a query
- Backend: `GET /api/team/{team_id}/graph/entity/{entity_id}` — entity detail + neighborhood
- Frontend: `react-force-graph-2d` or `d3-force` for interactive visualization
- Features: drag, zoom, click entity for details, expand neighbor nodes, filter by entity type

**Components:**
- `backend/api/routes/graph.py` — Graph exploration endpoints
- `frontend/src/components/knowledge-graph.tsx` — 2D force-directed graph component
- `frontend/src/routes/_dashboard.graph.tsx` — Graph explorer page
- `frontend/src/components/entity-detail-panel.tsx` — Side panel for selected entity

### B8. Audit Logging

Full compliance trail: who queried what, which docs were used, timestamps.

**Architecture:**
- Append-only `audit_log` table (no UPDATEs, no DELETEs)
- Each query execution creates an audit record with: user_id, team_id, query text, response length, retrieval sources, latency_ms, timestamp
- Admin-only query endpoint: `GET /api/admin/audit/logs` with filtering
- Retention policy: configurable TTL (default 90 days), auto-purge via Celery Beat

**Schema:**
```sql
CREATE TABLE audit_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    team_id VARCHAR(36) NOT NULL,
    query_text TEXT NOT NULL,
    response_length INT,
    retrieval_sources JSON,
    latency_ms INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_audit_team_time (team_id, created_at DESC),
    INDEX idx_audit_user (user_id, created_at DESC)
) ENGINE=InnoDB;
```

**Components:**
- `backend/models.py` — AuditLog model
- `backend/api/routes/query.py` — Audit record creation on every query
- `backend/api/routes/admin.py` — Audit log query endpoint
- `backend/tasks/audit_cleanup.py` — TTL-based purge task

### B9. Analytics Dashboard

Popular queries, top documents, user activity, performance metrics.

**Architecture:**
- Aggregation queries on `audit_log` and `router_log` tables
- Materialized via Celery Beat: `aggregate-analytics-hourly`
- Cached in Redis with 1h TTL for dashboard performance
- Frontend: Recharts for visualization

**Metrics tracked:**
- Queries over time (daily/weekly active users)
- Popular documents (most frequently retrieved source_docs)
- Average response latency over time
- Route distribution (vector vs graph vs hybrid)
- CRAG fallback rate (how often web search is triggered)
- Error rate (failed queries / total queries)

**Components:**
- `backend/tasks/analytics_worker.py` — Hourly aggregation
- `backend/api/routes/analytics.py` — Dashboard data endpoints
- `frontend/src/routes/_dashboard.analytics.tsx` — Metrics dashboard page

### B10. PDF Viewer with Highlighted Citations

Click a citation → scroll PDF to exact page/position.

**Architecture:**
- Store page-level bounding boxes from Docling metadata
- Frontend: `react-pdf` or `pdfjs-dist` for PDF rendering
- Citation click → extract page_number + bbox → scroll PDF viewport to position
- Server: `GET /api/documents/{doc_id}/pdf` — serves PDF binary (cached)

**Components:**
- `backend/api/routes/documents.py` — PDF serving endpoint
- `frontend/src/components/pdf-viewer.tsx` — PDF renderer with scroll-to-citation
- `frontend/src/components/CitationDrawer.tsx` — Extended with "Open PDF" button

### B11. Export/Report Generation

Export conversation threads as PDF, Markdown, or structured reports.

**Architecture:**
- Backend: `POST /api/chat/sessions/{session_id}/export?format=pdf|md|json`
- Markdown export: straightforward template with message content
- PDF export: convert Markdown via `weasyprint` or `pdfkit`
- JSON export: raw message array for programmatic consumption
- Report template: include session metadata, full conversation, citations used

**Components:**
- `backend/api/routes/export.py` — Export endpoints
- `backend/export/renderers.py` — Markdown/PDF/JSON renderers
- `frontend/src/routes/_dashboard.chat.tsx` — Export button in chat UI

---

## 4. Dependency Graph

```
Phase 0: Foundation (must come first)
  A1 (SSE streaming) ─── blocks ──→ B1 (Eval Dashboard, needs real stream)
  A2 (API design) ─── blocks ──→ All frontend features
  A3 (MySQL schema) ─── blocks ──→ B1, B3, B4, B8, B9
  A4 (Neo4j isolation) ─── blocks ──→ B7 (Graph visualizer)
  A7 (RBAC) ─── blocks ──→ B8 (Audit logging)

Phase 1: Independently buildable after Phase 0
  A5 (Guardrails) ─── independent
  A6 (Rate limiting) ─── independent
  A8 (Neo4j pooling) ─── independent
  A9 (Redis port) ─── independent
  A10 (History retrieval) ─── independent
  A11 (Pagination) ─── independent
  A12 (SSE errors) ─── independent
  A13 (Test infra) ─── independent
  A14 (Entity extraction) ─── independent
  A15 (Celery safety) ─── independent

Phase 2: New features (depend on Phase 0)
  B1 (Eval Dashboard) ─── needs A1, A3
  B2 (Semantic Cache) ─── needs A1
  B3 (Doc Versioning) ─── needs A3
  B4 (Annotations) ─── needs A3
  B5 (Email ingest) ─── independent (new subsystem)
  B6 (Doc sync) ─── independent (new subsystem)
  B7 (Graph visualizer) ─── needs A4, A8
  B8 (Audit logging) ─── needs A2, A7, A3
  B9 (Analytics) ─── needs B8
  B10 (PDF viewer) ─── needs A3
  B11 (Export) ─── needs A1
```

---

## 5. File Structure Map

### New Files to Create

```
backend/
├── api/routes/
│   ├── annotations.py          # B4 — Annotation CRUD
│   ├── analytics.py            # B9 — Dashboard data endpoints
│   ├── export.py               # B11 — Export endpoints
│   ├── graph.py                # B7 — Graph exploration
│   └── sync.py                 # B6 — Sync source management
├── cache/
│   └── semantic_cache.py       # B2 — Embedding-based cache
├── db/migrations/
│   ├── 004_versioning.sql      # B3 — Versioning schema
│   └── 005_features.sql        # B4, B8 — Annotations, audit_log, eval_scores
├── export/
│   ├── __init__.py
│   └── renderers.py            # B11 — Markdown/PDF/JSON renderers
├── ingestion/
│   └── versioning.py           # B3 — Version diff logic
├── tasks/
│   ├── analytics_worker.py     # B9 — Hourly aggregation
│   ├── audit_cleanup.py        # B8 — TTL purge
│   ├── email_worker.py         # B5 — IMAP polling
│   └── sync/
│       ├── __init__.py
│       ├── google_drive_watch.py  # B6
│       ├── s3_watch.py            # B6
│       └── sync_orchestrator.py   # B6
└── tests/
    └── test_annotations.py     # B4 tests
    └── test_semantic_cache.py  # B2 tests

frontend/src/
├── components/
│   ├── annotation-layer.tsx    # B4
│   ├── annotation-thread.tsx   # B4
│   ├── knowledge-graph.tsx     # B7
│   ├── entity-detail-panel.tsx # B7
│   └── pdf-viewer.tsx          # B10
├── routes/
│   ├── _dashboard.analytics.tsx # B9
│   ├── _dashboard.eval.tsx      # B1
│   └── _dashboard.graph.tsx     # B7
```

### Modified Files

```
backend/
├── main.py                     # A6 — Rate limiting middleware
├── config.py                   # A6, B2 — New settings
├── models.py                   # A3 — New tables
├── agents/
│   ├── graph_orchestrator.py   # A1, A10 — Async streaming, history in retrieval
│   ├── safety.py               # A5 — Replace Guardrails with presidio
│   ├── retriever.py            # A10 — History-aware retrieval
│   └── crag.py                 # A1 — Telemetry emission
├── api/routes/
│   ├── query.py                # A1, A2, A12 — POST, SSE streaming, audit
│   ├── auth.py                 # A2 — Register, refresh endpoints
│   ├── admin.py                # A7 — Role alignment
│   └── upload.py               # A7, B3 — Team role check, versioning
├── db/
│   ├── mysql.py                # A3 — Session management
│   ├── weaviate.py             # A15 — No global singletons
│   └── neo4j.py                # A4, A8, A15 — Per-tenant, pooling, no singletons
├── ingestion/
│   ├── extractor.py            # A14 — No noise generation
│   └── parser.py               # — B3 — Version metadata
├── tasks/
│   ├── celery_app.py           # A15 — Worker lifecycle
│   ├── ingestion_worker.py     # B3 — Version-aware indexing
│   └── decay_worker.py         # A15 — Safe connection handling
├── auth/
│   └── middleware.py           # A7 — Team membership validation
└── tests/
    ├── conftest.py             # A13 — Testcontainers MySQL
    └── test_query.py           # A2 — Updated for POST
frontend/
├── src/
│   ├── routes/_dashboard.chat.tsx  # A1, A2, A12 — SSE stream refactor
│   ├── lib/api.ts              # A2 — X-Active-Team-ID header
│   └── components/CitationDrawer.tsx  # B10 — PDF viewer integration
docker-compose.yml              # A9 — Redis port fix
```
