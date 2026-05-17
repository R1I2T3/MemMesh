# Auth & Session Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add JWT-based authentication with API key exchange and session context persistence using a local libsql database.

**Architecture:** Single libsql database stores users, API keys, teams, and session messages. Auth is a FastAPI dependency that validates JWTs. Session messages are loaded before each query and saved after streaming completes. Data is scoped by team_id.

**Tech Stack:** Python, FastAPI, libsql (sqlite3), PyJWT, bcrypt, pytest

---

## File Structure

| File | Responsibility |
|------|---------------|
| `db/migrations/001_auth_sessions.sql` | SQL schema for auth and session tables |
| `db/auth_store.py` | User, team, API key CRUD operations against libsql |
| `db/session_store.py` | Session message load/save/cleanup operations |
| `auth/__init__.py` | Package init |
| `auth/jwt.py` | JWT encode/decode utilities |
| `auth/middleware.py` | `require_auth` and `require_admin` FastAPI dependencies |
| `auth/models.py` | Pydantic request/response models for auth endpoints |
| `auth/routes.py` | Auth endpoint handlers (register, token, api-keys, revoke, me) |
| `agentos.py` | Wire up auth routes, protect endpoints, inject session history |
| `pyproject.toml` | Add `pyjwt` and `bcrypt` dependencies |
| `.env.sample` | Document new env vars |
| `tests/unit/test_auth_store.py` | Tests for auth_store CRUD operations |
| `tests/unit/test_session_store.py` | Tests for session_store operations |
| `tests/unit/test_jwt.py` | Tests for JWT encode/decode |
| `tests/unit/test_auth_middleware.py` | Tests for require_auth dependency |
| `tests/unit/test_auth_routes.py` | Tests for auth endpoints |
| `tests/unit/test_query_api.py` | Updated: add auth + session tests |

---

### Task 1: Add dependencies and database migration

**Files:**
- Create: `db/migrations/001_auth_sessions.sql`
- Modify: `pyproject.toml`
- Modify: `.env.sample`

- [ ] **Step 1: Add dependencies to pyproject.toml**

Add to the dependencies list in `pyproject.toml`:

```toml
    "pyjwt>=2.10.1",
    "bcrypt>=4.3.0",
```

- [ ] **Step 2: Create the SQL migration**

Create `db/migrations/001_auth_sessions.sql`:

```sql
CREATE TABLE IF NOT EXISTS teams (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    team_id TEXT REFERENCES teams(id),
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS api_keys (
    key_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    label TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS session_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id),
    team_id TEXT REFERENCES teams(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_session_messages_session
    ON session_messages(session_id, team_id, created_at);
```

- [ ] **Step 3: Update .env.sample**

Add to `.env.sample`:

```
JWT_SECRET=generate-a-random-secret-key
JWT_EXPIRY_MINUTES=15
ADMIN_API_KEY=admin-bootstrap-api-key
SESSION_HISTORY_LIMIT=10
SESSION_TTL_DAYS=30
```

- [ ] **Step 4: Install dependencies**

Run: `uv sync`
Expected: pyjwt and bcrypt installed

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .env.sample db/migrations/001_auth_sessions.sql
git commit -m "feat: add auth dependencies and database migration"
```

---

### Task 2: Create auth_store module

**Files:**
- Create: `db/auth_store.py`
- Test: `tests/unit/test_auth_store.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_auth_store.py`:

```python
import pytest
import os
import tempfile
import sqlite3

from db.auth_store import AuthStore


@pytest.fixture
def auth_store():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    store = AuthStore(path)
    yield store
    store.close()
    os.unlink(path)


def test_create_team(auth_store):
    team_id = auth_store.create_team("Team Alpha")
    assert team_id is not None
    team = auth_store.get_team(team_id)
    assert team["name"] == "Team Alpha"


def test_create_user(auth_store):
    team_id = auth_store.create_team("Team Alpha")
    user_id = auth_store.create_user("alice@test.com", "password123", team_id)
    assert user_id is not None
    user = auth_store.get_user_by_email("alice@test.com")
    assert user["email"] == "alice@test.com"
    assert user["team_id"] == team_id
    assert user["is_admin"] is False


def test_create_admin_user(auth_store):
    user_id = auth_store.create_user("admin@test.com", "adminpass", is_admin=True)
    user = auth_store.get_user_by_email("admin@test.com")
    assert user["is_admin"] is True
    assert user["team_id"] is None


def test_verify_password_correct(auth_store):
    user_id = auth_store.create_user("bob@test.com", "secret")
    assert auth_store.verify_password(user_id, "secret") is True


def test_verify_password_incorrect(auth_store):
    user_id = auth_store.create_user("bob@test.com", "secret")
    assert auth_store.verify_password(user_id, "wrong") is False


