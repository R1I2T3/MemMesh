# Phase 7 — Hybrid RAG: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the full Hybrid Retrieval-Augmented Generation (RAG) pipeline comprising LLM query routing, step-back query rewriting, FalkorDB multi-hop graph traversal, cross-retrieval context fusion, cross-encoder neural reranking, and live Pipeline Lens visualization.

**Architecture:** An SQLite migration sets up a cache and classification logs. High-performance modules orchestrate the pipeline: `router.py` (Gemini route classifier), `rewriter.py` (query rephraser), `graph_traversal.py` (FalkorDB query with team filters), `fusion.py` (combines vector and graph nodes), and `reranker.py` (scores relevance). These are integrated into the main `/query` entry point, feeding the real-time SvelteKit Pipeline Lens.

**Tech Stack:** Python 3.11+, FastAPI, FalkorDB, ChromaDB, Google Gemini API, SentenceTransformers (CrossEncoder), SQLite

---

## Scope Note

This plan builds on all previous phases. It represents the key RAG intelligence, combining semantic vectors and structural graph schemas.

---

## File Structure

### Backend New/Modified Files

```
backend/
├── db/
│   └── migrations/
│       └── 005_hybrid_rag.sql                  # Create: Schema migrations for RAG caches & logs
├── agents/
│   ├── router.py                               # Create: LLM-based query router
│   ├── rewriter.py                             # Create: Step-back query rewriter
│   ├── graph_traversal.py                      # Create: FalkorDB multi-hop retriever
│   ├── fusion.py                               # Create: Vector and graph context merger
│   └── reranker.py                             # Create: Neural cross-encoder reranker
└── tests/
    └── test_hybrid_rag.py                      # Create: Integration tests for the full pipeline
```

### Frontend New/Modified Files

```
frontend/
├── src/
│   └── routes/
│       └── dashboard/
│           ├── pipeline-lens.svelte            # Modify: Add Routing and Graph hop views
│           └── stage-timeline.svelte           # Modify: Incorporate all 7 pipeline stages
```

---

## Group A: Advanced Backend Retrieval & Routing

### Task 1: Hybrid RAG Schemas & Logs

**Files:**
- Create: `backend/db/migrations/005_hybrid_rag.sql`

- [ ] **Step 1: Write migration SQL**

Create `backend/db/migrations/005_hybrid_rag.sql`:

```sql
-- backend/db/migrations/005_hybrid_rag.sql
CREATE TABLE router_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id     TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    query_hash  TEXT NOT NULL,
    route       TEXT NOT NULL CHECK (route IN ('graph', 'vector', 'hybrid')),
    created_at  DATETIME NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE rewrite_cache (
    query_hash  TEXT PRIMARY KEY,
    team_id     TEXT NOT NULL,
    rewrites    TEXT NOT NULL, -- JSON list of rewritten string queries
    created_at  DATETIME NOT NULL DEFAULT (datetime('now'))
);
```

- [ ] **Step 2: Apply migration**

Run: `cd backend && make reset-db`
Expected: Migrations successfully apply.

- [ ] **Step 3: Commit**

```bash
git add db/migrations/005_hybrid_rag.sql
git commit -m "migration: add hybrid RAG classification log and rewrite cache schemas"
```

---

### Task 2: Query Routing & Rewriting Modules

**Files:**
- Create: `backend/agents/router.py`
- Create: `backend/agents/rewriter.py`

- [ ] **Step 1: Create Query Router**

Create `backend/agents/router.py` using Gemini API with structured classifier:

```python
# backend/agents/router.py
import hashlib
import json
import google.generativeai as genai
from db.sqlite import get_connection
from config import settings

class QueryRouter:
    def __init__(self):
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    def route_query(self, team_id: str, user_id: str, query: str) -> str:
        """Classify route using Gemini. Fall back to 'hybrid' on failure or ambiguity."""
        prompt = (
            f"Classify the following query into exactly one of three routing keys:\n"
            f"- 'graph': Query requires structural relationships, network connections, or entity attributes.\n"
            f"- 'vector': Query asks for general knowledge, text description summaries, or conceptual search.\n"
            f"- 'hybrid': Query requires both semantic background and exact structural relationship context.\n\n"
            f"Query: \"{query}\"\n"
            f"Respond with exactly one word (lowercase): 'graph', 'vector', or 'hybrid'."
        )
        try:
            response = self.model.generate_content(prompt)
            route = response.text.strip().lower()
            if route not in ["graph", "vector", "hybrid"]:
                route = "hybrid"
        except Exception:
            route = "hybrid"

        # Log decision to DB
        query_hash = hashlib.sha256(query.encode()).hexdigest()
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO router_log (team_id, user_id, query_hash, route) VALUES (?, ?, ?, ?)",
                (team_id, user_id, query_hash, route)
            )
            conn.commit()
        finally:
            conn.close()
            
        return route
```

