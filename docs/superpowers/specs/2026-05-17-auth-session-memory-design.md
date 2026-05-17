# Auth & Session Memory Design

## Overview

Add JWT-based authentication to protect sensitive endpoints and implement session context persistence across queries using a local libsql database.

## Database Schema

Single libsql database at `data/memmesh.db` with the following tables:

```sql
CREATE TABLE teams (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    team_id TEXT REFERENCES teams(id),
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE api_keys (
    key_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    label TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMP
);

CREATE TABLE session_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id),
    team_id TEXT REFERENCES teams(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_session_messages_session ON session_messages(session_id, team_id, created_at);
```

### Data Scoping

- Each user belongs to one team via `team_id`
- Ingested documents are tagged with `team_id` in both LanceDB (filter column) and Neo4j (edge property)
- Queries filter vector and graph results by the authenticated user's `team_id`
- Admin users (`is_admin = TRUE`) bypass team filtering and see all data
- Session messages are scoped to `(session_id, team_id)` — cross-team session reuse is impossible

## Authentication Flow

### Endpoints

| Method | Path | Auth Required | Description |
|--------|------|---------------|-------------|
| POST | `/auth/register` | Admin API key | Create a new user |
| POST | `/auth/api-keys` | JWT | Generate a new API key for the authenticated user |
| POST | `/auth/token` | API key header | Exchange API key for JWT |
| POST | `/auth/revoke-key` | JWT | Revoke an API key |
| GET | `/auth/me` | JWT | Get current user info |

### JWT Structure

- Algorithm: HS256
- Secret: `JWT_SECRET` env var
- Expiry: 15 minutes (configurable via `JWT_EXPIRY_MINUTES`)
- Payload: `{sub: user_id, email, team_id, is_admin, exp}`
- Header: `Authorization: Bearer <token>`

### API Key Exchange Flow

1. Admin registers a user via `/auth/register` (requires `X-API-Key: <ADMIN_API_KEY>` header)
2. User creates an API key via `/auth/api-keys` (key returned once in plaintext, stored as bcrypt hash)
3. User exchanges API key for JWT via `/auth/token` (`X-API-Key: <key>` header)
4. JWT used for all subsequent authenticated requests

### Protected Endpoints

The following endpoints require valid JWT:
- `POST /query`
- `POST /ingest`
- `GET /ingest/{task_id}`
- `GET /memory/search`
- `GET /memory/graph`

Public endpoints:
- `GET /health`
- `POST /session/new`

## Session Memory Persistence

### Query Flow with Session Context

1. Request arrives at `/query` with valid JWT
2. Extract `session_id` from request body
3. If `session_id` is provided, retrieve last N messages (default 10, configurable via `SESSION_HISTORY_LIMIT`) from `session_messages` where `session_id = req.session_id AND team_id = user.team_id`, ordered by `created_at`
4. Build agno conversation history as `[{role: "user", content: "..."}, {role: "assistant", content: "..."}]` from retrieved messages
5. Pass history to `agent.arun()` for context-aware response
6. After streaming completes, save user message and assistant response to `session_messages`
7. Return streaming response to client

### Stateless Queries

If `session_id` is `None`, no history is loaded or saved. The query runs without prior context.

### Cleanup

Messages older than `SESSION_TTL_DAYS` (default 30) are purged. A background cleanup runs on server startup or can be triggered via a management endpoint.

## New Dependencies

- `pyjwt` — JWT encoding/decoding
- `bcrypt` — password and API key hashing
- `libsql` (or `sqlite3` compatible) — local database

## File Structure

```
db/
  auth_store.py          # User, API key, team CRUD operations
  session_store.py       # Session message persistence
  migrations/
    001_auth_sessions.sql # Schema migration
auth/
  __init__.py
  middleware.py           # require_auth FastAPI dependency
  jwt.py                  # JWT encode/decode utilities
  models.py               # Pydantic models for auth endpoints
agentos.py                # Updated: auth routes, protected endpoints, session injection
pyproject.toml            # New dependencies
.env.sample               # New env vars documented
```

## Environment Variables

```
JWT_SECRET=<random-secret>
JWT_EXPIRY_MINUTES=15
ADMIN_API_KEY=<admin-api-key-for-bootstrapping>
SESSION_HISTORY_LIMIT=10
SESSION_TTL_DAYS=30
```

## Error Responses

| Status | Condition |
|--------|-----------|
| 401 | Missing or invalid JWT |
| 403 | Valid JWT but insufficient permissions (e.g., non-admin accessing admin endpoint) |
| 401 | Expired API key or JWT |
| 400 | Invalid registration/login payload |
| 409 | Duplicate email or API key label |
