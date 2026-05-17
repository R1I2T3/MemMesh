# Pipeline Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete unused code, relocate misplaced functions, integrate QueryRouter/MultiHopRetriever/HybridRetriever into a unified retrieval pipeline, and split god files into focused modules.

**Architecture:** Extract `db/dependencies.py` into `db/context.py` + `api/dependencies.py` + `agents/retrieval/pipeline.py`. Move file extraction from `utils/chunker.py` to `ingestion/extractors.py`. Replace two agent tools with one `hybrid_memory_search` that routes, rewrites, retrieves (vector + multi-hop graph), and reranks. Split `agentos.py` into `api/routes/` routers.

**Tech Stack:** Python 3.14, FastAPI, Agno, Neo4j, LanceDB, Celery, Google GenAI, sentence-transformers, pytest

---

## Phase 1: Create new files (backward compatible — old imports still work)

### Task 1: Create `db/context.py`

**Files:**
- Create: `db/context.py`
- Create: `db/__init__.py` (if not exists)

- [ ] **Step 1: Create `db/context.py` with context variable management**

Extract the context variable code from `db/dependencies.py` lines 1-41.

```python
# db/context.py
"""Context variable management for per-request store and citation access."""
from contextvars import ContextVar

from db.graph_store import GraphStore
from db.vector_store import VectorStore

_graph_store_ctx: ContextVar[GraphStore | None] = ContextVar("graph_store", default=None)
_vector_store_ctx: ContextVar[VectorStore | None] = ContextVar("vector_store", default=None)
_citations_ctx: ContextVar[list] = ContextVar("citations", default=[])


def get_graph_store_ctx() -> GraphStore | None:
    return _graph_store_ctx.get()


def get_vector_store_ctx() -> VectorStore | None:
    return _vector_store_ctx.get()


def set_graph_store_ctx(store: GraphStore):
    _graph_store_ctx.set(store)


def set_vector_store_ctx(store: VectorStore):
    _vector_store_ctx.set(store)


def set_citations_ctx(citations: list):
    _citations_ctx.set(citations)


def get_citations_ctx() -> list:
    return _citations_ctx.get()
```

- [ ] **Step 2: Create `db/__init__.py` if it doesn't exist**

```python
# db/__init__.py
```

- [ ] **Step 3: Verify existing imports still work**

Run: `python -c "from db.context import get_graph_store_ctx, set_citations_ctx; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add db/context.py db/__init__.py
git commit -m "refactor: extract context variables from db/dependencies into db/context.py"
```

---

### Task 2: Create `api/dependencies.py`

**Files:**
- Create: `api/__init__.py`
- Create: `api/dependencies.py`
- Create: `api/routes/__init__.py`

- [ ] **Step 1: Create `api/__init__.py`**

```python
# api/__init__.py
```

- [ ] **Step 2: Create `api/dependencies.py` with FastAPI DI functions**

Extract `get_graph_store` and `get_vector_store` from `db/dependencies.py`.

```python
# api/dependencies.py
"""FastAPI dependency injection for shared store instances."""
from fastapi import Request

from db.graph_store import GraphStore
from db.vector_store import VectorStore


async def get_graph_store(request: Request) -> GraphStore:
    """FastAPI dependency that yields the shared GraphStore from app state."""
    return request.app.state.graph_store


async def get_vector_store(request: Request) -> VectorStore:
    """FastAPI dependency that yields the shared VectorStore from app state."""
    return request.app.state.vector_store
```

- [ ] **Step 3: Create `api/routes/__init__.py`**

```python
# api/routes/__init__.py
"""API router assembly."""
from fastapi import APIRouter

from api.routes.health import router as health_router
from api.routes.query import router as query_router
from api.routes.memory import router as memory_router
from api.routes.ingest import router as ingest_router
from api.routes.session import router as session_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(query_router)
api_router.include_router(memory_router)
api_router.include_router(ingest_router)
api_router.include_router(session_router)
```

- [ ] **Step 4: Commit**

```bash
git add api/__init__.py api/dependencies.py api/routes/__init__.py
git commit -m "refactor: create api/ layer with FastAPI DI and route assembly"
```

---

### Task 3: Create `ingestion/extractors.py`

**Files:**
- Create: `ingestion/__init__.py`
- Create: `ingestion/extractors.py`

- [ ] **Step 1: Create `ingestion/__init__.py`**

```python
# ingestion/__init__.py
```

- [ ] **Step 2: Create `ingestion/extractors.py` with file extraction logic**

Move `extract_text_from_file`, `extract_text_from_url`, `chunk_document`, `chunk_webpage` from `utils/chunker.py`. Keep imports for `chunk_text` from `utils.chunker`.

