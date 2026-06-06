# Phase 2 — Teams & User Management: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement team-scoped data containerization and multi-team user memberships, including role-based access controls (RBAC) on both global and per-team levels, backend API endpoints, and a SvelteKit-based admin interface.

**Architecture:** SQLite schemas are extended via a migration creating `teams` and `team_members` tables. PER-TEAM role hierarchy is introduced: Admin (global), Superadmin (global), Team Lead (per-team), and User (per-team). Authentication middleware is updated to decode JWTs carrying team memberships and enforce fine-grained RBAC permissions. The frontend features specialized Admin routes to manage teams, users, and roles.

**Tech Stack:** Python 3.11+, FastAPI, SQLite, SvelteKit, Playwright, TailwindCSS

---

## Scope Note

This plan builds directly on **Phase 1**. It does not implement document ingestion or RAG pipelines; it focuses entirely on the multi-tenant architecture and administrative user controls required by subsequent stages.

---

## File Structure

### Backend New/Modified Files

```
backend/
├── db/
│   └── migrations/
│       └── 002_teams.sql                       # Create: Schema migrations for teams
├── auth/
│   ├── jwt.py                                  # Modify: Inject team memberships into JWT
│   └── middleware.py                           # Modify: Add Role-based dependencies
├── api/
│   └── routes/
│       ├── teams.py                            # Create: Team CRUD and membership APIs
│       └── auth.py                             # Modify: Update login to query team memberships
├── tests/
│   ├── test_teams_api.py                       # Create: Integration tests for team RBAC
│   └── conftest.py                             # Modify: Add team fixtures
```

### Frontend New/Modified Files

```
frontend/
├── src/
│   ├── lib/
│   │   ├── types.ts                            # Modify: Add Team and Membership interfaces
│   │   └── api.ts                              # Modify: Add teams and members API calls
│   └── routes/
│       ├── admin/
│       │   ├── teams/
│       │   │   └── +page.svelte                # Create: Teams dashboard (admin-only)
│       │   └── users/
│       │       └── +page.svelte                # Create: User roles dashboard (admin-only)
│       └── dashboard/
│           └── +page.svelte                    # Modify: Add team selector and context
```

---

## Group A: Backend Schema & Auth Refactoring

### Task 1: SQLite Teams Database Migration

**Files:**

- Create: `backend/db/migrations/002_teams.sql`

- [ ] **Step 1: Write migration SQL**

Create `backend/db/migrations/002_teams.sql`:

```sql
-- backend/db/migrations/002_teams.sql
CREATE TABLE teams (
    team_id     TEXT PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at  DATETIME NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE team_members (
    membership_id TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    team_id       TEXT NOT NULL REFERENCES teams(team_id) ON DELETE CASCADE,
    role          TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'lead')),
    added_by      TEXT REFERENCES users(user_id) ON DELETE SET NULL,
    added_at      DATETIME NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, team_id)
);
```

- [ ] **Step 2: Verify migration applies**

Run: `cd backend && make reset-db`
Expected: Database is reset and `001_init.sql` and `002_teams.sql` are applied successfully.

- [ ] **Step 3: Commit**

```bash
git add db/migrations/002_teams.sql
git commit -m "migration: add teams and team_members SQLite schema"
```

---

### Task 2: JWT & Login Refactoring

**Files:**

- Modify: `backend/auth/jwt.py`
- Modify: `backend/api/routes/auth.py`
- Modify: `backend/tests/test_jwt.py`

- [ ] **Step 1: Update JWT module**

Modify `backend/auth/jwt.py` to embed team memberships:

```python
# backend/auth/jwt.py
import datetime
from typing import Optional, List, Dict
from jose import jwt, JWTError
from config import settings

def create_access_token(
    user_id: str,
    global_role: str,
    team_memberships: List[Dict[str, str]],
    expires_delta: Optional[datetime.timedelta] = None
) -> str:
    """Create a signed JWT access token carrying the user's identities and team scopes."""
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=settings.jwt_expiry_minutes)

    to_encode = {
        "user_id": user_id,
        "role": global_role,
        "team_memberships": team_memberships,
        "exp": expire
    }
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm="HS256")
    return encoded_jwt

def verify_token(token: str) -> Optional[dict]:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return payload
    except JWTError:
        return None
```

