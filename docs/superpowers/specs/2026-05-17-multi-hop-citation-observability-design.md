# Design: Multi-Hop Reasoning, Citation/Attribution, Observability

**Date:** 2026-05-17
**Status:** Draft

---

## Feature 1: Multi-Hop Reasoning

### Problem

The current graph search is limited to depth-2 via `fetch_subgraph(entity, depth=2)`. Complex queries that require traversing multiple relationship chains cannot be answered with a single shallow fetch.

### Architecture

```
POST /query
  ↓
build_rag_team_with_stores()
  ↓
multi_hop_retriever.run(query)  ← NEW: runs BEFORE agent
  ↓
  Loop (max 5 hops):
    1. LLM selects promising entities from current results
    2. Batch fetch subgraphs for selected entities (depth=1 per hop)
    3. Accumulate results, deduplicate
    4. LLM evaluates: "Is this enough to answer the query?" → stop if yes
  ↓
  Returns: { "results": [...], "hops_taken": int, "entities_expanded": [...] }
  ↓
Combined with vector search results → RAG Agent → Answer
```

### Components

**`MultiHopRetriever` (`agents/retrieval/multi_hop.py`)**

- Constructor: `MultiHopRetriever(graph_store: GraphStore, model: Gemini, max_hops: int = 5)`
- `run(query: str) -> MultiHopResult`
- Hop 0: Extract entities from query using LLM with structured output (`EntityExtractionResult: List[str]`), fetch their depth-1 subgraphs
- Hop N (1..max_hops-1):
  1. LLM reviews accumulated context, selects which entities to expand next via structured output (`EntitySelectionResult: List[str]`)
  2. Batch `fetch_subgraph(entity, depth=1)` for each selected entity
  3. Deduplicate results by (entity_name, relationship, target)
  4. LLM termination check via structured output (`TerminationResult: bool`) — "Given the query and current context, is more graph traversal needed?"
- Returns `MultiHopResult`: `results: List[CitationResult]`, `hops_taken: int`, `entities_expanded: List[str]`
- Fallback: if LLM fails at any step, returns whatever was accumulated so far (graceful degradation)

**Integration (`db/dependencies.py`)**

- `build_rag_team_with_stores` creates a `MultiHopRetriever` instance
- Calls `multi_hop_retriever.run(query)` before creating the RAG agent
- Multi-hop results are formatted and injected into the agent's system prompt as pre-retrieved context
- The agent also receives a `lookup_entity(entity)` tool for targeted single-entity lookups (replaces the old `graph_search_tool`)

**`lookup_entity` tool**

- Replaces `graph_search_tool(entity, depth=2)`
- Calls `graph_store.fetch_subgraph(entity, depth=1)` — single-depth fetch only
- Wraps results into `List[CitationResult]`, which is then formatted into a context string for the agent
- Agent uses it for precise lookups of specific entities not covered by multi-hop

### Error Handling

- LLM entity selection fails → expand all entities from previous hop (degrade to programmatic expansion)
- LLM termination check fails → continue to max hops
- Graph store unavailable → return empty results, agent proceeds with vector search only
- Any hop failure → return accumulated results so far, do not retry

---

## Feature 2: Citation & Attribution

### Problem

The current system returns answers without source references. Users cannot verify which chunks or graph nodes informed the answer.

### Architecture

```
vector_search_tool(query) → returns List[CitationResult]
multi_hop_retriever.run(query) → returns List[CitationResult]
  ↓
Both tools return structured results with citation metadata:
  CitationResult {
    id: str,                    # chunk UUID or graph node ID
    type: "vector" | "graph",   # source type
    content: str,               # text snippet or relationship string
    source: str,                # filename (vector) or "knowledge_graph" (graph)
    chunk_index: int | None,    # chunk position in source (vector only)
    entity_name: str | None,    # entity name (graph only)
    relationship: str | None,   # relationship path (graph only)
    connected_entities: List,   # related entities (graph only)
    relevance_score: float,     # LanceDB distance (vector) or 1/(hop+1) (graph, hop 0 = 1.0, hop 1 = 0.5, etc.)
  }
  ↓
Formatted context string → injected into agent prompt
Raw CitationResult list → stored in request context
  ↓
Agent generates answer → NDJSON stream includes:
  { "event": "answer", "content": "...", "citations": [CitationResult, ...] }
```

### Components

**`CitationResult` dataclass (`db/citation.py`)**

- Unified dataclass for both vector and graph results
- All fields optional except `id`, `type`, `content`
- `to_dict()` method for JSON serialization in NDJSON
- `from_vector_result(dict) -> CitationResult` class method
- `from_graph_result(dict, hop: int) -> CitationResult` class method

**Tool modifications (`db/dependencies.py`)**

