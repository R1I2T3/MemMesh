# Pipeline Refactoring Design — MemMesh

**Date:** 2026-05-17
**Status:** Approved

## Problem

The current retrieval pipeline has several components that were built but never integrated:
- `MultiHopRetriever` is instantiated but never called
- `QueryRouter` exists but the agent blindly hits both vector and graph every time
- `HybridRetriever` (cross-encoder reranker) is never used
- `QueryRewriter` only applies to vector search, not graph search
- `chunk_webpage`/`extract_text_from_url`/`chunk_document` have no API endpoint
- `tools/` directory uses legacy singleton pattern, superseded by context-var tools
- `agents/rag_team.py` is superseded by `build_rag_team_with_stores()`
- `test_api.py` and `test_query_api.py` are heavily duplicated

## Architecture: Unified Retrieval Pipeline

### Before (current)

```
Query → build_rag_team_with_stores()
  → Agent with 2 tools:
    1. vector_search_tool(query) → QueryRewriter → vector search → citations
    2. lookup_entity(entity) → single-hop graph fetch → citations
  → MultiHopRetriever created but never used
  → No routing, no reranking, results concatenated
```

### After (redesigned)

```
Query → hybrid_memory_search(query)
  1. QueryRouter.classify_query(query) → "vector" | "graph" | "hybrid"
  2. QueryRewriter.rewrite(query) → step_back + alternatives
  3. Parallel retrieval:
     - Vector: embed original + rewritten queries → LanceDB search
     - Graph: extract entities → MultiHopRetriever.run() → intelligent traversal
  4. HybridRetriever.rerank() → cross-encoder scores all results together
  5. Return unified, ranked context string with citations
```

The agent gets **one tool** (`hybrid_memory_search`) instead of two. This is simpler for the LLM, ensures consistent retrieval quality, and eliminates wasted tool calls.

## File Relocations

### `db/dependencies.py` — split into 3 files (god file, mixes 3 concerns)

This file currently mixes context variable management, FastAPI dependency injection, and retrieval pipeline logic. Each belongs in a different layer.

| Current location | Move to | Reason |
|------------------|---------|--------|
| `_graph_store_ctx`, `_vector_store_ctx`, `_citations_ctx` + all getters/setters | `db/context.py` (new) | Context variables are DB-layer state management |
| `get_graph_store()`, `get_vector_store()` | `api/dependencies.py` (new) | FastAPI DI functions belong in the API layer, not db/ |
| `vector_search_with_rewriting()` | `agents/retrieval/pipeline.py` (new) | This is retrieval logic, not a database concern |
| `build_rag_team_with_stores()` | `agents/rag_team.py` (replace existing) | Agent construction belongs in agents/, not db/ |
| `get_embedder()` | DELETE | Never wired, not needed |

### `utils/chunker.py` — extract file parsing into ingestion layer

This file mixes pure chunking utilities with file format extraction (PDF, DOCX, PPTX, EML parsing). File extraction is ingestion logic, not a general utility.

| Current location | Move to | Reason |
|------------------|---------|--------|
| `extract_text_from_file()` | `ingestion/extractors.py` (new) | File format parsing is ingestion, not a utility |
| `extract_text_from_url()` | `ingestion/extractors.py` (new) | Web scraping is ingestion, not a utility |
| `chunk_webpage()` | `ingestion/extractors.py` (new) | Composes extract_text_from_url + chunk_text, belongs with extraction |
| `chunk_text()` | `utils/chunker.py` (keep) | Pure text chunking — this IS a utility |
| `chunk_document()` | `ingestion/extractors.py` (new) | Orchestrates extraction + chunking, belongs in ingestion layer |

### `auth/` — deduplicate `get_auth_store()`

| Current location | Fix |
|------------------|-----|
| `auth/routes.py:get_auth_store()` | DELETE — duplicate |
| `auth/middleware.py:get_auth_store()` | Keep as single source, import in routes |

### `workers/tasks.py` — remove module-level global state

| Current location | Fix |
|------------------|-----|
| `graph_store = GraphStore(...)` at module level | Lazy init inside task functions |
| `vector_store = VectorStore(...)` at module level | Lazy init inside task functions |
| `memory_manager = MemoryManager(...)` at module level | Lazy init inside task functions |

Module-level store initialization causes: (1) Celery worker startup fails if Neo4j/LanceDB unavailable, (2) stores can't be mocked in tests without sys.modules hacking, (3) no way to use different stores per task.

### `db/lifecycle/memory_manager.py` — remove cross-layer dependency

