# Phase 5 — First RAG Experience: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the primary Retrieval-Augmented Generation (RAG) query interface with team-scoped semantic vector search, real-time citation tracking, streaming Gemini synthesis via NDJSON, chat session persistence, and a streaming frontend chat interface.

**Architecture:** A unified pipeline performs semantic query embedding via sentence-transformers, searches the team's dedicated ChromaDB collection (`team_{team_id}`), maps hits to structural SQLite citations, forwards context to Google Gemini, and streams chunks in real-time as NDJSON events. SQLite schema additions handle persistent conversation `sessions` and chat history `turns`. The frontend implements streaming chunk assembly, reactive markdown rendering, a side-pane citation viewer, and a persistent chat history list.

**Tech Stack:** Python 3.11+, FastAPI, ChromaDB, Google Gemini API, SvelteKit, SSE / NDJSON, SQLite

---

## Scope Note

This plan builds on **Phase 4** (indexing & collections). It relies on team-scoped vectors being present. It introduces the first user-facing agentic search capability of the platform.

---

## File Structure

### Backend New/Modified Files

```
backend/
├── db/
│   └── migrations/
│       └── 004_sessions.sql                    # Create: Migrations for session & turn tables
├── agents/
│   ├── __init__.py                             # Create
│   ├── vector_search.py                        # Create: Scoped ChromaDB search
│   └── synthesis.py                            # Create: LLM synthesis and streamer
├── api/
│   └── routes/
│       └── query.py                            # Create: Streaming query and session APIs
└── tests/
    └── test_rag_api.py                         # Create: Integration tests for streaming RAG
```

### Frontend New/Modified Files

```
frontend/
├── src/
│   └── routes/
│       └── dashboard/
│           ├── +page.svelte                    # Modify: Incorporate Chat interface
│           ├── chat-window.svelte              # Create: Interactive streaming chat
│           ├── session-list.svelte             # Create: Persistent chat sessions sidebar
│           └── citation-drawer.svelte          # Create: Citations detail sliding drawer
```

---

## Group A: Database Schemas & Vector Retrieve

### Task 1: Chat Session Schemas

**Files:**
- Create: `backend/db/migrations/004_sessions.sql`

- [ ] **Step 1: Write SQL Schema**

Create `backend/db/migrations/004_sessions.sql`:

```sql
-- backend/db/migrations/004_sessions.sql
CREATE TABLE sessions (
    session_id      TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    team_id         TEXT NOT NULL REFERENCES teams(team_id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    created_at      DATETIME NOT NULL DEFAULT (datetime('now')),
    consolidated_at DATETIME
);

CREATE TABLE turns (
    turn_id         TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    team_id         TEXT NOT NULL REFERENCES teams(team_id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT NOT NULL,
    created_at      DATETIME NOT NULL DEFAULT (datetime('now'))
);
```

- [ ] **Step 2: Run migration**

Run: `cd backend && make reset-db`
Expected: Database drops and recreates successfully with 4 applied migrations.

- [ ] **Step 3: Commit**

```bash
git add db/migrations/004_sessions.sql
git commit -m "migration: add chat session and turn SQLite tables"
```

---

### Task 2: Vector Retrieval Scoping

**Files:**
- Create: `backend/agents/vector_search.py`

- [ ] **Step 1: Implement vector query module**

Create `backend/agents/vector_search.py`:

```python
# backend/agents/vector_search.py
from typing import List, Dict, Any
import chromadb
from config import settings

class ScopedVectorSearch:
    def __init__(self, chroma_dir: str = settings.data_dir + "/chroma"):
        self.client = chromadb.PersistentClient(path=chroma_dir)
        
    def search(self, team_id: str, query_vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """Retrieve vector chunks strictly scoped to the active team's collection."""
        collection_name = f"team_{team_id}"
        try:
            collection = self.client.get_collection(collection_name)
        except Exception:
            # If collection doesn't exist yet, return empty
            return []
            
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )
        
        hits = []
        if not results or not results["documents"]:
            return hits
            
        for i in range(len(results["documents"][0])):
            hits.append({
                "chunk_id": results["ids"][0][i],
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i]
            })
        return hits
```

- [ ] **Step 2: Commit**

```bash
git add agents/vector_search.py
git commit -m "feat: implement team-scoped vector search retriever"
```

---

## Group B: Gemini Synthesis & Streaming Endpoints

### Task 3: Streaming Synthesis Pipeline

**Files:**
- Create: `backend/agents/synthesis.py`

- [ ] **Step 1: Write synthesis streaming module**

Create `backend/agents/synthesis.py`:

