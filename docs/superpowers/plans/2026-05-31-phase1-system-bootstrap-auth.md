# Phase 1 — System Bootstrap & Authentication: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the project scaffold (Makefile, venv, env config), a FastAPI backend with SQLite, JWT authentication, bcrypt password hashing, superadmin bootstrap, and a SvelteKit frontend with login page, session management, protected routing, and logout — all tested end-to-end.

**Architecture:** A Python FastAPI backend serves the API on port 8000. SQLite stores users and auth data. JWT tokens (python-jose) + bcrypt handle authentication. A SvelteKit frontend (Vite dev server on port 5173) provides the login UI, stores the JWT in memory + localStorage, and protects routes. The Makefile orchestrates all lifecycle commands with no Docker dependency.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, SQLite, python-jose (JWT), bcrypt, SvelteKit, Vite, Playwright

---

## Scope Note

This plan covers **Phase 1 only** from the end-to-end PRD. The PRD defines 11 phases — each phase will have its own plan. Phase 1 is the foundation: authenticated users can access the application securely. No team management, no document upload, no RAG pipeline — those come in later phases.

---

## File Structure

### Backend (`backend/`)

```
backend/
├── Makefile
├── requirements.txt
├── .env.example
├── config.py                     # Env var loading & validation
├── main.py                       # Uvicorn entrypoint
├── api/
│   ├── __init__.py
│   ├── server.py                 # FastAPI app factory
│   └── routes/
│       ├── __init__.py
│       ├── auth.py               # POST /auth/login, POST /auth/refresh
│       └── health.py             # GET /health
├── auth/
│   ├── __init__.py
│   ├── jwt.py                    # JWT create/verify
│   ├── passwords.py              # bcrypt hash/verify
│   └── middleware.py             # FastAPI dependency for protected routes
├── db/
│   ├── __init__.py
│   ├── sqlite.py                 # SQLite connection manager
│   └── migrations/
│       └── 001_init.sql          # Users table schema
└── tests/
    ├── __init__.py
    ├── conftest.py               # Shared test fixtures
    ├── test_passwords.py         # Unit: bcrypt
    ├── test_jwt.py               # Unit: JWT
    ├── test_auth_api.py          # API: login, refresh, protected routes
    └── test_health.py            # API: health endpoint
```

### Frontend (`frontend/`)

```
frontend/
├── package.json
├── svelte.config.js
├── vite.config.ts
├── playwright.config.ts
├── src/
│   ├── app.html
│   ├── app.css                   # Global styles + CSS vars for themes
│   ├── lib/
│   │   ├── api.ts                # HTTP client (fetch wrapper with JWT)
│   │   ├── auth.ts               # Auth store (Svelte store for JWT + user)
│   │   └── types.ts              # TypeScript types
│   └── routes/
│       ├── +layout.svelte        # Root layout with auth guard
│       ├── +layout.ts            # Load function for auth check
│       ├── login/
│       │   └── +page.svelte      # Login page
│       └── dashboard/
│           └── +page.svelte      # Protected dashboard (placeholder)
├── tests/
│   └── e2e/
│       └── auth.spec.ts          # Playwright E2E: login → dashboard → logout → redirect
└── static/
    └── favicon.png
```

---

## Group A: Backend Project Scaffold

### Task 1: Makefile & Requirements

**Files:**
- Create: `backend/Makefile`
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `backend/.gitignore`

- [ ] **Step 1: Create `requirements.txt`**

```
# backend/requirements.txt
fastapi==0.115.0
uvicorn[standard]==0.32.0
python-jose[cryptography]==3.3.0
bcrypt==4.2.0
python-dotenv==1.0.1
pytest==8.3.2
httpx==0.28.0
```

- [ ] **Step 2: Create `.env.example`**

```env
# backend/.env.example

# Admin bootstrap
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=changeme

# Auth
JWT_SECRET=change-this-secret-in-production
JWT_EXPIRY_MINUTES=60

# Server
API_HOST=127.0.0.1
API_PORT=8000

# Data directories (relative to project root)
DATA_DIR=./data
SQLITE_PATH=./data/db.sqlite3
```

- [ ] **Step 3: Create `Makefile`**

```makefile
# backend/Makefile

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
UVICORN := $(VENV)/bin/uvicorn

.PHONY: check-deps install setup migrate seed-admin run run-bg stop test lint format clean reset-db

check-deps:
	@echo "Checking prerequisites..."
	@python3 --version | grep -q "3.1[1-9]\|3.[2-9][0-9]" || (echo "ERROR: Python 3.11+ required" && exit 1)
	@which pip3 > /dev/null || (echo "ERROR: pip3 not found" && exit 1)
	@echo "All prerequisites met."

install: check-deps
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

setup:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo ".env created from .env.example — edit it with your settings."; \
	else \
		echo ".env already exists, skipping."; \
	fi

migrate:
	@mkdir -p data
	$(PYTHON) -c "from db.sqlite import run_migrations; run_migrations()"
	@echo "Migrations applied."

seed-admin:
	$(PYTHON) -c "from db.sqlite import seed_admin; seed_admin()"
	@echo "Superadmin seeded."

run:
	$(UVICORN) main:app --host $${API_HOST:-127.0.0.1} --port $${API_PORT:-8000} --reload

run-bg:
	$(UVICORN) main:app --host $${API_HOST:-127.0.0.1} --port $${API_PORT:-8000} &
	@echo $$! > .pid
	@echo "Server started (PID: $$(cat .pid))"

stop:
	@if [ -f .pid ]; then \
		kill $$(cat .pid) 2>/dev/null || true; \
		rm .pid; \
		echo "Server stopped."; \
	else \
		echo "No .pid file found."; \
	fi

test:
	$(PYTEST) tests/ -v

lint:
	$(VENV)/bin/ruff check .
	$(VENV)/bin/black --check .

format:
	$(VENV)/bin/black .
	$(VENV)/bin/isort .

clean:
	rm -rf $(VENV) data __pycache__ .pid .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

reset-db:
	rm -f data/db.sqlite3
	$(MAKE) migrate
	$(MAKE) seed-admin
```

- [ ] **Step 4: Create `.gitignore`**

```gitignore
# backend/.gitignore
.venv/
data/
__pycache__/
*.pyc
.pid
.env
.pytest_cache/
*.egg-info/
```

- [ ] **Step 5: Verify the scaffold**

Run: `cd backend && cat Makefile requirements.txt .env.example .gitignore | head -5`
Expected: First 5 lines of Makefile visible, confirming all files exist.

- [ ] **Step 6: Commit**

```bash
cd backend
git add Makefile requirements.txt .env.example .gitignore
git commit -m "chore: add Makefile, requirements.txt, .env.example, .gitignore for backend scaffold"
```