| Current location | Fix |
|------------------|-----|
| `from agents.extractor_agent import ExtractorAgent` | Accept extractor as constructor parameter |

The memory manager is a DB-layer component that shouldn't import from agents/. The extractor should be injected, making the manager testable without LLM dependencies.

## Deletions

### Files to delete entirely
| File | Reason |
|------|--------|
| `agents/rag_team.py` | Superseded by `build_rag_team_with_stores()` |
| `tools/vector_tool.py` | Legacy singleton, replaced by context-var tools |
| `tools/graph_tool.py` | Legacy singleton, replaced by context-var tools |

### Functions to delete from existing files
| File | Function | Reason |
|------|----------|--------|
| `db/dependencies.py` | `get_embedder()` | FastAPI dep never wired |
| `auth/middleware.py` | `require_admin()` | No route uses it |
| `auth/models.py` | `TokenRequest` | Never used |
| `auth/models.py` | `RevokeApiKeyRequest` | Never used |

### Code to inline
| File | Code | Reason |
|------|------|--------|
| `auth/routes.py` | `validate_admin_api_key()`, `_admin_auth_dep()` | Only used once on `register` route |

### Duplicate tests to merge
| Files | Action |
|-------|--------|
| `tests/unit/test_api.py` + `tests/unit/test_query_api.py` | Merge into `tests/unit/test_api.py`, remove duplicates |

### Deduplicated code
| Issue | Fix |
|-------|-----|
| `get_auth_store()` defined in `auth/routes.py` AND `auth/middleware.py` | Keep only in `auth/middleware.py`, import in routes |

## New Integrations

### 1. `hybrid_memory_search` tool (in `agents/retrieval/pipeline.py`)

Replaces `vector_search_tool` + `lookup_entity`. Single tool that runs the full pipeline:
- Routes query (vector/graph/hybrid)
- Rewrites query for recall
- Runs vector search with rewritten queries
- Runs multi-hop graph retrieval when route is graph or hybrid
- Reranks all results with cross-encoder
- Returns unified context string, tracks citations

### 2. `QueryRouter` integrated into retrieval

Called at the start of `hybrid_memory_search`. Controls which retrieval paths execute:
- `vector` → only vector search (saves graph API cost)
- `graph` → only multi-hop graph (saves vector embed cost)
- `hybrid` → both paths, then rerank

### 3. `QueryRewriter` applied to graph search

Currently only used for vector search. Also applied to graph: rewritten queries feed into `MultiHopRetriever` for broader entity extraction.

### 4. `MultiHopRetriever` actually runs

Replaces the hardcoded `lookup_entity` single-hop fetch. Uses LLM-based entity extraction, intelligent traversal, and termination detection.

### 5. `HybridRetriever` reranks fused results

When both vector and graph return results (hybrid route), cross-encoder reranks them into a single ordered list. Pure vector or pure graph routes skip reranking (single-source results are already ranked).

### 6. New `/ingest/url` endpoint (in `agentos.py`)

Accepts a URL, extracts text via `extract_text_from_url`, chunks via `chunk_text`, and queues async ingestion via Celery. Reuses the existing `process_document_ingestion` task by writing extracted text to a temp file.

## File Changes Summary

### New files
| File | Contents |
|------|----------|
| `db/context.py` | Context variable management (extracted from `db/dependencies.py`) |
| `api/dependencies.py` | FastAPI DI functions `get_graph_store`, `get_vector_store` |
| `api/routes/__init__.py` | Router assembly |
| `api/routes/query.py` | `/query` endpoint (extracted from `agentos.py`) |
| `api/routes/memory.py` | `/memory/search`, `/memory/graph` endpoints |
| `api/routes/ingest.py` | `/ingest`, `/ingest/{task_id}`, `/ingest/url` endpoints |
| `api/routes/session.py` | `/session/new` endpoint |
| `api/routes/health.py` | `/health` endpoint |
| `agents/retrieval/pipeline.py` | `vector_search_with_rewriting()`, `hybrid_memory_search()` |
| `ingestion/extractors.py` | `extract_text_from_file()`, `extract_text_from_url()`, `chunk_document()`, `chunk_webpage()` |

### Deleted files
| File | Reason |
|------|--------|
| `agents/rag_team.py` | Replaced — agent construction moves to new `agents/rag_team.py` with `build_rag_team_with_stores` |
| `tools/vector_tool.py` | Legacy singleton, replaced by pipeline tools |
| `tools/graph_tool.py` | Legacy singleton, replaced by pipeline tools |
| `tools/` directory | Empty after above deletions |
| `tests/unit/test_query_api.py` | Merged into `test_api.py` |
| `tests/unit/test_vector_tool.py` | Tools deleted, tests move to `test_pipeline.py` |
| `tests/unit/test_graph_tool.py` | Tools deleted, tests move to `test_pipeline.py` |