def test_create_api_key(auth_store):
    user_id = auth_store.create_user("carol@test.com", "pass")
    raw_key, key_hash = auth_store.create_api_key(user_id, "my-key")
    assert raw_key is not None
    assert key_hash is not None
    assert auth_store.validate_api_key(raw_key) is not None


def test_validate_api_key_returns_user(auth_store):
    user_id = auth_store.create_user("dave@test.com", "pass")
    raw_key, _ = auth_store.create_api_key(user_id, "key")
    user = auth_store.validate_api_key(raw_key)
    assert user["id"] == user_id


def test_revoke_api_key(auth_store):
    user_id = auth_store.create_user("eve@test.com", "pass")
    raw_key, key_hash = auth_store.create_api_key(user_id, "key")
    auth_store.revoke_api_key(key_hash)
    assert auth_store.validate_api_key(raw_key) is None


def test_duplicate_email_raises(auth_store):
    auth_store.create_user("dup@test.com", "pass")
    with pytest.raises(Exception):
        auth_store.create_user("dup@test.com", "pass2")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_auth_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'db.auth_store'`

- [ ] **Step 3: Write the implementation**

Create `db/auth_store.py`:

```python
import os
import sqlite3
import uuid
import bcrypt
from pathlib import Path
from typing import Optional