```python
# ingestion/extractors.py
"""File format extraction and document chunking for the ingestion pipeline."""
import os
import json
import email
from email import policy
import time
import requests
from typing import List, Dict, Any

from bs4 import BeautifulSoup

from utils.chunker import chunk_text


def extract_text_from_file(file_path: str) -> str:
    """Extracts raw text from various enterprise file formats."""
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        import pypdf
        text = ""
        with open(file_path, "rb") as f:
            reader = pypdf.PdfReader(f)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
        return text

    elif ext == ".docx":
        import docx
        doc = docx.Document(file_path)
        return "\n".join([para.text for para in doc.paragraphs])

    elif ext == ".pptx":
        import pptx
        prs = pptx.Presentation(file_path)
        text_runs = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text:
                    text_runs.append(shape.text)
        return "\n\n".join(text_runs)

    elif ext == ".ppt":
        raise ValueError("Legacy .ppt binary files are not natively supported. Please convert to .pptx format.")

    elif ext == ".xml":
        with open(file_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "xml")
            return soup.get_text(separator=" ")

    elif ext == ".eml":
        with open(file_path, "rb") as f:
            msg = email.message_from_binary_file(f, policy=policy.default)
        content = f"Subject: {msg.get('subject', '')}\nFrom: {msg.get('from', '')}\nTo: {msg.get('to', '')}\n\n"
        body = msg.get_body(preferencelist=('plain',))
        if body:
            content += body.get_content()
        return content

    elif ext in [".txt", ".md"]:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    else:
        raise ValueError(f"Unsupported file extension for plain text extraction: {ext}")


def extract_text_from_url(url: str, max_retries: int = 3, backoff_factor: float = 1.0) -> str:
    """Extracts clean text from a web page with retry logic for transient failures."""
    last_exception = None

    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            for script in soup(["script", "style"]):
                script.extract()

            text = soup.get_text(separator=" ")
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            return '\n'.join(chunk for chunk in chunks if chunk)

        except (requests.ConnectionError, requests.Timeout) as e:
            last_exception = e
            if attempt < max_retries - 1:
                wait_time = backoff_factor * (2 ** attempt)
                time.sleep(wait_time)

    raise RuntimeError(
        f"Failed to extract text from {url} after {max_retries} attempts: {last_exception}"
    )


def chunk_document(file_path: str, chunk_size: int = 1000, overlap: int = 200) -> List[Dict[str, Any]]:
    """Extracts text from a file and chunks it. Handles tabular and JSON formats specially."""
    ext = os.path.splitext(file_path)[1].lower()
    source_metadata = os.path.basename(file_path)

    # Context-aware tabular chunking for spreadsheets / CSVs
    if ext in [".xlsx", ".xls", ".csv"]:
        import pandas as pd
        if ext == ".csv":
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)

        chunks = []
        header = df.columns.tolist()
        current_chunk_text = ""

        for _, row in df.iterrows():
            row_str = " | ".join(f"{h}: {row[h]}" for h in header if pd.notna(row[h])) + "\n"
            if len(current_chunk_text) + len(row_str) > chunk_size and current_chunk_text:
                chunks.append({
                    "chunk_index": len(chunks),
                    "text": current_chunk_text.strip(),
                    "source": source_metadata,
                })
                current_chunk_text = row_str
            else:
                current_chunk_text += row_str

        if current_chunk_text:
            chunks.append({
                "chunk_index": len(chunks),
                "text": current_chunk_text.strip(),
                "source": source_metadata,
            })
        return chunks

    # Context-aware chunking for JSON APIs / configurations
    elif ext == ".json":
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list) and all(isinstance(item, dict) for item in data):
            chunks = []
            current_chunk_text = ""
            for item in data:
                item_str = json.dumps(item) + "\n"
                if len(current_chunk_text) + len(item_str) > chunk_size and current_chunk_text:
                    chunks.append({
                        "chunk_index": len(chunks),
                        "text": current_chunk_text.strip(),
                        "source": source_metadata,
                    })
                    current_chunk_text = item_str
                else:
                    current_chunk_text += item_str

            if current_chunk_text:
                chunks.append({
                    "chunk_index": len(chunks),
                    "text": current_chunk_text.strip(),
                    "source": source_metadata,
                })
            return chunks
        else:
            text = json.dumps(data, indent=2)
            return chunk_text(text, chunk_size, overlap, source_metadata=source_metadata)

    # Standard recursive chunking for regular documents
    text = extract_text_from_file(file_path)
    return chunk_text(text, chunk_size, overlap, source_metadata=source_metadata)


def chunk_webpage(url: str, chunk_size: int = 1000, overlap: int = 200) -> List[Dict[str, Any]]:
    """Extracts text from a URL and chunks it."""
    text = extract_text_from_url(url)
    return chunk_text(text, chunk_size, overlap, source_metadata=url)
```

- [ ] **Step 3: Verify imports work**

Run: `python -c "from ingestion.extractors import extract_text_from_file, chunk_document; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add ingestion/__init__.py ingestion/extractors.py
git commit -m "refactor: move file extraction from utils/chunker.py to ingestion/extractors.py"
```

---

### Task 4: Create `agents/retrieval/pipeline.py`

**Files:**
- Create: `agents/retrieval/pipeline.py`

- [ ] **Step 1: Create `agents/retrieval/pipeline.py` with retrieval pipeline logic**

This is the core new file. It contains `vector_search_with_rewriting` (moved from `db/dependencies.py`) and the new `hybrid_memory_search` that integrates QueryRouter, QueryRewriter, MultiHopRetriever, and HybridRetriever.

```python
# agents/retrieval/pipeline.py
"""Unified retrieval pipeline: route, rewrite, retrieve, rerank."""
import logging
from typing import List

from db.citation import CitationResult
from db.context import get_citations_ctx
from db.graph_store import GraphStore
from db.vector_store import VectorStore
from utils.embedder import embed_chunks
from utils.fusion.reranker import HybridRetriever
from agents.router.query_rewriter import QueryRewriter
from agents.router.query_router import QueryRouter
from agents.retrieval.multi_hop import MultiHopRetriever

logger = logging.getLogger(__name__)


def vector_search_with_rewriting(query: str, vector_store: VectorStore, top_k: int = 5) -> List[CitationResult]:
    """Enhanced vector search with query rewriting for improved recall."""
    try:
        rewriter = QueryRewriter()
        rewrite_result = rewriter.rewrite(query)

        all_queries = [query, rewrite_result.step_back_query] + rewrite_result.alternative_queries

        seen_ids = set()
        combined_results: List[CitationResult] = []
        any_embedded = False

        for q in all_queries:
            embedded = embed_chunks([{"text": q}])
            if not embedded or "embedding" not in embedded[0]:
                continue

            any_embedded = True
            results = vector_store.search(query_vector=embedded[0]["embedding"], top_k=top_k)
            for r in results:
                rid = r.get("id")
                if rid and rid not in seen_ids:
                    seen_ids.add(rid)
                    citation = CitationResult.from_vector_result(r)
                    combined_results.append(citation)

        if not any_embedded:
            return []

        return combined_results
    except Exception as e:
        logger.error(f"Vector search with rewriting failed: {e}")
        return []


def hybrid_memory_search(query: str, graph_store: GraphStore, vector_store: VectorStore, top_k: int = 5) -> str:
    """
    Unified retrieval tool that runs the full pipeline:
    1. Route query (vector/graph/hybrid)
    2. Rewrite query for recall
    3. Retrieve from vector and/or graph
    4. Rerank fused results
    5. Return unified context string with citation tracking
    """
    try:
        # Step 1: Route the query
        router = QueryRouter()
        route = router.classify_query(query)

        # Step 2: Rewrite the query for improved recall
        rewriter = QueryRewriter()
        rewrite_result = rewriter.rewrite(query)
        all_queries = [query, rewrite_result.step_back_query] + rewrite_result.alternative_queries

        vector_results: List[CitationResult] = []
        graph_results: List[CitationResult] = []

        # Step 3a: Vector retrieval (for 'vector' or 'hybrid' routes)
        if route in ("vector", "hybrid"):
            vector_results = vector_search_with_rewriting(query, vector_store, top_k=top_k)

        # Step 3b: Graph retrieval with multi-hop (for 'graph' or 'hybrid' routes)
        if route in ("graph", "hybrid"):
            from agno.models.google import Gemini
            multi_hop = MultiHopRetriever(
                graph_store=graph_store,
                model=Gemini(id="gemini-3.0-flash"),
                max_hops=3,
            )
            # Run multi-hop on the original query and the step-back query for broader coverage
            hop_result = multi_hop.run(query)
            graph_results = hop_result.results

            if rewrite_result.step_back_query and rewrite_result.step_back_query != query:
                step_back_result = multi_hop.run(rewrite_result.step_back_query)
                for r in step_back_result.results:
                    if r not in graph_results:
                        graph_results.append(r)

        # Step 4: Track citations
        existing_citations = get_citations_ctx()
        all_results = vector_results + graph_results
        existing_citations.extend(all_results)

        if not all_results:
            return "Memory search: no results found."

        # Step 5: Rerank if we have both vector and graph results (hybrid route)
        if route == "hybrid" and vector_results and graph_results:
            reranker = HybridRetriever()
            vector_texts = [r.content for r in vector_results]
            graph_texts = [r.content for r in graph_results]
            reranked_texts = reranker.rerank_results(query, graph_texts, vector_texts, top_k=top_k * 2)

            # Map reranked texts back to CitationResults
            content_to_result = {}
            for r in all_results:
                content_to_result[r.content] = r

            reranked_results = []
            for text in reranked_texts:
                if text in content_to_result:
                    reranked_results.append(content_to_result[text])
            all_results = reranked_results

        # Step 6: Format as context string
        lines = []
        for r in all_results[:top_k * 2]:
            lines.append(f"[{r.id}] {r.content}")

        return "Retrieved context:\n" + "\n".join(lines)

    except Exception as e:
        logger.error(f"Hybrid memory search failed: {e}")
        return f"Memory search error: {str(e)}"
```

