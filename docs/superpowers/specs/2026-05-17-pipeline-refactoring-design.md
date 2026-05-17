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

### 1. `hybrid_memory_search` tool (in `db/dependencies.py`)

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

| File | Action |
|------|--------|
| `agents/rag_team.py` | DELETE |
| `tools/vector_tool.py` | DELETE |
| `tools/graph_tool.py` | DELETE |
| `tools/` directory | DELETE (empty after above) |
| `db/dependencies.py` | REWRITE: remove `get_embedder()`, replace 2 tools with `hybrid_memory_search` |
| `auth/middleware.py` | EDIT: remove `require_admin()`, keep `get_auth_store()` as single source |
| `auth/routes.py` | EDIT: inline admin auth, import `get_auth_store` from middleware |
| `auth/models.py` | EDIT: remove `TokenRequest`, `RevokeApiKeyRequest` |
| `agentos.py` | EDIT: remove `tools/` imports, add `/ingest/url` endpoint |
| `utils/chunker.py` | NO CHANGE (keep functions, they're used by new endpoint) |
| `agents/retrieval/multi_hop.py` | NO CHANGE (now actively used) |
| `agents/router/query_router.py` | NO CHANGE (now actively used) |
| `agents/router/query_rewriter.py` | NO CHANGE (now used for both paths) |
| `utils/fusion/reranker.py` | NO CHANGE (now actively used) |
| `tests/unit/test_api.py` | EDIT: merge with test_query_api.py, update for new tool |
| `tests/unit/test_query_api.py` | DELETE (merged into test_api.py) |
| `tests/unit/test_vector_tool.py` | DELETE (tools/ deleted, tool now in dependencies) |
| `tests/unit/test_graph_tool.py` | DELETE (tools/ deleted, tool now in dependencies) |
| `tests/unit/test_retrieval_pipeline.py` | EDIT: update for `hybrid_memory_search` |
| `tests/unit/test_reranker.py` | NO CHANGE |
| `tests/unit/test_query_router.py` | NO CHANGE |
| `tests/unit/test_query_rewriter.py` | NO CHANGE |
| `tests/unit/test_multi_hop.py` | NO CHANGE |

## Risk Mitigation

- All existing tests for individual components (QueryRouter, QueryRewriter, MultiHopRetriever, HybridRetriever) remain unchanged and passing
- The `build_rag_team_with_stores()` function signature stays the same (accepts graph_store, vector_store)
- `/query`, `/memory/search`, `/memory/graph`, `/ingest`, `/ingest/{task_id}` endpoints keep same signatures
- Only internal tool implementation changes, not the API contract
