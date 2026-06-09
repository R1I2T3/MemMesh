# Task 18: Error Handling, Logging, Health Checks & ErrorBoundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement structured logging, global exception handling, an all-service health check endpoint in FastAPI, and a React ErrorBoundary to prevent screen blanking on frontend component crashes.

**Architecture:** A custom Python logging configuration format is applied globally. A FastAPI global exception handler catches unhandled exceptions, returning standard JSON error responses. The `/api/health` endpoint checks all database dependencies (MySQL, Redis, Weaviate, Neo4j) synchronously. In React, a custom `ErrorBoundary` component wraps the root route to intercept component tree errors and display a recovery UI.

**Tech Stack:** FastAPI, Python logging, React (TypeScript), Tailwind CSS

---

### Task 1: Structured Logging

**Files:**
- Create: `backend/middleware/logging_config.py`

- [ ] **Step 1: Write logging configuration module**
  Create `backend/middleware/logging_config.py` with standard formatter outputting to `sys.stdout` and logger quiet levels.
  ```python
  import logging
  import sys

  def setup_logging(level: str = "INFO"):
      formatter = logging.Formatter(
          fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
          datefmt="%Y-%m-%d %Y %H:%M:%S",
      )
      
      root_logger = logging.getLogger()
      for handler in list(root_logger.handlers):
          root_logger.removeHandler(handler)
          
      handler = logging.StreamHandler(sys.stdout)
      handler.setFormatter(formatter)
      root_logger.addHandler(handler)
      root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
      
      # Quiet noisy libraries
      noisy_loggers = ["neo4j", "weaviate", "urllib3", "uvicorn", "uvicorn.access", "uvicorn.error"]
      for logger_name in noisy_loggers:
          logging.getLogger(logger_name).setLevel(logging.WARNING)
  ```

- [ ] **Step 2: Commit**
  ```bash
  git add backend/middleware/logging_config.py
  git commit -m "feat: implement structured logging setup"
  ```

---

### Task 2: Global Exception Handler

**Files:**
- Create: `backend/middleware/error_handler.py`

- [ ] **Step 1: Create the global and HTTP exception handlers**
  Create `backend/middleware/error_handler.py`.
  ```python
  import logging
  from fastapi import Request
  from fastapi.responses import JSONResponse
  from fastapi.exceptions import RequestValidationError, HTTPException

  logger = logging.getLogger(__name__)

  async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
      logger.error(f"Unhandled exception occurred for {request.method} {request.url.path}: {exc}", exc_info=True)
      return JSONResponse(status_code=500, content={"detail": "Internal server error"})

  async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
      logger.warning(f"HTTPException for {request.method} {request.url.path}: {exc.detail}")
      return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

  async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
      logger.warning(f"Validation error for {request.method} {request.url.path}: {exc.errors()}")
      return JSONResponse(status_code=422, content={"detail": exc.errors()})
  ```

- [ ] **Step 2: Commit**
  ```bash
  git add backend/middleware/error_handler.py
  git commit -m "feat: implement global exception handlers"
  ```

---

### Task 3: Lifespan and Routing Modifications in FastAPI

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/db/neo4j.py`

- [ ] **Step 1: Update Neo4jManager to track global reference**
  Modify `backend/db/neo4j.py` to store a reference to the global `_neo4j_mgr` when instantiated.
  ```python
  _neo4j_mgr = None
  ```
  And inside `Neo4jManager.__init__`:
  ```python
  global _neo4j_mgr
  _neo4j_mgr = self
  ```

- [ ] **Step 2: Modify backend/main.py**
  Incorporate logging setup on startup, exception handlers registration, shutdown connection closing (Weaviate, Neo4j, Redis), and the full `/api/health` multi-service check.
  ```python
  # Register setup_logging at main file entry
  from backend.middleware.logging_config import setup_logging
  setup_logging()
  
  # Register exception handlers
  from backend.middleware.error_handler import (
      global_exception_handler,
      http_exception_handler,
      validation_exception_handler
  )
  from fastapi.exceptions import HTTPException, RequestValidationError
  
  app.add_exception_handler(Exception, global_exception_handler)
  app.add_exception_handler(HTTPException, http_exception_handler)
  app.add_exception_handler(RequestValidationError, validation_exception_handler)
  ```

- [ ] **Step 3: Commit**
  ```bash
  git add backend/main.py backend/db/neo4j.py
  git commit -m "feat: update main lifespan, exception handlers registration, and health check"
  ```

---

### Task 4: Backend Unit Tests

**Files:**
- Create: `backend/tests/test_error_handling.py`

- [ ] **Step 1: Write unit tests**
  Create `backend/tests/test_error_handling.py`.
  - Test unhandled exceptions (500 JSONResponse instead of tracebacks).
  - Test health checks under successful and failing states (mocking service clients).

- [ ] **Step 2: Commit**
  ```bash
  git add backend/tests/test_error_handling.py
  git commit -m "test: add error handling and health check unit tests"
  ```

---

### Task 5: React ErrorBoundary

**Files:**
- Create: `frontend/src/components/ErrorBoundary.tsx`

- [ ] **Step 1: Create React ErrorBoundary component**
  Write class component that catches rendering errors and shows a recovery UI.
  
- [ ] **Step 2: Wrap routing root in React**
  Modify `frontend/src/routes/__root.tsx` to wrap the Outlet inside the `<ErrorBoundary>` component.

- [ ] **Step 3: Commit**
  ```bash
  git add frontend/src/components/ErrorBoundary.tsx frontend/src/routes/__root.tsx
  git commit -m "feat: implement react ErrorBoundary and wrap root route"
  ```