---

### Task 2: Config Module

**Files:**
- Create: `backend/config.py`

- [ ] **Step 1: Create `config.py`**

```python
# backend/config.py
"""Environment configuration loader with validation."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the backend directory
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(_env_path)


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables."""

    # Admin bootstrap
    admin_email: str
    admin_password: str

    # Auth
    jwt_secret: str
    jwt_expiry_minutes: int

    # Server
    api_host: str
    api_port: int

    # Data directories
    data_dir: str
    sqlite_path: str


def load_settings() -> Settings:
    """Load settings from environment variables. Raises ValueError on missing required vars."""
    jwt_secret = os.getenv("JWT_SECRET", "")
    if not jwt_secret or jwt_secret == "change-this-secret-in-production":
        import warnings
        warnings.warn(
            "JWT_SECRET is not set or using default value. "
            "Set a strong secret in .env for production.",
            stacklevel=2,
        )
        if not jwt_secret:
            jwt_secret = "dev-fallback-secret-do-not-use-in-production"

    return Settings(
        admin_email=os.getenv("ADMIN_EMAIL", "admin@example.com"),
        admin_password=os.getenv("ADMIN_PASSWORD", "changeme"),
        jwt_secret=jwt_secret,
        jwt_expiry_minutes=int(os.getenv("JWT_EXPIRY_MINUTES", "60")),
        api_host=os.getenv("API_HOST", "127.0.0.1"),
        api_port=int(os.getenv("API_PORT", "8000")),
        data_dir=os.getenv("DATA_DIR", "./data"),
        sqlite_path=os.getenv("SQLITE_PATH", "./data/db.sqlite3"),
    )


settings = load_settings()
```

- [ ] **Step 2: Verify config loads**

Run: `cd backend && python3 -c "from config import settings; print(settings.api_port)"`
Expected: `8000`

- [ ] **Step 3: Commit**

```bash
cd backend
git add config.py
git commit -m "feat: add config module for env var loading"
```

---

### Task 3: SQLite Database & Migrations

**Files:**
- Create: `backend/db/__init__.py`
- Create: `backend/db/sqlite.py`
- Create: `backend/db/migrations/001_init.sql`

- [ ] **Step 1: Create migration SQL**

```sql
-- backend/db/migrations/001_init.sql

CREATE TABLE IF NOT EXISTS users (
    user_id       TEXT PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    global_role   TEXT NOT NULL DEFAULT 'user',
    created_at    DATETIME NOT NULL DEFAULT (datetime('now'))
);
```

- [ ] **Step 2: Create `db/__init__.py`**

```python
# backend/db/__init__.py
```

- [ ] **Step 3: Create `db/sqlite.py`**

```python
# backend/db/sqlite.py
"""SQLite connection manager, migration runner, and admin seeder."""

import sqlite3
import uuid
from pathlib import Path

from config import settings


def get_connection() -> sqlite3.Connection:
    """Return a new SQLite connection with row_factory set."""
    db_path = Path(settings.sqlite_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def run_migrations() -> None:
    """Apply all SQL migration files in order."""
    migrations_dir = Path(__file__).resolve().parent / "migrations"
    conn = get_connection()
    try:
        # Track applied migrations
        conn.execute(
            "CREATE TABLE IF NOT EXISTS _migrations ("
            "  filename TEXT PRIMARY KEY,"
            "  applied_at DATETIME DEFAULT (datetime('now'))"
            ")"
        )
        applied = {
            row[0]
            for row in conn.execute("SELECT filename FROM _migrations").fetchall()
        }

        migration_files = sorted(migrations_dir.glob("*.sql"))
        for mf in migration_files:
            if mf.name not in applied:
                sql = mf.read_text()
                conn.executescript(sql)
                conn.execute(
                    "INSERT INTO _migrations (filename) VALUES (?)", (mf.name,)
                )
                conn.commit()
                print(f"Applied migration: {mf.name}")

    finally:
        conn.close()


def seed_admin() -> None:
    """Create the superadmin account if it doesn't exist."""
    from auth.passwords import hash_password

    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT user_id FROM users WHERE email = ?", (settings.admin_email,)
        ).fetchone()

        if existing:
            print(f"Admin account already exists: {settings.admin_email}")
            return

        user_id = str(uuid.uuid4())
        password_hash = hash_password(settings.admin_password)
        conn.execute(
            "INSERT INTO users (user_id, email, password_hash, global_role) "
            "VALUES (?, ?, ?, ?)",
            (user_id, settings.admin_email, password_hash, "superadmin"),
        )
        conn.commit()
        print(f"Superadmin created: {settings.admin_email}")
    finally:
        conn.close()
```

- [ ] **Step 4: Commit**

```bash
cd backend
git add db/
git commit -m "feat: add SQLite connection manager, migration runner, and admin seeder"
```

---

## Group B: Backend Auth Layer

### Task 4: Password Hashing Module

**Files:**
- Create: `backend/auth/__init__.py`
- Create: `backend/auth/passwords.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_passwords.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/__init__.py` (empty) and `backend/tests/test_passwords.py`:

```python
# backend/tests/test_passwords.py
"""Unit tests for bcrypt password hashing."""

from auth.passwords import hash_password, verify_password


def test_hash_returns_string():
    hashed = hash_password("mypassword")
    assert isinstance(hashed, str)
    assert len(hashed) > 0


def test_hash_is_not_plaintext():
    password = "mypassword"
    hashed = hash_password(password)
    assert hashed != password


def test_verify_correct_password():
    password = "testpass123"
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True


def test_verify_wrong_password():
    hashed = hash_password("correctpassword")
    assert verify_password("wrongpassword", hashed) is False


def test_different_hashes_for_same_password():
    """bcrypt generates unique salts, so same password produces different hashes."""
    h1 = hash_password("samepassword")
    h2 = hash_password("samepassword")
    assert h1 != h2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python3 -m pytest tests/test_passwords.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'auth.passwords'`

- [ ] **Step 3: Create `auth/__init__.py`**

```python
# backend/auth/__init__.py
```

- [ ] **Step 4: Write minimal implementation**

```python
# backend/auth/passwords.py
"""Bcrypt password hashing and verification."""

import bcrypt


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt. Returns the hash as a string."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(
        password.encode("utf-8"), password_hash.encode("utf-8")
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python3 -m pytest tests/test_passwords.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
cd backend
git add auth/ tests/
git commit -m "feat: add bcrypt password hashing with unit tests"
```

---

### Task 5: JWT Module

