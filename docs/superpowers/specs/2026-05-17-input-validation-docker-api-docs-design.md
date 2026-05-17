# Input Validation, Docker Compose, and API Documentation Design

> **Date:** 2026-05-17
> **Status:** Approved

## Overview

Three independent improvements to the MemMesh project:
1. Input validation with length guards, content sanitization, PII detection, and prompt injection prevention
2. Docker Compose completeness — add Redis and Celery worker services
3. OpenAPI/Swagger API documentation with examples and response schemas

---

## 1. Input Validation

### File: `utils/input_validator.py`

**Function: `validate_query(text: str) -> str`**

Raises `HTTPException(400)` on failure, returns sanitized text on success.

**Checks (executed in order):**

1. **Length guard** — `len(text) > 5000` → reject with "Query exceeds maximum length of 5000 characters"
2. **Control character sanitization** — strip `\x00-\x08`, `\x0b-\x0c`, `\x0e-\x1f` silently
3. **Prompt injection detection** — case-insensitive regex match against ~15 patterns:
   - `ignore previous instructions`, `ignore above`, `disregard`
   - `system:`, `<system>`, `</system>`
   - `you are now`, `pretend you are`, `act as`
   - `output your prompt`, `repeat the instructions`, `show your system`
   - `##`, `---` (markdown injection)
   - Reject with "Query contains disallowed patterns"
4. **PII detection** — regex patterns for email, phone, SSN, credit card numbers:
   - Email: standard RFC-ish pattern
   - Phone: various formats (with/without country code, dashes, spaces)
   - SSN: `\d{3}-\d{2}-\d{4}`
   - Credit card: 13-19 digit sequences (with/without spaces/dashes)
   - Reject with "Query contains potential personal information"

**Integration points:**
- `/query` — `validate_query(req.message)` before processing
- `/memory/search` — `validate_query(query)` before embedding
- `/memory/graph` — `validate_query(entity)` before lookup

---

## 2. Docker Compose

### Changes to `docker-compose.yml`

**New service: `redis`**
- Image: `redis:7-alpine`
- Port: `6379:6379`
- Volume: `./data/redis:/data`
- Command: `redis-server --appendonly yes`
- Healthcheck: `redis-cli ping`
- Restart: `unless-stopped`

**New service: `worker`**
- Build: `.` (uses project Dockerfile)
- Command: `celery -A workers.celery_app worker --loglevel=info`
- Depends on: `neo4j`, `minio`, `redis`
- Env file: `.env`
- Volume: `.:/app` (for local development hot reload)
- Working dir: `/app`
- Restart: `unless-stopped`

**Note:** No API server service — uvicorn stays as local dev command.

---

## 3. API Documentation

### Changes to `agentos.py`

**Enhanced Pydantic models:**
- `QueryRequest`: add `Field(json_schema_extra={"examples": [...]})`
- New `ErrorResponse` model: `{detail: str, status_code: int}`

**Endpoint metadata:**
- All endpoints get `tags` parameter (Query, Memory, Ingestion, Session, Health)
- All endpoints get `summary` and `description`
- Streaming endpoints get proper `responses` dict documenting NDJSON format

**Custom OpenAPI override:**
- `app.openapi()` extended with:
  - `info.description` with project overview
  - `servers` list
  - Per-endpoint request/response examples

**Result:** `GET /docs` serves full Swagger UI with tagged groups, example requests, and response schemas for every endpoint.