- [ ] **Step 2: Create Query Rewriter**

Create `backend/agents/rewriter.py` producing a step-back query and caches results.

- [ ] **Step 3: Commit**

```bash
git add agents/router.py agents/rewriter.py
git commit -m "feat: implement Gemini-based query router and step-back rewriter"
```

---

### Task 3: FalkorDB Multi-Hop Graph Traversal

**Files:**
- Create: `backend/agents/graph_traversal.py`

- [ ] **Step 1: Write graph traversal module**

Create `backend/agents/graph_traversal.py` asserting strict `team_id` filtration:

```python
# backend/agents/graph_traversal.py
from typing import List, Dict, Any
from falkordb import FalkorDB
from config import settings

class GraphTraversal:
    def __init__(self):
        # falkordb-python client
        self.db = FalkorDB(host=settings.falkordb_host, port=settings.falkordb_port)

    def traverse(self, team_id: str, start_entities: List[str], max_hops: int = 3) -> List[Dict[str, Any]]:
        """Perform multi-hop traversal strictly scoped to the active team's sub-graph."""
        graph = self.db.select_graph(f"team_{team_id}")
        
        # Enforce defense-in-depth: raise error if team_id matches no scope
        if not team_id:
            raise ValueError("Access Denied: Missing team context scope.")

        results = []
        for entity in start_entities:
            query = (
                f"MATCH path = (e:Entity {{name: $name, team_id: $team_id}})-[r:RELATES_TO*1..{max_hops}]->(target) "
                f"RETURN path, target.name, target.type LIMIT 10"
            )
            try:
                res = graph.query(query, {"name": entity, "team_id": team_id})
                for row in res.result_set:
                    results.append({
                        "path": str(row[0]),
                        "target_name": row[1],
                        "target_type": row[2]
                    })
            except Exception:
                # FalkorDB down fallback: continue vector only
                pass
        return results
```

- [ ] **Step 2: Commit**

```bash
git add agents/graph_traversal.py
git commit -m "feat: implement secure multi-hop FalkorDB graph traverser"
```

---

### Task 4: Hybrid Fusion & Cross-Encoder Reranker

**Files:**
- Create: `backend/agents/fusion.py`
- Create: `backend/agents/reranker.py`

- [ ] **Step 1: Write fusion and reranking modules**

Create `backend/agents/fusion.py` merging vector and graph nodes.
Create `backend/agents/reranker.py` using `cross-encoder/ms-marco-MiniLM-L-6-v2` with a BM25 scoring fallback.

- [ ] **Step 2: Commit**

```bash
git add agents/fusion.py agents/reranker.py
git commit -m "feat: add hybrid context fusion and cross-encoder reranker"
```

---

## Group B: Integration & Verification

### Task 5: Orchestrate Hybrid Pipeline

**Files:**
- Modify: `backend/api/routes/query.py`

- [ ] **Step 1: Wire all modules into Query endpoint**

Update query handler to process: Rewriting → Routing → Concurrent Graph/Vector Search → Context Fusion → Reranking → Synthesis. Make sure all stages emit Pipeline stage events.

- [ ] **Step 2: Commit**

```bash
git add api/routes/query.py
git commit -m "feat: orchestrate comprehensive 7-stage Hybrid RAG retrieval pipeline"
```

---

### Task 6: Playwright Hybrid Verification

**Files:**
- Create: `frontend/tests/e2e/hybrid_rag.spec.ts`

- [ ] **Step 1: Create spec**

Create E2E test making complex requests demanding both semantic and graph contexts, asserting correct traversal logs display in the timeline.

- [ ] **Step 2: Execute tests**

Run: `cd frontend && npx playwright test`
Expected: Complete suite passes.

- [ ] **Step 3: Commit**

```bash
git add frontend/tests/e2e/hybrid_rag.spec.ts
git commit -m "test: add E2E verification spec for full Hybrid RAG retrieval"
```
```