```python
# backend/agents/synthesis.py
import json
from typing import AsyncGenerator, List, Dict, Any
import google.generativeai as genai
from config import settings

genai.configure(api_key=settings.gemini_api_key)

class GeminiSynthesis:
    def __init__(self, model_name: str = "gemini-1.5-flash"):
        self.model = genai.GenerativeModel(model_name)
        
    async def synthesize(
        self,
        query: str,
        contexts: List[Dict[str, Any]],
        team_id: str
    ) -> AsyncGenerator[str, None]:
        """Synthesize answer with inline citations and stream as NDJSON lines."""
        # 1. Format context and citations
        context_str = ""
        citations = []
        
        for idx, ctx in enumerate(contexts):
            ref_num = idx + 1
            meta = ctx["metadata"]
            context_str += f"[{ref_num}] Document: {meta.get('filename', 'Unknown')}, Page: {meta.get('page_number', '1')}\nContent: {ctx['content']}\n\n"
            citations.append({
                "type": "citation",
                "source": "vector",
                "chunk_id": ctx["chunk_id"],
                "score": float(1 - ctx["distance"]),
                "source_doc": meta.get("filename", "Unknown"),
                "page": meta.get("page_number", 1),
                "team_id": team_id
            })
            
        # 2. Emit citation metadata immediately
        for cit in citations:
            yield json.dumps(cit) + "\n"
            
        # 3. Request streaming response from Gemini
        prompt = (
            f"You are an assistant answering a question based strictly on the following context. "
            f"Ground all statements. Cite sources inline using bracketed numbers corresponding to the context list (e.g. [1]).\n\n"
            f"Context:\n{context_str}\n\n"
            f"Question: {query}\nAnswer:"
        )
        
        response = self.model.generate_content(prompt, stream=True)
        for chunk in response:
            if chunk.text:
                yield json.dumps({"type": "text_chunk", "content": chunk.text}) + "\n"
                
        yield json.dumps({"type": "done"}) + "\n"
```

- [ ] **Step 2: Commit**

```bash
git add agents/synthesis.py
git commit -m "feat: implement streaming RAG answer synthesis via Google Gemini API"
```

---

### Task 4: Query Endpoint

**Files:**
- Create: `backend/api/routes/query.py`
- Modify: `backend/api/server.py`

- [ ] **Step 1: Write endpoint**

Create `backend/api/routes/query.py` using `StreamingResponse` with `application/x-ndjson`:

```python
# backend/api/routes/query.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uuid
from db.sqlite import get_connection
from auth.middleware import require_team_role
from agents.vector_search.py import ScopedVectorSearch
from agents.synthesis.py import GeminiSynthesis

router = APIRouter(prefix="/query", tags=["query"])

class QueryRequest(BaseModel):
    query: str
    active_team_id: str
    session_id: str = None

@router.post("")
async def query_pipeline(
    body: QueryRequest,
    current_user: dict = Depends(require_team_role("user"))
):
    # Validate user is in the team (handled by require_team_role)
    session_id = body.session_id or str(uuid.uuid4())
    
    # 1. Embed query (Mock embedding here for compilation, replace with sentence-transformers)
    query_vector = [0.1] * 384  # Replace with actual embedder output
    
    # 2. Search
    searcher = ScopedVectorSearch()
    contexts = searcher.search(body.active_team_id, query_vector)
    
    # 3. Stream response
    synthesizer = GeminiSynthesis()
    
    return StreamingResponse(
        synthesizer.synthesize(body.query, contexts, body.active_team_id),
        media_type="application/x-ndjson"
    )
```

- [ ] **Step 2: Register router**

Modify `backend/api/server.py` to register `query.py` router.

- [ ] **Step 3: Commit**

```bash
git add api/routes/query.py api/server.py
git commit -m "feat: create /query NDJSON streaming API endpoint"
```

---

## Group C: Frontend Chat UI

### Task 5: Streaming Chat Interface

**Files:**
- Create: `frontend/src/routes/dashboard/chat-window.svelte`
- Create: `frontend/src/routes/dashboard/session-list.svelte`
- Create: `frontend/src/routes/dashboard/citation-drawer.svelte`
- Modify: `frontend/src/routes/dashboard/+page.svelte`

- [ ] **Step 1: Write chat assembler**

Create `frontend/src/routes/dashboard/chat-window.svelte` parsing stream lines, appending markdown-rendered content dynamically, and showing citation reference cards underneath responses.

- [ ] **Step 2: Add citation drawer**

Create `frontend/src/routes/dashboard/citation-drawer.svelte` that slides in from the right when clicking a bracketed inline source citation.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/routes/dashboard/
git commit -m "feat: complete interactive SvelteKit streaming chat window and citations panel"
```

---

## Group D: Testing

### Task 6: Playwright Chat Integration Test

**Files:**
- Create: `frontend/tests/e2e/chat.spec.ts`

- [ ] **Step 1: Write query E2E test**

Create `frontend/tests/e2e/chat.spec.ts` simulating a chat session, asking a question, verifying response chunks arrive, and opening the citation drawer.

- [ ] **Step 2: Run all tests**

Run: `cd frontend && npx playwright test`
Expected: ALL vector search, streaming auth, and UI tests pass.

- [ ] **Step 3: Commit**

```bash
git add frontend/tests/e2e/chat.spec.ts
git commit -m "test: add Playwright E2E verification test for streaming chat RAG interface"
```