**Files:**
- Create: `backend/auth/jwt.py`
- Create: `backend/tests/test_jwt.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_jwt.py
"""Unit tests for JWT token creation and verification."""

import time
from auth.jwt import create_access_token, verify_token


def test_create_token_returns_string():
    token = create_access_token(
        user_id="user-1",
        global_role="user",
        team_memberships=[],
    )
    assert isinstance(token, str)
    assert len(token) > 0


def test_verify_valid_token():
    token = create_access_token(
        user_id="user-1",
        global_role="admin",
        team_memberships=[{"team_id": "t1", "role": "team_lead"}],
    )
    payload = verify_token(token)
    assert payload is not None
    assert payload["user_id"] == "user-1"
    assert payload["role"] == "admin"
    assert payload["team_memberships"] == [{"team_id": "t1", "role": "team_lead"}]


def test_verify_invalid_token_returns_none():
    payload = verify_token("this.is.not.a.valid.jwt")
    assert payload is None


def test_verify_tampered_token_returns_none():
    token = create_access_token(
        user_id="user-1",
        global_role="user",
        team_memberships=[],
    )
    # Tamper with the token by changing a character
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
    payload = verify_token(tampered)
    assert payload is None


def test_token_contains_expiry():
    token = create_access_token(
        user_id="user-1",
        global_role="user",
        team_memberships=[],
    )
    payload = verify_token(token)
    assert "exp" in payload


def test_expired_token_returns_none():
    token = create_access_token(
        user_id="user-1",
        global_role="user",
        team_memberships=[],
        expiry_minutes=-1,  # Already expired
    )
    payload = verify_token(token)
    assert payload is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python3 -m pytest tests/test_jwt.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'auth.jwt'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/auth/jwt.py
"""JWT token creation and verification using python-jose."""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from config import settings

ALGORITHM = "HS256"


def create_access_token(
    user_id: str,
    global_role: str,
    team_memberships: list[dict[str, str]],
    expiry_minutes: int | None = None,
) -> str:
    """Create a signed JWT access token.

    Args:
        user_id: The user's unique identifier.
        global_role: The user's global role ('user', 'admin', 'superadmin').
        team_memberships: List of dicts with 'team_id' and 'role' keys.
        expiry_minutes: Override expiry. Defaults to settings.jwt_expiry_minutes.

    Returns:
        Encoded JWT string.
    """
    if expiry_minutes is None:
        expiry_minutes = settings.jwt_expiry_minutes

    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expiry_minutes)

    payload: dict[str, Any] = {
        "user_id": user_id,
        "role": global_role,
        "team_memberships": team_memberships,
        "exp": expire,
        "iat": now,
    }

    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def verify_token(token: str) -> dict[str, Any] | None:
    """Verify and decode a JWT token.

    Returns:
        Decoded payload dict if valid, None if invalid or expired.
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python3 -m pytest tests/test_jwt.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
cd backend
git add auth/jwt.py tests/test_jwt.py
git commit -m "feat: add JWT creation and verification with unit tests"
```

---

### Task 6: Auth Middleware (FastAPI Dependency)

**Files:**
- Create: `backend/auth/middleware.py`

- [ ] **Step 1: Write the middleware**

```python
# backend/auth/middleware.py
"""FastAPI dependency for JWT authentication on protected routes."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth.jwt import verify_token

_bearer_scheme = HTTPBearer()


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> dict:
    """FastAPI dependency that extracts and verifies the JWT from the Authorization header.

    Returns:
        Decoded JWT payload dict containing user_id, role, team_memberships.

    Raises:
        HTTPException 401 if token is missing, invalid, or expired.
    """
    token = credentials.credentials
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload
```

- [ ] **Step 2: Commit**

```bash
cd backend
git add auth/middleware.py
git commit -m "feat: add auth middleware (FastAPI dependency for JWT verification)"
```

---

### Task 7: Health Endpoint

**Files:**
- Create: `backend/api/__init__.py`
- Create: `backend/api/routes/__init__.py`
- Create: `backend/api/routes/health.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_health.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/conftest.py`:

```python
# backend/tests/conftest.py
"""Shared test fixtures for the backend test suite."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Override SQLITE_PATH before importing anything that uses config
_test_db = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
os.environ["SQLITE_PATH"] = _test_db.name
os.environ["JWT_SECRET"] = "test-secret-key-for-tests"

from api.server import create_app
from db.sqlite import run_migrations, seed_admin


@pytest.fixture(scope="session", autouse=True)
def _setup_test_db():
    """Create test database with migrations and seed data."""
    run_migrations()
    seed_admin()
    yield
    os.unlink(_test_db.name)


@pytest.fixture()
def client():
    """FastAPI test client."""
    app = create_app()
    return TestClient(app)
```

Create test:

```python
# backend/tests/test_health.py
"""Tests for the health endpoint."""


def test_health_returns_200(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_status_ok(client):
    response = client.get("/health")
    data = response.json()
    assert data["status"] == "ok"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python3 -m pytest tests/test_health.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.server'`

- [ ] **Step 3: Create the route and app factory**

Create `backend/api/__init__.py`:

```python
# backend/api/__init__.py
```

Create `backend/api/routes/__init__.py`:

```python
# backend/api/routes/__init__.py
```

Create `backend/api/routes/health.py`:

```python
# backend/api/routes/health.py
"""Public health check endpoint."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Return basic health status. No auth required."""
    return {"status": "ok"}
```

Create `backend/api/server.py`:

```python
# backend/api/server.py
"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.health import router as health_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="MemMesh API",
        description="Advanced Agentic RAG System with Hybrid Memory",
        version="0.1.0",
    )

    # CORS — allow frontend dev server
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    app.include_router(health_router)

    return app
```

Create `backend/main.py`:

```python
# backend/main.py
"""Uvicorn entrypoint. Run via: uvicorn main:app --reload"""

from api.server import create_app

app = create_app()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python3 -m pytest tests/test_health.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
cd backend
git add api/ main.py tests/conftest.py tests/test_health.py
git commit -m "feat: add health endpoint, FastAPI app factory, and test client fixture"
```

---

### Task 8: Auth Routes (Login & Refresh)

**Files:**
- Create: `backend/api/routes/auth.py`
- Create: `backend/tests/test_auth_api.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_auth_api.py
"""API tests for authentication endpoints."""


def test_login_success(client):
    response = client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "changeme"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client):
    response = client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_nonexistent_user(client):
    response = client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "whatever"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_missing_fields(client):
    response = client.post("/auth/login", json={"email": "admin@example.com"})
    assert response.status_code == 422  # Validation error


def test_refresh_token_success(client):
    # First login to get a refresh token
    login_resp = client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "changeme"},
    )
    refresh_token = login_resp.json()["refresh_token"]

    # Use the refresh token
    response = client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_refresh_token_invalid(client):
    response = client.post(
        "/auth/refresh",
        json={"refresh_token": "invalid.token.here"},
    )
    assert response.status_code == 401


def test_protected_endpoint_without_token(client):
    """Verify that accessing a protected endpoint without a token returns 403 (no credentials)."""
    response = client.get("/auth/me")
    assert response.status_code == 403


def test_protected_endpoint_with_valid_token(client):
    # Login first
    login_resp = client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "changeme"},
    )
    token = login_resp.json()["access_token"]

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "admin@example.com"
    assert data["global_role"] == "superadmin"


def test_protected_endpoint_with_expired_token(client):
    from auth.jwt import create_access_token

    expired_token = create_access_token(
        user_id="user-1",
        global_role="user",
        team_memberships=[],
        expiry_minutes=-1,
    )
    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python3 -m pytest tests/test_auth_api.py -v`
