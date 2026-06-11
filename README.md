# MemMesh

**Multi-agent RAG platform** combining vector search, knowledge graphs, and LLM orchestration for document-grounded enterprise Q&A.

[![Version](https://img.shields.io/badge/version-0.1.0-blue)]()
[![Python](https://img.shields.io/badge/python-3.12-blue)]()
[![React](https://img.shields.io/badge/react-18-61DAFB)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

---

## Table of Contents

- [What is MemMesh?](#what-is-memmesh)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## What is MemMesh?

MemMesh is a **multi-agent RAG (Retrieval-Augmented Generation) engine** that answers questions over your documents. Unlike simple RAG pipelines that only do vector search, MemMesh uses a **LangGraph-orchestrated agent pipeline** that:

- Rewrites queries for better retrieval
- Routes to **vector search** (Weaviate), **knowledge graphs** (Neo4j), or both
- Validates retrieved context with **Corrective RAG** (CRAG)
- Falls back to **web search** when context is insufficient
- Cites sources with numbered references
- Supports **multi-tenant teams** with isolated data per team

### What it does

- Upload PDFs, DOCX, PPTX, images, HTML — layout-aware parsing via Docling
- Ask questions in natural language, get cited answers with source references
- Switch between conversations with branching message trees
- Export chat sessions as Markdown, JSON, or PDF
- Monitor system health, analytics, and RAG evaluation scores from a dashboard

### What it doesn't

- Not a general-purpose chatbot — optimized for document-grounded Q&A
- Not a vector database replacement — uses Weaviate under the hood
- Not designed for single-user local use — built for multi-tenant deployments
- No support for real-time document collaboration or editing
- No native mobile app (responsive web UI only)

---

## Architecture

```
┌──────────────┐     ┌─────────────────────────────────────────────────────────────────────────────┐
│   Frontend   │     │                                  Backend                                    │
│   (React +   │     │                                                                             │
│   TanStack)  │     │  ┌──────────┐   ┌──────────────────────────────────────────────────────┐   │
│              │     │  │  FastAPI  │   │                   Agent Pipeline                     │   │
│  ┌────────┐  │     │  │  Routes   │   │                                                      │   │
│  │ Chat   │──┼─────┼─►│          │──►│  ┌──────┐  ┌─────────┐  ┌──────┐  ┌──────────┐       │   │
│  │ UI     │  │     │  │ /query   │   │  │Safety│─►│Rewriter │─►│Router│─►│Retriever │       │   │
│  └────────┘  │     │  │ /upload  │   │  │Guard │  │(Gemini) │  │(Gem.)│  │          │       │   │
│  ┌────────┐  │     │  │ /auth    │   │  └──────┘  └─────────┘  └──────┘  └────┬─────┘       │   │
│  │ Docs   │──┼─────┼─►│ /chat    │   │                                          │            │   │
│  │ UI     │  │     │  │ /admin   │   │                              ┌───────────┼──────────┐ │   │
│  └────────┘  │     │  │ /eval    │   │                              ▼           ▼          │ │   │
│  ┌────────┐  │     │  └──────────┘   │  ┌──────────────┐  ┌────────────┐  ┌────────────┐   │ │   │
│  │ Admin  │──┼─────┼─►  Celery      │  │  Web Search  │◄─│    CRAG    │◄─│ Weaviate   │   │ │   │
│  │ UI     │  │     │  │  Workers    │  │  (DuckDuckGo) │  │ (relevance │  │ (vector +  │   │ │   │
│  └────────┘  │     │  │             │  │  (fallback)   │  │   check)   │  │  BM25)     │   │ │   │
│  ┌────────┐  │     │  │ ┌─────────┐ │  └──────────────┘  └──────┬─────┘  └────────────┘   │ │   │
│  │ Eval   │──┼─────┼─► │ │Ingestion│ │                          │                         │ │   │
│  │ UI     │  │     │  │ │Worker   │ │                          ▼                         │ │   │
│  └────────┘  │     │  │ ├─────────┤ │  ┌──────────────────────────────────────────┐      │ │   │
│  ┌────────┐  │     │  │ │Decay    │ │  │              Synthesis                   │      │ │   │
│  │Analytics│─┼─────┼─► │ │Worker   │ │  │  (Gemini generates answer with          │      │ │   │
│  │ UI      │  │     │  │ ├─────────┤ │  │   [1][2] source citations)              │      │ │   │
│  └────────┘  │     │  │ │Analytics│ │  └──────────────────────────────────────────┘      │ │   │
│              │     │  │ │Worker   │ │                          │                         │ │   │
│              │     │  │ ├─────────┤ │                          ▼                         │ │   │
│              │     │  │ │Drift    │ │  ┌──────────────────────────────────────────┐      │ │   │
│              │     │  │ │Worker   │ │  │          Output Safety                   │      │ │   │
│              │     │  │ └─────────┘ │  │  (PII scrub + toxic content check on     │      │ │   │
│              │     │  └─────────────┘  │   final answer)                          │      │ │   │
│              │     │                   └──────────────────────────────────────────┘      │ │   │
│              │     │                                      │                             │ │   │
│              │     │                                      ▼                             │ │   │
│              │     │  ┌────────────────────────────────────────────────────────────┐    │ │   │
│              │     │  │                    Persistence Layer                       │    │ │   │
│              │     │  │  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │    │ │   │
│              │     │  │  │ MySQL   │  │ Weaviate │  │  Neo4j   │  │  Redis   │   │    │ │   │
│              │     │  │  │ (rel.   │  │ (vector  │  │ (graph   │  │ (cache + │   │    │ │   │
│              │     │  │  │  data)  │  │  search) │  │  store)  │  │  queue)  │   │    │ │   │
│              │     │  │  └─────────┘  └──────────┘  └──────────┘  └──────────┘   │    │ │   │
│              │     │  └────────────────────────────────────────────────────────────┘    │ │   │
│              │     └─────────────────────────────────────────────────────────────────────┘ │   │
└──────────────┘     └───────────────────────────────────────────────────────────────────────┘   │
                                                                                                 │
┌─────────────────────────────────────────────────────────────────────────────────────────────────┘
│
▼
curl -X POST http://localhost:8000/api/query \
  -H "Authorization: Bearer <token>" \
  -d '{"query": "What is revenue growth?", "team_id": "..."}'
```

### Agent Pipeline

| Stage | Component | What it does |
|---|---|---|
| Safety | `agents/safety.py` | PII scrubbing + toxic content filtering (input and output) |
| Rewrite | `agents/rewriter.py` | Gemini generates 2-3 query variants for broader recall |
| Route | `agents/router.py` | Gemini classifies query as `vector`, `graph`, or `hybrid` |
| Retrieve | `agents/retriever.py` | Weaviate hybrid search (BM25 + vector) and/or Neo4j Cypher queries |
| CRAG | `agents/crag.py` | Gemini evaluates relevance score; falls back to web search (DuckDuckGo) if < 0.5 |
| Synthesize | `agents/safety.py` | Final answer generated with `[1]`, `[2]` source citations |
| Memory | `agents/memory.py` | Redis-backed conversation history (7-day TTL, 20 msg sliding window) |

### Data Stores

| Store | Technology | Purpose |
|---|---|---|
| Vector DB | Weaviate 1.28 | Document chunk embeddings (3072-dim Gemini), hybrid search, multi-tenancy |
| Graph DB | Neo4j 5 | Entity-relationship knowledge graph, per-tenant database isolation |
| RDBMS | MySQL 8.0 | Users, teams, sessions, messages, source docs, audit logs |
| Cache | Redis 7 | Celery broker + result backend, semantic cache, rate limiter, conversation memory |


### Background Workers (Celery)

| Schedule | Task | Description |
|---|---|---|
| Every hour | Memory decay | Reduces importance scores in Weaviate + Neo4j; deletes entities with score ≤ 0 |
| Every hour | Analytics aggregation | Computes query volume, latency, feedback metrics |
| Daily | Data drift detection | Analyzes user feedback for topic shifts |
| Weekly | DeepEval run | Computes faithfulness, hallucination, answer relevancy scores |

---

## Quick Start

### Prerequisites

- **Python 3.12** (with `uv` installed: `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **Node.js 20+** and **npm**
- **Docker** and **Docker Compose v2**
- A **Gemini API key** ([get one here](https://aistudio.google.com/apikey))

### 1. Clone and configure

```bash
git clone <repo-url>
cd memmesh
cp .env.example .env
# Edit .env — at minimum set GEMINI_API_KEY
```

### 2. Start infrastructure

```bash
docker compose up -d
```

This starts Weaviate, MySQL 8.0, Neo4j 5, and Redis 7.

### 3. Install dependencies

```bash
# Backend
uv sync --project backend

# Frontend
cd frontend && npm install && cd ..
```

### 4. Run database migrations

```bash
make db-upgrade
```

### 5. Start the stack

Open three terminal tabs:

```bash
# Terminal 1 — Backend API
make dev-backend

# Terminal 2 — Frontend dev server
make dev-frontend

# Terminal 3 — Celery worker (for document ingestion, memory decay, etc.)
make dev-worker
```

### 6. Open the app

Visit **http://localhost:5173** and log in with:

- **Email:** `superadmin@memmesh.com`
- **Password:** `admin_secret_password_change_me`

---

## Usage

### Ask a question (blocking)

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "query": "What does the Q3 financial report say about revenue growth?",
    "team_id": "team-uuid-here"
  }'
```

### Ask a question (streaming — SSE)

```bash
curl -N -X POST http://localhost:8000/api/query/stream \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "query": "Summarize our competitive analysis findings",
    "team_id": "team-uuid-here"
  }'
```

### Upload a document

```bash
curl -X POST http://localhost:8000/api/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@report.pdf" \
  -F "team_id=team-uuid-here"
```

### List documents

```bash
curl http://localhost:8000/api/documents \
  -H "Authorization: Bearer <token>" \
  -H "X-Team-ID: team-uuid-here"
```

### Export a chat session

```bash
# Markdown
curl http://localhost:8000/api/chat/sessions/<id>/export?format=md \
  -H "Authorization: Bearer <token>"

# JSON
curl http://localhost:8000/api/chat/sessions/<id>/export?format=json \
  -H "Authorization: Bearer <token>"
```

### Check system health

```bash
curl http://localhost:8000/api/health
```

---

## Configuration

All configuration is via environment variables in `.env`. See `.env.example` for a template.

### LLM

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | — | Google Gemini API key |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Model identifier |

### MySQL

| Variable | Default | Description |
|---|---|---|
| `MYSQL_HOST` | `127.0.0.1` | Database host |
| `MYSQL_PORT` | `3306` | Database port |
| `MYSQL_USER` | `app_user` | Database user |
| `MYSQL_PASSWORD` | `user_password_change_me` | Database password |
| `MYSQL_DATABASE` | `memmesh` | Database name |

### Weaviate

| Variable | Default | Description |
|---|---|---|
| `WEAVIATE_HOST` | `127.0.0.1` | Weaviate host |
| `WEAVIATE_PORT` | `8080` | HTTP API port |
| `WEAVIATE_GRPC_PORT` | `50051` | gRPC port |

### Neo4j

| Variable | Default | Description |
|---|---|---|
| `NEO4J_URI` | `bolt://127.0.0.1:7687` | Bolt connection URI |
| `NEO4J_USER` | `neo4j` | Database user |
| `NEO4J_PASSWORD` | `neo4j_password_change_me` | Database password |

### Redis

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | Redis connection string |

### Auth

| Variable | Default | Description |
|---|---|---|
| `JWT_SECRET` | `super_secret_jwt_key_change_me` | Signing key |
| `JWT_ALGORITHM` | `HS256` | Signing algorithm |
| `JWT_EXPIRY_MINUTES` | `60` | Token TTL |

### Rate Limiting

| Variable | Default | Description |
|---|---|---|
| `RATE_LIMIT_LOGIN` | `30/minute` | Login endpoint |
| `RATE_LIMIT_REGISTER` | `3/minute` | Register endpoint |
| `RATE_LIMIT_QUERY` | `30/minute` | Query endpoints |
| `RATE_LIMIT_GLOBAL` | `100/minute` | Global limit |

### Semantic Cache

| Variable | Default | Description |
|---|---|---|
| `SEMANTIC_CACHE_TTL` | `86400` | Cache TTL in seconds (24h) |
| `SEMANTIC_CACHE_THRESHOLD` | `0.92` | Cosine similarity threshold |

### Other

| Variable | Default | Description |
|---|---|---|
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins |
| `MAX_UPLOAD_SIZE_MB` | `50` | Max document upload size |
| `SUPERADMIN_EMAIL` | `superadmin@memmesh.com` | Seeded on startup |
| `SUPERADMIN_PASSWORD` | `admin_secret_password_change_me` | Seeded on startup |

---

## API Reference

All endpoints are prefixed with `/api`.

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/health` | — | System health (MySQL, Redis, Weaviate, Neo4j) |
| POST | `/api/auth/login` | Rate-limited | Login, returns JWT |
| POST | `/api/auth/register` | Rate-limited | Register new user |
| POST | `/api/auth/refresh` | Token | Refresh JWT |
| POST | `/api/query` | Token | Blocking Q&A |
| POST | `/api/query/stream` | Token | SSE streaming Q&A |
| GET | `/api/chat/sessions` | Token | List sessions |
| GET | `/api/chat/messages` | Token | Get session messages |
| GET | `/api/chat/sessions/{id}/export` | Token | Export session (md/json/pdf) |
| POST | `/api/upload` | Team lead+ | Upload document |
| GET | `/api/upload/status/{id}` | Token | Upload task status |
| POST | `/api/feedback` | Token | Submit feedback (up/down) |
| POST | `/api/eval` | Superadmin | Trigger RAG evaluation |
| GET | `/api/eval/scores` | Superadmin | Evaluation history |
| GET | `/api/admin/teams` | Superadmin | List teams |
| POST | `/api/admin/teams` | Superadmin | Create team |
| DELETE | `/api/admin/teams/{id}` | Superadmin | Delete team |
| GET | `/api/admin/users` | Superadmin | List users |
| POST | `/api/admin/users` | Superadmin | Create user |
| GET | `/api/documents` | Token | List team documents |
| GET | `/api/documents/{id}/pdf` | Token | Serve PDF file |

---

## Testing

### Backend (pytest)

```bash
# Unit tests (SQLite in-memory, mocked LLM)
make test-backend

# With real MySQL (Docker required)
USE_TESTCONTAINERS=1 make test-backend
```

Uses `MOCK_LLM=true` by default. Set `MOCK_LLM=false` to run against real Gemini.

### Frontend (vitest)

```bash
make test-frontend
```

### E2E (Playwright)

```bash
make test-e2e
```

E2E tests require the backend, frontend, and infrastructure to be running. `MOCK_LLM=true` is set automatically in the Playwright config.

### Run all tests

```bash
make test
```

---

## Project Structure

```
MemMesh/
├── backend/
│   ├── agents/            # LangGraph agent pipeline
│   │   ├── graph_orchestrator.py  # State graph + SSE streaming
│   │   ├── rewriter.py            # Query rewriting
│   │   ├── router.py              # Route classification
│   │   ├── retriever.py           # Vector + graph retrieval
│   │   ├── crag.py                # Corrective RAG relevance check
│   │   ├── safety.py              # PII + toxic content
│   │   ├── web_search.py          # DuckDuckGo fallback
│   │   ├── memory.py              # Conversation history
│   │   └── telemetry.py           # SSE event types
│   ├── api/routes/        # FastAPI route handlers
│   ├── auth/              # JWT, middleware, password hashing
│   ├── cache/             # Semantic caching (Redis + embeddings)
│   ├── db/                # Database clients (MySQL, Weaviate, Neo4j)
│   ├── ingestion/         # Document parsing, entity extraction, versioning
│   ├── tasks/             # Celery background workers
│   ├── export/            # Chat session exporters (md/json/pdf)
│   ├── middleware/        # Error handlers, logging
│   ├── migrations/        # Alembic migrations
│   ├── tests/             # Pytest test suite
│   ├── config.py          # Pydantic Settings
│   ├── main.py            # FastAPI app factory
│   ├── models.py          # SQLAlchemy ORM models
│   └── rate_limiter.py    # slowapi limiter
├── frontend/
│   ├── src/
│   │   ├── components/    # React components (chat, docs, admin, shared, UI)
│   │   ├── hooks/         # useChatStream, etc.
│   │   ├── routes/        # TanStack Router pages
│   │   ├── utils/         # Auth, query, health, upload helpers
│   │   └── types/         # TypeScript type definitions
│   ├── package.json
│   └── vite.config.ts
├── tests/e2e/             # Playwright E2E tests
├── docs/                  # Design specs and plans
├── docker-compose.yml     # Infrastructure containers
├── Makefile               # Dev commands
└── .env.example           # Configuration template
```

---

## Troubleshooting

### "No module named 'backend'"

Run `uv sync --project backend` from the project root. Make sure your terminal is not inside the `backend/` directory when starting the server.

### Celery worker crashes on startup

Set `CELERY_WORKER_PREFETCH_MULTIPLIER=1` and `worker_max_tasks_per_child=1` in your environment. MemMesh's Celery app already configures fork safety, but your broker settings may override it.

### "rate limit exceeded" on login

The login endpoint is rate-limited to 30 requests/minute by default. If you're testing programmatically, reuse the JWT token instead of logging in for every request.

### PDF viewer shows blank page

The PDF viewer uses `pdfjs-dist` with credentials from the auth header. Make sure you're running a recent Chrome/Edge/Firefox. Safari's PDF.js support is limited.

### "Could not connect to Weaviate"

Ensure Docker containers are running (`docker compose ps`). On first startup, Weaviate takes 15-30 seconds to initialize. Wait for the health check to pass.

---

## Contributing

Contributions are welcome. Open an issue to discuss changes before submitting PRs.

- Report bugs and suggest features via [GitHub Issues](https://github.com/anomalyco/MemMesh/issues)
- Follow existing code style — the project uses `ruff` for Python and `prettier` for TypeScript
- Ensure tests pass before submitting: `make test`

---

## License

MIT. See [LICENSE](LICENSE) for details.