class AuthStore:
    def __init__(self, db_path: str = "data/memmesh.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._run_migrations()

    def _run_migrations(self):
        migration_path = Path(__file__).parent / "migrations" / "001_auth_sessions.sql"
        if migration_path.exists():
            sql = migration_path.read_text()
            self.conn.executescript(sql)
            self.conn.commit()

    def close(self):
        self.conn.close()

    def create_team(self, name: str) -> str:
        team_id = str(uuid.uuid4())
        self.conn.execute("INSERT INTO teams (id, name) VALUES (?, ?)", (team_id, name))
        self.conn.commit()
        return team_id

    def get_team(self, team_id: str) -> Optional[dict]:
        row = self.conn.execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone()
        return dict(row) if row else None

    def create_user(self, email: str, password: str, team_id: Optional[str] = None, is_admin: bool = False) -> str:
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user_id = str(uuid.uuid4())
        self.conn.execute(
            "INSERT INTO users (id, email, password_hash, team_id, is_admin) VALUES (?, ?, ?, ?, ?)",
            (user_id, email, password_hash, team_id, is_admin),
        )
        self.conn.commit()
        return user_id

    def get_user_by_email(self, email: str) -> Optional[dict]:
        row = self.conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None

    def get_user_by_id(self, user_id: str) -> Optional[dict]:
        row = self.conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    def verify_password(self, user_id: str, password: str) -> bool:
        user = self.get_user_by_id(user_id)
        if not user:
            return False
        return bcrypt.checkpw(password.encode(), user["password_hash"].encode())

    def create_api_key(self, user_id: str, label: Optional[str] = None) -> tuple[str, str]:
        raw_key = str(uuid.uuid4())
        key_hash = bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode()
        self.conn.execute(
            "INSERT INTO api_keys (key_hash, user_id, label) VALUES (?, ?, ?)",
            (key_hash, user_id, label),
        )
        self.conn.commit()
        return raw_key, key_hash

    def validate_api_key(self, raw_key: str) -> Optional[dict]:
        rows = self.conn.execute(
            """
            SELECT u.* FROM api_keys k
            JOIN users u ON k.user_id = u.id
            WHERE k.revoked_at IS NULL
            """
        ).fetchall()
        for row in rows:
            if bcrypt.checkpw(raw_key.encode(), row["key_hash"].encode()):
                return dict(row)
        return None

    def revoke_api_key(self, key_hash: str):
        self.conn.execute(
            "UPDATE api_keys SET revoked_at = CURRENT_TIMESTAMP WHERE key_hash = ?",
            (key_hash,),
        )
        self.conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_auth_store.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add db/auth_store.py tests/unit/test_auth_store.py
git commit -m "feat: add AuthStore with user, team, and API key management"
```

---

### Task 3: Create session_store module

**Files:**
- Create: `db/session_store.py`
- Test: `tests/unit/test_session_store.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_session_store.py`:

```python
import pytest
import os
import tempfile

from db.session_store import SessionStore


@pytest.fixture
def session_store():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    store = SessionStore(path)
    yield store
    store.close()
    os.unlink(path)


def test_save_and_load_messages(session_store):
    session_store.save_message("sess-1", "user-1", "team-1", "user", "Hello")
    session_store.save_message("sess-1", "user-1", "team-1", "assistant", "Hi there")

    messages = session_store.get_session_history("sess-1", "team-1", limit=10)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "Hi there"


def test_respects_limit(session_store):
    for i in range(15):
        session_store.save_message("sess-1", "user-1", "team-1", "user", f"msg-{i}")

    messages = session_store.get_session_history("sess-1", "team-1", limit=5)
    assert len(messages) == 5
    assert messages[0]["content"] == "msg-10"


def test_filters_by_team(session_store):
    session_store.save_message("sess-1", "user-1", "team-1", "user", "team1 msg")
    session_store.save_message("sess-1", "user-2", "team-2", "user", "team2 msg")

    messages = session_store.get_session_history("sess-1", "team-1", limit=10)
    assert len(messages) == 1
    assert messages[0]["content"] == "team1 msg"


def test_empty_session_returns_empty(session_store):
    messages = session_store.get_session_history("nonexistent", "team-1", limit=10)
    assert messages == []


def test_cleanup_old_messages(session_store):
    session_store.save_message("sess-1", "user-1", "team-1", "user", "old msg")
    session_store.conn.execute(
        "UPDATE session_messages SET created_at = datetime('now', '-60 days')"
    )
    session_store.conn.commit()

    session_store.save_message("sess-1", "user-1", "team-1", "user", "new msg")

    session_store.cleanup_expired(days=30)

    messages = session_store.get_session_history("sess-1", "team-1", limit=10)
    assert len(messages) == 1
    assert messages[0]["content"] == "new msg"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_session_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'db.session_store'`

- [ ] **Step 3: Write the implementation**

Create `db/session_store.py`:

```python
import os
import sqlite3
from pathlib import Path
from typing import Optional


class SessionStore:
    def __init__(self, db_path: str = "data/memmesh.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def _ensure_schema(self):
        migration_path = Path(__file__).parent / "migrations" / "001_auth_sessions.sql"
        if migration_path.exists():
            sql = migration_path.read_text()
            self.conn.executescript(sql)
            self.conn.commit()

    def close(self):
        self.conn.close()

    def save_message(self, session_id: str, user_id: str, team_id: Optional[str], role: str, content: str):
        self.conn.execute(
            "INSERT INTO session_messages (session_id, user_id, team_id, role, content) VALUES (?, ?, ?, ?, ?)",
            (session_id, user_id, team_id, role, content),
        )
        self.conn.commit()

    def get_session_history(self, session_id: str, team_id: str, limit: int = 10) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT * FROM session_messages
            WHERE session_id = ? AND team_id = ?
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (session_id, team_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def cleanup_expired(self, days: int = 30):
        self.conn.execute(
            "DELETE FROM session_messages WHERE created_at < datetime('now', ?)",
            (f"-{days} days",),
        )
        self.conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_session_store.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add db/session_store.py tests/unit/test_session_store.py
git commit -m "feat: add SessionStore for session message persistence"
```

---

### Task 4: Create JWT utilities

**Files:**
- Create: `auth/jwt.py`
- Test: `tests/unit/test_jwt.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_jwt.py`:

```python
import pytest
import time
from auth.jwt import encode_jwt, decode_jwt, JWTError


SECRET = "test-secret-key"


def test_encode_and_decode_jwt():
    payload = {"sub": "user-1", "email": "a@b.com", "team_id": "team-1", "is_admin": False}
    token = encode_jwt(payload, secret=SECRET, expires_minutes=15)
    decoded = decode_jwt(token, secret=SECRET)
    assert decoded["sub"] == "user-1"
    assert decoded["email"] == "a@b.com"
    assert decoded["team_id"] == "team-1"
    assert decoded["is_admin"] is False


def test_expired_jwt_raises():
    payload = {"sub": "user-1"}
    token = encode_jwt(payload, secret=SECRET, expires_minutes=0)
    time.sleep(1)
    with pytest.raises(JWTError, match="expired"):
        decode_jwt(token, secret=SECRET)


def test_invalid_signature_raises():
    payload = {"sub": "user-1"}
    token = encode_jwt(payload, secret=SECRET, expires_minutes=15)
    with pytest.raises(JWTError, match="invalid"):
        decode_jwt(token, secret="wrong-secret")


def test_malformed_token_raises():
    with pytest.raises(JWTError):
        decode_jwt("not.a.valid.token", secret=SECRET)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_jwt.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'auth'`

- [ ] **Step 3: Write the implementation**

Create `auth/__init__.py` (empty file).

Create `auth/jwt.py`:

```python
import jwt
from datetime import datetime, timedelta, timezone


class JWTError(Exception):
    pass


def encode_jwt(payload: dict, secret: str, expires_minutes: int = 15) -> str:
    now = datetime.now(timezone.utc)
    to_encode = payload.copy()
    to_encode["exp"] = now + timedelta(minutes=expires_minutes)
    to_encode["iat"] = now
    return jwt.encode(to_encode, secret, algorithm="HS256")


def decode_jwt(token: str, secret: str) -> dict:
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise JWTError("Token has expired")
    except jwt.InvalidTokenError:
        raise JWTError("Invalid token")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_jwt.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add auth/__init__.py auth/jwt.py tests/unit/test_jwt.py
git commit -m "feat: add JWT encode/decode utilities"
```

---

### Task 5: Create auth middleware

**Files:**
- Create: `auth/middleware.py`
- Test: `tests/unit/test_auth_middleware.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_auth_middleware.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient

from auth.middleware import require_auth, require_admin


@pytest.fixture
def app():
    app = FastAPI()

    @app.get("/protected")
    def protected(user: dict = Depends(require_auth)):
        return {"user_id": user["id"]}

    @app.get("/admin-only")
    def admin_endpoint(user: dict = Depends(require_admin)):
        return {"admin": True}

    return app


def test_valid_jwt_returns_user(app):
    with patch("auth.middleware.decode_jwt") as mock_decode:
        mock_decode.return_value = {
            "sub": "user-1",
            "email": "a@b.com",
            "team_id": "team-1",
            "is_admin": False,
        }
        with patch("auth.middleware.get_auth_store") as mock_store:
            mock_store.return_value.get_user_by_id.return_value = {
                "id": "user-1",
                "email": "a@b.com",
                "team_id": "team-1",
                "is_admin": False,
            }
            client = TestClient(app)
            r = client.get("/protected", headers={"Authorization": "Bearer faketoken"})
            assert r.status_code == 200
            assert r.json()["user_id"] == "user-1"


def test_missing_auth_header_returns_401(app):
    client = TestClient(app)
    r = client.get("/protected")
    assert r.status_code == 401


def test_invalid_jwt_returns_401(app):
    with patch("auth.middleware.decode_jwt", side_effect=Exception("invalid")):
        client = TestClient(app)
        r = client.get("/protected", headers={"Authorization": "Bearer badtoken"})
        assert r.status_code == 401


def test_non_admin_accessing_admin_endpoint_returns_403(app):
    with patch("auth.middleware.decode_jwt") as mock_decode:
        mock_decode.return_value = {
            "sub": "user-1",
            "email": "a@b.com",
            "team_id": "team-1",
            "is_admin": False,
        }
        with patch("auth.middleware.get_auth_store") as mock_store:
            mock_store.return_value.get_user_by_id.return_value = {
                "id": "user-1",
                "is_admin": False,
            }
            client = TestClient(app)
            r = client.get("/admin-only", headers={"Authorization": "Bearer faketoken"})
            assert r.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_auth_middleware.py -v`
Expected: FAIL — `ModuleNotFoundError` or import errors

- [ ] **Step 3: Write the implementation**

Create `auth/middleware.py`:

```python
import os
from fastapi import Header, HTTPException, Request

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


def require_admin(authorization: str = Header(None)) -> dict:
    user = require_auth(authorization)
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_auth_middleware.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add auth/middleware.py tests/unit/test_auth_middleware.py
git commit -m "feat: add auth middleware with require_auth and require_admin"
```

---

### Task 6: Create auth models and routes

**Files:**
- Create: `auth/models.py`
- Create: `auth/routes.py`
- Test: `tests/unit/test_auth_routes.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_auth_routes.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from auth.routes import router


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def test_register_creates_user(client):
    with patch("auth.routes.get_auth_store") as mock_store:
        store = MagicMock()
        store.get_user_by_email.return_value = None
        store.create_team.return_value = "team-1"
        store.create_user.return_value = "user-1"
        mock_store.return_value = store

        with patch("auth.routes.validate_admin_api_key", return_value=True):
            r = client.post(
                "/auth/register",
                json={"email": "new@test.com", "password": "secret", "team_name": "Team X"},
            )
            assert r.status_code == 201
            assert "user_id" in r.json()


def test_register_missing_admin_key_returns_401(client):
    r = client.post("/auth/register", json={"email": "a@b.com", "password": "x"})
    assert r.status_code == 401


def test_token_exchange_returns_jwt(client):
    with patch("auth.routes.get_auth_store") as mock_store:
        store = MagicMock()
        store.validate_api_key.return_value = {
            "id": "user-1",
            "email": "a@b.com",
            "team_id": "team-1",
            "is_admin": False,
        }
        mock_store.return_value = store

        with patch("auth.routes.encode_jwt", return_value="faketoken"):
            r = client.post("/auth/token", headers={"X-API-Key": "some-api-key"})
            assert r.status_code == 200
            assert "token" in r.json()


def test_token_invalid_api_key_returns_401(client):
    with patch("auth.routes.get_auth_store") as mock_store:
        mock_store.return_value.validate_api_key.return_value = None
        r = client.post("/auth/token", headers={"X-API-Key": "bad-key"})
        assert r.status_code == 401


def test_create_api_key_returns_plaintext(client):
    with patch("auth.middleware.require_auth") as mock_auth:
        mock_auth.return_value = {"id": "user-1", "team_id": "team-1"}

        with patch("auth.routes.get_auth_store") as mock_store:
            store = MagicMock()
            store.create_api_key.return_value = ("raw-key-123", "hash-456")
            mock_store.return_value = store

            r = client.post("/auth/api-keys", json={"label": "my-key"})
            assert r.status_code == 201
            assert "api_key" in r.json()


def test_me_returns_current_user(client):
    with patch("auth.middleware.require_auth") as mock_auth:
        mock_auth.return_value = {
            "id": "user-1",
            "email": "a@b.com",
            "team_id": "team-1",
            "is_admin": False,
        }

        r = client.get("/auth/me")
        assert r.status_code == 200
        assert r.json()["email"] == "a@b.com"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_auth_routes.py -v`
Expected: FAIL — import errors

- [ ] **Step 3: Write auth models**

Create `auth/models.py`:

```python
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


class TokenRequest(BaseModel):
    pass


class TokenResponse(BaseModel):
    token: str
    expires_in: int


class CreateApiKeyRequest(BaseModel):
    label: Optional[str] = None


class CreateApiKeyResponse(BaseModel):
    api_key: str


class RevokeApiKeyRequest(BaseModel):
    key_hash: str


class UserResponse(BaseModel):
    id: str
    email: str
    team_id: Optional[str]
    is_admin: bool
```

- [ ] **Step 4: Write auth routes**

Create `auth/routes.py`:

```python
import os
from fastapi import APIRouter, Depends, Header, HTTPException

from auth.jwt import encode_jwt
from auth.middleware import require_auth
from auth.models import (
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    CreateApiKeyRequest,
    CreateApiKeyResponse,
    UserResponse,
)
from db.auth_store import AuthStore

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_store() -> AuthStore:
    db_path = os.getenv("AUTH_DB_PATH", "data/memmesh.db")
    return AuthStore(db_path)


def validate_admin_api_key(x_api_key: str = Header(None)) -> bool:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Admin API key required")
    admin_key = os.getenv("ADMIN_API_KEY", "")
    if not admin_key or x_api_key != admin_key:
        raise HTTPException(status_code=401, detail="Invalid admin API key")
    return True


@router.post("/register", status_code=201, response_model=RegisterResponse)
def register(req: RegisterRequest, _: bool = Depends(validate_admin_api_key)):
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

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_auth_routes.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add auth/models.py auth/routes.py tests/unit/test_auth_routes.py
git commit -m "feat: add auth endpoints (register, token, api-keys, revoke, me)"
```

---

### Task 7: Wire auth into agentos.py and protect endpoints

**Files:**
- Modify: `agentos.py`
- Test: `tests/unit/test_query_api.py` (updated)

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/test_query_api.py` — append these tests at the end of the file:

```python
@pytest.mark.unit
def test_query_without_auth_returns_401(client_no_auth):
    r = client_no_auth.post("/query", json={"message": "hello"})
    assert r.status_code == 401


@pytest.mark.unit
def test_memory_search_without_auth_returns_401(client_no_auth):
    r = client_no_auth.get("/memory/search", params={"query": "test"})
    assert r.status_code == 401


@pytest.mark.unit
def test_memory_graph_without_auth_returns_401(client_no_auth):
    r = client_no_auth.get("/memory/graph", params={"entity": "test"})
    assert r.status_code == 401


@pytest.mark.unit
def test_health_without_auth_returns_200(client_no_auth):
    r = client_no_auth.get("/health")
    assert r.status_code == 200
```

- [ ] **Step 2: Modify agentos.py to add auth**

Replace the imports section in `agentos.py` (lines 1-27) with:

```python
import json
import os
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from celery.result import AsyncResult
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from db.graph_store import GraphStore
from db.vector_store import VectorStore
from db.dependencies import (
    get_graph_store,
    get_vector_store,
    build_rag_team_with_stores,
    set_graph_store_ctx,
    set_vector_store_ctx,
    set_citations_ctx,
    get_citations_ctx,
)
from db.session_store import SessionStore
from workers.celery_app import celery_app
from utils.observability import start_request, log_step, end_request, _configure_json_logging
from utils.input_validator import validate_query
from auth.middleware import require_auth
from auth.routes import router as auth_router
```

Add session store to lifespan in `agentos.py` — modify the lifespan function (lines 30-55):

```python
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

    app.state.graph_store = graph_store
    app.state.vector_store = vector_store
    app.state.session_store = session_store

    set_graph_store_ctx(graph_store)
    set_vector_store_ctx(vector_store)

    yield

    graph_store.close()
    session_store.close()
```

Add the auth router after CORS middleware (after line 65):

```python
app.include_router(auth_router)
```

Protect the `/query` endpoint — modify the function signature (line 78-83):

```python
@app.post("/query")
async def query(
    req: QueryRequest,
    user: dict = Depends(require_auth),
    graph_store: GraphStore = Depends(get_graph_store),
    vector_store: VectorStore = Depends(get_vector_store),
):
```

Protect `/memory/search` — modify (line 129-133):

```python
@app.get("/memory/search")
def memory_search(
    query: str,
    user: dict = Depends(require_auth),
    vector_store: VectorStore = Depends(get_vector_store),
):
```

Protect `/memory/graph` — modify (line 146-150):

```python
@app.get("/memory/graph")
def memory_graph(
    entity: str,
    user: dict = Depends(require_auth),
    graph_store: GraphStore = Depends(get_graph_store),
):
```

- [ ] **Step 3: Run tests to verify existing tests still pass**

Run: `uv run pytest tests/unit/test_query_api.py -v`
Expected: Existing tests may fail due to auth requirement — this is expected. The existing test fixtures need auth headers. We'll fix in the next step by updating the fixture.

- [ ] **Step 4: Update the existing test fixture to provide auth**

The existing `client` fixture in `tests/unit/test_query_api.py` (lines 42-140) rebuilds the app. Replace the entire fixture with this updated version that includes auth mocking:

```python
@pytest.fixture(scope="module")
def client():
    import sys
    mods_to_remove = [m for m in sys.modules if m == "agentos" or m.startswith("agentos.")]
    for mod in mods_to_remove:
        del sys.modules[mod]

    mock_graph_store = MagicMock()
    mock_vector_store = MagicMock()
    mock_agent = MagicMock()
    mock_agent.arun = mock_arun_stream

    mock_celery_app = MagicMock()
    mock_async_result = MagicMock()

    celery_mod = MagicMock()
    celery_result_mod = MagicMock()
    celery_result_mod.AsyncResult = mock_async_result
    workers_mod = MagicMock()
    workers_celery_app_mod = MagicMock()
    workers_celery_app_mod.celery_app = mock_celery_app

    with patch.dict(sys.modules, {
        "celery": celery_mod,
        "celery.result": celery_result_mod,
        "workers": workers_mod,
        "workers.celery_app": workers_celery_app_mod,
    }):
        with patch("agentos.GraphStore", return_value=mock_graph_store):
            with patch("agentos.VectorStore", return_value=mock_vector_store):
                with patch("agentos.build_rag_team_with_stores", return_value=mock_agent):
                    with patch("auth.middleware.decode_jwt") as mock_jwt:
                        mock_jwt.return_value = {
                            "sub": "user-1",
                            "email": "a@b.com",
                            "team_id": "team-1",
                            "is_admin": False,
                        }
                    with patch("auth.middleware.get_auth_store") as mock_auth_store:
                        mock_auth_store.return_value.get_user_by_id.return_value = {
                            "id": "user-1",
                            "email": "a@b.com",
                            "team_id": "team-1",
                            "is_admin": False,
                        }
                    from agentos import app
                    with TestClient(app) as test_client:
                        yield test_client
```

Also add the `client_no_auth` fixture for testing 401 responses:

```python
@pytest.fixture(scope="module")
def client_no_auth():
    """Test client without auth for testing 401 responses."""
    import sys
    mods_to_remove = [m for m in sys.modules if m == "agentos" or m.startswith("agentos.")]
    for mod in mods_to_remove:
        del sys.modules[mod]

    mock_graph_store = MagicMock()
    mock_vector_store = MagicMock()
    mock_agent = MagicMock()
    mock_agent.arun = mock_arun_stream

    mock_celery_app = MagicMock()
    mock_async_result = MagicMock()

    celery_mod = MagicMock()
    celery_result_mod = MagicMock()
    celery_result_mod.AsyncResult = mock_async_result
    workers_mod = MagicMock()
    workers_celery_app_mod = MagicMock()
    workers_celery_app_mod.celery_app = mock_celery_app

    with patch.dict(sys.modules, {
        "celery": celery_mod,
        "celery.result": celery_result_mod,
        "workers": workers_mod,
        "workers.celery_app": workers_celery_app_mod,
    }):
        with patch("agentos.GraphStore", return_value=mock_graph_store):
            with patch("agentos.VectorStore", return_value=mock_vector_store):
                with patch("agentos.build_rag_team_with_stores", return_value=mock_agent):
                    with patch("auth.middleware.decode_jwt") as mock_jwt:
                        mock_jwt.side_effect = Exception("invalid")
                        from agentos import app
                        with TestClient(app) as test_client:
                            yield test_client
```

- [ ] **Step 5: Run tests to verify**

Run: `uv run pytest tests/unit/test_query_api.py -v`
Expected: All tests pass, including new auth tests

- [ ] **Step 6: Commit**

```bash
git add agentos.py tests/unit/test_query_api.py
git commit -m "feat: protect endpoints with auth middleware, wire auth routes"
```

---

### Task 8: Implement session memory injection in /query

**Files:**
- Modify: `agentos.py`
- Test: `tests/unit/test_query_api.py` (updated)

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/test_query_api.py`:

```python
@pytest.mark.unit
def test_query_loads_session_history(client_with_session):
    """The /query endpoint should load prior messages and pass them to the agent."""
    r = client_with_session.post(
        "/query",
        json={"message": "Follow up question", "session_id": "sess-1"},
    )
    assert r.status_code == 200
    # Verify the agent received history — check that arun was called with history kwarg
    lines = [line for line in r.iter_lines() if line.strip()]
    assert len(lines) >= 1


@pytest.mark.unit
def test_query_saves_messages_to_session(client_with_session):
    """The /query endpoint should save the user message and response to the session store."""
    r = client_with_session.post(
        "/query",
        json={"message": "New question", "session_id": "sess-2"},
    )
    assert r.status_code == 200
```

- [ ] **Step 2: Add session history injection to /query endpoint**

Modify the `/query` endpoint in `agentos.py`. The full endpoint function should be:

```python
@app.post("/query")
async def query(
    req: QueryRequest,
    user: dict = Depends(require_auth),
    graph_store: GraphStore = Depends(get_graph_store),
    vector_store: VectorStore = Depends(get_vector_store),
):
    req.message = validate_query(req.message)
    ctx = start_request("POST", "/query")
    set_citations_ctx([])

    try:
        with log_step(ctx, "multi_hop_pre_retrieval"):
            rag_team = build_rag_team_with_stores(graph_store, vector_store)

        # Load session history
        session_store: SessionStore = graph_store  # type: ignore - accessed via app.state
        history = []
        if req.session_id and user.get("team_id"):
            session_store = graph_team_store()  # will be set below
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

                # Save messages to session store
                if req.session_id and user.get("team_id"):
                    session_store = get_session_store_from_ctx()
                    session_store.save_message(req.session_id, user["id"], user.get("team_id"), "user", req.message)
                    response_text = "".join([e.content for e in full_response if hasattr(e, "content") and e.content])
                    if response_text:
                        session_store.save_message(req.session_id, user["id"], user.get("team_id"), "assistant", response_text)

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

Wait — this has a problem. The session_store needs to be accessible. Let me use a cleaner approach by adding it as a FastAPI dependency. Let me rewrite the full `/query` endpoint properly:

Replace the entire `/query` endpoint in `agentos.py` with:

```python
def get_session_store(request: Request) -> SessionStore:
    return request.app.state.session_store


@app.post("/query")
async def query(
    req: QueryRequest,
    user: dict = Depends(require_auth),
    graph_store: GraphStore = Depends(get_graph_store),
    vector_store: VectorStore = Depends(get_vector_store),
    session_store: SessionStore = Depends(get_session_store),
):
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

Also need to add `Request` to the fastapi imports at the top of `agentos.py`:

```python
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile, Request
```

- [ ] **Step 3: Add the fixture for session tests**

Add to `tests/unit/test_query_api.py`:

```python
@pytest.fixture(scope="module")
def client_with_session():
    import sys
    from contextlib import asynccontextmanager
    mods_to_remove = [m for m in sys.modules if m == "agentos" or m.startswith("agentos.")]
    for mod in mods_to_remove:
        del sys.modules[mod]

    mock_graph_store = MagicMock()
    mock_vector_store = MagicMock()
    mock_session_store = MagicMock()
    mock_session_store.get_session_history.return_value = [
        {"role": "user", "content": "Previous question"},
        {"role": "assistant", "content": "Previous answer"},
    ]
    mock_agent = MagicMock()
    mock_agent.arun = mock_arun_stream

    mock_celery_app = MagicMock()
    mock_async_result = MagicMock()

    celery_mod = MagicMock()
    celery_result_mod = MagicMock()
    celery_result_mod.AsyncResult = mock_async_result
    workers_mod = MagicMock()
    workers_celery_app_mod = MagicMock()
    workers_celery_app_mod.celery_app = mock_celery_app

    @asynccontextmanager
    async def mock_lifespan(app):
        app.state.graph_store = mock_graph_store
        app.state.vector_store = mock_vector_store
        app.state.session_store = mock_session_store
        yield

    with patch.dict(sys.modules, {
        "celery": celery_mod,
        "celery.result": celery_result_mod,
        "workers": workers_mod,
        "workers.celery_app": workers_celery_app_mod,
    }):
        with patch("agentos.GraphStore", return_value=mock_graph_store):
            with patch("agentos.VectorStore", return_value=mock_vector_store):
                with patch("agentos.build_rag_team_with_stores", return_value=mock_agent):
                    with patch("auth.middleware.decode_jwt") as mock_jwt:
                        mock_jwt.return_value = {
                            "sub": "user-1",
                            "email": "a@b.com",
                            "team_id": "team-1",
                            "is_admin": False,
                        }
                    with patch("auth.middleware.get_auth_store") as mock_auth_store:
                        mock_auth_store.return_value.get_user_by_id.return_value = {
                            "id": "user-1",
                            "email": "a@b.com",
                            "team_id": "team-1",
                            "is_admin": False,
                        }
                    with patch("agentos.lifespan", mock_lifespan):
                        from agentos import app
                        with TestClient(app) as test_client:
                            yield test_client
```

- [ ] **Step 4: Run tests to verify**

Run: `uv run pytest tests/unit/test_query_api.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add agentos.py tests/unit/test_query_api.py
git commit -m "feat: inject session history into query and save messages after response"
```

---

### Task 9: Protect ingest endpoints and add team scoping to ingestion

**Files:**
- Modify: `agentos.py`
- Test: `tests/unit/test_ingestion_api.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/test_ingestion_api.py`:

```python
@pytest.mark.unit
def test_ingest_without_auth_returns_401(client_no_auth_ingest):
    r = client_no_auth_ingest.post("/ingest", files={"file": ("test.txt", b"content")})
    assert r.status_code == 401


@pytest.mark.unit
def test_ingest_status_without_auth_returns_401(client_no_auth_ingest):
    r = client_no_auth_ingest.get("/ingest/some-task-id")
    assert r.status_code == 401
```

- [ ] **Step 2: Protect ingest endpoints**

In `agentos.py`, modify the `/ingest` endpoint signature:

```python
@app.post("/ingest")
async def ingest(
    file: UploadFile = File(...),
    multimodal: bool = Query(False),
    user: dict = Depends(require_auth),
):
```

Modify the `/ingest/{task_id}` endpoint signature:

```python
@app.get("/ingest/{task_id}")
def ingest_status(task_id: str, user: dict = Depends(require_auth)):
```

- [ ] **Step 3: Run tests to verify**

Run: `uv run pytest tests/unit/test_ingestion_api.py -v`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add agentos.py tests/unit/test_ingestion_api.py
git commit -m "feat: protect ingest endpoints with auth"
```

---

### Task 10: Add session cleanup on startup

**Files:**
- Modify: `agentos.py`
- Test: `tests/unit/test_api.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_api.py`:

```python
@pytest.mark.unit
def test_session_cleanup_runs_on_startup(client):
    """Session cleanup should run during lifespan startup."""
    with patch("agentos.SessionStore") as mock_store_cls:
        mock_store = MagicMock()
        mock_store_cls.return_value = mock_store

        with patch("agentos.GraphStore"):
            with patch("agentos.VectorStore"):
                with patch("agentos.build_rag_team_with_stores"):
                    from agentos import app
                    with TestClient(app) as test_client:
                        mock_store.cleanup_expired.assert_called_once()
```

- [ ] **Step 2: Add cleanup to lifespan**

Modify the lifespan function in `agentos.py` to include cleanup:

```python
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
```

- [ ] **Step 3: Run tests to verify**

Run: `uv run pytest tests/unit/test_api.py -v`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add agentos.py tests/unit/test_api.py
git commit -m "feat: run session cleanup on server startup"
```

---

### Task 11: Final verification and linting

**Files:**
- All modified files

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/unit -v`
Expected: All unit tests pass

- [ ] **Step 2: Verify no import errors**

Run: `uv run python -c "from agentos import app; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Verify migration runs cleanly**

Run: `uv run python -c "from db.auth_store import AuthStore; s = AuthStore(':memory:'); print('OK'); s.close()"`
Expected: `OK`

- [ ] **Step 4: Commit any remaining changes**

```bash
git status
git add -A
git commit -m "chore: final verification and cleanup"
```