Expected: FAIL — errors related to missing route `/auth/login`

- [ ] **Step 3: Write the auth routes**

```python
# backend/api/routes/auth.py
"""Authentication routes: login, refresh, and me."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from auth.jwt import create_access_token, verify_token
from auth.middleware import require_auth
from auth.passwords import verify_password
from db.sqlite import get_connection

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshedTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    user_id: str
    email: str
    global_role: str


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    """Authenticate with email + password and receive JWT tokens."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT user_id, email, password_hash, global_role FROM users WHERE email = ?",
            (body.email,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not verify_password(body.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # In Phase 1, no teams exist yet — team_memberships is empty
    team_memberships: list[dict[str, str]] = []

    # Fetch team memberships if any exist (future-proofing)
    conn = get_connection()
    try:
        members = conn.execute(
            "SELECT team_id, role FROM team_members WHERE user_id = ?",
            (row["user_id"],),
        ).fetchall()
        team_memberships = [
            {"team_id": m["team_id"], "role": m["role"]} for m in members
        ]
    except Exception:
        # team_members table may not exist yet in Phase 1
        pass
    finally:
        conn.close()

    access_token = create_access_token(
        user_id=row["user_id"],
        global_role=row["global_role"],
        team_memberships=team_memberships,
    )

    # Refresh token has a longer expiry (7 days)
    refresh_token = create_access_token(
        user_id=row["user_id"],
        global_role=row["global_role"],
        team_memberships=team_memberships,
        expiry_minutes=60 * 24 * 7,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=RefreshedTokenResponse)
async def refresh(body: RefreshRequest):
    """Exchange a valid refresh token for a new access token."""
    payload = verify_token(body.refresh_token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Issue a fresh access token
    access_token = create_access_token(
        user_id=payload["user_id"],
        global_role=payload["role"],
        team_memberships=payload.get("team_memberships", []),
    )

    return RefreshedTokenResponse(access_token=access_token)


@router.get("/me", response_model=UserResponse)
async def get_current_user(current_user: dict = Depends(require_auth)):
    """Return the currently authenticated user's info."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT user_id, email, global_role FROM users WHERE user_id = ?",
            (current_user["user_id"],),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse(
        user_id=row["user_id"],
        email=row["email"],
        global_role=row["global_role"],
    )
```

- [ ] **Step 4: Register auth router in server.py**

Update `backend/api/server.py` to import and include the auth router:

```python
# backend/api/server.py
"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.auth import router as auth_router
from api.routes.health import router as health_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="MemMesh API",
        description="Advanced Agentic RAG System with Hybrid Memory",
        version="0.1.0",
    )

    # CORS — allow frontend dev server
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    app.include_router(health_router)
    app.include_router(auth_router)

    return app
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python3 -m pytest tests/test_auth_api.py -v`
Expected: 9 passed

- [ ] **Step 6: Commit**

```bash
cd backend
git add api/routes/auth.py api/server.py tests/test_auth_api.py
git commit -m "feat: add auth routes (login, refresh, me) with API tests"
```

---

### Task 9: Verify Full Backend Test Suite

**Files:**
- No new files

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && python3 -m pytest tests/ -v`
Expected: All tests pass (5 password + 6 JWT + 2 health + 9 auth API = 22 tests)

- [ ] **Step 2: Verify the server starts**

Run: `cd backend && cp .env.example .env && python3 -c "from main import app; print(app.title)"`
Expected: `MemMesh API`

- [ ] **Step 3: Commit (if any fixups needed)**

```bash
cd backend
git add -A
git commit -m "test: verify full backend test suite passes"
```

---

## Group C: Frontend Scaffold

### Task 10: SvelteKit Project Setup

**Files:**
- Create: `frontend/` (via `npx create-svelte`)

- [ ] **Step 1: Check SvelteKit create options**

Run: `npx -y create-svelte@latest --help`
Expected: Help output showing available options

- [ ] **Step 2: Create SvelteKit project**

Run from the project root:

```bash
cd /home/ritesh/workspace/MemMesh
npx -y create-svelte@latest frontend --template skeleton --types typescript --no-prettier --no-eslint --no-playwright --no-vitest
```

If the CLI doesn't support those flags non-interactively, use the interactive mode and choose:
- Template: Skeleton project
- Type checking: TypeScript
- Additional options: none (we'll add Playwright separately)

- [ ] **Step 3: Install dependencies**

```bash
cd frontend
npm install
```

- [ ] **Step 4: Install Playwright**

```bash
cd frontend
npm install -D @playwright/test
npx playwright install --with-deps chromium
```

- [ ] **Step 5: Verify dev server starts**

```bash
cd frontend
npm run dev -- --host 0.0.0.0 &
sleep 3
curl -s http://localhost:5173 | head -5
kill %1
```
Expected: HTML output from SvelteKit dev server

- [ ] **Step 6: Commit**

```bash
cd frontend
git add -A
git commit -m "chore: scaffold SvelteKit project with TypeScript"
```

---

### Task 11: Global Styles & Theme System

**Files:**
- Create: `frontend/src/app.css`

- [ ] **Step 1: Create global CSS with theme variables**

```css
/* frontend/src/app.css */

/* ===== CSS Custom Properties (Theme Tokens) ===== */

:root {
  /* Dark Theme (default) */
  --bg: #0f0f11;
  --surface: #1a1a1f;
  --surface-hover: #242429;
  --accent: #f5a623;
  --accent-hover: #e09510;
  --text: #e8e4da;
  --text-muted: #9c9a93;
  --border: #2d2d33;
  --error: #ef4444;
  --success: #22c55e;

  /* Spacing */
  --space-xs: 0.25rem;
  --space-sm: 0.5rem;
  --space-md: 1rem;
  --space-lg: 1.5rem;
  --space-xl: 2rem;
  --space-2xl: 3rem;

  /* Typography */
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
  --text-xs: 0.75rem;
  --text-sm: 0.875rem;
  --text-base: 1rem;
  --text-lg: 1.125rem;
  --text-xl: 1.25rem;
  --text-2xl: 1.5rem;
  --text-3xl: 2rem;

  /* Borders & Radius */
  --radius-sm: 0.375rem;
  --radius-md: 0.5rem;
  --radius-lg: 0.75rem;
  --radius-xl: 1rem;
  --radius-full: 9999px;

  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.4);
  --shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.5);
  --shadow-glow: 0 0 20px rgba(245, 166, 35, 0.15);

  /* Transitions */
  --transition-fast: 150ms ease;
  --transition-normal: 250ms ease;
  --transition-slow: 400ms ease;

  color-scheme: dark;
}