- [ ] **Step 2: Update `agents/retrieval/__init__.py` to also export pipeline functions**

Current content:
```python
from agents.retrieval.multi_hop import MultiHopRetriever, MultiHopResult

__all__ = ["MultiHopRetriever", "MultiHopResult"]
```

New content:
```python
from agents.retrieval.multi_hop import MultiHopRetriever, MultiHopResult
from agents.retrieval.pipeline import vector_search_with_rewriting, hybrid_memory_search

__all__ = ["MultiHopRetriever", "MultiHopResult", "vector_search_with_rewriting", "hybrid_memory_search"]
```

- [ ] **Step 3: Verify imports work**

Run: `python -c "from agents.retrieval.pipeline import hybrid_memory_search, vector_search_with_rewriting; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add agents/retrieval/pipeline.py agents/retrieval/__init__.py
git commit -m "feat: create unified retrieval pipeline with routing, rewriting, multi-hop, and reranking"
```

---

## Phase 2: Delete old files, update imports

### Task 5: Delete `db/dependencies.py` and update all imports

**Files:**
- Delete: `db/dependencies.py`
- Modify: `agentos.py`
- Modify: `tools/vector_tool.py` (will be deleted in next task, but update import first)
- Modify: `tools/graph_tool.py` (will be deleted in next task, but update import first)
- Modify: `tests/unit/test_retrieval_pipeline.py`

- [ ] **Step 1: Update `agentos.py` imports**

Replace:
```python
from db.dependencies import (
    get_graph_store,
    get_vector_store,
    build_rag_team_with_stores,
    set_graph_store_ctx,
    set_vector_store_ctx,
    set_citations_ctx,
    get_citations_ctx,
)
```

With:
```python
from api.dependencies import get_graph_store, get_vector_store
from db.context import set_graph_store_ctx, set_vector_store_ctx, set_citations_ctx, get_citations_ctx
from agents.rag_team import build_rag_team_with_stores
```

- [ ] **Step 2: Update `tools/vector_tool.py` import**

Replace:
```python
from db.dependencies import get_vector_store_ctx
```

With:
```python
from db.context import get_vector_store_ctx
```

- [ ] **Step 3: Update `tools/graph_tool.py` import**

Replace:
```python
from db.dependencies import get_graph_store_ctx
```

With:
```python
from db.context import get_graph_store_ctx
```

- [ ] **Step 4: Update `tests/unit/test_retrieval_pipeline.py` imports**

Replace:
```python
from db.dependencies import vector_search_with_rewriting
```

With:
```python
from agents.retrieval.pipeline import vector_search_with_rewriting
```

And replace all `patch("db.dependencies.QueryRewriter"` with `patch("agents.retrieval.pipeline.QueryRewriter"` and `patch("db.dependencies.embed_chunks"` with `patch("agents.retrieval.pipeline.embed_chunks"`.

Also update the `build_rag_team_with_stores` import:
Replace:
```python
from db.dependencies import build_rag_team_with_stores
```

With:
```python
from agents.rag_team import build_rag_team_with_stores
```

- [ ] **Step 5: Delete `db/dependencies.py`**

```bash
rm db/dependencies.py
```

- [ ] **Step 6: Verify imports still work**