### Rewritten files
| File | Changes |
|------|---------|
| `db/dependencies.py` | DELETE — contents split into `db/context.py`, `api/dependencies.py`, `agents/retrieval/pipeline.py` |
| `db/lifecycle/memory_manager.py` | Remove `ExtractorAgent` import, accept extractor as constructor param |
| `agents/rag_team.py` | Rewrite: contains `build_rag_team_with_stores()` with single `hybrid_memory_search` tool |
| `auth/middleware.py` | Remove `require_admin()`, keep `get_auth_store()` as single source |
| `auth/routes.py` | Inline admin auth, import `get_auth_store` from middleware |
| `auth/models.py` | Remove `TokenRequest`, `RevokeApiKeyRequest` |
| `utils/chunker.py` | Remove `extract_text_from_file`, `extract_text_from_url`, `chunk_document`, `chunk_webpage` |
| `workers/tasks.py` | Remove module-level globals, lazy-init stores inside tasks, update imports |
| `agentos.py` | Slim down to app assembly + lifespan only, include routers from `api/routes/` |
| `scripts/verify_connection.py` | Update imports for new structure |

### Updated imports (all files that import from moved/deleted modules)
| File | Import change |
|------|---------------|
| `agentos.py` | `from db.dependencies import ...` → `from api.dependencies import ...`, `from db.context import ...` |
| `workers/tasks.py` | `from utils.chunker import extract_text_from_file, chunk_text` → `from ingestion.extractors import extract_text_from_file, chunk_document` |
| `db/lifecycle/memory_manager.py` | Remove `from agents.extractor_agent import ExtractorAgent` |
| `tests/unit/test_chunker.py` | Update imports for moved functions |
| `tests/unit/test_workers.py` | Update imports for lazy-init tasks |
| `tests/unit/test_ingestion_task.py` | Update imports for lazy-init tasks |
| `tests/unit/test_memory_manager.py` | Update for extractor-as-param MemoryManager |
| `tests/unit/test_retrieval_pipeline.py` | Import from `agents.retrieval.pipeline` instead of `db.dependencies` |
| `tests/unit/test_api.py` | Merge with test_query_api.py, update for new router structure |

### Unchanged files (now actively used)
| File | Status |
|------|--------|
| `agents/retrieval/multi_hop.py` | Now called by pipeline |
| `agents/router/query_router.py` | Now called by pipeline |
| `agents/router/query_rewriter.py` | Now used for both vector and graph paths |
| `agents/extractor_agent.py` | Injected into MemoryManager, used by ingestion task |
| `utils/fusion/reranker.py` | Now called by pipeline |
| `utils/embedder.py` | No changes |
| `utils/input_validator.py` | No changes |
| `utils/observability.py` | No changes |
| `db/graph_store.py` | No changes |
| `db/vector_store.py` | No changes |
| `db/session_store.py` | No changes |
| `db/auth_store.py` | No changes |
| `db/citation.py` | No changes |
| `auth/jwt.py` | No changes |
| `auth/__init__.py` | No changes |
| `workers/celery_app.py` | No changes |
| All component unit tests | QueryRouter, QueryRewriter, MultiHop, Reranker, Embedder, Chunker, GraphStore, VectorStore, SessionStore, AuthStore, JWT, Citation, Observability, InputValidator |

## Risk Mitigation

- All existing tests for individual components (QueryRouter, QueryRewriter, MultiHopRetriever, HybridRetriever) remain unchanged and passing
- Public API endpoints (`/query`, `/memory/search`, `/memory/graph`, `/ingest`, `/ingest/{task_id}`, `/health`, `/session/new`, `/auth/*`) keep same signatures
- `build_rag_team_with_stores(graph_store, vector_store)` signature unchanged, only moved to `agents/rag_team.py`
- Celery task names unchanged (`process_document_ingestion`, `trigger_memory_decay`, etc.)
- Import paths change for: `db.dependencies` → `db.context` + `api.dependencies` + `agents.retrieval.pipeline`
- Import paths change for: `utils.chunker.extract_text_from_file` → `ingestion.extractors.extract_text_from_file`

## Final Project Structure