/* Light Theme */
[data-theme='light'] {
  --bg: #faf9f7;
  --surface: #ffffff;
  --surface-hover: #f3f2ef;
  --accent: #d98c00;
  --accent-hover: #c07b00;
  --text: #1f2937;
  --text-muted: #6b7280;
  --border: #e5e3df;
  --error: #dc2626;
  --success: #16a34a;

  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.06);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.08);
  --shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.12);
  --shadow-glow: 0 0 20px rgba(217, 140, 0, 0.1);

  color-scheme: light;
}

/* ===== Reduced Motion ===== */
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}

/* ===== Global Reset & Base ===== */

*,
*::before,
*::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html {
  font-size: 16px;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

body {
  font-family: var(--font-sans);
  background-color: var(--bg);
  color: var(--text);
  line-height: 1.6;
  min-height: 100vh;
}

a {
  color: var(--accent);
  text-decoration: none;
  transition: color var(--transition-fast);
}

a:hover {
  color: var(--accent-hover);
}

/* ===== Utility Classes ===== */

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

/* ===== Font Import ===== */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
```

- [ ] **Step 2: Commit**

```bash
cd frontend
git add src/app.css
git commit -m "feat: add global CSS with dark/light theme system and design tokens"
```

---

### Task 12: TypeScript Types & Auth Store

**Files:**
- Create: `frontend/src/lib/types.ts`
- Create: `frontend/src/lib/auth.ts`
- Create: `frontend/src/lib/api.ts`

- [ ] **Step 1: Create types**

```typescript
// frontend/src/lib/types.ts

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface RefreshedTokenResponse {
  access_token: string;
  token_type: string;
}

export interface User {
  user_id: string;
  email: string;
  global_role: string;
}

export interface ApiError {
  detail: string;
}
```

- [ ] **Step 2: Create API client**

```typescript
// frontend/src/lib/api.ts

import { get } from 'svelte/store';
import { authStore, logout } from './auth';
import type { LoginRequest, TokenResponse, RefreshedTokenResponse, User } from './types';

const API_BASE = 'http://localhost:8000';

class ApiClient {
  private getToken(): string | null {
    const state = get(authStore);
    return state.accessToken;
  }

  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = this.getToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> || {}),
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      // Try to refresh the token
      const refreshed = await this.tryRefresh();
      if (refreshed) {
        // Retry the original request with the new token
        headers['Authorization'] = `Bearer ${this.getToken()}`;
        const retryResponse = await fetch(`${API_BASE}${path}`, {
          ...options,
          headers,
        });
        if (!retryResponse.ok) {
          const error = await retryResponse.json().catch(() => ({ detail: 'Request failed' }));
          throw new Error(error.detail || `HTTP ${retryResponse.status}`);
        }
        return retryResponse.json();
      }
      logout();
      throw new Error('Session expired');
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  private async tryRefresh(): Promise<boolean> {
    const state = get(authStore);
    if (!state.refreshToken) return false;

    try {
      const response = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: state.refreshToken }),
      });

      if (!response.ok) return false;

      const data: RefreshedTokenResponse = await response.json();
      authStore.update((s) => ({ ...s, accessToken: data.access_token }));
      if (typeof localStorage !== 'undefined') {
        const stored = localStorage.getItem('auth');
        if (stored) {
          const parsed = JSON.parse(stored);
          parsed.accessToken = data.access_token;
          localStorage.setItem('auth', JSON.stringify(parsed));
        }
      }
      return true;
    } catch {
      return false;
    }
  }

  async login(credentials: LoginRequest): Promise<TokenResponse> {
    const response = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(credentials),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Login failed' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  async getMe(): Promise<User> {
    return this.request<User>('/auth/me');
  }
}

export const api = new ApiClient();
```

- [ ] **Step 3: Create auth store**

```typescript
// frontend/src/lib/auth.ts

import { writable } from 'svelte/store';
import type { User } from './types';

export interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

const initialState: AuthState = {
  accessToken: null,
  refreshToken: null,
  user: null,
  isAuthenticated: false,
  isLoading: true,
};

export const authStore = writable<AuthState>(initialState);

/**
 * Initialize auth state from localStorage (called on app start).
 */
export function initAuth(): void {
  if (typeof localStorage === 'undefined') {
    authStore.set({ ...initialState, isLoading: false });
    return;
  }

  const stored = localStorage.getItem('auth');
  if (stored) {
    try {
      const parsed = JSON.parse(stored);
      authStore.set({
        accessToken: parsed.accessToken || null,
        refreshToken: parsed.refreshToken || null,
        user: parsed.user || null,
        isAuthenticated: !!parsed.accessToken,
        isLoading: false,
      });
    } catch {
      localStorage.removeItem('auth');
      authStore.set({ ...initialState, isLoading: false });
    }
  } else {
    authStore.set({ ...initialState, isLoading: false });
  }
}

/**
 * Set auth state after successful login.
 */
export function setAuth(accessToken: string, refreshToken: string, user: User): void {
  const state: AuthState = {
    accessToken,
    refreshToken,
    user,
    isAuthenticated: true,
    isLoading: false,
  };
  authStore.set(state);

  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('auth', JSON.stringify({
      accessToken,
      refreshToken,
      user,
    }));
  }
}

/**
 * Clear auth state (logout).
 */
export function logout(): void {
  authStore.set({ ...initialState, isLoading: false });
  if (typeof localStorage !== 'undefined') {
    localStorage.removeItem('auth');
  }
}
```

- [ ] **Step 4: Commit**

```bash
cd frontend
git add src/lib/
git commit -m "feat: add TypeScript types, API client, and auth store"
```

---

### Task 13: Root Layout with Auth Guard

**Files:**
- Modify: `frontend/src/routes/+layout.svelte`
- Create: `frontend/src/routes/+layout.ts`

- [ ] **Step 1: Create root layout load function**

```typescript
// frontend/src/routes/+layout.ts

