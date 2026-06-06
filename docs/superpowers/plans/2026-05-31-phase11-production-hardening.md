# Phase 11 — Production Hardening: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute complete production hardening including structured JSON observability, request-ID routing, backend dependency fallbacks, API rate-limiting, CORS tightening, high-performance connection pooling, full keyboard & screen reader accessibility compliance (WCAG AA), theme styling checks, and end-to-end full workflow regression tests.

**Architecture:** Middleware extensions establish structured telemetry context, rate limiting, and sanitization on all input vectors. The startup system validates external ChromaDB and FalkorDB lifecycles before execution. Global exception handlers intercept error streams, dynamically selecting robust fallbacks (e.g. vector-only or BM25 searches) if indexes are offline. The SvelteKit layout integrates active keyboard accessibility mappings and prefers-reduced-motion media query adaptations.

**Tech Stack:** Python 3.11+, FastAPI, SlowAPI (rate limits), Gzip compression, SvelteKit, Axe-core, Playwright

---

## Scope Note

This represents the final stabilization phase of the roadmap, consolidating all modules under high availability, telemetry inspection, security hardening, and accessibility guidelines.

---

## File Structure

### Backend New/Modified Files

```
backend/
├── middleware/
│   ├── __init__.py                             # Create
│   ├── request_id.py                           # Create: Request logging correlation middleware
│   └── rate_limit.py                           # Create: API rate limiting rules
├── api/
│   ├── routes/
│   │   └── health.py                           # Modify: Add deep status checks for all dependencies
│   └── errors.py                               # Create: Global exception routing and fallback triggers
└── main.py                                     # Modify: Setup startup validations, connection pools, and Gzip
```

### Frontend New/Modified Files

```
frontend/
├── src/
│   ├── lib/
│   │   └── components/
│   │       └── error-boundary.svelte           # Create: Root accessibility error boundaries
│   └── routes/
│       └── +layout.svelte                      # Modify: Implement global accessibility & keyboard navigation
```

---

## Group A: Backend Production Infrastructure

### Task 1: Structured JSON Logging & Request ID Middleware

**Files:**
- Create: `backend/middleware/request_id.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Write Request ID & Latency logger**

Create `backend/middleware/request_id.py` injecting correlation tags:

```python
# backend/middleware/request_id.py
import time
import uuid
import json
import sys
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start_time = time.time()
        
        # Attach request_id to request state
        request.state.request_id = request_id
        
        response = await call_next(request)
        
        duration = time.time() - start_time
        log_payload = {
            "timestamp": time.time(),
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "status_code": response.status_code,
            "duration_seconds": duration
        }
        
        # Output structured JSON directly to stdout
        sys.stdout.write(json.dumps(log_payload) + "\n")
        sys.stdout.flush()
        
        response.headers["X-Request-ID"] = request_id
        return response
```

- [ ] **Step 2: Register middleware in main**

Modify `backend/main.py` adding `StructuredLoggingMiddleware` and gzip compression.

- [ ] **Step 3: Commit**

```bash
git add middleware/request_id.py main.py
git commit -m "feat: add structured JSON telemetry logging and request correlation middleware"
```

---

### Task 2: Rate Limiting & Deep Health Audits

**Files:**
- Create: `backend/middleware/rate_limit.py`
- Modify: `backend/api/routes/health.py`

- [ ] **Step 1: Implement Rate Limiting**

Create `backend/middleware/rate_limit.py` targeting `/auth/login` to restrict clients to 5 requests per minute per IP using `slowapi`.

- [ ] **Step 2: Implement Dependency Audits**

Modify `backend/api/routes/health.py` to assert connectivity to FalkorDB, ChromaDB, and SQLite:

```python
# backend/api/routes/health.py (partial diff)
import sqlite3
from db.sqlite import get_connection

@router.get("/health")
async def deep_health():
    status = {"status": "ok", "services": {}}
    
    # Audit SQLite
    try:
        conn = get_connection()
        conn.execute("SELECT 1")
        conn.close()
        status["services"]["sqlite"] = "healthy"
    except Exception:
        status["services"]["sqlite"] = "unhealthy"
        status["status"] = "error"
        
    # Add ChromaDB and FalkorDB connection probes...
    
    return status
```

- [ ] **Step 3: Commit**

```bash
git add middleware/rate_limit.py api/routes/health.py
git commit -m "feat: add deep dependency health audits and login API rate limits"
```

---

### Task 3: Fail-soft Fault Tolerances

**Files:**
- Create: `backend/api/errors.py`

- [ ] **Step 1: Write exception fallbacks**

Create `backend/api/errors.py` implementing robust, graceful degradation rules:
- **FalkorDB unreachable:** Bypass graph traversal steps silently, performing vector search only, logging warning events to system traces.
- **ChromaDB unreachable:** Fall back to graph traversal and relational attributes, returning answers with graph citations.
- **Reranker cross-encoder failure:** Revert to simple BM25 calculations instantly.

- [ ] **Step 2: Commit**

```bash
git add api/errors.py
git commit -m "feat: add fail-soft RAG exception handling and degradation fallbacks"
```

---

## Group B: Accessibility & UI Validation

### Task 4: Keyboard Navigation & Screen Reader Compliance

**Files:**
- Modify: `frontend/src/routes/+layout.svelte`
- Create: `frontend/src/lib/components/error-boundary.svelte`

- [ ] **Step 1: Global keyboard shortcuts & ARIA roles**

Modify `frontend/src/routes/+layout.svelte` to support full keyboard navigation (focus indicators, tab ordering), respect `prefers-reduced-motion` settings, and include aria-live announcements for screen readers.

- [ ] **Step 2: Root error boundary**

Create `frontend/src/lib/components/error-boundary.svelte` displaying graceful offline alerts and interactive recovery guidelines.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/
git commit -m "feat: implement comprehensive WCAG AA accessibility, theme validations, and error boundaries"
```

---

## Group C: Final Regression

### Task 5: Axiomatic Verification Suite

**Files:**
- Create: `frontend/tests/e2e/production.spec.ts`

- [ ] **Step 1: Write production smoke spec**

Create `frontend/tests/e2e/production.spec.ts` running an Axe-core accessibility scan across the UI and asserting high contrast rendering compliance.

- [ ] **Step 2: Execute global test script**

Run: `cd backend && make test && cd ../frontend && npx playwright test`
Expected: 100% pass on all unit, integration, and E2E regression suits.

- [ ] **Step 3: Commit**

```bash
git add frontend/tests/e2e/production.spec.ts
git commit -m "test: add Axe-core accessibility scans and complete E2E production regression"
```
