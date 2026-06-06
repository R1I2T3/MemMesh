# Phase 6 — Pipeline Lens: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a real-time, visual pipeline introspection layer (Pipeline Lens) that streams multi-stage execution metrics (latency, status, intermediate state) directly to the user's dashboard during query execution.

**Architecture:** A Python-based `PipelineContext` tracking system is introduced in the backend to capture pipeline metrics across execution stages (e.g. Query Rewrite, Vector Search, Synthesis). These intermediate stage transitions are streamed live alongside content chunks as structured NDJSON events. The frontend implements the Pipeline Lens dashboard widget as a fully keyboard-accessible sidebar (desktop) that shifts to a drawer (tablet) or modal (mobile), complete with animated stage transitions, real-time durations, and accessibility alerts.

**Tech Stack:** Python 3.11+, FastAPI, NDJSON, SvelteKit, WAI-ARIA, HSL CSS variables

---

## Scope Note

This plan builds directly on **Phase 5** (RAG pipeline). It upgrades the `/query` endpoint to inject diagnostic stage milestones directly into the NDJSON event stream, exposing internal operations to users.

---

## File Structure

### Backend New/Modified Files

```
backend/
├── models/
│   ├── __init__.py                             # Create
│   └── context.py                              # Create: PipelineContext and Event models
├── api/
│   └── routes/
│       └── query.py                            # Modify: Update to track and stream pipeline events
└── tests/
    └── test_pipeline_lens_api.py               # Create: Integration tests for stage tracking
```

### Frontend New/Modified Files

```
frontend/
├── src/
│   └── routes/
│       └── dashboard/
│           ├── +page.svelte                    # Modify: Add Pipeline Lens layout
│           ├── pipeline-lens.svelte            # Create: Lens sidebar panel
│           └── stage-timeline.svelte           # Create: Vertical timeline visualizer
```

---

## Group A: Backend Introspection Layer

### Task 1: Pipeline Introspection Context

**Files:**
- Create: `backend/models/context.py`

- [ ] **Step 1: Write Context Dataclasses**

Create `backend/models/context.py` to capture metrics programmatically:

```python
# backend/models/context.py
import time
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class PipelineStageEvent(BaseModel):
    type: str = "pipeline_stage"
    stage: str
    status: str  # "started" | "completed" | "failed"
    timestamp: float
    duration_ms: Optional[float] = None
    results_count: Optional[int] = None
    error: Optional[str] = None

class PipelineContext:
    def __init__(self, team_id: str, user_id: str, session_id: str):
        self.team_id = team_id
        self.user_id = user_id
        self.session_id = session_id
        self.stage_starts: Dict[str, float] = {}
        self.events: List[PipelineStageEvent] = []

    def start_stage(self, stage_name: str) -> PipelineStageEvent:
        now = time.time()
        self.stage_starts[stage_name] = now
        event = PipelineStageEvent(
            stage=stage_name,
            status="started",
            timestamp=now
        )
        self.events.append(event)
        return event

    def complete_stage(self, stage_name: str, results_count: int = 0) -> PipelineStageEvent:
        now = time.time()
        start = self.stage_starts.get(stage_name, now)
        duration = (now - start) * 1000.0
        event = PipelineStageEvent(
            stage=stage_name,
            status="completed",
            timestamp=now,
            duration_ms=duration,
            results_count=results_count
        )
        self.events.append(event)
        return event

    def fail_stage(self, stage_name: str, error_message: str) -> PipelineStageEvent:
        now = time.time()
        start = self.stage_starts.get(stage_name, now)
        duration = (now - start) * 1000.0
        event = PipelineStageEvent(
            stage=stage_name,
            status="failed",
            timestamp=now,
            duration_ms=duration,
            error=error_message
        )
        self.events.append(event)
        return event
```

- [ ] **Step 2: Commit**

```bash
git add models/context.py
git commit -m "feat: implement backend PipelineContext instrumentation tracking classes"
```

---

### Task 2: Introspective Query Pipeline Stream

**Files:**
- Modify: `backend/api/routes/query.py`

- [ ] **Step 1: Update API query response generator**

Modify `backend/api/routes/query.py` to stream intermediate events:

```python
# backend/api/routes/query.py (partial diff)
import json
from models.context import PipelineContext

async def introspective_synthesize(query: str, team_id: str, user_id: str, session_id: str):
    ctx = PipelineContext(team_id, user_id, session_id)

    # 1. Pipeline Start
    yield json.dumps(ctx.start_stage("vector_search").dict()) + "\n"
    
    # Simulate Vector Search
    searcher = ScopedVectorSearch()
    contexts = searcher.search(team_id, [0.1] * 384)
    
    yield json.dumps(ctx.complete_stage("vector_search", results_count=len(contexts)).dict()) + "\n"

    # 2. Citations Output
    for c in contexts:
        yield json.dumps({
            "type": "citation",
            "source_doc": c["metadata"].get("filename"),
            "page": c["metadata"].get("page_number", 1),
            "score": float(1 - c["distance"])
        }) + "\n"

    # 3. Gemini Synthesis Start
    yield json.dumps(ctx.start_stage("synthesis").dict()) + "\n"
    
    synthesizer = GeminiSynthesis()
    async for chunk in synthesizer.synthesize_stream(query, contexts, team_id):
        yield chunk

    yield json.dumps(ctx.complete_stage("synthesis").dict()) + "\n"
    yield json.dumps({"type": "done"}) + "\n"
```

- [ ] **Step 2: Commit**

```bash
git add api/routes/query.py
git commit -m "feat: stream introspective pipeline stage events in query NDJSON"
```

---

## Group B: Frontend Timeline & Visualizations

### Task 3: Pipeline Lens Visual Component

**Files:**
- Create: `frontend/src/routes/dashboard/pipeline-lens.svelte`
- Create: `frontend/src/routes/dashboard/stage-timeline.svelte`
- Modify: `frontend/src/routes/dashboard/+page.svelte`

- [ ] **Step 1: Timeline CSS variables & structure**

Create `frontend/src/routes/dashboard/stage-timeline.svelte` using modern HSL themes, showing vertical timelines with smooth pulsing micro-animations for active steps and red error blocks for failures.

- [ ] **Step 2: Add collapsible local-storage toggle**

Create `frontend/src/routes/dashboard/pipeline-lens.svelte` that reads/writes localStorage to persist open/collapsed states, shifting dynamically between right sidebar, bottom drawer, or full screen depending on viewport.

- [ ] **Step 3: Screen reader accessibility**

Ensure screen readers announce stage completions dynamically:
```html
<div class="sr-only" aria-live="polite">
  Stage {activeStage} completed in {stageDuration} milliseconds.
</div>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/routes/dashboard/
git commit -m "feat: complete visual stage timeline in pipeline lens sidebar with responsive transitions"
```

---

## Group C: Validation

### Task 4: Real-time Pipeline Verification

**Files:**
- Create: `frontend/tests/e2e/pipeline.spec.ts`

- [ ] **Step 1: Write integration E2E spec**

Create `frontend/tests/e2e/pipeline.spec.ts` asserting that typing a query results in the Pipeline Lens rendering a sequence of started/completed animations.

- [ ] **Step 2: Execute test suite**

Run: `cd frontend && npx playwright test`
Expected: Pipeline visual verification tests pass cleanly.

- [ ] **Step 3: Commit**

```bash
git add frontend/tests/e2e/pipeline.spec.ts
git commit -m "test: add Playwright E2E real-time pipeline event assertion flow"
```