```
MemMesh/
├── agents/
│   ├── rag_team.py              # build_rag_team_with_stores() — single hybrid_memory_search tool
│   ├── extractor_agent.py       # Triple extraction via LLM
│   ├── retrieval/
│   │   ├── __init__.py          # exports MultiHopRetriever, MultiHopResult
│   │   ├── multi_hop.py         # MultiHopRetriever — intelligent graph traversal
│   │   └── pipeline.py          # vector_search_with_rewriting(), hybrid_memory_search()
│   └── router/
│       ├── query_router.py      # QueryRouter — vector/graph/hybrid classification
│       └── query_rewriter.py    # QueryRewriter — step-back + alternative queries
├── api/
│   ├── dependencies.py          # FastAPI DI: get_graph_store, get_vector_store
│   └── routes/
│       ├── __init__.py          # router assembly
│       ├── health.py            # /health
│       ├── query.py             # /query (streaming)
│       ├── memory.py            # /memory/search, /memory/graph
│       ├── ingest.py            # /ingest, /ingest/{task_id}, /ingest/url
│       └── session.py           # /session/new
├── auth/
│   ├── __init__.py
│   ├── jwt.py                   # encode_jwt, decode_jwt, JWTError
│   ├── middleware.py            # require_auth, get_auth_store (single source)
│   ├── models.py                # Pydantic request/response models
│   └── routes.py                # /auth/* endpoints
├── db/
│   ├── context.py               # ContextVar management for stores/citations
│   ├── graph_store.py           # Neo4j wrapper
│   ├── vector_store.py          # LanceDB wrapper
│   ├── session_store.py         # SQLite session/message store
│   ├── auth_store.py            # SQLite user/team/api_key store
│   ├── citation.py              # CitationResult dataclass
│   ├── dependencies.py          # DELETED — contents split across context.py, api/dependencies.py, agents/retrieval/pipeline.py
│   ├── migrations/
│   │   └── 001_auth_sessions.sql
│   └── lifecycle/
│       └── memory_manager.py    # Memory decay, consolidation, dedup (extractor injected)
├── ingestion/
│   └── extractors.py            # extract_text_from_file, extract_text_from_url, chunk_document, chunk_webpage
├── utils/
│   ├── chunker.py               # chunk_text only (pure chunking utility)
│   ├── embedder.py              # Google GenAI embedding
│   ├── input_validator.py       # Query validation, injection/PII detection
│   ├── observability.py         # Request tracing, JSON logging
│   └── fusion/
│       └── reranker.py          # HybridRetriever — cross-encoder reranking
├── workers/
│   ├── celery_app.py            # Celery app config
│   └── tasks.py                 # Ingestion tasks (lazy-init stores)
├── scripts/
│   └── verify_connection.py     # Gemini connectivity check
├── tests/
│   ├── unit/
│   │   ├── test_api.py          # Merged: API endpoint tests
│   │   ├── test_pipeline.py     # NEW: hybrid_memory_search tests (replaces test_vector_tool + test_graph_tool)
│   │   ├── test_retrieval_pipeline.py  # Updated imports
│   │   ├── test_query_router.py
│   │   ├── test_query_rewriter.py
│   │   ├── test_multi_hop.py
│   │   ├── test_reranker.py
│   │   ├── test_extractor_agent.py
│   │   ├── test_chunker.py      # Updated imports
│   │   ├── test_embedder.py
│   │   ├── test_graph_store.py
│   │   ├── test_vector_store.py
│   │   ├── test_session_store.py
│   │   ├── test_auth_store.py
│   │   ├── test_auth_routes.py
│   │   ├── test_auth_middleware.py
│   │   ├── test_jwt.py
│   │   ├── test_citation.py
│   │   ├── test_observability.py
│   │   ├── test_input_validator.py
│   │   ├── test_memory_manager.py  # Updated for injected extractor
│   │   ├── test_workers.py         # Updated for lazy-init
│   │   ├── test_ingestion_task.py  # Updated for lazy-init + new imports
│   │   └── test_verify_connection.py
│   └── e2e/
│       ├── conftest.py
│       ├── test_health.py
│       ├── test_chat_flow.py
│       ├── test_memory_panels.py
│       └── test_session.py
├── agentos.py                   # Slim: app assembly + lifespan + router includes
├── tools/                       # DELETED entirely
├── data/
├── frontend/
├── docs/
│   └── superpowers/
│       └── specs/
│           └── 2026-05-17-pipeline-refactoring-design.md
├── pyproject.toml
├── Makefile
├── docker-compose.yml
└── .env
```
