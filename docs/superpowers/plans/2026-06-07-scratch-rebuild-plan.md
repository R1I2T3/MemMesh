# MemMesh Rebuild: Step-by-Step Implementation Plan (v2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the entire MemMesh platform from scratch utilizing React + Tailwind + TanStack Start, LangChain + LangGraph, MySQL, Weaviate (multi-tenancy), Neo4j (multi-database isolation), IBM Docling, Celery + Redis, Guardrails AI, DeepEval, and self-hosted Arize Phoenix tracing.

**Architecture:** A stateless FastAPI web application exposes REST and SSE endpoints, offloading long-running parser and crawlers to decoupled Celery workers via Redis. Stateful querying runs on LangGraph loops with corrective web fallback routing. Data isolation is maintained physically at the database level (Neo4j tenant tagging and Weaviate tenant shards).

**Tech Stack:** Python 3.11/3.12, FastAPI, Celery, Redis, MySQL, Weaviate (v4 client), Neo4j, Docling, LangGraph, Guardrails, DeepEval, Arize Phoenix, React, Vite, Tailwind CSS, Playwright, Vitest (frontend unit testing), Pytest (backend unit testing).

---

## System Requirements & Prerequisites

Before starting the implementation, ensure the following local environment dependencies are installed:

1. **Operating System**: Linux (Ubuntu 22.04 LTS or compatible)
2. **Python Environment Manager**: `uv` (Fast Python package installer and resolver)
   * Install: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   * Verify: `uv --version`
3. **Container Engine**: Docker and Docker Compose (v2.0+)
   * Verify: `docker --version` and `docker compose version`
4. **Node.js Environment**: Node.js (v18.x or v20.x) and `npm`
   * Verify: `node --version` and `npm --version`
5. **Required Environment Variables** (configured in a root `.env` file):
   ```bash
   # LLM API Config
   GEMINI_API_KEY=your_gemini_api_key_here

   # Databases
   MYSQL_ROOT_PASSWORD=root_password_change_me
   MYSQL_DATABASE=memmesh
   MYSQL_USER=app_user
   MYSQL_PASSWORD=user_password_change_me
   MYSQL_HOST=127.0.0.1
   MYSQL_PORT=3306

   WEAVIATE_HOST=127.0.0.1
   WEAVIATE_PORT=8080
   WEAVIATE_GRPC_PORT=50051

   NEO4J_URI=bolt://127.0.0.1:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=neo4j_password_change_me

   REDIS_URL=redis://127.0.0.1:6379/0

   # Observability (Arize Phoenix Self-Hosted)
   PHOENIX_COLLECTOR_ENDPOINT=http://127.0.0.1:6006

   # Authentication
   JWT_SECRET=super_secret_jwt_key_change_me
   JWT_ALGORITHM=HS256
   JWT_EXPIRY_MINUTES=60

   # Initial Super Admin Account Setup
   SUPERADMIN_EMAIL=superadmin@memmesh.com
   SUPERADMIN_PASSWORD=admin_secret_password_change_me

   # API
   CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
   MAX_UPLOAD_SIZE_MB=50

   # Frontend
   VITE_API_URL=http://127.0.0.1:8000
   ```

---

## Phase 1: Infrastructure Foundation

### Task 1: Docker Compose & Project Scaffolding

**Files:**
* Create: `docker-compose.yml`
* Create: `backend/pyproject.toml` (via `uv`)
* Create: `frontend/package.json` (via Vite)
* Create: `playwright.config.ts`
* Create: `.gitignore`

- [ ] **Step 1: Write root `docker-compose.yml`**
  ```yaml
  services:
    weaviate:
      image: cr.weaviate.io/semitechnologies/weaviate:1.28.4
      container_name: weaviate_db
      ports:
        - "8080:8080"
        - "50051:50051"
      environment:
        QUERY_DEFAULTS_LIMIT: 25
        AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED: "true"
        PERSISTENCE_DATA_PATH: "/var/lib/weaviate"
        DEFAULT_VECTORIZER_MODULE: "none"
        CLUSTER_HOSTNAME: "node1"
      volumes:
        - weaviate_data:/var/lib/weaviate
      healthcheck:
        test: ["CMD", "wget", "--spider", "-q", "http://localhost:8080/v1/.well-known/ready"]
        interval: 10s
        timeout: 5s
        retries: 5

    mysql:
      image: mysql:8.0
      container_name: mysql_db
      ports:
        - "3306:3306"
      environment:
        MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
        MYSQL_DATABASE: ${MYSQL_DATABASE}
        MYSQL_USER: ${MYSQL_USER}
        MYSQL_PASSWORD: ${MYSQL_PASSWORD}
      volumes:
        - mysql_data:/var/lib/mysql
      healthcheck:
        test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
        interval: 10s
        timeout: 5s
        retries: 5

    neo4j:
      image: neo4j:5.18
      container_name: neo4j_db
      ports:
        - "7474:7474"
        - "7687:7687"
      environment:
        NEO4J_AUTH: ${NEO4J_USER}/${NEO4J_PASSWORD}
        NEO4J_PLUGINS: '["apoc"]'
      volumes:
        - neo4j_data:/data
        - neo4j_logs:/logs
      healthcheck:
        test: ["CMD", "cypher-shell", "-u", "neo4j", "-p", "${NEO4J_PASSWORD}", "RETURN 1"]
        interval: 10s
        timeout: 5s
        retries: 5

    redis:
      image: redis:7.0-alpine
      container_name: redis_broker
      ports:
        - "6379:6379"
      volumes:
        - redis_data:/data
      healthcheck:
        test: ["CMD", "redis-cli", "ping"]
        interval: 10s
        timeout: 5s
        retries: 5

    phoenix:
      image: arizephoenix/phoenix:latest
      container_name: phoenix_collector
      ports:
        - "6006:6006"
        - "4317:4317"
      restart: always

  volumes:
    weaviate_data:
    mysql_data:
    neo4j_data:
    neo4j_logs:
    redis_data:
  ```
  > **v2 fixes:** Removed deprecated `version` key. Added healthchecks for all services. Used env var interpolation instead of hardcoded passwords. Updated Weaviate to v1.28.4 (compatible with v4 Python client).

- [ ] **Step 2: Scaffold backend with `uv`**
  ```bash
  uv init --app backend
  cd backend
  uv add fastapi uvicorn[standard] sqlalchemy[asyncio] pymysql cryptography pydantic-settings bcrypt python-jose[cryptography] python-multipart alembic
  uv add celery redis
  uv add weaviate-client  # v4 client
  uv add neo4j
  uv add langgraph langchain-core langchain-community langchain-google-genai
  uv add guardrails-ai deepeval docling
  uv add arize-phoenix openinference-instrumentation-langchain
  uv add --dev pytest httpx pytest-asyncio
  cd ..
  ```