export const ssr = false;
```

- [ ] **Step 2: Create root layout component**

```svelte
<!-- frontend/src/routes/+layout.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { authStore, initAuth } from '$lib/auth';
  import '../app.css';

  const publicPaths = ['/login'];

  onMount(() => {
    initAuth();
  });

  $: {
    const state = $authStore;
    const currentPath = $page.url.pathname;

    if (!state.isLoading) {
      if (!state.isAuthenticated && !publicPaths.includes(currentPath)) {
        goto('/login');
      }
      if (state.isAuthenticated && currentPath === '/login') {
        goto('/dashboard');
      }
    }
  }
</script>

{#if $authStore.isLoading}
  <div class="loading-screen" role="status" aria-label="Loading application">
    <div class="loading-spinner"></div>
  </div>
{:else}
  <slot />
{/if}

<style>
  .loading-screen {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    background-color: var(--bg);
  }

  .loading-spinner {
    width: 40px;
    height: 40px;
    border: 3px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
```

- [ ] **Step 3: Commit**

```bash
cd frontend
git add src/routes/+layout.svelte src/routes/+layout.ts
git commit -m "feat: add root layout with auth guard and loading state"
```

---

### Task 14: Login Page

**Files:**
- Create: `frontend/src/routes/login/+page.svelte`

- [ ] **Step 1: Create the login page**

```svelte
<!-- frontend/src/routes/login/+page.svelte -->
<script lang="ts">
  import { goto } from '$app/navigation';
  import { api } from '$lib/api';
  import { setAuth } from '$lib/auth';

  let email = '';
  let password = '';
  let error = '';
  let isSubmitting = false;

  async function handleLogin() {
    error = '';
    isSubmitting = true;

    try {
      const tokens = await api.login({ email, password });
      const user = await (async () => {
        // Temporarily set the token to fetch user info
        const response = await fetch('http://localhost:8000/auth/me', {
          headers: { Authorization: `Bearer ${tokens.access_token}` },
        });
        if (!response.ok) throw new Error('Failed to fetch user info');
        return response.json();
      })();

      setAuth(tokens.access_token, tokens.refresh_token, user);
      goto('/dashboard');
    } catch (err) {
      error = err instanceof Error ? err.message : 'Login failed';
    } finally {
      isSubmitting = false;
    }
  }
</script>

<svelte:head>
  <title>Login — MemMesh</title>
  <meta name="description" content="Sign in to MemMesh — Advanced RAG System with Hybrid Memory" />
</svelte:head>

<main class="login-container">
  <div class="login-card">
    <div class="login-header">
      <div class="logo" aria-hidden="true">
        <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
          <circle cx="20" cy="20" r="18" stroke="var(--accent)" stroke-width="2" />
          <circle cx="20" cy="14" r="4" fill="var(--accent)" />
          <circle cx="12" cy="26" r="4" fill="var(--accent)" opacity="0.7" />
          <circle cx="28" cy="26" r="4" fill="var(--accent)" opacity="0.7" />
          <line x1="20" y1="18" x2="12" y2="22" stroke="var(--accent)" stroke-width="1.5" opacity="0.5" />
          <line x1="20" y1="18" x2="28" y2="22" stroke="var(--accent)" stroke-width="1.5" opacity="0.5" />
          <line x1="12" y1="26" x2="28" y2="26" stroke="var(--accent)" stroke-width="1.5" opacity="0.3" />
        </svg>
      </div>
      <h1>MemMesh</h1>
      <p class="subtitle">Hybrid Memory RAG System</p>
    </div>

    <form on:submit|preventDefault={handleLogin} class="login-form" aria-label="Login form">
      {#if error}
        <div class="error-banner" role="alert">
          <span class="error-icon" aria-hidden="true">⚠</span>
          {error}
        </div>
      {/if}

      <div class="field">
        <label for="email">Email</label>
        <input
          id="email"
          type="email"
          bind:value={email}
          placeholder="you@example.com"
          required
          autocomplete="email"
          disabled={isSubmitting}
        />
      </div>

      <div class="field">
        <label for="password">Password</label>
        <input
          id="password"
          type="password"
          bind:value={password}
          placeholder="Enter your password"
          required
          autocomplete="current-password"
          disabled={isSubmitting}
        />
      </div>

      <button type="submit" class="login-button" disabled={isSubmitting} id="login-submit">
        {#if isSubmitting}
          <span class="button-spinner" aria-hidden="true"></span>
          Signing in…
        {:else}
          Sign In
        {/if}
      </button>
    </form>
  </div>
</main>

<style>
  .login-container {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    padding: var(--space-md);
    background: var(--bg);
  }

  .login-card {
    width: 100%;
    max-width: 420px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-xl);
    padding: var(--space-2xl);
    box-shadow: var(--shadow-lg);
  }

  .login-header {
    text-align: center;
    margin-bottom: var(--space-xl);
  }

  .logo {
    display: inline-block;
    margin-bottom: var(--space-md);
    animation: fadeIn 0.6s ease;
  }

  .login-header h1 {
    font-size: var(--text-2xl);
    font-weight: 700;
    color: var(--text);
    letter-spacing: -0.02em;
  }

  .subtitle {
    font-size: var(--text-sm);
    color: var(--text-muted);
    margin-top: var(--space-xs);
  }

  .login-form {
    display: flex;
    flex-direction: column;
    gap: var(--space-lg);
  }

  .error-banner {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    padding: var(--space-sm) var(--space-md);
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.3);
    border-radius: var(--radius-md);
    color: var(--error);
    font-size: var(--text-sm);
  }

  .error-icon {
    flex-shrink: 0;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
  }

  .field label {
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--text-muted);
  }

  .field input {
    width: 100%;
    padding: var(--space-sm) var(--space-md);
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    color: var(--text);
    font-family: var(--font-sans);
    font-size: var(--text-base);
    transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
    outline: none;
  }

  .field input:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(245, 166, 35, 0.15);
  }

  .field input::placeholder {
    color: var(--text-muted);
    opacity: 0.5;
  }

  .field input:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .login-button {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-sm);
    width: 100%;
    padding: var(--space-sm) var(--space-lg);
    background: var(--accent);
    color: #0f0f11;
    border: none;
    border-radius: var(--radius-md);
    font-family: var(--font-sans);
    font-size: var(--text-base);
    font-weight: 600;
    cursor: pointer;
    transition: background var(--transition-fast), transform var(--transition-fast), box-shadow var(--transition-fast);
  }

  .login-button:hover:not(:disabled) {
    background: var(--accent-hover);
    transform: translateY(-1px);
    box-shadow: var(--shadow-glow);
  }

  .login-button:active:not(:disabled) {
    transform: translateY(0);
  }

  .login-button:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }

  .button-spinner {
    width: 16px;
    height: 16px;
    border: 2px solid rgba(15, 15, 17, 0.3);
    border-top-color: #0f0f11;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(-8px); }
    to { opacity: 1; transform: translateY(0); }
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }
</style>
```

- [ ] **Step 2: Commit**

```bash
cd frontend
git add src/routes/login/
git commit -m "feat: add login page with styled form and error handling"
```

---

### Task 15: Dashboard Page (Protected)

**Files:**
- Create: `frontend/src/routes/dashboard/+page.svelte`

- [ ] **Step 1: Create the dashboard page**

```svelte
<!-- frontend/src/routes/dashboard/+page.svelte -->
<script lang="ts">
  import { authStore, logout } from '$lib/auth';
  import { goto } from '$app/navigation';

  function handleLogout() {
    logout();
    goto('/login');
  }