Run: `python -c "from agentos import app; print('OK')"`
Expected: `OK` (may fail if tools/ still references old paths — that's handled in next task)

- [ ] **Step 7: Commit**

```bash
git add -u db/dependencies.py agentos.py tools/ tests/unit/test_retrieval_pipeline.py
git commit -m "refactor: delete db/dependencies.py, update imports across codebase"
```

---

### Task 6: Delete `tools/` directory

**Files:**
- Delete: `tools/vector_tool.py`
- Delete: `tools/graph_tool.py`
- Delete: `tools/` directory
- Modify: `agents/rag_team.py`
- Delete: `tests/unit/test_vector_tool.py`
- Delete: `tests/unit/test_graph_tool.py`

- [ ] **Step 1: Delete `tools/` directory**

```bash
rm -rf tools/
```

- [ ] **Step 2: Delete tool tests**

```bash
rm tests/unit/test_vector_tool.py tests/unit/test_graph_tool.py
```

- [ ] **Step 3: Commit**

```bash
git add -u tools/ tests/unit/test_vector_tool.py tests/unit/test_graph_tool.py
git commit -m "refactor: delete legacy tools/ directory and associated tests"
```

---

### Task 7: Rewrite `agents/rag_team.py` with `build_rag_team_with_stores`

**Files:**
- Modify: `agents/rag_team.py`

- [ ] **Step 1: Rewrite `agents/rag_team.py`**

Replace entire file with:

```python
# agents/rag_team.py
"""RAG team agent construction with unified hybrid memory search tool."""
import logging
from agno.agent import Agent
from agno.models.google import Gemini

from db.graph_store import GraphStore
from db.vector_store import VectorStore
from db.context import get_citations_ctx
from agents.retrieval.pipeline import hybrid_memory_search

logger = logging.getLogger(__name__)


def build_rag_team_with_stores(graph_store: GraphStore, vector_store: VectorStore) -> Agent:
    """
    Builds a RAG team agent with a single hybrid_memory_search tool.
    The tool internally routes, rewrites, retrieves (vector + multi-hop graph), and reranks.
    """

    def memory_search(query: str, top_k: int = 5) -> str:
        """Searches the hybrid memory engine (vector + graph) for relevant context."""
        return hybrid_memory_search(query, graph_store, vector_store, top_k=top_k)

    agent = Agent(
        name="Graph-RAG Master",
        model=Gemini(id="gemini-3.0-flash"),
        description="""You are a senior intelligent backend researcher.
        You have access to a Hybrid Memory Engine composed of a Vector Database and a Graph Database.
        When asked a question:
        1. Use memory_search to find relevant context from both vector and graph stores.
        2. Synthesize a pristine, grounded answer strictly based on the extracted memory.""",
        tools=[memory_search],
    )
    return agent
```

- [ ] **Step 2: Verify import works**

Run: `python -c "from agents.rag_team import build_rag_team_with_stores; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add agents/rag_team.py
git commit -m "refactor: rewrite agents/rag_team.py with single hybrid_memory_search tool"
```

---

## Phase 3: Split agentos.py into api/routes/

### Task 8: Create `api/routes/health.py`

**Files:**
- Create: `api/routes/health.py`

- [ ] **Step 1: Create `api/routes/health.py`**

```python
# api/routes/health.py
"""Health check endpoint."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok", "service": "Graph-RAG AgentOS"}
```

- [ ] **Step 2: Commit**

```bash
git add api/routes/health.py
git commit -m "refactor: extract /health endpoint to api/routes/health.py"
```

---

### Task 9: Create `api/routes/query.py`

**Files:**
- Create: `api/routes/query.py`

- [ ] **Step 1: Create `api/routes/query.py`**

Extract the `/query` endpoint from `agentos.py`.

```python
# api/routes/query.py
"""Streaming query endpoint."""
import json
import os
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from db.graph_store import GraphStore
from db.vector_store import VectorStore
from db.session_store import SessionStore
from db.context import set_citations_ctx, get_citations_ctx
from api.dependencies import get_graph_store, get_vector_store
from utils.observability import start_request, log_step, end_request
from utils.input_validator import validate_query
from auth.middleware import require_auth
from agents.rag_team import build_rag_team_with_stores

router = APIRouter()


class QueryRequest(BaseModel):
    message: str
    session_id: str | None = None


def get_session_store(request: Request) -> SessionStore:
    return request.app.state.session_store


@router.post("/query")
async def query(
    req: QueryRequest,
    user: dict = Depends(require_auth),
    graph_store: GraphStore = Depends(get_graph_store),
    vector_store: VectorStore = Depends(get_vector_store),
    session_store: SessionStore = Depends(get_session_store),
):
    """
    Streaming endpoint to interact with the Graph-RAG Agent.
    Emits NDJSON events as the agent processes the request.
    """
    req.message = validate_query(req.message)
    ctx = start_request("POST", "/query")
    set_citations_ctx([])

    try:
        with log_step(ctx, "multi_hop_pre_retrieval"):
            rag_team = build_rag_team_with_stores(graph_store, vector_store)

        history = []
        if req.session_id and user.get("team_id"):
            limit = int(os.getenv("SESSION_HISTORY_LIMIT", "10"))
            messages = session_store.get_session_history(req.session_id, user["team_id"], limit=limit)
            history = [{"role": m["role"], "content": m["content"]} for m in messages]

        async def stream():
            with log_step(ctx, "agent_synthesis"):
                full_response = []
                async for event in rag_team.arun(
                    req.message,
                    stream=True,
                    session_id=req.session_id,
                    history=history if history else None,
                ):
                    full_response.append(event)
                    yield json.dumps(asdict(event)) + "\n"

                if req.session_id and user.get("team_id"):
                    session_store.save_message(req.session_id, user["id"], user.get("team_id"), "user", req.message)
                    response_text = "".join(
                        [e.content for e in full_response if hasattr(e, "content") and e.content]
                    )
                    if response_text:
                        session_store.save_message(
                            req.session_id, user["id"], user.get("team_id"), "assistant", response_text
                        )

            citations = get_citations_ctx()
            seen_ids = set()
            deduped = []
            for c in citations:
                if c.id not in seen_ids:
                    seen_ids.add(c.id)
                    deduped.append(c)

            if deduped:
                citation_event = {
                    "event": "citations",
                    "content": [c.to_dict() for c in deduped],
                }
                yield json.dumps(citation_event) + "\n"

            end_request(ctx, "ok", citation_count=len(deduped))

        return StreamingResponse(stream(), media_type="application/x-ndjson")
    except Exception as e:
        end_request(ctx, "error", error=str(e))
        raise
```

- [ ] **Step 2: Commit**

```bash
git add api/routes/query.py
git commit -m "refactor: extract /query endpoint to api/routes/query.py"
```

---

### Task 10: Create `api/routes/memory.py`

**Files:**
- Create: `api/routes/memory.py`

- [ ] **Step 1: Create `api/routes/memory.py`**

```python
# api/routes/memory.py
"""Memory search endpoints: vector and graph."""
from fastapi import APIRouter, Depends

from db.graph_store import GraphStore
from db.vector_store import VectorStore
from api.dependencies import get_graph_store, get_vector_store
from utils.input_validator import validate_query
from utils.embedder import embed_chunks
from auth.middleware import require_auth

router = APIRouter()


@router.get("/memory/search")
def memory_search(
    query: str,
    user: dict = Depends(require_auth),
    vector_store: VectorStore = Depends(get_vector_store),
):
    """Direct HTTP bridge to the Vector Engine using DI."""
    query = validate_query(query)
    embedded = embed_chunks([{"text": query}])
    if not embedded or "embedding" not in embedded[0]:
        return {"results": "Vector search failed: Could not generate embedding."}

    results = vector_store.search(query_vector=embedded[0]["embedding"])
    return {"results": results}


@router.get("/memory/graph")
def memory_graph(
    entity: str,
    user: dict = Depends(require_auth),
    graph_store: GraphStore = Depends(get_graph_store),
):
    """Direct HTTP bridge to the Graph Engine using DI."""
    entity = validate_query(entity)
    results = graph_store.fetch_subgraph(entity)
    return {"results": results}
```

- [ ] **Step 2: Commit**

```bash
git add api/routes/memory.py
git commit -m "refactor: extract /memory/* endpoints to api/routes/memory.py"
```

---

### Task 11: Create `api/routes/ingest.py`

**Files:**
- Create: `api/routes/ingest.py`

- [ ] **Step 1: Create `api/routes/ingest.py`**

```python
# api/routes/ingest.py
"""Document ingestion endpoints: file upload, URL ingestion, and status polling."""
import tempfile
from pathlib import Path

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from workers.celery_app import celery_app
from utils.input_validator import validate_query
from auth.middleware import require_auth
from ingestion.extractors import extract_text_from_url, chunk_text

router = APIRouter()

STAGING_DIR = Path("./data/staging")
STAGING_DIR.mkdir(parents=True, exist_ok=True)

SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".pptx", ".xml", ".eml", ".txt", ".md", ".csv", ".xlsx", ".json",
}


@router.post("/ingest")
async def ingest(
    file: UploadFile = File(...),
    multimodal: bool = Query(False),
    user: dict = Depends(require_auth),
):
    """
    Accepts a document file, stages it, and queues async ingestion via Celery.
    Returns a task_id for status polling.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    try:
        content = await file.read()
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to read file content")

    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    import uuid
    unique_name = f"{uuid.uuid4()}_{file.filename}"
    staging_path = STAGING_DIR / unique_name

    try:
        with open(staging_path, "wb") as f:
            f.write(content)
    except OSError:
        raise HTTPException(status_code=500, detail="Failed to save file to staging")

    try:
        task = celery_app.send_task(
            "workers.tasks.process_document_ingestion",
            args=[str(staging_path), multimodal],
        )
    except Exception:
        staging_path.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail="Celery broker unavailable")

    return {"task_id": task.id, "status": "pending"}


@router.post("/ingest/url")
async def ingest_url(
    url: str,
    user: dict = Depends(require_auth),
):
    """
    Accepts a URL, extracts text, chunks it, stages as a temp file, and queues async ingestion.
    Returns a task_id for status polling.
    """
    url = validate_query(url)

    try:
        text = extract_text_from_url(url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to extract text from URL: {str(e)}")

    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="No text content found at URL")

    chunks = chunk_text(text, source_metadata=url)
    if not chunks:
        raise HTTPException(status_code=400, detail="No chunks produced from URL content")

    # Write chunks to a temp file for the ingestion worker
    import uuid
    import json
    unique_name = f"{uuid.uuid4()}_url_ingest.json"
    staging_path = STAGING_DIR / unique_name

    try:
        with open(staging_path, "w") as f:
            json.dump({"url": url, "chunks": chunks}, f)
    except OSError:
        raise HTTPException(status_code=500, detail="Failed to stage URL content")

    try:
        task = celery_app.send_task(
            "workers.tasks.process_document_ingestion",
            args=[str(staging_path), False],
        )
    except Exception:
        staging_path.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail="Celery broker unavailable")

    return {"task_id": task.id, "status": "pending"}


@router.get("/ingest/{task_id}")
def ingest_status(task_id: str, user: dict = Depends(require_auth)):
    """
    Polls the Celery result backend for the status of an ingestion task.
    """
    result = AsyncResult(task_id, app=celery_app)

    state_map = {
        "PENDING": "pending",
        "RECEIVED": "pending",
        "STARTED": "running",
        "SUCCESS": "completed",
        "FAILURE": "failed",
        "RETRY": "running",
        "REVOKED": "failed",
    }

    status = state_map.get(result.state, "pending")

    response = {"task_id": task_id, "status": status}

    if result.state == "SUCCESS":
        response["result"] = result.result
    elif result.state == "FAILURE":
        response["error"] = str(result.result)

    return response
```

- [ ] **Step 2: Commit**

```bash
git add api/routes/ingest.py
git commit -m "feat: extract /ingest endpoints to api/routes/ingest.py, add /ingest/url endpoint"
```

---

### Task 12: Create `api/routes/session.py`

**Files:**
- Create: `api/routes/session.py`

- [ ] **Step 1: Create `api/routes/session.py`**

```python
# api/routes/session.py
"""Session management endpoint."""
import uuid

from fastapi import APIRouter

router = APIRouter()


@router.post("/session/new")
def new_session():
    """Generates a novel session ID for conversational state routing."""
    return {"session_id": str(uuid.uuid4())}
```

- [ ] **Step 2: Commit**

```bash
git add api/routes/session.py
git commit -m "refactor: extract /session/new endpoint to api/routes/session.py"
```

---

### Task 13: Slim down `agentos.py`

**Files:**
- Modify: `agentos.py`

- [ ] **Step 1: Rewrite `agentos.py`**

Replace entire file with:

```python
# agentos.py
"""Graph-RAG AgentOS — FastAPI application assembly and lifespan management."""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.graph_store import GraphStore
from db.vector_store import VectorStore
from db.session_store import SessionStore
from db.context import set_graph_store_ctx, set_vector_store_ctx
from utils.observability import _configure_json_logging
from auth.routes import router as auth_router
from api.routes import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_json_logging()

    graph_store = GraphStore(
        uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        user=os.getenv("NEO4J_USER", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "password"),
    )
    vector_store = VectorStore(path=os.getenv("LANCEDB_PATH", "./data/lancedb"))
    session_store = SessionStore()

    # Cleanup expired session messages
    ttl_days = int(os.getenv("SESSION_TTL_DAYS", "30"))
    session_store.cleanup_expired(days=ttl_days)

    app.state.graph_store = graph_store
    app.state.vector_store = vector_store
    app.state.session_store = session_store

    set_graph_store_ctx(graph_store)
    set_vector_store_ctx(vector_store)

    yield

    graph_store.close()
    session_store.close()


app = FastAPI(title="Graph-RAG AgentOS", version="1.0.0", lifespan=lifespan)

# Enable CORS for frontend integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(api_router)
```

- [ ] **Step 2: Verify app loads**

Run: `python -c "from agentos import app; print('Routes:', [r.path for r in app.routes]); print('OK')"`
Expected: Lists all routes including `/health`, `/query`, `/memory/search`, `/memory/graph`, `/ingest`, `/ingest/url`, `/ingest/{task_id}`, `/session/new`, `/auth/*`

- [ ] **Step 3: Commit**

```bash
git add agentos.py
git commit -m "refactor: slim agentos.py to app assembly + lifespan, routes in api/routes/"
```

---

## Phase 4: Clean up remaining files

### Task 14: Clean up `auth/` files

**Files:**
- Modify: `auth/middleware.py`
- Modify: `auth/routes.py`
- Modify: `auth/models.py`

- [ ] **Step 1: Update `auth/middleware.py` — remove `require_admin`**

Current content has `require_admin` function. Remove it. New content:

```python
# auth/middleware.py
import os
from fastapi import Header, HTTPException

from auth.jwt import decode_jwt, JWTError
from db.auth_store import AuthStore


def get_auth_store() -> AuthStore:
    db_path = os.getenv("AUTH_DB_PATH", "data/memmesh.db")
    return AuthStore(db_path)


def require_auth(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = authorization.split(" ", 1)[1]
    secret = os.getenv("JWT_SECRET", "")
    if not secret:
        raise HTTPException(status_code=500, detail="JWT_SECRET not configured")

    try:
        payload = decode_jwt(token, secret)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    store = get_auth_store()
    user = store.get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user
```

- [ ] **Step 2: Update `auth/routes.py` — inline admin auth, import get_auth_store from middleware**

Replace entire file with:

```python
# auth/routes.py
import os
from fastapi import APIRouter, Depends, Header, HTTPException

from auth.jwt import encode_jwt
from auth.middleware import require_auth, get_auth_store
from auth.models import (
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    CreateApiKeyRequest,
    CreateApiKeyResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _require_admin(x_api_key: str = Header(None)) -> bool:
    """Inline admin API key check — only used by the register endpoint."""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Admin API key required")
    admin_key = os.getenv("ADMIN_API_KEY", "")
    if not admin_key or x_api_key != admin_key:
        raise HTTPException(status_code=401, detail="Invalid admin API key")
    return True


@router.post("/register", status_code=201, response_model=RegisterResponse)
def register(req: RegisterRequest, _: bool = Depends(_require_admin)):
    store = get_auth_store()

    if store.get_user_by_email(req.email):
        raise HTTPException(status_code=409, detail="Email already registered")

    team_id = None
    if req.team_name:
        team_id = store.create_team(req.team_name)

    user_id = store.create_user(req.email, req.password, team_id)
    return RegisterResponse(user_id=user_id, email=req.email, team_id=team_id)


@router.post("/token", response_model=TokenResponse)
def token_exchange(x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")

    store = get_auth_store()
    user = store.validate_api_key(x_api_key)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")

    expires_minutes = int(os.getenv("JWT_EXPIRY_MINUTES", "15"))
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "team_id": user["team_id"],
        "is_admin": bool(user["is_admin"]),
    }
    jwt_token = encode_jwt(payload, secret=os.getenv("JWT_SECRET", ""), expires_minutes=expires_minutes)
    return TokenResponse(token=jwt_token, expires_in=expires_minutes * 60)


@router.post("/api-keys", status_code=201, response_model=CreateApiKeyResponse)
def create_api_key(req: CreateApiKeyRequest, user: dict = Depends(require_auth)):
    store = get_auth_store()
    raw_key, _ = store.create_api_key(user["id"], req.label)
    return CreateApiKeyResponse(api_key=raw_key)


@router.post("/revoke-key")
def revoke_api_key(req: dict, user: dict = Depends(require_auth)):
    key_hash = req.get("key_hash")
    if not key_hash:
        raise HTTPException(status_code=400, detail="key_hash required")
    store = get_auth_store()
    store.revoke_api_key(key_hash)
    return {"status": "revoked"}


@router.get("/me", response_model=UserResponse)
def get_me(user: dict = Depends(require_auth)):
    return UserResponse(
        id=user["id"],
        email=user["email"],
        team_id=user.get("team_id"),
        is_admin=bool(user.get("is_admin", False)),
    )
```

- [ ] **Step 3: Update `auth/models.py` — remove unused models**

Replace entire file with:

```python
# auth/models.py
from pydantic import BaseModel
from typing import Optional


class RegisterRequest(BaseModel):
    email: str
    password: str
    team_name: Optional[str] = None


class RegisterResponse(BaseModel):
    user_id: str
    email: str
    team_id: Optional[str]


class TokenResponse(BaseModel):
    token: str
    expires_in: int


class CreateApiKeyRequest(BaseModel):
    label: Optional[str] = None


class CreateApiKeyResponse(BaseModel):
    api_key: str


class UserResponse(BaseModel):
    id: str
    email: str
    team_id: Optional[str]
    is_admin: bool
```

- [ ] **Step 4: Commit**

```bash
git add auth/middleware.py auth/routes.py auth/models.py
git commit -m "refactor: clean up auth/ — remove require_admin, deduplicate get_auth_store, remove unused models"
```

---

### Task 15: Clean up `utils/chunker.py`

**Files:**
- Modify: `utils/chunker.py`

- [ ] **Step 1: Rewrite `utils/chunker.py` — keep only `chunk_text`**

Replace entire file with:

```python
# utils/chunker.py
"""Pure text chunking utility using Agno's RecursiveChunking."""
from typing import List, Dict, Any

from agno.knowledge.document import Document
from agno.knowledge.chunking.recursive import RecursiveChunking


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 200,
    source_metadata: str = "text",
) -> List[Dict[str, Any]]:
    """Chunks text uniformly using Agno's abstract RecursiveChunking."""
    if not text or not text.strip():
        return []

    splitter = RecursiveChunking(
        chunk_size=chunk_size,
        overlap=overlap,
    )

    doc = Document(content=text, name=source_metadata)
    chunked_docs = splitter.chunk(doc)

    return [
        {
            "chunk_index": i,
            "text": d.content,
            "source": source_metadata,
        }
        for i, d in enumerate(chunked_docs)
    ]
```

- [ ] **Step 2: Commit**

```bash
git add utils/chunker.py
git commit -m "refactor: slim utils/chunker.py to only chunk_text(), move extraction to ingestion/"
```

---

### Task 16: Clean up `workers/tasks.py` — lazy init stores

**Files:**
- Modify: `workers/tasks.py`

- [ ] **Step 1: Rewrite `workers/tasks.py` with lazy initialization**

Replace entire file with:

```python
# workers/tasks.py
"""Celery tasks for document ingestion and memory lifecycle management."""
import os
import logging

from workers.celery_app import celery_app
from ingestion.extractors import extract_text_from_file
from utils.chunker import chunk_text
from utils.embedder import embed_chunks
from agents.extractor_agent import ExtractorAgent

logger = logging.getLogger(__name__)


def _get_graph_store():
    """Lazy-init the graph store."""
    from db.graph_store import GraphStore
    return GraphStore(
        uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        user=os.getenv("NEO4J_USER", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "password"),
    )


def _get_vector_store():
    """Lazy-init the vector store."""
    from db.vector_store import VectorStore
    return VectorStore(path=os.getenv("LANCEDB_PATH", "./data/lancedb"))


def _get_memory_manager():
    """Lazy-init the memory manager."""
    from db.lifecycle.memory_manager import MemoryManager
    from agents.extractor_agent import ExtractorAgent
    extractor = ExtractorAgent()
    return MemoryManager(_get_graph_store(), _get_vector_store(), extractor=extractor)


@celery_app.task(bind=True, max_retries=3)
def process_document_ingestion(self, document_path: str, multimodal: bool = False):
    """
    Asynchronous Ingestion Worker for large documents/PDFs/Markdown.
    Full pipeline: extract -> chunk -> embed -> vector insert -> extract triples -> graph insert.
    """
    logger.info(f"Starting async ingestion for {document_path}")

    try:
        # 1. Extract text from file
        text = extract_text_from_file(document_path)
        if not text or not text.strip():
            logger.warning(f"No text extracted from {document_path}")
            os.remove(document_path)
            return {"chunks_count": 0, "triples_count": 0, "source": os.path.basename(document_path)}

        source_name = os.path.basename(document_path)

        # 2. Chunk the text
        chunks = chunk_text(text, source_metadata=source_name)
        if not chunks:
            logger.warning(f"No chunks produced from {document_path}")
            os.remove(document_path)
            return {"chunks_count": 0, "triples_count": 0, "source": source_name}

        # 3. Embed chunks
        embedded_chunks = embed_chunks(chunks)

        # 4. Insert into vector store
        vector_store = _get_vector_store()
        vector_store.insert(embedded_chunks)
        logger.info(f"Inserted {len(embedded_chunks)} chunks into vector store")

        # 5. Extract triples from full text
        full_text = "\n".join(c["text"] for c in chunks)
        extractor = ExtractorAgent()
        triples = extractor.extract(full_text)

        # 6. Insert triples into graph store
        if triples:
            graph_store = _get_graph_store()
            graph_store.upsert_triples(triples, context_id=document_path)
            logger.info(f"Inserted {len(triples)} triples into graph store")

        # 7. Clean up staging file
        os.remove(document_path)

        logger.info(f"Successfully ingested {document_path}")
        return {
            "chunks_count": len(embedded_chunks),
            "triples_count": len(triples),
            "source": source_name,
        }
    except Exception as exc:
        logger.error(f"Ingestion failed: {exc}")
        try:
            os.remove(document_path)
        except OSError:
            pass
        self.retry(exc=exc, countdown=60)

- [ ] **Step 2: Commit**

```bash
git add workers/tasks.py
git commit -m "refactor: lazy-init stores in workers/tasks.py, remove module-level globals"
```

---

### Task 17: Clean up `db/lifecycle/memory_manager.py` — inject extractor

**Files:**
- Modify: `db/lifecycle/memory_manager.py`

- [ ] **Step 1: Rewrite `db/lifecycle/memory_manager.py` with injected extractor**

Replace entire file with:

```python
# db/lifecycle/memory_manager.py
"""Memory lifecycle management: decay, consolidation, deduplication."""
import datetime
import logging

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Handles the lifecycle of memories in the GraphRAG system.
    The extractor agent is injected to avoid cross-layer imports.
    """

    def __init__(self, graph_store, vector_store, extractor=None):
        self.graph = graph_store
        self.vector = vector_store
        self.extractor = extractor

    def merge_duplicate_entities(self, similarity_threshold=0.85):
        """
        Entity Resolution / Graph Deduplication:
        Finds nodes with similar labels/names and merges their relationships.
        """
        logger.info("Starting Entity Resolution/Deduplication job...")
        merge_query = """
        MATCH (a:Entity), (b:Entity)
        WHERE a.name <> b.name AND (
            toLower(a.name) CONTAINS toLower(b.name)
            OR toLower(b.name) CONTAINS toLower(a.name)
        )
        WITH a, b LIMIT 100
        CALL apoc.refactor.mergeNodes([a, b], {properties: "discard", mergeRels: true}) YIELD node
        RETURN node
        """
        self.graph.run_query(merge_query)
        logger.info("Entity resolution completed.")

    def apply_memory_decay(self, decay_days=30):
        """
        Memory Decay / Forgetting Mechanism:
        Reduces the weight of old memories or deletes them if their TTL has expired.
        """
        logger.info(f"Applying memory decay for memories older than {decay_days} days...")
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=decay_days)
        cutoff_iso = cutoff_date.isoformat()

        # 1. Decay Vector Store (LanceDB) — delete low-importance stale records
        self.vector.table.delete(
            f"last_accessed < '{cutoff_iso}' AND importance_score < 0.3"
        )

        # 2. Decay Graph Store (Neo4j) — detach delete stale low-importance memories
        decay_query = """
        MATCH (m:Memory)
        WHERE m.last_accessed < $cutoff_date AND m.importance_score < 0.3
        DETACH DELETE m
        """
        self.graph.run_query(decay_query, {"cutoff_date": cutoff_iso})
        logger.info("Memory decay applied.")

    def consolidate_session_memories(self, session_id):
        """
        Memory Consolidation & Summarization:
        Takes a raw session chat log, extracts core long-term facts,
        updates stores, and deletes the verbose raw logs.
        """
        logger.info(f"Consolidating memory for session {session_id}...")

        if not self.extractor:
            logger.warning("No extractor available for memory consolidation.")
            return

        # 1. Fetch raw logs for session from vector store
        raw_logs = self.vector.table.search().where(
            f"session_id = '{session_id}' AND role = 'raw'"
        ).to_list()

        if not raw_logs:
            logger.info(f"No raw logs found for session {session_id}.")
            return

        # 2. Concatenate raw text for summarization
        session_text = "\n".join(record.get("text", "") for record in raw_logs)

        # 3. Use extractor agent to summarize into key semantic facts
        triples = self.extractor.extract(session_text)

        # 4. Insert extracted facts into Graph store
        if triples:
            self.graph.upsert_triples(triples, context_id=session_id)

        # 5. Mark raw logs as consolidated (update metadata)
        raw_ids = [record.get("id") for record in raw_logs if record.get("id")]
        if raw_ids:
            id_list = ", ".join(f"'{rid}'" for rid in raw_ids)
            self.vector.table.delete(f"id IN ({id_list})")

        logger.info(f"Session {session_id} consolidation completed. Extracted {len(triples)} facts.")
```

- [ ] **Step 2: Commit**

```bash
git add db/lifecycle/memory_manager.py
git commit -m "refactor: inject extractor into MemoryManager, remove cross-layer import"
```

---

## Phase 5: Update tests

### Task 18: Update `tests/unit/test_chunker.py`

**Files:**
- Modify: `tests/unit/test_chunker.py`

- [ ] **Step 1: Read current test file and update imports**

The test currently imports `extract_text_from_url` from `utils.chunker`. Update to import from `ingestion.extractors`.

Replace:
```python
from utils.chunker import chunk_text, extract_text_from_url
```

With:
```python
from utils.chunker import chunk_text
from ingestion.extractors import extract_text_from_url
```

- [ ] **Step 2: Commit**

```bash
git add tests/unit/test_chunker.py
git commit -m "test: update test_chunker.py imports for moved extract_text_from_url"
```

---

### Task 19: Update `tests/unit/test_memory_manager.py`

**Files:**
- Modify: `tests/unit/test_memory_manager.py`

- [ ] **Step 1: Update test fixtures for injected extractor**

The `MemoryManager` now takes `extractor` as a constructor parameter. Update the fixture:

Replace:
```python
@pytest.fixture
def memory_manager(mock_stores):
    return MemoryManager(graph_store=mock_stores[0], vector_store=mock_stores[1])
```

With:
```python
@pytest.fixture
def memory_manager(mock_stores):
    return MemoryManager(graph_store=mock_stores[0], vector_store=mock_stores[1], extractor=MagicMock())
```

Also update `test_consolidate_session_memories_extracts_and_stores_facts` — remove the `patch("db.lifecycle.memory_manager.ExtractorAgent")` since the extractor is now injected via fixture.

- [ ] **Step 2: Commit**

```bash
git add tests/unit/test_memory_manager.py
git commit -m "test: update test_memory_manager.py for injected extractor"
```

---

### Task 20: Update `tests/unit/test_workers.py` and `tests/unit/test_ingestion_task.py`

**Files:**
- Modify: `tests/unit/test_workers.py`
- Modify: `tests/unit/test_ingestion_task.py`

- [ ] **Step 1: Update `test_workers.py`**

Since stores are now lazy-init inside task functions, the patching approach changes. Update the `tasks_module` fixture:

Replace the entire `tasks_module` fixture with:

```python
@pytest.fixture
def tasks_module(mock_celery):
    """Import workers.tasks after celery is patched."""
    with patch("workers.tasks._get_graph_store", return_value=MagicMock()):
        with patch("workers.tasks._get_vector_store", return_value=MagicMock()):
            with patch("workers.tasks._get_memory_manager", return_value=MagicMock()):
                with patch("workers.tasks.ExtractorAgent"):
                    from workers import tasks
                    yield tasks
```

- [ ] **Step 2: Update `test_ingestion_task.py`**

Update the `ingestion_task` fixture similarly:

```python
@pytest.fixture
def ingestion_task(mock_celery):
    with patch("workers.tasks._get_graph_store", return_value=MagicMock()):
        with patch("workers.tasks._get_vector_store", return_value=MagicMock()):
            with patch("workers.tasks._get_memory_manager", return_value=MagicMock()):
                with patch("workers.tasks.ExtractorAgent"):
                    for mod_name in list(sys.modules.keys()):
                        if mod_name.startswith("workers"):
                            del sys.modules[mod_name]
                    from workers import tasks
                    yield tasks
```

Also update the import in the test:
Replace:
```python
with patch("workers.tasks.extract_text_from_file", return_value="chunk one\nchunk two"):
    with patch("workers.tasks.chunk_text", return_value=mock_chunks):
```

With:
```python
with patch("workers.tasks.extract_text_from_file", return_value="chunk one\nchunk two"):
    with patch("workers.tasks.chunk_text", return_value=mock_chunks):
```

(These stay the same since they're already patching the right module.)

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_workers.py tests/unit/test_ingestion_task.py
git commit -m "test: update worker tests for lazy-init store pattern"
```

---

### Task 21: Merge `test_api.py` + `test_query_api.py`, delete `test_query_api.py`

**Files:**
- Modify: `tests/unit/test_api.py`
- Delete: `tests/unit/test_query_api.py`

- [ ] **Step 1: Read both files and merge**

The merged `test_api.py` should contain:
- All unique tests from `test_api.py` (health, query streaming, validation, injection/PII checks, memory search/graph, session)
- All unique tests from `test_query_api.py` (query NDJSON with citations, auth checks, session history loading/saving)
- Remove duplicate `MockStreamEvent` dataclass (keep one)
- Remove duplicate `mock_arun_stream` function (keep one)
- Remove duplicate test functions (e.g., `test_health_returns_ok` appears in both)

Update imports to use new module paths:
- `from agents.rag_team import build_rag_team_with_stores` (was `from db.dependencies import ...`)

- [ ] **Step 2: Delete `test_query_api.py`**

```bash
rm tests/unit/test_query_api.py
```

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_api.py tests/unit/test_query_api.py
git commit -m "test: merge test_api.py + test_query_api.py, remove duplicates"
```

---

### Task 22: Update `tests/unit/test_retrieval_pipeline.py`

**Files:**
- Modify: `tests/unit/test_retrieval_pipeline.py`

- [ ] **Step 1: Update imports**

Already done in Task 5, but verify the `build_rag_team_with_stores` test uses the correct import:

```python
from agents.rag_team import build_rag_team_with_stores
```

- [ ] **Step 2: Commit**

```bash
git add tests/unit/test_retrieval_pipeline.py
git commit -m "test: update test_retrieval_pipeline.py imports"
```

---

### Task 23: Update `tests/unit/test_auth_routes.py`

**Files:**
- Modify: `tests/unit/test_auth_routes.py`

- [ ] **Step 1: Update test to use new import path for `get_auth_store`**

The test patches `auth.routes.get_auth_store`. Since `get_auth_store` is now imported from `auth.middleware`, the patch path changes.

Replace:
```python
with patch("auth.routes.get_auth_store") as mock_store:
```

With:
```python
with patch("auth.routes.get_auth_store") as mock_store:
```

(This stays the same because `auth.routes` imports `get_auth_store` from middleware, so patching `auth.routes.get_auth_store` still works.)

Also update the admin key test — `validate_admin_api_key` is now `_require_admin` and inlined:

Replace:
```python
with patch("auth.routes.validate_admin_api_key", return_value=True):
```

With:
```python
with patch("auth.routes._require_admin", return_value=True):
```

- [ ] **Step 2: Commit**

```bash
git add tests/unit/test_auth_routes.py
git commit -m "test: update test_auth_routes.py for inlined admin auth"
```

---

### Task 24: Update `tests/unit/test_auth_middleware.py`

**Files:**
- Modify: `tests/unit/test_auth_middleware.py`

- [ ] **Step 1: Remove `require_admin` test**

Since `require_admin` was deleted, remove any test that tests it. Keep tests for `require_auth` and `get_auth_store`.

- [ ] **Step 2: Commit**

```bash
git add tests/unit/test_auth_middleware.py
git commit -m "test: remove require_admin tests from test_auth_middleware.py"
```

---

## Phase 6: Final verification

### Task 25: Run all tests

- [ ] **Step 1: Run unit tests**

```bash
uv run pytest tests/unit -v --tb=short
```

Expected: All tests pass. If any fail, fix the import paths or test fixtures.

- [ ] **Step 2: Run test coverage**

```bash
uv run pytest tests/unit --cov=. --cov-report=term-missing
```

Expected: Coverage report shows all modules covered.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "refactor: fix all test failures, full test suite passing"
```

---

### Task 26: Verify app loads and routes are correct

- [ ] **Step 1: Verify app loads**

```bash
uv run python -c "
from agentos import app
routes = [(r.path, r.methods) for r in app.routes if hasattr(r, 'methods')]
for path, methods in sorted(routes):
    print(f'{methods} {path}')
"
```

Expected output includes:
```
{'GET'} /health
{'POST'} /query
{'GET'} /memory/search
{'GET'} /memory/graph
{'POST'} /ingest
{'POST'} /ingest/url
{'GET'} /ingest/{task_id}
{'POST'} /session/new
{'POST'} /auth/register
{'POST'} /auth/token
{'POST'} /auth/api-keys
{'POST'} /auth/revoke-key
{'GET'} /auth/me
```

- [ ] **Step 2: Verify no dead imports**

```bash
uv run python -c "
import agentos
import workers.tasks
import agents.rag_team
import agents.retrieval.pipeline
import ingestion.extractors
import db.context
import api.dependencies
import auth.middleware
import auth.routes
print('All imports OK')
"
```

Expected: `All imports OK`

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "refactor: verify app loads, all routes registered, no dead imports"
```

---

### Task 27: Verify project structure matches spec

- [ ] **Step 1: Verify deleted files are gone**

```bash
test ! -f tools/vector_tool.py && test ! -f tools/graph_tool.py && test ! -d tools && test ! -f db/dependencies.py && test ! -f tests/unit/test_query_api.py && test ! -f tests/unit/test_vector_tool.py && test ! -f tests/unit/test_graph_tool.py && echo "All deletions confirmed"
```

Expected: `All deletions confirmed`

- [ ] **Step 2: Verify new files exist**

```bash
test -f db/context.py && test -f api/dependencies.py && test -f api/routes/__init__.py && test -f api/routes/health.py && test -f api/routes/query.py && test -f api/routes/memory.py && test -f api/routes/ingest.py && test -f api/routes/session.py && test -f agents/retrieval/pipeline.py && test -f ingestion/extractors.py && echo "All new files exist"
```

Expected: `All new files exist`

- [ ] **Step 3: Final commit with cleanup**

```bash
git add -A
git commit -m "refactor: final cleanup — all files relocated, deleted, and verified"
```