- `vector_search_tool` wraps raw LanceDB results into `List[CitationResult]`
- `lookup_entity` wraps graph results into `List[CitationResult]`
- Both tools attach citation metadata to every result before returning
- Multi-hop retriever also returns `List[CitationResult]` with `relevance_score = 1 / (hop_number + 1)` (hop 0 = 1.0, hop 1 = 0.5, etc.)

**NDJSON stream enhancement (`agentos.py`)**

- Final answer event includes `citations` field with the full deduplicated list
- Citations are deduplicated by `id` before emission
- Existing `citations` field in Agno stream events is populated from the request context

### Error Handling

- Missing citation fields → filled with `None`, result still included
- Duplicate citations → deduplicated by `id` before emission
- Agent produces answer without using any citations → empty `citations` array (valid)

---

## Feature 3: Observability

### Problem

No structured logging exists. Logs are plain f-strings with no correlation IDs, timing, or retrieval stats. Debugging query performance is impossible.

### Architecture

```
Request arrives → generate request_id
  ↓
Request-level log: {"event": "request_start", "request_id": "...", "method": "POST", "path": "/query"}
  ↓
Step logs (each stage):
  {"event": "step_start", "step": "query_rewriting", "request_id": "..."}
  {"event": "step_end", "step": "query_rewriting", "request_id": "...", "duration_ms": 342, "result_count": 3}
  {"event": "step_start", "step": "vector_search", "request_id": "..."}
  {"event": "step_end", "step": "vector_search", "request_id": "...", "duration_ms": 120, "result_count": 8}
  {"event": "step_start", "step": "multi_hop", "request_id": "..."}
  {"event": "step_end", "step": "multi_hop", "request_id": "...", "duration_ms": 890, "hops_taken": 3, "entities_expanded": 12}
  {"event": "step_start", "step": "agent_synthesis", "request_id": "..."}
  {"event": "step_end", "step": "agent_synthesis", "request_id": "...", "duration_ms": 2100, "tokens_used": 450}
  ↓
Request-level log: {"event": "request_end", "request_id": "...", "total_duration_ms": 3452, "status": "ok", "citation_count": 5}
```

### Components

**`utils/observability.py`**

- `RequestContext` dataclass: `request_id: str`, `start_time: float`, `steps: List[StepRecord]`
- `StepRecord` dataclass: `name: str`, `start_time: float`, `end_time: float | None`, `metrics: dict`
- `start_request(method: str, path: str) -> RequestContext` — creates context, emits `request_start` log
- `log_step(ctx: RequestContext, name: str, **metrics)` — context manager that emits `step_start`/`step_end` with timing
- `end_request(ctx: RequestContext, status: str, **metrics)` — emits `request_end` log with summary
- Thread-safe via `contextvars` so request context flows through async code

**JSON logging configuration (`agentos.py` lifespan)**

- Custom `JSONFormatter` — outputs structured JSON with consistent fields
- Fields: `timestamp`, `level`, `event`, `request_id`, `duration_ms`, plus any step-specific metrics
- Configured at app startup via `logging.basicConfig()`, applies to all loggers
- Log level: INFO for step/request events, DEBUG for internal details, WARNING for errors

**Integration points**

- `/query` endpoint: `start_request` → wrap each stage in `log_step` → `end_request`
- Multi-hop retriever: logs each hop as a sub-step
- Vector search: logs embedding + search latency
- `/ingest` endpoint: `start_request` → `log_step("file_validation")` → `log_step("celery_queue")` → `end_request`

### Error Handling

- Logging failure never crashes the request — all logging wrapped in `try/except` with silent fallback
- Missing request context → logs still emitted but without `request_id`
- Malformed metrics → logged as-is, no validation

---

## Dependencies

- No new external dependencies
- Uses existing: Google Gemini API (for multi-hop LLM decisions), Python `logging` module, `contextvars`
- Redis/Neo4j/LanceDB unchanged

## Testing Strategy

**Multi-Hop:**
- Unit: test `MultiHopRetriever.run()` with mocked LLM and graph store
- Unit: test termination logic (LLM says stop, max hops reached, no new entities)
- Unit: test fallback behavior when LLM fails mid-hop
- Integration: test full pipeline with real graph store and mocked LLM

**Citation:**
- Unit: test `CitationResult` dataclass serialization/deserialization
- Unit: test deduplication logic
- Unit: test tool wrappers produce correct citation metadata
- Integration: test NDJSON stream includes citations in final answer event

**Observability:**
- Unit: test `JSONFormatter` output structure
- Unit: test `RequestContext` lifecycle (start → steps → end)
- Unit: test contextvar propagation in async code
- Integration: test `/query` endpoint produces structured logs with request ID