- [ ] **Step 2: Update Auth Login Route**

Modify `backend/api/routes/auth.py` to fetch memberships from database on login:

```python
# backend/api/routes/auth.py (partial diff)
# Ensure the login route queries the team memberships for the user:

@router.post("/login", response_model=TokenResponse)
async def login(credentials: LoginRequest):
    conn = get_connection()
    try:
        user = conn.execute(
            "SELECT user_id, email, password_hash, global_role FROM users WHERE email = ?",
            (credentials.email,)
        ).fetchone()

        if user is None or not verify_password(credentials.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        memberships_rows = conn.execute(
            "SELECT team_id, role FROM team_members WHERE user_id = ?",
            (user["user_id"],)
        ).fetchall()

        memberships = [{"team_id": m["team_id"], "role": m["role"]} for m in memberships_rows]

        access_token = create_access_token(
            user_id=user["user_id"],
            global_role=user["global_role"],
            team_memberships=memberships
        )
        refresh_token = create_access_token(
            user_id=user["user_id"],
            global_role=user["global_role"],
            team_memberships=memberships,
            expires_delta=datetime.timedelta(days=7)
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )
    finally:
        conn.close()
```

- [ ] **Step 3: Test JWT payload structure**

Run: `pytest tests/test_jwt.py`
Verify all unit tests pass, and update the tests to mock `team_memberships` parameters.

- [ ] **Step 4: Commit**

```bash
git add auth/jwt.py api/routes/auth.py
git commit -m "feat: embed team memberships into JWT on login"
```

---

### Task 3: RBAC Middleware

**Files:**

- Modify: `backend/auth/middleware.py`

- [ ] **Step 1: Update Auth Middleware**

Implement role enforcement dependency helpers in `backend/auth/middleware.py`:

```python
# backend/auth/middleware.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from auth.jwt import verify_token

security = HTTPBearer()

async def require_auth(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload

def require_global_role(required_roles: list[str]):
    """Returns a dependency checking global roles (e.g. superadmin, admin)."""
    async def dependency(current_user: dict = Depends(require_auth)) -> dict:
        if current_user.get("role") not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    return dependency

def require_team_role(min_role: str):
    """Dependency asserting membership and per-team role permissions."""
    async def dependency(team_id: str, current_user: dict = Depends(require_auth)) -> dict:
        # Global admins bypass team checks
        if current_user.get("role") in ["superadmin", "admin"]:
            return current_user

        memberships = current_user.get("team_memberships", [])
        team_member = next((m for m in memberships if m["team_id"] == team_id), None)

        if not team_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this team"
            )

        if min_role == "lead" and team_member["role"] != "lead":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Team lead permission required"
            )

        return current_user
    return dependency
```

- [ ] **Step 2: Commit**

```bash
git add auth/middleware.py
git commit -m "feat: implement fine-grained global and per-team RBAC middleware"
```

---

## Group B: Teams & Membership CRUD Endpoints

### Task 4: Teams CRUD APIs (Admin only)

**Files:**

- Create: `backend/api/routes/teams.py`
- Modify: `backend/api/server.py`

- [ ] **Step 1: Implement Team CRUD routes**

Create `backend/api/routes/teams.py`:

```python
# backend/api/routes/teams.py
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
import uuid
from db.sqlite import get_connection
from auth.middleware import require_global_role, require_auth, require_team_role

router = APIRouter(prefix="/admin/teams", tags=["admin-teams"])

class TeamCreate(BaseModel):
    name: str
    description: Optional[str] = None

class TeamResponse(BaseModel):
    team_id: str
    name: str
    description: Optional[str]
    created_at: str

@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(body: TeamCreate, current_user: dict = Depends(require_global_role(["superadmin", "admin"]))):
    conn = get_connection()
    try:
        existing = conn.execute("SELECT team_id FROM teams WHERE name = ?", (body.name,)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Team name already exists")

        team_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO teams (team_id, name, description) VALUES (?, ?, ?)",
            (team_id, body.name, body.description)
        )
        conn.commit()
        return TeamResponse(team_id=team_id, name=body.name, description=body.description, created_at="now")
    finally:
        conn.close()

@router.get("", response_model=List[TeamResponse])
async def list_teams(current_user: dict = Depends(require_global_role(["superadmin", "admin"]))):
    conn = get_connection()
    try:
        rows = conn.execute("SELECT team_id, name, description, created_at FROM teams").fetchall()
        return [TeamResponse(team_id=r["team_id"], name=r["name"], description=r["description"], created_at=r["created_at"]) for r in rows]
    finally:
        conn.close()

@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(team_id: str, current_user: dict = Depends(require_global_role(["superadmin", "admin"]))):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM teams WHERE team_id = ?", (team_id,))
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 2: Register teams router in server.py**

Modify `backend/api/server.py` to include router:

```python
from api.routes.teams import router as teams_router
app.include_router(teams_router)
```

- [ ] **Step 3: Commit**

```bash
git add api/routes/teams.py api/server.py
git commit -m "feat: implement administrative Teams CRUD endpoints"
```

---

### Task 5: Member Assignment and Team Lead APIs

**Files:**

- Modify: `backend/api/routes/teams.py`

- [ ] **Step 1: Implement Membership Management**

Add member CRUD endpoints to `backend/api/routes/teams.py`:

```python
# backend/api/routes/teams.py (continued)
from pydantic import Field

class MemberAddRequest(BaseModel):
    user_id: str
    role: str = Field("user", regex="^(user|lead)$")

class MemberResponse(BaseModel):
    user_id: str
    email: str
    role: str

@router.post("/{team_id}/members", status_code=status.HTTP_201_CREATED)
async def add_member(
    team_id: str,
    body: MemberAddRequest,
    current_user: dict = Depends(require_global_role(["superadmin", "admin"]))
):
    conn = get_connection()
    try:
        membership_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO team_members (membership_id, user_id, team_id, role, added_by) "
            "VALUES (?, ?, ?, ?, ?)",
            (membership_id, body.user_id, team_id, body.role, current_user["user_id"])
        )
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=400, detail="User already in team or database error")
    finally:
        conn.close()

@router.delete("/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    team_id: str,
    user_id: str,
    current_user: dict = Depends(require_global_role(["superadmin", "admin"]))
):
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM team_members WHERE team_id = ? AND user_id = ?",
            (team_id, user_id)
        )
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 2: Commit**

```bash
git add api/routes/teams.py
git commit -m "feat: add team members administrative endpoints"
```

---

## Group C: Frontend Viewsions are perfectly spec-compliant.

### Task 6: Admin Management Views

**Files:**

- Create: `frontend/src/routes/admin/teams/+page.svelte`
- Create: `frontend/src/routes/admin/users/+page.svelte`

- [ ] **Step 1: Create Teams Management view**

Create `frontend/src/routes/admin/teams/+page.svelte` with theme classes, a list of teams, and form to create new teams.

- [ ] **Step 2: Create Users Roles view**

Create `frontend/src/routes/admin/users/+page.svelte` listing users and letting admins assign them to teams and assign roles within teams.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/routes/admin/
git commit -m "feat: create Teams and Users role-assignment dashboards in frontend"
```

---

### Task 7: Playwright Integration Tests

**Files:**

- Create: `frontend/tests/e2e/teams.spec.ts`

- [ ] **Step 1: Write team verification test**

Create `frontend/tests/e2e/teams.spec.ts` demonstrating Admin creating a team, adding a user, and verifying permissions.

- [ ] **Step 2: Execute all tests**

Run: `cd frontend && npx playwright test`
Expected: All E2E tests pass.

- [ ] **Step 3: Commit**

```bash
git add frontend/tests/e2e/teams.spec.ts
git commit -m "test: add Playwright E2E team workspace verification flow"
```