</script>

<svelte:head>
  <title>Dashboard — MemMesh</title>
  <meta name="description" content="MemMesh Dashboard — Your knowledge base overview" />
</svelte:head>

<div class="dashboard">
  <header class="topbar">
    <div class="topbar-left">
      <div class="logo-small" aria-hidden="true">
        <svg width="28" height="28" viewBox="0 0 40 40" fill="none">
          <circle cx="20" cy="20" r="18" stroke="var(--accent)" stroke-width="2" />
          <circle cx="20" cy="14" r="4" fill="var(--accent)" />
          <circle cx="12" cy="26" r="4" fill="var(--accent)" opacity="0.7" />
          <circle cx="28" cy="26" r="4" fill="var(--accent)" opacity="0.7" />
          <line x1="20" y1="18" x2="12" y2="22" stroke="var(--accent)" stroke-width="1.5" opacity="0.5" />
          <line x1="20" y1="18" x2="28" y2="22" stroke="var(--accent)" stroke-width="1.5" opacity="0.5" />
        </svg>
      </div>
      <span class="brand">MemMesh</span>
    </div>

    <div class="topbar-right">
      {#if $authStore.user}
        <span class="user-info">
          <span class="user-email">{$authStore.user.email}</span>
          <span class="user-role">{$authStore.user.global_role}</span>
        </span>
      {/if}
      <button class="logout-button" on:click={handleLogout} id="logout-button">
        Sign Out
      </button>
    </div>
  </header>

  <main class="dashboard-content">
    <div class="welcome-card">
      <h1>Welcome to MemMesh</h1>
      <p>Your authenticated session is active. The full dashboard will be available in Phase 2.</p>

      <div class="info-grid">
        <div class="info-item">
          <span class="info-label">User</span>
          <span class="info-value">{$authStore.user?.email ?? '—'}</span>
        </div>
        <div class="info-item">
          <span class="info-label">Role</span>
          <span class="info-value">{$authStore.user?.global_role ?? '—'}</span>
        </div>
        <div class="info-item">
          <span class="info-label">Status</span>
          <span class="info-value status-active">Authenticated</span>
        </div>
      </div>
    </div>
  </main>
</div>

<style>
  .dashboard {
    min-height: 100vh;
    background: var(--bg);
  }

  .topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-sm) var(--space-xl);
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    height: 56px;
  }

  .topbar-left {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
  }

  .brand {
    font-size: var(--text-lg);
    font-weight: 700;
    color: var(--text);
    letter-spacing: -0.02em;
  }

  .topbar-right {
    display: flex;
    align-items: center;
    gap: var(--space-lg);
  }

  .user-info {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
  }

  .user-email {
    font-size: var(--text-sm);
    color: var(--text);
  }

  .user-role {
    font-size: var(--text-xs);
    color: var(--accent);
    background: rgba(245, 166, 35, 0.1);
    padding: 2px 8px;
    border-radius: var(--radius-full);
    text-transform: uppercase;
    font-weight: 600;
    letter-spacing: 0.05em;
  }

  .logout-button {
    padding: var(--space-xs) var(--space-md);
    background: transparent;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    color: var(--text-muted);
    font-family: var(--font-sans);
    font-size: var(--text-sm);
    cursor: pointer;
    transition: all var(--transition-fast);
  }

  .logout-button:hover {
    border-color: var(--error);
    color: var(--error);
    background: rgba(239, 68, 68, 0.05);
  }

  .dashboard-content {
    padding: var(--space-2xl);
    max-width: 800px;
    margin: 0 auto;
  }

  .welcome-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-xl);
    padding: var(--space-2xl);
    box-shadow: var(--shadow-md);
    animation: fadeIn 0.4s ease;
  }

  .welcome-card h1 {
    font-size: var(--text-2xl);
    font-weight: 700;
    margin-bottom: var(--space-sm);
  }

  .welcome-card p {
    color: var(--text-muted);
    font-size: var(--text-base);
    margin-bottom: var(--space-xl);
  }

  .info-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: var(--space-md);
  }

  .info-item {
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
    padding: var(--space-md);
    background: var(--bg);
    border-radius: var(--radius-md);
    border: 1px solid var(--border);
  }

  .info-label {
    font-size: var(--text-xs);
    color: var(--text-muted);
    text-transform: uppercase;
    font-weight: 600;
    letter-spacing: 0.05em;
  }

  .info-value {
    font-size: var(--text-base);
    font-weight: 500;
    color: var(--text);
  }

  .status-active {
    color: var(--success);
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
  }
</style>
```

- [ ] **Step 2: Commit**

```bash
cd frontend
git add src/routes/dashboard/
git commit -m "feat: add protected dashboard page with user info and logout"
```

---

### Task 16: Root Page Redirect

**Files:**
- Create: `frontend/src/routes/+page.svelte`

- [ ] **Step 1: Create root page that redirects**

```svelte
<!-- frontend/src/routes/+page.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { authStore } from '$lib/auth';

  onMount(() => {
    const unsubscribe = authStore.subscribe((state) => {
      if (!state.isLoading) {
        if (state.isAuthenticated) {
          goto('/dashboard');
        } else {
          goto('/login');
        }
        unsubscribe();
      }
    });
  });
</script>

<div class="loading-screen" role="status" aria-label="Redirecting...">
  <div class="loading-spinner"></div>
</div>

<style>
  .loading-screen {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    background-color: var(--bg);
  }

  .loading-spinner {
    width: 40px;
    height: 40px;
    border: 3px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
```

- [ ] **Step 2: Commit**

```bash
cd frontend
git add src/routes/+page.svelte
git commit -m "feat: add root page redirect based on auth state"
```

---

## Group D: Frontend Integration Verification

### Task 17: Playwright Config

**Files:**
- Create: `frontend/playwright.config.ts`

- [ ] **Step 1: Create Playwright configuration**

```typescript
// frontend/playwright.config.ts

import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: 'list',
  timeout: 30_000,
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      command: 'cd ../backend && .venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000',
      port: 8000,
      reuseExistingServer: !process.env.CI,
      timeout: 15_000,
    },
    {
      command: 'npm run dev',
      port: 5173,
      reuseExistingServer: !process.env.CI,
      timeout: 15_000,
    },
  ],
});
```

- [ ] **Step 2: Commit**

```bash
cd frontend
git add playwright.config.ts
git commit -m "chore: add Playwright config with backend + frontend web servers"
```

---

### Task 18: Playwright E2E Auth Tests

**Files:**
- Create: `frontend/tests/e2e/auth.spec.ts`

- [ ] **Step 1: Create the E2E test file**

```typescript
// frontend/tests/e2e/auth.spec.ts