- [ ] **Step 3: Scaffold frontend with Vite + React**
  ```bash
  npx -y create-vite@latest frontend --template react-ts
  cd frontend
  npm install @tanstack/react-router @tanstack/react-query lucide-react clsx tailwind-merge @microsoft/fetch-event-source
  npm install -D tailwindcss postcss autoprefixer vitest @testing-library/react @testing-library/jest-dom jsdom
  npx tailwindcss init -p
  cd ..
  ```
  > **v2 fix:** Added `@microsoft/fetch-event-source` (native EventSource can't send auth headers). Added testing-library for proper component tests.

- [ ] **Step 4: Setup Playwright**
  ```bash
  npm install -D @playwright/test
  npx playwright install chromium
  ```
  Create `playwright.config.ts`:
  ```typescript
  import { defineConfig, devices } from '@playwright/test';

  export default defineConfig({
    testDir: './tests/e2e',
    timeout: 30000,
    retries: process.env.CI ? 2 : 0,
    use: { baseURL: 'http://localhost:5173' },
    projects: [
      { name: 'setup', testMatch: /.*\.setup\.ts/ },
      {
        name: 'chromium',
        use: {
          ...devices['Desktop Chrome'],
          storageState: '.auth/superadmin.json',
        },
        dependencies: ['setup'],
      },
    ],
    webServer: [
      {
        command: 'npm run dev --prefix frontend',
        url: 'http://localhost:5173',
        reuseExistingServer: !process.env.CI,
      },
      {
        command: 'uv run --project backend uvicorn backend.main:app --host 127.0.0.1 --port 8000',
        url: 'http://127.0.0.1:8000/api/health',
        reuseExistingServer: !process.env.CI,
      }
    ]
  });
  ```

- [ ] **Step 5: Create `__init__.py` files for all backend packages**
  ```bash
  touch backend/__init__.py
  mkdir -p backend/db backend/auth backend/api/routes backend/agents backend/ingestion backend/tasks backend/tests backend/middleware
  touch backend/db/__init__.py backend/auth/__init__.py backend/api/__init__.py backend/api/routes/__init__.py
  touch backend/agents/__init__.py backend/ingestion/__init__.py backend/tasks/__init__.py backend/tests/__init__.py backend/middleware/__init__.py
  ```
  > **v2 fix:** Original plan never created `__init__.py` files — Python imports would fail.

- [ ] **Step 6: Commit**
  ```bash
  git add . && git commit -m "chore(scaffold): project structure, docker-compose, and dev tooling"
  ```

---

### Task 2: Backend Config & Database Connection

**Files:**
* Create: `backend/config.py`
* Create: `backend/db/mysql.py`
* Create: `backend/main.py`
* Create: `backend/tests/test_mysql_conn.py`
* Create: `frontend/src/lib/api.ts`
* Create: `frontend/src/utils/health.ts`
* Create: `frontend/src/utils/health.test.ts`
* Create: `tests/e2e/health.spec.ts`

- [ ] **Step 1: Write tests**
  * Backend test `backend/tests/test_mysql_conn.py`:
    ```python
    import pytest
    from sqlalchemy import text
    from backend.db.mysql import engine

    def test_db_ping():
        with engine.connect() as conn:
            val = conn.execute(text("SELECT 1")).scalar()
            assert val == 1
    ```
  * Frontend test `frontend/src/utils/health.test.ts`:
    ```typescript
    import { expect, test } from 'vitest';
    import { formatHealthStatus } from './health';

    test('formats all health statuses correctly', () => {
      expect(formatHealthStatus({ mysql: 'ok', weaviate: 'ok', neo4j: 'ok', redis: 'ok' }))
        .toEqual({ overall: 'operational', services: 4, healthy: 4 });

      expect(formatHealthStatus({ mysql: 'ok', weaviate: 'error', neo4j: 'ok', redis: 'ok' }))
        .toEqual({ overall: 'degraded', services: 4, healthy: 3 });
    });
    ```
  * E2E test `tests/e2e/health.spec.ts`:
    ```typescript
    import { test, expect } from '@playwright/test';

    test('should display all service statuses on login page', async ({ page }) => {
      await page.goto('http://localhost:5173/');
      const statusEl = page.locator('#system-status');
      await expect(statusEl).toBeVisible({ timeout: 10000 });
      await expect(statusEl).toContainText('operational');
    });
    ```

- [ ] **Step 2: Run tests to verify failure**
  ```bash
  uv run --project backend pytest backend/tests/test_mysql_conn.py  # -> FAIL
  cd frontend && npx vitest run  # -> FAIL
  ```

- [ ] **Step 3: Implement config**
  Create `backend/config.py`:
  ```python
  from pydantic_settings import BaseSettings, SettingsConfigDict

  class Settings(BaseSettings):
      MYSQL_HOST: str = "127.0.0.1"
      MYSQL_PORT: int = 3306
      MYSQL_USER: str = "app_user"
      MYSQL_PASSWORD: str = "user_password_change_me"
      MYSQL_DATABASE: str = "memmesh"

      WEAVIATE_HOST: str = "127.0.0.1"
      WEAVIATE_PORT: int = 8080
      WEAVIATE_GRPC_PORT: int = 50051

      NEO4J_URI: str = "bolt://127.0.0.1:7687"
      NEO4J_USER: str = "neo4j"
      NEO4J_PASSWORD: str = "neo4j_password_change_me"

      REDIS_URL: str = "redis://127.0.0.1:6379/0"

      PHOENIX_COLLECTOR_ENDPOINT: str = "http://127.0.0.1:6006"

      SUPERADMIN_EMAIL: str = "superadmin@memmesh.com"
      SUPERADMIN_PASSWORD: str = "admin_secret_password_change_me"

      JWT_SECRET: str = "super_secret_jwt_key_change_me"
      JWT_ALGORITHM: str = "HS256"
      JWT_EXPIRY_MINUTES: int = 60

      CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
      MAX_UPLOAD_SIZE_MB: int = 50

      model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

      @property
      def cors_origin_list(self) -> list[str]:
          return [o.strip() for o in self.CORS_ORIGINS.split(",")]

      @property
      def max_upload_bytes(self) -> int:
          return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

  settings = Settings()
  ```
  > **v2 fixes:** Added `JWT_EXPIRY_MINUTES`, `CORS_ORIGINS` (explicit list instead of wildcard), `MAX_UPLOAD_SIZE_MB`, Weaviate gRPC port, and all missing DB configs.

- [ ] **Step 4: Implement DB connection with production pool settings**
  Create `backend/db/mysql.py`:
  ```python
  from sqlalchemy import create_engine
  from sqlalchemy.orm import DeclarativeBase, sessionmaker
  from backend.config import settings

  DATABASE_URL = (
      f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
      f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
  )

  engine = create_engine(
      DATABASE_URL,
      pool_pre_ping=True,
      pool_size=20,
      max_overflow=10,
      pool_recycle=3600,
  )

  SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

  class Base(DeclarativeBase):
      pass

  def get_db():
      db = SessionLocal()
      try:
          yield db
      finally:
          db.close()
  ```
  > **v2 fixes:** Uses `DeclarativeBase` (modern SQLAlchemy 2.0) instead of deprecated `declarative_base()`. Added `pool_size`, `max_overflow`, and `pool_recycle` for production.

- [ ] **Step 5: Implement health endpoint checking ALL services**
  Create `backend/main.py`:
  ```python
  import logging
  from contextlib import asynccontextmanager
  from fastapi import FastAPI, Depends
  from fastapi.middleware.cors import CORSMiddleware
  from sqlalchemy.orm import Session
  from sqlalchemy import text
  from backend.db.mysql import get_db
  from backend.config import settings

  logger = logging.getLogger(__name__)

  @asynccontextmanager
  async def lifespan(app: FastAPI):
      logger.info("MemMesh starting up...")
      yield
      logger.info("MemMesh shutting down...")

  app = FastAPI(title="MemMesh API", lifespan=lifespan)

  app.add_middleware(
      CORSMiddleware,
      allow_origins=settings.cors_origin_list,
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )

  @app.get("/api/health")
  def health(db: Session = Depends(get_db)):
      statuses = {}
      try:
          db.execute(text("SELECT 1"))
          statuses["mysql"] = "ok"
      except Exception as e:
          logger.error(f"MySQL health check failed: {e}")
          statuses["mysql"] = "error"
      # Weaviate, Neo4j, Redis health checks added in Task 18
      return {"status": "ok" if all(v == "ok" for v in statuses.values()) else "degraded", "services": statuses}
  ```
  > **v2 fixes:** Uses `lifespan` context manager (not deprecated `on_event`). CORS uses explicit origin list from config. Added structured logging.

- [ ] **Step 6: Create frontend API helper with configurable base URL**
  Create `frontend/src/lib/api.ts`:
  ```typescript
  export const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

  export async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
    const token = localStorage.getItem('token');
    const headers: Record<string, string> = {
      ...((options.headers as Record<string, string>) || {}),
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    if (!(options.body instanceof FormData)) {
      headers['Content-Type'] = headers['Content-Type'] || 'application/json';
    }
    return fetch(`${API_BASE}${path}`, { ...options, headers });
  }
  ```
  > **v2 fix:** Centralized API base URL (was hardcoded `http://127.0.0.1:8000` in every component). Auto-attaches auth token.

  Create `frontend/src/utils/health.ts`:
  ```typescript
  type ServiceStatuses = Record<string, string>;

  export function formatHealthStatus(services: ServiceStatuses) {
    const total = Object.keys(services).length;
    const healthy = Object.values(services).filter(s => s === 'ok').length;
    return { overall: healthy === total ? 'operational' : 'degraded', services: total, healthy };
  }
  ```

- [ ] **Step 7: Run tests to verify they pass**
  Ensure Docker containers are running: `docker compose up -d`
  ```bash
  uv run --project backend pytest backend/tests/test_mysql_conn.py
  cd frontend && npx vitest run
  ```
  Expected: PASS.

- [ ] **Step 8: Commit**
  ```bash
  git add . && git commit -m "feat(core): backend config, MySQL connection pool, health endpoint, and API helper"
  ```

---

### Task 3: SQLAlchemy Models with Indexes & Alembic Migrations

**Files:**
* Create: `backend/models.py`
* Create: `backend/alembic.ini` (via `alembic init`)
* Create: `backend/migrations/` directory
* Create: `backend/tests/test_models.py`

- [ ] **Step 1: Write tests**
  Create `backend/tests/test_models.py`:
  ```python
  import uuid
  from sqlalchemy import create_engine
  from sqlalchemy.orm import sessionmaker
  from backend.db.mysql import Base
  from backend.models import User, Team, TeamMember, ParentDocument, Message, UserFeedback

  def test_models_create_all_tables():
      """Verify all models produce valid DDL and tables are created."""
      engine = create_engine("sqlite:///:memory:")
      Base.metadata.create_all(bind=engine)
      Session = sessionmaker(bind=engine)
      with Session() as session:
          u = User(user_id=str(uuid.uuid4()), email="test@test.com", password_hash="hash", global_role="user")
          session.add(u)
          session.commit()
          result = session.query(User).filter_by(email="test@test.com").first()
          assert result is not None
          assert result.global_role == "user"

  def test_message_tree_structure():
      """Verify parent-child message relationships work."""
      engine = create_engine("sqlite:///:memory:")
      Base.metadata.create_all(bind=engine)
      Session = sessionmaker(bind=engine)
      with Session() as session:
          parent_id = str(uuid.uuid4())
          child_id = str(uuid.uuid4())
          session.add(Message(message_id=parent_id, session_id="s1", parent_message_id=None, role="user", content="Hello"))
          session.add(Message(message_id=child_id, session_id="s1", parent_message_id=parent_id, role="assistant", content="Hi"))
          session.commit()
          child = session.query(Message).filter_by(message_id=child_id).first()
          assert child.parent_message_id == parent_id
  ```
  > **v2 fix:** Tests use in-memory SQLite for isolation — no running MySQL needed for model tests.

- [ ] **Step 2: Run tests to verify failure**
  ```bash
  uv run --project backend pytest backend/tests/test_models.py  # -> FAIL
  ```

- [ ] **Step 3: Implement models with proper indexes and column types**
  Create `backend/models.py`:
  ```python
  from sqlalchemy import Column, String, ForeignKey, Text, Integer, Index, DateTime, func
  from backend.db.mysql import Base

  class User(Base):
      __tablename__ = "users"
      user_id = Column(String(36), primary_key=True)
      email = Column(String(255), unique=True, nullable=False, index=True)
      password_hash = Column(String(255), nullable=False)
      global_role = Column(String(20), default="user", index=True)
      created_at = Column(DateTime, server_default=func.now())

  class Team(Base):
      __tablename__ = "teams"
      team_id = Column(String(36), primary_key=True)
      name = Column(String(100), unique=True, nullable=False)
      created_at = Column(DateTime, server_default=func.now())

  class TeamMember(Base):
      __tablename__ = "team_members"
      team_id = Column(String(36), ForeignKey("teams.team_id", ondelete="CASCADE"), primary_key=True)
      user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
      role = Column(String(20), default="member")

  class ParentDocument(Base):
      __tablename__ = "parent_documents"
      parent_id = Column(String(36), primary_key=True)
      filename = Column(String(255), nullable=False)
      content = Column(Text(4294967295), nullable=False)  # LONGTEXT for large PDFs
      team_id = Column(String(36), ForeignKey("teams.team_id"), nullable=False, index=True)
      created_at = Column(DateTime, server_default=func.now())

  class Message(Base):
      __tablename__ = "messages"
      message_id = Column(String(36), primary_key=True)
      session_id = Column(String(36), nullable=False, index=True)
      parent_message_id = Column(String(36), ForeignKey("messages.message_id"), nullable=True, index=True)
      role = Column(String(20), nullable=False)
      content = Column(Text, nullable=False)
      created_at = Column(DateTime, server_default=func.now())
      __table_args__ = (Index('ix_messages_session_parent', 'session_id', 'parent_message_id'),)

  class UserFeedback(Base):
      __tablename__ = "user_feedbacks"
      feedback_id = Column(String(36), primary_key=True)
      query = Column(Text, nullable=False)
      response = Column(Text, nullable=False)
      rating = Column(Integer, nullable=False, index=True)  # 1 = Up, -1 = Down
      trace_id = Column(String(100), nullable=False, index=True)
      created_at = Column(DateTime, server_default=func.now())
  ```
  > **v2 fixes:**
  > - `ParentDocument.content` uses `Text(4294967295)` = MySQL LONGTEXT (was `Text` = 64KB max)
  > - Added `index=True` on frequently-queried columns (`session_id`, `parent_message_id`, `team_id`, `rating`, `email`)
  > - Added composite index on `(session_id, parent_message_id)` for chat tree queries
  > - Added `created_at` timestamps on all tables
  > - Added `ondelete="CASCADE"` on foreign keys

- [ ] **Step 4: Initialize Alembic for migrations**
  ```bash
  cd backend
  uv run alembic init migrations
  ```
  Update `backend/migrations/env.py` to import `Base.metadata` and `settings.DATABASE_URL`.
  ```bash
  uv run alembic revision --autogenerate -m "initial models"
  uv run alembic upgrade head
  ```
  > **v2 fix:** Original plan used `create_all()` which is destructive on schema changes. Alembic provides safe, incremental migrations.

- [ ] **Step 5: Run tests to verify they pass**
  ```bash
  uv run --project backend pytest backend/tests/test_models.py
  ```
  Expected: PASS.

- [ ] **Step 6: Commit**
  ```bash
  git add . && git commit -m "feat(models): SQLAlchemy 2.0 ORM with indexes, LONGTEXT, and Alembic migrations"
  ```

---

### Task 4: Frontend TanStack Router Setup

**Files:**
* Create: `frontend/src/router.tsx`
* Create: `frontend/src/routes/__root.tsx`
* Create: `frontend/src/routes/index.tsx`
* Create: `frontend/src/routes/_dashboard.tsx`
* Modify: `frontend/src/main.tsx`

> **CRITICAL v2 FIX:** The original plan had self-referential `getParentRoute: () => Route.getParentRoute()` in every route — this causes infinite recursion. Each route must import its actual parent.

- [ ] **Step 1: Create route tree**
  Create `frontend/src/routes/__root.tsx`:
  ```tsx
  import { createRootRoute, Outlet } from '@tanstack/react-router';

  export const Route = createRootRoute({
    component: () => <Outlet />,
  });
  ```

  Create `frontend/src/routes/index.tsx`:
  ```tsx
  import { createRoute } from '@tanstack/react-router';
  import { Route as rootRoute } from './__root';

  export const Route = createRoute({
    getParentRoute: () => rootRoute,  // ✅ FIXED: imports actual parent
    path: '/',
    component: LoginHome,
  });

  function LoginHome() {
    return (
      <div style={{ padding: '2rem', fontFamily: 'sans-serif' }}>
        <h1>MemMesh</h1>
        <p id="system-status">Loading...</p>
        <h2>Login</h2>
        {/* Login form implemented in Task 6 */}
      </div>
    );
  }
  ```

  Create `frontend/src/routes/_dashboard.tsx`:
  ```tsx
  import { createRoute, Outlet } from '@tanstack/react-router';
  import { Route as rootRoute } from './__root';

  export const Route = createRoute({
    getParentRoute: () => rootRoute,  // ✅ FIXED: imports actual parent
    path: '/dashboard',
    component: DashboardLayout,
  });

  function DashboardLayout() {
    return (
      <div style={{ padding: '2rem' }}>
        <h1 id="dashboard-header">Dashboard</h1>
        <Outlet />
      </div>
    );
  }
  ```

- [ ] **Step 2: Create router and update entrypoint**
  Create `frontend/src/router.tsx`:
  ```tsx
  import { createRouter } from '@tanstack/react-router';
  import { Route as rootRoute } from './routes/__root';
  import { Route as indexRoute } from './routes/index';
  import { Route as dashboardLayoutRoute } from './routes/_dashboard';

  const routeTree = rootRoute.addChildren([indexRoute, dashboardLayoutRoute]);

  export const router = createRouter({ routeTree });

  declare module '@tanstack/react-router' {
    interface Register {
      router: typeof router;
    }
  }
  ```
  > **v2 fix:** Added type registration for TanStack Router.

  Update `frontend/src/main.tsx`:
  ```tsx
  import React from 'react';
  import ReactDOM from 'react-dom/client';
  import { RouterProvider } from '@tanstack/react-router';
  import { router } from './router';

  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <RouterProvider router={router} />
    </React.StrictMode>
  );
  ```

- [ ] **Step 3: Verify frontend boots**
  ```bash
  cd frontend && npm run dev
  ```
  Navigate to `http://localhost:5173/` — should render without errors.

- [ ] **Step 4: Commit**
  ```bash
  git add . && git commit -m "feat(router): TanStack Router with correct parent references and type registration"
  ```

---

## Phase 2: Authentication & Authorization

### Task 5: Password Security, JWT & Auth Middleware

**Files:**
* Create: `backend/auth/passwords.py`
* Create: `backend/auth/jwt.py`
* Create: `backend/auth/middleware.py`
* Create: `backend/tests/test_auth.py`
* Create: `frontend/src/utils/auth.ts`
* Create: `frontend/src/utils/auth.test.ts`

- [ ] **Step 1: Write tests**
  Create `backend/tests/test_auth.py`:
  ```python
  import pytest
  from backend.auth.passwords import hash_password, verify_password
  from backend.auth.jwt import create_access_token, decode_access_token

  def test_password_hash_and_verify():
      hashed = hash_password("my_secret_123")
      assert hashed != "my_secret_123"
      assert verify_password("my_secret_123", hashed) is True
      assert verify_password("wrong_password", hashed) is False

  def test_jwt_create_and_decode():
      token = create_access_token({"sub": "user-123", "role": "superadmin"})
      payload = decode_access_token(token)
      assert payload["sub"] == "user-123"
      assert payload["role"] == "superadmin"
      assert "exp" in payload

  def test_jwt_invalid_token_raises():
      with pytest.raises(ValueError):
          decode_access_token("invalid.token.here")
  ```

  Create `frontend/src/utils/auth.test.ts`:
  ```typescript
  import { expect, test } from 'vitest';
  import { parseTokenPayload, isTokenExpired } from './auth';

  test('decodes JWT payload correctly', () => {
    // {"sub":"123","role":"superadmin","exp":9999999999}
    const mock = 'h.eyJzdWIiOiIxMjMiLCJyb2xlIjoic3VwZXJhZG1pbiIsImV4cCI6OTk5OTk5OTk5OX0.s';
    const payload = parseTokenPayload(mock);
    expect(payload?.role).toBe('superadmin');
    expect(payload?.sub).toBe('123');
  });

  test('returns null for invalid tokens', () => {
    expect(parseTokenPayload('not-a-jwt')).toBeNull();
    expect(parseTokenPayload('')).toBeNull();
  });

  test('detects expired tokens', () => {
    const expired = 'h.eyJzdWIiOiIxIiwiZXhwIjoxfQ.s';
    expect(isTokenExpired(expired)).toBe(true);
  });
  ```

- [ ] **Step 2: Run tests to verify failure**
  ```bash
  uv run --project backend pytest backend/tests/test_auth.py  # -> FAIL
  cd frontend && npx vitest run  # -> FAIL
  ```

- [ ] **Step 3: Implement password hashing**
  Create `backend/auth/passwords.py`:
  ```python
  import bcrypt

  def hash_password(password: str) -> str:
      return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

  def verify_password(password: str, hashed: str) -> bool:
      return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
  ```

- [ ] **Step 4: Implement JWT with configurable expiry**
  Create `backend/auth/jwt.py`:
  ```python
  from datetime import datetime, timezone, timedelta
  from jose import jwt, JWTError
  from backend.config import settings

  def create_access_token(data: dict) -> str:
      to_encode = data.copy()
      expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRY_MINUTES)
      to_encode.update({"exp": expire})
      return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

  def decode_access_token(token: str) -> dict:
      try:
          return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
      except JWTError:
          raise ValueError("Invalid or expired token")
  ```

- [ ] **Step 5: Implement auth middleware**
  Create `backend/auth/middleware.py`:
  ```python
  import logging
  from fastapi import Header, HTTPException, Depends
  from backend.auth.jwt import decode_access_token

  logger = logging.getLogger(__name__)

  def get_current_user(authorization: str = Header(...)):
      if not authorization.startswith("Bearer "):
          raise HTTPException(status_code=401, detail="Invalid authorization header")
      try:
          token = authorization.split(" ", 1)[1]
          return decode_access_token(token)
      except ValueError:
          raise HTTPException(status_code=401, detail="Invalid or expired token")

  def require_global_role(role: str):
      def dep(payload: dict = Depends(get_current_user)):
          if payload.get("role") != role:
              logger.warning(f"Forbidden: user {payload.get('sub')} tried role={role}")
              raise HTTPException(status_code=403, detail="Insufficient permissions")
          return payload
      return dep
  ```

- [ ] **Step 6: Implement frontend auth utilities**
  Create `frontend/src/utils/auth.ts`:
  ```typescript
  interface TokenPayload { sub: string; role: string; exp: number; }

  export function parseTokenPayload(token: string): TokenPayload | null {
    try {
      if (!token || token.split('.').length !== 3) return null;
      const base64Url = token.split('.')[1];
      const json = atob(base64Url.replace(/-/g, '+').replace(/_/g, '/'));
      return JSON.parse(json);
    } catch { return null; }
  }

  export function isTokenExpired(token: string): boolean {
    const payload = parseTokenPayload(token);
    if (!payload?.exp) return true;
    return Date.now() / 1000 > payload.exp;
  }

  export function getStoredAuth(): { token: string; role: string } | null {
    const token = localStorage.getItem('token');
    if (!token || isTokenExpired(token)) {
      localStorage.removeItem('token');
      localStorage.removeItem('role');
      return null;
    }
    return { token, role: localStorage.getItem('role') || 'user' };
  }
  ```

- [ ] **Step 7: Run tests to verify they pass**
  ```bash
  uv run --project backend pytest backend/tests/test_auth.py
  cd frontend && npx vitest run
  ```
  Expected: PASS.

- [ ] **Step 8: Commit**
  ```bash
  git add . && git commit -m "feat(auth): password hashing, JWT tokens with expiry, and auth middleware"
  ```

---

### Task 6: Login API, Superadmin Seeding & Route Guards

**Files:**
* Create: `backend/api/routes/auth.py`
* Modify: `backend/main.py` (lifespan: seed superadmin, register router)
* Modify: `frontend/src/routes/index.tsx` (login form)
* Modify: `frontend/src/routes/_dashboard.tsx` (route guard)
* Create: `tests/e2e/auth.setup.ts`
* Create: `tests/e2e/auth.spec.ts`

- [ ] **Step 1: Write E2E tests**
  Create `tests/e2e/auth.setup.ts`:
  ```typescript
  import { test as setup, expect } from '@playwright/test';
  const authFile = '.auth/superadmin.json';

  setup('authenticate as superadmin', async ({ page }) => {
    await page.goto('http://localhost:5173/');
    await page.locator('#email-input').fill('superadmin@memmesh.com');
    await page.locator('#password-input').fill('admin_secret_password_change_me');
    await page.locator('#login-button').click();
    await expect(page.locator('#dashboard-header')).toBeVisible({ timeout: 10000 });
    await page.context().storageState({ path: authFile });
  });
  ```

  Create `tests/e2e/auth.spec.ts`:
  ```typescript
  import { test, expect } from '@playwright/test';

  test('authenticated user sees dashboard', async ({ page }) => {
    await page.goto('http://localhost:5173/dashboard');
    await expect(page.locator('#dashboard-header')).toBeVisible();
  });

  test('unauthenticated user is redirected to login', async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.goto('http://localhost:5173/dashboard');
    await expect(page).toHaveURL(/\/$/);
    await context.close();
  });
  ```

- [ ] **Step 2: Implement login API**
  Create `backend/api/routes/auth.py`:
  ```python
  import logging
  from fastapi import APIRouter, Depends, HTTPException
  from sqlalchemy.orm import Session
  from pydantic import BaseModel
  from backend.db.mysql import get_db
  from backend.models import User
  from backend.auth.passwords import verify_password
  from backend.auth.jwt import create_access_token

  logger = logging.getLogger(__name__)
  router = APIRouter(prefix="/api/auth", tags=["auth"])

  class LoginRequest(BaseModel):
      email: str
      password: str

  @router.post("/login")
  def login(payload: LoginRequest, db: Session = Depends(get_db)):
      user = db.query(User).filter_by(email=payload.email).first()
      if not user or not verify_password(payload.password, user.password_hash):
          logger.warning(f"Failed login attempt for {payload.email}")
          raise HTTPException(status_code=401, detail="Invalid credentials")
      token = create_access_token({"sub": user.user_id, "role": user.global_role})
      return {"token": token, "role": user.global_role}
  ```

- [ ] **Step 3: Add superadmin seeding to lifespan**
  Modify `backend/main.py` lifespan:
  ```python
  import uuid
  from backend.db.mysql import engine, Base, SessionLocal
  from backend.models import User
  from backend.auth.passwords import hash_password
  from backend.api.routes.auth import router as auth_router

  @asynccontextmanager
  async def lifespan(app: FastAPI):
      logger.info("MemMesh starting up...")
      Base.metadata.create_all(bind=engine)
      with SessionLocal() as session:
          admin = session.query(User).filter_by(email=settings.SUPERADMIN_EMAIL).first()
          if not admin:
              session.add(User(
                  user_id=str(uuid.uuid4()),
                  email=settings.SUPERADMIN_EMAIL,
                  password_hash=hash_password(settings.SUPERADMIN_PASSWORD),
                  global_role="superadmin"
              ))
              session.commit()
              logger.info("Superadmin account created")
      yield
      logger.info("MemMesh shutting down...")

  app.include_router(auth_router)
  ```

- [ ] **Step 4: Update frontend login with proper SPA navigation**
  Modify `frontend/src/routes/index.tsx`:
  ```tsx
  import { createRoute, useNavigate } from '@tanstack/react-router';
  import { Route as rootRoute } from './__root';
  import React, { useEffect, useState } from 'react';
  import { apiFetch } from '../lib/api';
  import { formatHealthStatus } from '../utils/health';

  export const Route = createRoute({
    getParentRoute: () => rootRoute,
    path: '/',
    component: LoginHome,
  });

  function LoginHome() {
    const navigate = useNavigate();
    const [status, setStatus] = useState('Checking...');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    useEffect(() => {
      apiFetch('/api/health')
        .then(res => res.json())
        .then(data => {
          const health = formatHealthStatus(data.services || {});
          setStatus(health.overall);
        })
        .catch(() => setStatus('unreachable'));
    }, []);

    const handleLogin = async (e: React.FormEvent) => {
      e.preventDefault();
      setError('');
      setLoading(true);
      try {
        const res = await apiFetch('/api/auth/login', {
          method: 'POST',
          body: JSON.stringify({ email, password }),
        });
        if (res.ok) {
          const data = await res.json();
          localStorage.setItem('token', data.token);
          localStorage.setItem('role', data.role);
          navigate({ to: '/dashboard' });  // ✅ SPA navigation, no full reload
        } else {
          setError('Invalid email or password');
        }
      } catch { setError('Network error'); }
      finally { setLoading(false); }
    };

    return (
      <div style={{ padding: '2rem', fontFamily: 'sans-serif' }}>
        <h1>MemMesh</h1>
        <p id="system-status">System: {status}</p>
        <hr />
        <h2>Login</h2>
        <form onSubmit={handleLogin}>
          <input id="email-input" value={email} onChange={e => setEmail(e.target.value)} placeholder="Email" />
          <input id="password-input" type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Password" />
          <button id="login-button" type="submit" disabled={loading}>{loading ? 'Logging in...' : 'Login'}</button>
        </form>
        {error && <p id="login-error" style={{ color: 'red' }}>{error}</p>}
      </div>
    );
  }
  ```
  > **v2 fixes:** Uses `useNavigate()` instead of `window.location.href`. Added loading state, error display, form submission.

- [ ] **Step 5: Add route guard to dashboard**
  Modify `frontend/src/routes/_dashboard.tsx`:
  ```tsx
  import { createRoute, Outlet, useNavigate } from '@tanstack/react-router';
  import { Route as rootRoute } from './__root';
  import React, { useEffect } from 'react';
  import { getStoredAuth } from '../utils/auth';

  export const Route = createRoute({
    getParentRoute: () => rootRoute,
    path: '/dashboard',
    component: DashboardLayout,
  });

  function DashboardLayout() {
    const navigate = useNavigate();
    const auth = getStoredAuth();

    useEffect(() => {
      if (!auth) navigate({ to: '/' });
    }, [auth, navigate]);

    if (!auth) return null;

    return (
      <div style={{ padding: '2rem' }}>
        <h1 id="dashboard-header">Dashboard</h1>
        <Outlet />
      </div>
    );
  }
  ```
  > **v2 fix:** Dashboard now checks for valid, non-expired token. Redirects to login if missing.

- [ ] **Step 6: Run tests**
  ```bash
  npx playwright test
  ```
  Expected: PASS.

- [ ] **Step 7: Commit**
  ```bash
  git add . && git commit -m "feat(auth): login API, superadmin seeding, and dashboard route guard"
  ```

---

## Phase 3: Admin & UI Shell

### Task 7: Admin CRUD APIs (Teams, Users, Members)

**Files:**
* Create: `backend/api/routes/admin.py`
* Modify: `backend/main.py` (register router)
* Create: `backend/tests/test_admin.py`
* Create: `tests/e2e/admin.spec.ts`

- [ ] **Step 1: Write tests**
  Create `backend/tests/test_admin.py`:
  ```python
  from fastapi.testclient import TestClient
  from backend.main import app
  from backend.auth.jwt import create_access_token

  client = TestClient(app)

  def get_superadmin_headers():
      token = create_access_token({"sub": "test-admin", "role": "superadmin"})
      return {"Authorization": f"Bearer {token}"}

  def get_user_headers():
      token = create_access_token({"sub": "test-user", "role": "user"})
      return {"Authorization": f"Bearer {token}"}

  def test_create_team_as_superadmin():
      res = client.post("/api/admin/teams", json={"name": "TestTeam"}, headers=get_superadmin_headers())
      assert res.status_code == 200

  def test_create_team_as_user_forbidden():
      res = client.post("/api/admin/teams", json={"name": "TestTeam2"}, headers=get_user_headers())
      assert res.status_code == 403

  def test_list_teams():
      res = client.get("/api/admin/teams", headers=get_superadmin_headers())
      assert res.status_code == 200
      assert isinstance(res.json()["teams"], list)
  ```

- [ ] **Step 2: Implement admin CRUD routes with pagination**
  Create `backend/api/routes/admin.py`:
  ```python
  import logging, uuid
  from fastapi import APIRouter, Depends, HTTPException, Query
  from sqlalchemy.orm import Session
  from pydantic import BaseModel
  from backend.db.mysql import get_db
  from backend.models import User, Team, TeamMember
  from backend.auth.middleware import require_global_role
  from backend.auth.passwords import hash_password

  logger = logging.getLogger(__name__)
  router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_global_role("superadmin"))])

  class TeamCreate(BaseModel):
      name: str

  @router.post("/teams")
  def create_team(payload: TeamCreate, db: Session = Depends(get_db)):
      existing = db.query(Team).filter_by(name=payload.name).first()
      if existing:
          raise HTTPException(status_code=409, detail="Team already exists")
      team = Team(team_id=str(uuid.uuid4()), name=payload.name)
      db.add(team)
      db.commit()
      return {"status": "created", "team_id": team.team_id}

  @router.get("/teams")
  def list_teams(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
      teams = db.query(Team).offset(offset).limit(limit).all()
      total = db.query(Team).count()
      return {"teams": [{"team_id": t.team_id, "name": t.name} for t in teams], "total": total}

  @router.post("/users")
  def create_user(payload: dict, db: Session = Depends(get_db)):
      user = User(user_id=str(uuid.uuid4()), email=payload["email"],
                  password_hash=hash_password(payload["password"]), global_role=payload.get("global_role", "user"))
      db.add(user)
      db.commit()
      return {"status": "created", "user_id": user.user_id}

  @router.get("/users")
  def list_users(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
      users = db.query(User).offset(offset).limit(limit).all()
      return {"users": [{"user_id": u.user_id, "email": u.email, "role": u.global_role} for u in users]}
  ```
  > **v2 fixes:** Added pagination on list endpoints. Added duplicate checks. Proper error responses.

  Register in `backend/main.py`:
  ```python
  from backend.api.routes.admin import router as admin_router
  app.include_router(admin_router)
  ```

- [ ] **Step 3: Run tests, commit**
  ```bash
  uv run --project backend pytest backend/tests/test_admin.py
  git add . && git commit -m "feat(admin): CRUD APIs for teams, users with pagination"
  ```

---

### Task 8: Dashboard Layout, Sidebar, Theme Switcher & Child Routes

**Files:**
* Modify: `frontend/src/routes/_dashboard.tsx`
* Create: `frontend/src/routes/_dashboard.chat.tsx`
* Create: `frontend/src/routes/_dashboard.docs.tsx`
* Modify: `frontend/src/router.tsx`
* Create: `frontend/src/utils/theme.ts`
* Create: `frontend/src/utils/theme.test.ts`
* Create: `tests/e2e/theme.spec.ts`

- [ ] **Step 1: Write tests**
  Create `frontend/src/utils/theme.test.ts`:
  ```typescript
  import { expect, test } from 'vitest';
  import { getNextTheme } from './theme';

  test('toggles theme correctly', () => {
    expect(getNextTheme('light')).toBe('dark');
    expect(getNextTheme('dark')).toBe('light');
  });
  ```

  Create `tests/e2e/theme.spec.ts`:
  ```typescript
  import { test, expect } from '@playwright/test';

  test('should switch themes and navigate to chat', async ({ page }) => {
    await page.goto('http://localhost:5173/dashboard');
    const html = page.locator('html');
    const toggle = page.locator('#theme-toggle');
    await expect(html).not.toHaveClass(/dark/);
    await toggle.click();
    await expect(html).toHaveClass(/dark/);

    await page.locator('#link-chat').click();
    await expect(page.locator('#chat-title')).toContainText('Chat Interface Console');
  });
  ```

- [ ] **Step 2: Implement theme utility**
  Create `frontend/src/utils/theme.ts`:
  ```typescript
  export function getNextTheme(current: string): string {
    return current === 'light' ? 'dark' : 'light';
  }

  export function applyTheme(theme: string): void {
    if (theme === 'dark') { document.documentElement.classList.add('dark'); }
    else { document.documentElement.classList.remove('dark'); }
    localStorage.setItem('theme', theme);
  }

  export function getSavedTheme(): string {
    return localStorage.getItem('theme') || 'light';
  }
  ```

- [ ] **Step 3: Implement full dashboard layout with sidebar**
  Modify `frontend/src/routes/_dashboard.tsx` with sidebar, admin panel, and theme toggle. Create child routes `_dashboard.chat.tsx` and `_dashboard.docs.tsx` with **correct parent references**:
  ```tsx
  // _dashboard.chat.tsx
  import { createRoute } from '@tanstack/react-router';
  import { Route as dashboardRoute } from './_dashboard';

  export const Route = createRoute({
    getParentRoute: () => dashboardRoute,  // ✅ Correct parent
    path: '/chat',
    component: () => <h2 id="chat-title">Chat Interface Console</h2>,
  });
  ```
  ```tsx
  // _dashboard.docs.tsx
  import { createRoute } from '@tanstack/react-router';
  import { Route as dashboardRoute } from './_dashboard';

  export const Route = createRoute({
    getParentRoute: () => dashboardRoute,  // ✅ Correct parent
    path: '/docs',
    component: () => <h2 id="docs-title">Document Ingestion Console</h2>,
  });
  ```

- [ ] **Step 4: Update router with child routes**
  ```tsx
  const routeTree = rootRoute.addChildren([
    indexRoute,
    dashboardLayoutRoute.addChildren([chatRoute, docsRoute]),
  ]);
  ```

- [ ] **Step 5: Run tests, commit**
  ```bash
  cd frontend && npx vitest run
  npx playwright test tests/e2e/theme.spec.ts
  git add . && git commit -m "feat(ui): dashboard layout, sidebar, theme switcher, child routes"
  ```

---

## Phase 4: Data Ingestion Pipeline

### Task 9: Weaviate Schema, Multi-Tenancy & Tenant Provisioning

**Files:**
* Create: `backend/db/weaviate.py`
* Modify: `backend/main.py` (lifespan: create Weaviate schema)
* Modify: `backend/api/routes/admin.py` (create tenant on team creation)
* Create: `backend/tests/test_weaviate.py`

> **CRITICAL v2 FIX:** The original plan never created the Weaviate collection or provisioned tenants. Also mixed v3 and v4 client APIs which are incompatible. This task standardizes on the **Weaviate v4 Python client**.

- [ ] **Step 1: Write tests with mocks**
  Create `backend/tests/test_weaviate.py`:
  ```python
  from unittest.mock import patch, MagicMock
  from backend.db.weaviate import WeaviateManager

  def test_weaviate_manager_init():
      with patch('backend.db.weaviate.weaviate.connect_to_local') as mock_connect:
          mock_connect.return_value = MagicMock()
          manager = WeaviateManager()
          assert manager.client is not None

  def test_insert_chunks_batches_correctly():
      with patch('backend.db.weaviate.weaviate.connect_to_local') as mock_connect:
          mock_connect.return_value = MagicMock()
          manager = WeaviateManager()
          chunks = [{"text": f"chunk {i}", "parent_id": "p1", "page_number": 1, "bbox": []} for i in range(5)]
          manager.insert_chunks("team-1", chunks, ["user-1", "public"])
  ```

- [ ] **Step 2: Implement Weaviate manager with v4 client**
  Create `backend/db/weaviate.py`:
  ```python
  import logging
  import weaviate
  from weaviate.classes.config import Configure, Property, DataType
  from weaviate.classes.tenants import Tenant
  from weaviate.classes.query import Filter
  from backend.config import settings

  logger = logging.getLogger(__name__)
  COLLECTION_NAME = "DocumentChunk"

  class WeaviateManager:
      def __init__(self):
          self.client = weaviate.connect_to_local(
              host=settings.WEAVIATE_HOST, port=settings.WEAVIATE_PORT, grpc_port=settings.WEAVIATE_GRPC_PORT,
          )

      def ensure_schema(self):
          if self.client.collections.exists(COLLECTION_NAME):
              return
          self.client.collections.create(
              name=COLLECTION_NAME,
              multi_tenancy_config=Configure.multi_tenancy(enabled=True),
              properties=[
                  Property(name="text", data_type=DataType.TEXT),
                  Property(name="parent_id", data_type=DataType.TEXT),
                  Property(name="page_number", data_type=DataType.INT),
                  Property(name="bbox", data_type=DataType.NUMBER_ARRAY),
                  Property(name="allowed_user_ids", data_type=DataType.TEXT_ARRAY),
              ],
          )
          logger.info(f"Created collection {COLLECTION_NAME} with multi-tenancy")

      def create_tenant(self, team_id: str):
          collection = self.client.collections.get(COLLECTION_NAME)
          collection.tenants.create([Tenant(name=team_id)])

      def insert_chunks(self, tenant_id: str, chunks: list[dict], allowed_users: list[str]):
          collection = self.client.collections.get(COLLECTION_NAME).with_tenant(tenant_id)
          with collection.batch.dynamic() as batch:
              for chunk in chunks:
                  batch.add_object(properties={
                      "text": chunk["text"], "parent_id": chunk["parent_id"],
                      "page_number": chunk["page_number"], "bbox": chunk.get("bbox", []),
                      "allowed_user_ids": allowed_users,
                  })

      def hybrid_search(self, tenant_id: str, query: str, current_user_id: str, limit: int = 5) -> list[dict]:
          collection = self.client.collections.get(COLLECTION_NAME).with_tenant(tenant_id)
          results = collection.query.hybrid(
              query=query, alpha=0.5,
              filters=Filter.by_property("allowed_user_ids").contains_any([current_user_id, "public"]),
              limit=limit,
          )
          return [{"text": o.properties.get("text", ""), "parent_id": o.properties.get("parent_id", ""),
                   "page_number": o.properties.get("page_number", 0), "bbox": o.properties.get("bbox", [])}
                  for o in results.objects]

      def close(self):
          self.client.close()
  ```
  > **v2 fixes:** v4 client only. Batch context manager (was flushing per chunk). Schema creation. Tenant provisioning.

- [ ] **Step 3: Wire into startup and admin flow, commit**
  Add `weaviate_mgr.ensure_schema()` to lifespan. Add `weaviate_mgr.create_tenant(team_id)` to `create_team`.
  ```bash
  git add . && git commit -m "feat(weaviate): v4 client, schema creation, tenant provisioning, batch inserts"
  ```

---

### Task 10: IBM Docling Parser, Chunker & Celery Upload Worker

**Files:**
* Create: `backend/ingestion/parser.py`
* Create: `backend/ingestion/chunker.py`
* Create: `backend/tasks/celery_app.py`
* Create: `backend/tasks/ingestion_worker.py`
* Create: `backend/tests/test_chunker.py`

> **v2 fix:** Docling parsing is CPU-intensive. Offloaded to Celery worker instead of blocking FastAPI.

- [ ] **Step 1: Write chunker tests**
  ```python
  from backend.ingestion.chunker import split_text_recursively

  def test_chunking_produces_expected_count():
      chunks = split_text_recursively("A" * 1000, max_size=500, overlap=50)
      assert len(chunks) >= 2
      assert chunks[0][-50:] == chunks[1][:50]  # Verify overlap

  def test_short_text_single_chunk():
      assert len(split_text_recursively("Hello", max_size=500, overlap=50)) == 1

  def test_empty_text():
      assert len(split_text_recursively("", max_size=500, overlap=50)) == 0
  ```

- [ ] **Step 2: Implement chunker**
  ```python
  def split_text_recursively(text: str, max_size: int = 512, overlap: int = 64) -> list[str]:
      if not text: return []
      if len(text) <= max_size: return [text]
      chunks, start = [], 0
      while start < len(text):
          end = min(start + max_size, len(text))
          chunks.append(text[start:end])
          if end >= len(text): break
          start = end - overlap
      return chunks
  ```

- [ ] **Step 3: Implement Docling parser and Celery app**
  Celery app uses `settings.REDIS_URL` from config (not hardcoded). Ingestion worker handles parse → chunk → MySQL → Weaviate → Neo4j pipeline.

- [ ] **Step 4: Run tests, commit**
  ```bash
  git add . && git commit -m "feat(ingest): Docling parser, chunker, Celery ingestion worker"
  ```

---

### Task 11: Neo4j Knowledge Graph & Upload API

**Files:**
* Create: `backend/db/neo4j.py`
* Create: `backend/api/routes/upload.py`
* Modify: `backend/main.py`
* Modify: `frontend/src/routes/_dashboard.docs.tsx`
* Create: `backend/tests/test_neo4j.py`
* Create: `frontend/src/utils/upload.test.ts`
* Create: `tests/e2e/ingest.spec.ts`

- [ ] **Step 1: Implement Neo4j manager with tenant tagging**

- [ ] **Step 2: Implement upload API with auth + file size validation**
  ```python
  @router.post("/upload")
  async def upload_document(
      file: UploadFile = File(...),
      x_active_team_id: str = Header(..., alias="X-Active-Team-ID"),
      user: dict = Depends(get_current_user),  # ✅ Auth required
  ):
      content = await file.read()
      if len(content) > settings.max_upload_bytes:
          raise HTTPException(status_code=413, detail=f"File exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit")
      # Dispatch to Celery
      task = process_document_task.delay(content.hex(), file.filename, x_active_team_id, user["sub"])
      return {"status": "processing", "task_id": task.id}
  ```
  > **v2 fixes:** Auth required. File size validated. Async Celery processing. Status polling endpoint.

- [ ] **Step 3: Update docs frontend with upload UI and status polling**

- [ ] **Step 4: Run tests, commit**
  ```bash
  git add . && git commit -m "feat(ingest): Neo4j graph, upload API with auth+validation, Celery async"
  ```

---

## Phase 5: Query & Conversational Memory

### Task 12: Redis Session Memory & LangGraph Orchestrator

**Files:**
* Create: `backend/agents/memory.py`
* Create: `backend/agents/graph_orchestrator.py`
* Create: `backend/agents/router.py`
* Create: `backend/agents/rewriter.py`
* Create: `backend/tests/test_memory.py`
* Create: `backend/tests/test_agent_routing.py`

> **v2 fixes:** Redis chat history was stored in reverse order (LPUSH + LRANGE returns newest-first). Fixed to use RPUSH. LangGraph was compiled at module import time — now uses lazy initialization.

- [ ] **Step 1: Write memory tests verifying order**
  ```python
  def test_chat_history_ordering():
      """Verify messages are returned in chronological order (oldest first)."""
      # mock_redis.lrange returns oldest-first when using RPUSH + LRANGE -N -1
      assert history[0]["content"] == "first"
      assert history[2]["content"] == "third"

  def test_save_message_uses_rpush():
      """Verify RPUSH is used (not LPUSH) to maintain chronological order."""
      mock_redis.rpush.assert_called_once()
      mock_redis.lpush.assert_not_called()

  def test_ttl_is_set_on_save():
      """Verify session keys get a TTL to prevent unbounded Redis memory."""
      mock_redis.expire.assert_called_once()
  ```

- [ ] **Step 2: Implement Redis memory with correct ordering**
  ```python
  class RedisMemory:
      SESSION_TTL = 7 * 24 * 3600  # 7 days
      MAX_LENGTH = 20

      def get_history(self, session_id: str, limit: int = 10) -> list[dict]:
          messages = self.client.lrange(f"chat_history:{session_id}", -limit, -1)
          return [json.loads(m) for m in messages]

      def save_message(self, session_id: str, role: str, content: str):
          key = f"chat_history:{session_id}"
          self.client.rpush(key, json.dumps({"role": role, "content": content}))  # ✅ RPUSH not LPUSH
          self.client.ltrim(key, -self.MAX_LENGTH, -1)
          self.client.expire(key, self.SESSION_TTL)  # ✅ TTL prevents unbounded growth
  ```

- [ ] **Step 3: Implement lazy LangGraph**
  ```python
  _compiled_graph = None

  def get_graph():
      """Lazily compile and cache the LangGraph."""
      global _compiled_graph
      if _compiled_graph is not None:
          return _compiled_graph
      # ... build workflow ...
      _compiled_graph = workflow.compile()
      return _compiled_graph
  ```
  > **v2 fix:** Lazy compilation prevents FastAPI crash if Redis/dependencies aren't ready at import time.

- [ ] **Step 4: Run tests, commit**
  ```bash
  git add . && git commit -m "feat(agents): Redis memory with correct ordering, lazy LangGraph, routing"
  ```

---

### Task 13: Query API & Chat Branching UI

**Files:**
* Create: `backend/api/routes/query.py`
* Modify: `backend/main.py`
* Modify: `frontend/src/routes/_dashboard.chat.tsx`
* Create: `frontend/src/utils/query.test.ts`
* Create: `tests/e2e/query.spec.ts`

- [ ] **Step 1: Implement query API with auth and input validation**
  ```python
  @router.get("/query")
  def run_query(
      q: str = Query(..., min_length=3, max_length=2000),
      session_id: str = Query("default-session"),
      parent_msg_id: Optional[str] = Query(None),  # ✅ Proper typing
      user: dict = Depends(get_current_user),       # ✅ Auth required
      db: Session = Depends(get_db),
  ):
      history = memory.get_history(session_id)
      graph = get_graph()  # ✅ Lazy init
      result = graph.invoke({"query": q, "history": history, ...})
      # Store branched messages, update Redis
  ```

- [ ] **Step 2: Implement chat UI with message list, loading states, and apiFetch**

- [ ] **Step 3: Run tests, commit**
  ```bash
  git add . && git commit -m "feat(query): query API with auth, branching, Redis memory, chat UI"
  ```

---

## Phase 6: Advanced RAG & Safety

### Task 14: Hybrid Search, ACL Filters & CRAG Web Fallback

**Files:**
* Create: `backend/agents/retriever.py`
* Create: `backend/agents/crag.py`
* Create: `backend/agents/web_search.py`
* Modify: `backend/agents/graph_orchestrator.py`
* Create: `backend/tests/test_retriever.py`
* Create: `backend/tests/test_crag.py`
* Create: `tests/e2e/crag.spec.ts`

- [ ] **Step 1: Implement parent document retriever (fixes N+1 query)**
  ```python
  def retrieve_parent_documents(weaviate_mgr, tenant_id, query, current_user_id):
      chunks = weaviate_mgr.hybrid_search(tenant_id, query, current_user_id)
      parent_ids = list(set(c["parent_id"] for c in chunks))
      # ✅ Single batch query instead of N+1:
      with SessionLocal() as session:
          parents = session.query(ParentDocument).filter(ParentDocument.parent_id.in_(parent_ids)).all()
      return [{"parent_id": p.parent_id, "content": p.content} for p in parents]
  ```

- [ ] **Step 2: Implement CRAG evaluator and web search fallback**

- [ ] **Step 3: Update graph with CRAG node, run tests, commit**
  ```bash
  git add . && git commit -m "feat(rag): hybrid search with N+1 fix, ACL filters, CRAG web fallback"
  ```

---

### Task 15: Guardrails AI Validation & SSE Streaming

**Files:**
* Create: `backend/agents/safety.py`
* Modify: `backend/api/routes/query.py` (add streaming endpoint)
* Modify: `frontend/src/routes/_dashboard.chat.tsx` (SSE client)
* Create: `frontend/src/utils/safety.ts`
* Create: `backend/tests/test_safety.py`
* Create: `frontend/src/utils/safety.test.ts`
* Create: `tests/e2e/safety_stream.spec.ts`

> **CRITICAL v2 FIX:** Native `EventSource` is GET-only and **cannot send custom headers**. Uses `@microsoft/fetch-event-source` instead. SSE stream now sends `[DONE]` completion signal.

- [ ] **Step 1: Implement Guardrails safety validation**

- [ ] **Step 2: Add SSE streaming endpoint with completion signal**
  ```python
  async def generate_response_stream(query: str):
      tokens = ["Hello", " this", " is", " a", " streamed", " answer."]
      for token in tokens:
          yield f"data: {json.dumps({'token': token})}\n\n"
          await asyncio.sleep(0.05)
      yield "data: [DONE]\n\n"  # ✅ Completion signal
  ```

- [ ] **Step 3: Implement frontend with fetch-event-source**
  ```tsx
  import { fetchEventSource } from '@microsoft/fetch-event-source';

  await fetchEventSource(`${API_BASE}/api/query/stream?q=${encodeURIComponent(query)}`, {
    headers: { 'Authorization': `Bearer ${token}` },  // ✅ Can send auth headers
    onmessage(ev) {
      if (ev.data === '[DONE]') return;  // ✅ Handle completion
      const data = JSON.parse(ev.data);
      streamedText += data.token;
    },
  });
  ```

- [ ] **Step 4: Implement client-side SQL injection pattern check**
  ```typescript
  const SQL_PATTERNS = [/drop\s+table/i, /select\s+\*/i, /delete\s+from/i, /union\s+select/i];
  export function clientSideInputCheck(query: string): boolean {
    return !SQL_PATTERNS.some(p => p.test(query));
  }
  ```

- [ ] **Step 5: Run tests, commit**
  ```bash
  git add . && git commit -m "feat(safety): Guardrails validation, SSE streaming with fetch-event-source"
  ```

---

## Phase 7: Citations & Feedback

### Task 16: Citation Data Flow & PDF Viewer Drawer

**Files:**
* Create: `frontend/src/components/CitationDrawer.tsx`
* Modify: `frontend/src/routes/_dashboard.chat.tsx`
* Create: `frontend/src/components/CitationDrawer.test.tsx`
* Create: `tests/e2e/citations.spec.ts`

- [ ] **Step 1: Create CitationDrawer component with PDF.js viewport placeholder**

- [ ] **Step 2: Integrate into chat view (citations from SSE stream)**

- [ ] **Step 3: Run tests, commit**
  ```bash
  git add . && git commit -m "feat(citations): citation drawer with PDF viewport and stream integration"
  ```

---

### Task 17: RLHF Feedback Loop & DeepEval Metrics

**Files:**
* Create: `backend/api/routes/feedback.py`
* Create: `backend/api/routes/eval.py`
* Modify: `backend/main.py`
* Modify: `frontend/src/routes/_dashboard.chat.tsx` (thumbs up/down)
* Modify: `frontend/src/routes/_dashboard.docs.tsx` (eval button)
* Create: `backend/tests/test_feedback.py`
* Create: `tests/e2e/eval.spec.ts`

- [ ] **Step 1: Implement feedback API with auth**
  Both endpoints require `Depends(get_current_user)`.

- [ ] **Step 2: Implement DeepEval evaluation endpoint (superadmin only)**

- [ ] **Step 3: Update chat UI with feedback using actual query/response data**
  ```tsx
  const submitFeedback = async (rating: number) => {
    await apiFetch('/api/feedback', {
      method: 'POST',
      body: JSON.stringify({
        query: lastQuery,         // ✅ Actual query (was hardcoded)
        response: lastResponse,   // ✅ Actual response (was hardcoded)
        rating,
        trace_id: `trace-${Date.now()}`,  // ✅ Dynamic (was hardcoded)
      }),
    });
  };
  ```

- [ ] **Step 4: Run tests, commit**
  ```bash
  git add . && git commit -m "feat(feedback): RLHF feedback loop, DeepEval metrics, thumbs UI"
  ```

---

## Phase 8: Production Hardening

### Task 18: Error Handling, Logging, Health Checks & ErrorBoundary

**Files:**
* Create: `backend/middleware/error_handler.py`
* Create: `backend/middleware/logging_config.py`
* Modify: `backend/main.py` (full health checks, graceful shutdown)
* Create: `frontend/src/components/ErrorBoundary.tsx`
* Modify: `frontend/src/routes/__root.tsx`
* Create: `backend/tests/test_error_handling.py`

> This task addresses all missing elements: error handling, structured logging, health checks for ALL services (MySQL + Redis + Weaviate + Neo4j), graceful connection shutdown, and React error boundaries.

- [ ] **Step 1: Implement structured logging**
  ```python
  def setup_logging(level: str = "INFO"):
      formatter = logging.Formatter(
          fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
          datefmt="%Y-%m-%d %H:%M:%S",
      )
      # ... configure handlers, quiet noisy libraries
  ```

- [ ] **Step 2: Implement global exception handler**
  ```python
  async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
      logger.error(f"Unhandled: {request.method} {request.url.path}: {exc}")
      return JSONResponse(status_code=500, content={"detail": "Internal server error"})
  ```

- [ ] **Step 3: Full health check for ALL services**
  ```python
  @app.get("/api/health")
  def health(db: Session = Depends(get_db)):
      statuses = {}
      # MySQL, Redis, Weaviate, Neo4j — each in try/except
      overall = "ok" if all(v == "ok" for v in statuses.values()) else "degraded"
      return {"status": overall, "services": statuses}
  ```

- [ ] **Step 4: Graceful shutdown in lifespan**
  ```python
  yield
  app.state.weaviate.close()
  app.state.neo4j.close()
  logger.info("All connections closed")
  ```

- [ ] **Step 5: React ErrorBoundary**
  Wrap `<Outlet />` in `__root.tsx` with `<ErrorBoundary>` to catch component crashes.

- [ ] **Step 6: Run tests, commit**
  ```bash
  git add . && git commit -m "feat(hardening): error handler, logging, full health checks, ErrorBoundary"
  ```

---

### Task 19: Celery Background Jobs (Memory Decay & Drift Detection)

**Files:**
* Modify: `backend/tasks/celery_app.py` (beat schedule)
* Create: `backend/tasks/decay_worker.py`
* Create: `backend/tasks/drift_worker.py`
* Create: `backend/api/routes/decay.py`
* Modify: `frontend/src/routes/_dashboard.docs.tsx`
* Create: `backend/tests/test_decay.py`
* Create: `tests/e2e/decay.spec.ts`

- [ ] **Step 1: Implement decay and drift workers with proper lifecycle**

- [ ] **Step 2: Add Celery beat schedule**
  ```python
  celery_app.conf.beat_schedule = {
      "apply-memory-decay-hourly": {"task": "backend.tasks.decay_worker.decay_memory_weights", "schedule": 3600.0},
      "evaluate-drift-detection-daily": {"task": "backend.tasks.drift_worker.check_data_drift", "schedule": 86400.0},
  }
  ```

- [ ] **Step 3: Create decay API (superadmin only) and frontend trigger**

- [ ] **Step 4: Run tests, commit**
  ```bash
  git add . && git commit -m "feat(celery): memory decay and drift detection workers with beat schedule"
  ```

---

### Task 20: Arize Phoenix Tracing, Makefile & Full E2E Audit

**Files:**
* Modify: `backend/main.py` (Phoenix instrumentation)
* Create: `Makefile`
* Create: `tests/e2e/production.spec.ts`

- [ ] **Step 1: Configure Arize Phoenix OpenTelemetry tracing**
  ```python
  try:
      from openinference.instrumentation.langchain import LangChainInstrumentor
      LangChainInstrumentor().instrument()
  except ImportError:
      logger.warning("Phoenix tracing not available")
  ```

- [ ] **Step 2: Create Makefile for dev/test/production**
  ```makefile
  compose-up:
  	docker compose up -d
  dev-backend:
  	uv run --project backend uvicorn backend.main:app --reload
  dev-frontend:
  	cd frontend && npm run dev
  dev-worker:
  	uv run --project backend celery -A backend.tasks.celery_app worker --loglevel=info
  test: test-backend test-frontend test-e2e
  test-backend:
  	uv run --project backend pytest backend/tests/ -v
  test-frontend:
  	cd frontend && npx vitest run
  test-e2e:
  	npx playwright test
  production-up: compose-up
  	cd frontend && npm run build
  	uv run --project backend uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
  db-migrate:
  	cd backend && uv run alembic revision --autogenerate -m "auto"
  db-upgrade:
  	cd backend && uv run alembic upgrade head
  ```

- [ ] **Step 3: Write production E2E tests**
  ```typescript
  test('health endpoint returns all services', async ({ request }) => {
    const res = await request.get('http://127.0.0.1:8000/api/health');
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.services).toHaveProperty('mysql');
  });

  test('unauthenticated API calls return 401', async ({ request }) => {
    const res = await request.get('http://127.0.0.1:8000/api/admin/teams');
    expect(res.status()).toBe(401);
  });
  ```

- [ ] **Step 4: Run full test suite**
  ```bash
  make test
  ```
  Expected: ALL PASS.

- [ ] **Step 5: Commit**
  ```bash
  git add . && git commit -m "feat(release): Phoenix tracing, Makefile, production E2E audit"
  ```