import { test, expect } from '@playwright/test';

test.describe('Authentication Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Clear localStorage before each test
    await page.goto('/login');
    await page.evaluate(() => localStorage.clear());
    await page.goto('/login');
  });

  test('should display the login page', async ({ page }) => {
    await expect(page.locator('h1')).toHaveText('MemMesh');
    await expect(page.locator('#email')).toBeVisible();
    await expect(page.locator('#password')).toBeVisible();
    await expect(page.locator('#login-submit')).toBeVisible();
  });

  test('should show error on invalid credentials', async ({ page }) => {
    await page.fill('#email', 'admin@example.com');
    await page.fill('#password', 'wrongpassword');
    await page.click('#login-submit');

    await expect(page.locator('[role="alert"]')).toBeVisible();
    await expect(page.locator('[role="alert"]')).toContainText('Invalid email or password');
  });

  test('should login successfully and redirect to dashboard', async ({ page }) => {
    await page.fill('#email', 'admin@example.com');
    await page.fill('#password', 'changeme');
    await page.click('#login-submit');

    // Should redirect to dashboard
    await page.waitForURL('**/dashboard');
    await expect(page.locator('h1')).toHaveText('Welcome to MemMesh');
    await expect(page.locator('.user-email')).toHaveText('admin@example.com');
    await expect(page.locator('.user-role')).toHaveText('superadmin');
  });

  test('should persist session across page reloads', async ({ page }) => {
    // Login first
    await page.fill('#email', 'admin@example.com');
    await page.fill('#password', 'changeme');
    await page.click('#login-submit');
    await page.waitForURL('**/dashboard');

    // Reload the page
    await page.reload();

    // Should still be on dashboard
    await expect(page.locator('h1')).toHaveText('Welcome to MemMesh');
    await expect(page.locator('.user-email')).toHaveText('admin@example.com');
  });

  test('should logout and redirect to login', async ({ page }) => {
    // Login first
    await page.fill('#email', 'admin@example.com');
    await page.fill('#password', 'changeme');
    await page.click('#login-submit');
    await page.waitForURL('**/dashboard');

    // Click logout
    await page.click('#logout-button');

    // Should redirect to login
    await page.waitForURL('**/login');
    await expect(page.locator('h1')).toHaveText('MemMesh');
  });

  test('should redirect unauthenticated users to login', async ({ page }) => {
    // Try to access dashboard directly
    await page.goto('/dashboard');

    // Should redirect to login
    await page.waitForURL('**/login');
    await expect(page.locator('#login-submit')).toBeVisible();
  });

  test('should redirect authenticated users from login to dashboard', async ({ page }) => {
    // Login first
    await page.fill('#email', 'admin@example.com');
    await page.fill('#password', 'changeme');
    await page.click('#login-submit');
    await page.waitForURL('**/dashboard');

    // Try to go back to login
    await page.goto('/login');

    // Should redirect back to dashboard
    await page.waitForURL('**/dashboard');
  });
});
```

- [ ] **Step 2: Run the E2E tests**

Make sure both backend and frontend are set up:

```bash
# Terminal 1: Backend
cd backend
make install
make setup
make migrate
make seed-admin
make run &

# Terminal 2: Frontend
cd frontend
npm install
npx playwright install --with-deps chromium

# Run E2E tests
npx playwright test
```

Expected: 7 passed

- [ ] **Step 3: Commit**

```bash
cd frontend
git add tests/
git commit -m "test: add Playwright E2E tests for full auth flow"
```

---

## Group E: Final Integration & Verification

### Task 19: Root-Level Makefile (Orchestration)

**Files:**
- Create: `Makefile` (project root)

- [ ] **Step 1: Create root Makefile**

```makefile
# Makefile (project root) — orchestrates backend + frontend

.PHONY: install setup run test test-e2e clean

install:
	$(MAKE) -C backend install
	cd frontend && npm install

setup:
	$(MAKE) -C backend setup
	$(MAKE) -C backend migrate
	$(MAKE) -C backend seed-admin

run:
	@echo "Starting backend on :8000 and frontend on :5173..."
	@$(MAKE) -C backend run-bg
	@cd frontend && npm run dev

test:
	$(MAKE) -C backend test

test-api:
	$(MAKE) -C backend test

test-e2e:
	cd frontend && npx playwright test

clean:
	$(MAKE) -C backend clean
	cd frontend && rm -rf node_modules .svelte-kit
```

- [ ] **Step 2: Commit**

```bash
git add Makefile
git commit -m "chore: add root-level Makefile for orchestrating backend + frontend"
```

---

### Task 20: Full End-to-End Verification

**Files:**
- No new files

- [ ] **Step 1: Run all backend unit + API tests**

Run: `cd backend && make test`
Expected: 22 tests passed (passwords: 5, JWT: 6, health: 2, auth API: 9)

- [ ] **Step 2: Start the full system**

```bash
# Start backend
cd backend
make run-bg

# Start frontend (in separate terminal)
cd frontend
npm run dev &
```

- [ ] **Step 3: Manual smoke test**

Open http://localhost:5173 in a browser:
1. Should redirect to `/login`
2. Enter `admin@example.com` / `changeme`
3. Click "Sign In"
4. Should redirect to `/dashboard`
5. Should see email `admin@example.com` and role `superadmin`
6. Click "Sign Out"
7. Should redirect to `/login`

- [ ] **Step 4: Run Playwright E2E tests**

Run: `cd frontend && npx playwright test`
Expected: 7 tests passed

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: Phase 1 complete — system bootstrap & authentication"
```

---

## Summary

| Group | Tasks | Tests |
|-------|-------|-------|
| A: Backend Scaffold | 3 tasks (Makefile, config, SQLite) | — |
| B: Backend Auth | 6 tasks (passwords, JWT, middleware, health, auth routes, verify) | 22 unit + API tests |
| C: Frontend Scaffold | 7 tasks (SvelteKit, CSS, types, auth store, layout, login, dashboard) | — |
| D: Frontend E2E | 2 tasks (Playwright config, E2E tests) | 7 E2E tests |
| E: Integration | 2 tasks (root Makefile, full verification) | Full regression |

**Total:** 20 tasks, 29 automated tests, ~15 commits
