# Phase 8 — Website Crawl & Google Drive: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable knowledge ingestion from external web sources and Google Drive, with crawl job tracking, scheduled recrawl, and a full management UI — so Team Leads can populate their team's knowledge base from websites and shared drives.

**Architecture:** A web crawler (`ingestion/crawler.py`) uses crawl4ai for JS-rendered pages with httpx+BeautifulSoup4 fallback, converts HTML→Markdown, and stores content as team-scoped `source_docs`. A Google Drive connector (`ingestion/gdrive.py`) authenticates via Service Account JSON, exports Google Workspace files to parseable formats, and feeds them through the existing document parser. Crawl jobs are tracked in SQLite with status updates. APScheduler runs periodic recrawl jobs in-process. Frontend provides crawl management and Google Drive connection UIs.

**Tech Stack:** Python 3.11+, FastAPI, crawl4ai, httpx, BeautifulSoup4, markdownify, google-api-python-client, google-auth, APScheduler, SQLite, SvelteKit, TypeScript, Playwright

---

## Scope Note

This plan covers **Phase 8 only**. Phases 1–7 are assumed complete: full auth, teams, document upload, indexing pipeline (parser, chunker, ChromaDB, FalkorDB), full hybrid RAG pipeline (router, rewriter, graph traversal, vector search, fusion, reranker, synthesis), Pipeline Lens, and NDJSON streaming.

---

## File Structure

### Backend (`backend/`)

```
backend/
├── config.py                              # Update: add crawl + gdrive config vars
├── requirements.txt                       # Update: add crawl4ai, markdownify, etc.
├── .env.example                           # Update: add crawl + gdrive env vars
├── ingestion/
│   ├── __init__.py                        # Exists
│   ├── crawler.py                         # Create: web crawler
│   ├── gdrive.py                         # Create: Google Drive connector
│   ├── parser.py                          # Exists
│   └── chunker.py                         # Exists
├── api/
│   ├── server.py                          # Update: add APScheduler setup
│   └── routes/
│       └── ingest.py                      # Update: add URL crawl + gdrive endpoints
├── db/
│   ├── sqlite.py                          # Exists
│   └── migrations/
│       └── 00N_crawl_jobs.sql             # Create: crawl_jobs table
└── tests/
    ├── test_crawler.py                    # Create: crawler unit + integration tests
    ├── test_gdrive.py                     # Create: gdrive connector tests
    └── test_ingest_api.py                 # Update: add crawl + gdrive API tests
```

### Frontend (`frontend/`)

```
frontend/
├── src/
│   ├── lib/
│   │   ├── api.ts                         # Update: add crawl + gdrive API calls
│   │   └── types.ts                       # Update: add crawl + gdrive types
│   └── routes/
│       └── dashboard/
│           ├── ingest/
│           │   ├── +page.svelte           # Update: add crawl + gdrive tabs
│           │   ├── CrawlManager.svelte    # Create: crawl management component
│           │   └── GDriveConnect.svelte   # Create: Google Drive connection component
└── tests/
    └── e2e/
        └── crawl.spec.ts                  # Create: crawl E2E tests
```

---

## Group A: Backend Configuration & Migration

### Task 1: Update Config, Requirements, and Environment

**Files:**
- Modify: `backend/config.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/.env.example`

- [ ] **Step 1: Update `requirements.txt` with new dependencies**

Add the following lines to `backend/requirements.txt`:

```
# backend/requirements.txt (append these lines)
crawl4ai==0.4.3
markdownify==0.14.1
beautifulsoup4==4.12.3
httpx==0.28.0
google-api-python-client==2.155.0
google-auth==2.36.0
apscheduler==3.10.4
```

> Note: httpx may already exist from Phase 1. If so, skip that line.

- [ ] **Step 2: Update `.env.example` with crawl and gdrive config vars**

Append the following to `backend/.env.example`:

```env
# backend/.env.example (append these lines)

# Web Crawling
CRAWL_MAX_DEPTH=2
CRAWL_MAX_PAGES=100
CRAWL_RESPECT_ROBOTS=true
CRAWL_REFRESH_INTERVAL_HOURS=24

# Google Drive (optional)
GDRIVE_SERVICE_ACCOUNT_JSON=
```

- [ ] **Step 3: Update `config.py` to load crawl and gdrive settings**

Add crawl and gdrive fields to the `Settings` dataclass and `load_settings()` function in `backend/config.py`:

```python
# backend/config.py — updated Settings dataclass (add these fields)

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

    # (existing fields from earlier phases: chroma_dir, falkordb_dir, upload_dir,
    #  gemini_api_key, decay_importance_threshold, decay_window_days,
    #  session_retention_days, etc. — keep them as-is)

    # Web Crawling
    crawl_max_depth: int
    crawl_max_pages: int
    crawl_respect_robots: bool
    crawl_refresh_interval_hours: int

    # Google Drive
    gdrive_service_account_json: str
```

Update `load_settings()`:

```python
def load_settings() -> Settings:
    """Load settings from environment variables."""
    # ... existing loading code ...

    return Settings(
        # ... existing fields ...

        # Web Crawling
        crawl_max_depth=int(os.getenv("CRAWL_MAX_DEPTH", "2")),
        crawl_max_pages=int(os.getenv("CRAWL_MAX_PAGES", "100")),
        crawl_respect_robots=os.getenv("CRAWL_RESPECT_ROBOTS", "true").lower() == "true",
        crawl_refresh_interval_hours=int(os.getenv("CRAWL_REFRESH_INTERVAL_HOURS", "24")),

        # Google Drive
        gdrive_service_account_json=os.getenv("GDRIVE_SERVICE_ACCOUNT_JSON", ""),
    )
```

- [ ] **Step 4: Verify config loads the new settings**

Run: `cd backend && python3 -c "from config import settings; print(settings.crawl_max_depth, settings.crawl_max_pages, settings.crawl_respect_robots)"`
Expected: `2 100 True`

- [ ] **Step 5: Commit**

```bash
cd backend
git add config.py requirements.txt .env.example
git commit -m "chore: add crawl and gdrive config vars, dependencies"
```

---

### Task 2: Crawl Jobs Migration

**Files:**
- Create: `backend/db/migrations/00N_crawl_jobs.sql`

> Note: Replace `00N` with the actual next migration number in your project (e.g., `005_crawl_jobs.sql`).

- [ ] **Step 1: Create the crawl_jobs migration**

```sql
-- backend/db/migrations/005_crawl_jobs.sql

CREATE TABLE IF NOT EXISTS crawl_jobs (
    job_id       TEXT PRIMARY KEY,
    team_id      TEXT NOT NULL REFERENCES teams(team_id),
    triggered_by TEXT NOT NULL REFERENCES users(user_id),
    source_url   TEXT NOT NULL,
    job_type     TEXT NOT NULL DEFAULT 'url',  -- 'url' | 'sitemap' | 'recursive' | 'gdrive'
    status       TEXT NOT NULL DEFAULT 'running',  -- 'running' | 'done' | 'failed'
    pages_found  INTEGER DEFAULT 0,
    error_message TEXT,
    config_json  TEXT,  -- JSON: {max_depth, max_pages, folder_id, etc.}
    started_at   DATETIME NOT NULL DEFAULT (datetime('now')),
    finished_at  DATETIME
);

CREATE INDEX IF NOT EXISTS idx_crawl_jobs_team_id ON crawl_jobs(team_id);
CREATE INDEX IF NOT EXISTS idx_crawl_jobs_status ON crawl_jobs(status);
```

- [ ] **Step 2: Run the migration**

Run: `cd backend && make migrate`
Expected: `Applied migration: 005_crawl_jobs.sql`

- [ ] **Step 3: Verify the table exists**

Run: `cd backend && python3 -c "from db.sqlite import get_connection; c = get_connection(); print([row[0] for row in c.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name='crawl_jobs'\").fetchall()]); c.close()"`
Expected: `['crawl_jobs']`

- [ ] **Step 4: Commit**

```bash
cd backend
git add db/migrations/005_crawl_jobs.sql
git commit -m "feat: add crawl_jobs table migration"
```

---

## Group B: Web Crawler

### Task 3: URL Utilities & Robots.txt Parser

**Files:**
- Create: `backend/tests/test_crawler.py`
- Create: `backend/ingestion/crawler.py`

- [ ] **Step 1: Write failing tests for URL normalization and robots.txt**

```python
# backend/tests/test_crawler.py
"""Unit and integration tests for the web crawler."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from ingestion.crawler import (
    normalize_url,
    is_same_domain,
    check_robots_txt,
    extract_links,
    html_to_markdown,
    compute_content_hash,
)


class TestNormalizeUrl:
    def test_strips_fragment(self):
        assert normalize_url("https://example.com/page#section") == "https://example.com/page"

    def test_strips_trailing_slash(self):
        assert normalize_url("https://example.com/page/") == "https://example.com/page"

    def test_lowercases_scheme_and_host(self):
        assert normalize_url("HTTPS://EXAMPLE.COM/Page") == "https://example.com/Page"

    def test_preserves_path_case(self):
        assert normalize_url("https://example.com/CaseSensitive") == "https://example.com/CaseSensitive"

    def test_preserves_query_params(self):
        assert normalize_url("https://example.com/page?a=1&b=2") == "https://example.com/page?a=1&b=2"

    def test_root_url(self):
        assert normalize_url("https://example.com/") == "https://example.com"

    def test_root_url_no_slash(self):
        assert normalize_url("https://example.com") == "https://example.com"


class TestIsSameDomain:
    def test_same_domain(self):
        assert is_same_domain("https://example.com/page1", "https://example.com/page2") is True

    def test_different_domain(self):
        assert is_same_domain("https://example.com/page", "https://other.com/page") is False

    def test_subdomain_is_different(self):
        assert is_same_domain("https://blog.example.com/page", "https://example.com/page") is False


class TestContentHash:
    def test_same_content_same_hash(self):
        h1 = compute_content_hash("hello world")
        h2 = compute_content_hash("hello world")
        assert h1 == h2

    def test_different_content_different_hash(self):
        h1 = compute_content_hash("hello")
        h2 = compute_content_hash("world")
        assert h1 != h2

    def test_returns_hex_string(self):
        h = compute_content_hash("test")
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex digest


class TestHtmlToMarkdown:
    def test_converts_heading(self):
        html = "<h1>Hello World</h1>"
        md = html_to_markdown(html)
        assert "Hello World" in md
        assert "#" in md or "Hello World" in md

    def test_converts_paragraph(self):
        html = "<p>This is a paragraph.</p>"
        md = html_to_markdown(html)
        assert "This is a paragraph." in md

    def test_converts_link(self):
        html = '<p>Visit <a href="https://example.com">Example</a></p>'
        md = html_to_markdown(html)
        assert "Example" in md

    def test_strips_script_tags(self):
        html = "<p>Content</p><script>alert('xss')</script>"
        md = html_to_markdown(html)
        assert "alert" not in md
        assert "Content" in md

    def test_strips_style_tags(self):
        html = "<style>body{color:red}</style><p>Content</p>"
        md = html_to_markdown(html)
        assert "color" not in md
        assert "Content" in md


class TestExtractLinks:
    def test_extracts_absolute_links(self):
        html = '<a href="https://example.com/page1">Link 1</a><a href="https://example.com/page2">Link 2</a>'
        links = extract_links(html, "https://example.com")
        assert "https://example.com/page1" in links
        assert "https://example.com/page2" in links

    def test_resolves_relative_links(self):
        html = '<a href="/about">About</a>'
        links = extract_links(html, "https://example.com/page")
        assert "https://example.com/about" in links

    def test_filters_external_links(self):
        html = '<a href="https://other.com/page">Other</a><a href="/local">Local</a>'
        links = extract_links(html, "https://example.com")
        assert "https://other.com/page" not in links
        assert "https://example.com/local" in links

    def test_filters_non_http_links(self):
        html = '<a href="mailto:user@example.com">Email</a><a href="javascript:void(0)">JS</a>'
        links = extract_links(html, "https://example.com")
        assert len(links) == 0

    def test_deduplicates_links(self):
        html = '<a href="/page">L1</a><a href="/page">L2</a>'
        links = extract_links(html, "https://example.com")
        assert links.count("https://example.com/page") == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python3 -m pytest tests/test_crawler.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ingestion.crawler'`

- [ ] **Step 3: Implement URL utilities and HTML conversion**

```python
# backend/ingestion/crawler.py
"""Web crawler with crawl4ai + httpx/BeautifulSoup4 fallback.

Supports single page, sitemap, and recursive crawling.
Converts HTML to Markdown, respects robots.txt, tracks content hashes.
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify as md

from config import settings
from db.sqlite import get_connection

logger = logging.getLogger(__name__)


def normalize_url(url: str) -> str:
    """Normalize a URL: lowercase scheme/host, strip fragment, strip trailing slash."""
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path
    # Strip trailing slash (but keep root /)
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    elif path == "/":
        path = ""
    normalized = urlunparse((scheme, netloc, path, parsed.params, parsed.query, ""))
    return normalized


def is_same_domain(url1: str, url2: str) -> bool:
    """Check if two URLs belong to the same domain (exact match, no subdomain matching)."""
    return urlparse(url1).netloc.lower() == urlparse(url2).netloc.lower()


def compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of content string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def html_to_markdown(html: str) -> str:
    """Convert HTML to Markdown, stripping scripts and styles first."""
    soup = BeautifulSoup(html, "html.parser")
    # Remove script and style tags
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    cleaned_html = str(soup)
    return md(cleaned_html, heading_style="ATX", strip=["img"])


def extract_links(html: str, base_url: str) -> list[str]:
    """Extract same-domain HTTP(S) links from HTML, resolving relative URLs."""
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    links: list[str] = []
    base_domain = urlparse(base_url).netloc.lower()

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        # Resolve relative URLs
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)

        # Filter non-HTTP schemes
        if parsed.scheme not in ("http", "https"):
            continue

        # Filter external domains
        if parsed.netloc.lower() != base_domain:
            continue

        normalized = normalize_url(absolute)
        if normalized not in seen:
            seen.add(normalized)
            links.append(normalized)

    return links


def check_robots_txt(url: str, user_agent: str = "*") -> bool:
    """Check if a URL is allowed by the site's robots.txt.

    Returns True if allowed or if robots.txt cannot be fetched.
    """
    if not settings.crawl_respect_robots:
        return True

    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    try:
        rp = RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(user_agent, url)
    except Exception:
        logger.warning("Could not fetch robots.txt for %s, allowing by default", robots_url)
        return True


# === Crawl Job DB Operations ===


def create_crawl_job(
    team_id: str,
    triggered_by: str,
    source_url: str,
    job_type: str = "url",
    config: dict | None = None,
) -> str:
    """Create a crawl job record and return the job_id."""
    job_id = str(uuid.uuid4())
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO crawl_jobs (job_id, team_id, triggered_by, source_url, job_type, status, config_json) "
            "VALUES (?, ?, ?, ?, ?, 'running', ?)",
            (job_id, team_id, triggered_by, source_url, job_type, json.dumps(config or {})),
        )
        conn.commit()
        return job_id
    finally:
        conn.close()


def update_crawl_job(
    job_id: str,
    status: str | None = None,
    pages_found: int | None = None,
    error_message: str | None = None,
) -> None:
    """Update a crawl job's status and/or pages_found."""
    conn = get_connection()
    try:
        updates: list[str] = []
        params: list = []
        if status is not None:
            updates.append("status = ?")
            params.append(status)
            if status in ("done", "failed"):
                updates.append("finished_at = datetime('now')")
        if pages_found is not None:
            updates.append("pages_found = ?")
            params.append(pages_found)
        if error_message is not None:
            updates.append("error_message = ?")
            params.append(error_message)

        if updates:
            params.append(job_id)
            conn.execute(
                f"UPDATE crawl_jobs SET {', '.join(updates)} WHERE job_id = ?",
                params,
            )
            conn.commit()
    finally:
        conn.close()


def get_crawl_jobs(team_id: str) -> list[dict]:
    """Get all crawl jobs for a team, ordered by most recent first."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT job_id, team_id, triggered_by, source_url, job_type, status, "
            "pages_found, error_message, config_json, started_at, finished_at "
            "FROM crawl_jobs WHERE team_id = ? ORDER BY started_at DESC",
            (team_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_crawl_job(job_id: str) -> dict | None:
    """Get a single crawl job by ID."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT job_id, team_id, triggered_by, source_url, job_type, status, "
            "pages_found, error_message, config_json, started_at, finished_at "
            "FROM crawl_jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# === Page Storage ===


def store_crawled_page(
    team_id: str,
    url: str,
    markdown_content: str,
    content_hash: str,
    uploaded_by: str,
) -> tuple[str, bool]:
    """Store a crawled page in source_docs. Returns (doc_id, is_new_or_changed).

    If URL already exists for this team:
      - If content_hash matches, skip (return existing doc_id, False).
      - If content_hash differs, update content and return (doc_id, True).
    If URL does not exist, insert new record and return (doc_id, True).
    """
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT doc_id, content_hash FROM source_docs "
            "WHERE team_id = ? AND source_type = 'url' AND source_ref = ?",
            (team_id, url),
        ).fetchone()

        if existing:
            if existing["content_hash"] == content_hash:
                return existing["doc_id"], False
            # Content changed — update
            conn.execute(
                "UPDATE source_docs SET content_hash = ?, crawled_at = datetime('now'), "
                "modified_at = datetime('now'), status = 'pending' WHERE doc_id = ?",
                (content_hash, existing["doc_id"]),
            )
            conn.commit()
            return existing["doc_id"], True

        # New page
        doc_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO source_docs (doc_id, team_id, source_type, source_ref, file_name, "
            "file_format, content_hash, uploaded_by, crawled_at, status) "
            "VALUES (?, ?, 'url', ?, ?, 'html', ?, ?, datetime('now'), 'pending')",
            (doc_id, team_id, url, url.split("/")[-1] or "index", content_hash, uploaded_by),
        )
        conn.commit()
        return doc_id, True
    finally:
        conn.close()


# === Fetch Page ===


async def fetch_page_static(url: str) -> tuple[str, int]:
    """Fetch a page using httpx (for static content). Returns (html, status_code)."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        response = await client.get(
            url,
            headers={"User-Agent": "MemMesh-Crawler/1.0"},
        )
        return response.text, response.status_code


async def fetch_page_js(url: str) -> tuple[str, int]:
    """Fetch a JS-rendered page using crawl4ai. Returns (html, status_code).

    Falls back to static fetch if crawl4ai is not available.
    """
    try:
        from crawl4ai import AsyncWebCrawler

        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url)
            if result.success:
                return result.html, 200
            else:
                logger.warning("crawl4ai failed for %s, falling back to static fetch", url)
                return await fetch_page_static(url)
    except ImportError:
        logger.warning("crawl4ai not installed, using static fetch for %s", url)
        return await fetch_page_static(url)
    except Exception as e:
        logger.warning("crawl4ai error for %s: %s, falling back to static fetch", url, e)
        return await fetch_page_static(url)


# === Sitemap Parsing ===


async def parse_sitemap(sitemap_url: str) -> list[str]:
    """Parse a sitemap XML and return a list of page URLs."""
    html, status = await fetch_page_static(sitemap_url)
    if status != 200:
        logger.error("Failed to fetch sitemap %s: status %d", sitemap_url, status)
        return []

    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []

    # Handle sitemap index (contains other sitemaps)
    for sitemap in soup.find_all("sitemap"):
        loc = sitemap.find("loc")
        if loc and loc.text:
            child_urls = await parse_sitemap(loc.text.strip())
            urls.extend(child_urls)

    # Handle regular sitemap (contains page URLs)
    for url_tag in soup.find_all("url"):
        loc = url_tag.find("loc")
        if loc and loc.text:
            urls.append(normalize_url(loc.text.strip()))

    return urls


# === Main Crawl Functions ===


async def crawl_single_page(
    url: str,
    team_id: str,
    user_id: str,
    use_js: bool = False,
) -> tuple[str | None, str | None]:
    """Crawl a single page. Returns (doc_id, markdown_content) or (None, None) on failure."""
    normalized = normalize_url(url)

    if not check_robots_txt(normalized):
        logger.info("Blocked by robots.txt: %s", normalized)
        return None, None

    if use_js:
        html, status = await fetch_page_js(normalized)
    else:
        html, status = await fetch_page_static(normalized)

    if status != 200:
        logger.warning("Failed to fetch %s: status %d", normalized, status)
        return None, None

    markdown = html_to_markdown(html)
    content_hash = compute_content_hash(markdown)

    doc_id, is_new = store_crawled_page(team_id, normalized, markdown, content_hash, user_id)

    if not is_new:
        logger.info("Content unchanged for %s, skipping reindex", normalized)
        return doc_id, None

    return doc_id, markdown


async def crawl_recursive(
    start_url: str,
    team_id: str,
    user_id: str,
    job_id: str,
    max_depth: int | None = None,
    max_pages: int | None = None,
    use_js: bool = False,
) -> int:
    """Recursively crawl pages starting from start_url.

    Returns the number of pages successfully crawled.
    """
    if max_depth is None:
        max_depth = settings.crawl_max_depth
    if max_pages is None:
        max_pages = settings.crawl_max_pages

    visited: set[str] = set()
    queue: list[tuple[str, int]] = [(normalize_url(start_url), 0)]
    pages_crawled = 0

    while queue and pages_crawled < max_pages:
        url, depth = queue.pop(0)

        if url in visited:
            continue
        visited.add(url)

        if not check_robots_txt(url):
            logger.info("Blocked by robots.txt: %s", url)
            continue

        try:
            if use_js:
                html, status = await fetch_page_js(url)
            else:
                html, status = await fetch_page_static(url)

            if status != 200:
                logger.warning("Failed to fetch %s: status %d", url, status)
                continue

            markdown = html_to_markdown(html)
            content_hash = compute_content_hash(markdown)
            doc_id, is_new = store_crawled_page(team_id, url, markdown, content_hash, user_id)

            pages_crawled += 1
            update_crawl_job(job_id, pages_found=pages_crawled)

            # Index the page through the standard pipeline if content is new
            if is_new and markdown:
                await _index_crawled_content(doc_id, markdown, team_id)

            # Extract and queue links if we haven't reached max depth
            if depth < max_depth:
                links = extract_links(html, url)
                for link in links:
                    if link not in visited:
                        queue.append((link, depth + 1))

        except Exception as e:
            logger.error("Error crawling %s: %s", url, e)
            continue

    return pages_crawled


async def crawl_sitemap(
    sitemap_url: str,
    team_id: str,
    user_id: str,
    job_id: str,
    max_pages: int | None = None,
    use_js: bool = False,
) -> int:
    """Crawl all pages listed in a sitemap. Returns number of pages crawled."""
    if max_pages is None:
        max_pages = settings.crawl_max_pages

    urls = await parse_sitemap(sitemap_url)
    pages_crawled = 0

    for url in urls[:max_pages]:
        doc_id, markdown = await crawl_single_page(url, team_id, user_id, use_js=use_js)
        if doc_id and markdown:
            await _index_crawled_content(doc_id, markdown, team_id)
        if doc_id:
            pages_crawled += 1
            update_crawl_job(job_id, pages_found=pages_crawled)

    return pages_crawled


async def _index_crawled_content(doc_id: str, markdown: str, team_id: str) -> None:
    """Index crawled markdown content through the standard chunking + embedding pipeline."""
    from ingestion.chunker import chunk_text
    from db.chromadb import upsert_chunks
    from db.falkordb import upsert_entities

    chunks = chunk_text(markdown, doc_id=doc_id, team_id=team_id)

    if chunks:
        await upsert_chunks(chunks, team_id)
        await upsert_entities(chunks, team_id)

    # Mark doc as indexed
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE source_docs SET status = 'indexed' WHERE doc_id = ?",
            (doc_id,),
        )
        conn.commit()
    finally:
        conn.close()


# === Orchestrator (called by API route) ===


async def run_crawl_job(
    team_id: str,
    user_id: str,
    source_url: str,
    max_depth: int | None = None,
    max_pages: int | None = None,
    use_js: bool = False,
) -> str:
    """Start a crawl job. Returns the job_id.

    Determines job type (single page, sitemap, recursive) from URL and params.
    """
    # Detect sitemap
    is_sitemap = source_url.endswith(".xml") or "sitemap" in source_url.lower()
    job_type = "sitemap" if is_sitemap else ("recursive" if (max_depth or 0) > 0 else "url")

    config = {
        "max_depth": max_depth or settings.crawl_max_depth,
        "max_pages": max_pages or settings.crawl_max_pages,
        "use_js": use_js,
    }

    job_id = create_crawl_job(team_id, user_id, source_url, job_type, config)

    try:
        if is_sitemap:
            pages = await crawl_sitemap(
                source_url, team_id, user_id, job_id,
                max_pages=max_pages, use_js=use_js,
            )
        elif job_type == "recursive":
            pages = await crawl_recursive(
                source_url, team_id, user_id, job_id,
                max_depth=max_depth, max_pages=max_pages, use_js=use_js,
            )
        else:
            doc_id, markdown = await crawl_single_page(
                source_url, team_id, user_id, use_js=use_js,
            )
            pages = 1 if doc_id else 0
            if doc_id and markdown:
                await _index_crawled_content(doc_id, markdown, team_id)

        update_crawl_job(job_id, status="done", pages_found=pages)
    except Exception as e:
        logger.error("Crawl job %s failed: %s", job_id, e)
        update_crawl_job(job_id, status="failed", error_message=str(e))

    return job_id
```

- [ ] **Step 4: Run the tests**

Run: `cd backend && python3 -m pytest tests/test_crawler.py -v`
Expected: All tests in `TestNormalizeUrl`, `TestIsSameDomain`, `TestContentHash`, `TestHtmlToMarkdown`, `TestExtractLinks` pass.

- [ ] **Step 5: Commit**

```bash
cd backend
git add ingestion/crawler.py tests/test_crawler.py
git commit -m "feat: add web crawler with URL utils, HTML conversion, link extraction"
```

---

### Task 4: Crawler Integration Tests (Mock HTTP)

**Files:**
- Modify: `backend/tests/test_crawler.py`

- [ ] **Step 1: Add integration tests with mocked HTTP to `test_crawler.py`**

Append the following to `backend/tests/test_crawler.py`:

```python
# Append to backend/tests/test_crawler.py

import asyncio
from ingestion.crawler import (
    fetch_page_static,
    crawl_single_page,
    store_crawled_page,
    create_crawl_job,
    update_crawl_job,
    get_crawl_jobs,
    get_crawl_job,
    parse_sitemap,
)


class TestFetchPageStatic:
    @pytest.mark.asyncio
    async def test_fetches_html(self, httpx_mock):
        httpx_mock.add_response(
            url="https://example.com/test",
            html="<h1>Test Page</h1><p>Hello world.</p>",
        )
        html, status = await fetch_page_static("https://example.com/test")
        assert status == 200
        assert "<h1>Test Page</h1>" in html

    @pytest.mark.asyncio
    async def test_handles_404(self, httpx_mock):
        httpx_mock.add_response(
            url="https://example.com/missing",
            status_code=404,
        )
        html, status = await fetch_page_static("https://example.com/missing")
        assert status == 404


class TestStoreCrawledPage:
    def test_stores_new_page(self, tmp_db):
        """tmp_db fixture sets up a temporary SQLite with source_docs table."""
        doc_id, is_new = store_crawled_page(
            team_id="team-1",
            url="https://example.com/page1",
            markdown_content="# Page 1\nContent here.",
            content_hash="abc123",
            uploaded_by="user-1",
        )
        assert is_new is True
        assert doc_id is not None

    def test_skips_unchanged_content(self, tmp_db):
        doc_id1, is_new1 = store_crawled_page(
            team_id="team-1",
            url="https://example.com/page2",
            markdown_content="# Page 2",
            content_hash="hash1",
            uploaded_by="user-1",
        )
        doc_id2, is_new2 = store_crawled_page(
            team_id="team-1",
            url="https://example.com/page2",
            markdown_content="# Page 2",
            content_hash="hash1",
            uploaded_by="user-1",
        )
        assert is_new1 is True
        assert is_new2 is False
        assert doc_id1 == doc_id2

    def test_detects_content_change(self, tmp_db):
        doc_id1, is_new1 = store_crawled_page(
            team_id="team-1",
            url="https://example.com/page3",
            markdown_content="# Page 3 v1",
            content_hash="hash_v1",
            uploaded_by="user-1",
        )
        doc_id2, is_new2 = store_crawled_page(
            team_id="team-1",
            url="https://example.com/page3",
            markdown_content="# Page 3 v2",
            content_hash="hash_v2",
            uploaded_by="user-1",
        )
        assert is_new1 is True
        assert is_new2 is True
        assert doc_id1 == doc_id2


class TestCrawlJobDB:
    def test_create_and_get_job(self, tmp_db):
        job_id = create_crawl_job(
            team_id="team-1",
            triggered_by="user-1",
            source_url="https://example.com",
            job_type="url",
        )
        job = get_crawl_job(job_id)
        assert job is not None
        assert job["team_id"] == "team-1"
        assert job["status"] == "running"
        assert job["source_url"] == "https://example.com"

    def test_update_job_status(self, tmp_db):
        job_id = create_crawl_job(
            team_id="team-1",
            triggered_by="user-1",
            source_url="https://example.com",
        )
        update_crawl_job(job_id, status="done", pages_found=5)
        job = get_crawl_job(job_id)
        assert job["status"] == "done"
        assert job["pages_found"] == 5
        assert job["finished_at"] is not None

    def test_update_job_failure(self, tmp_db):
        job_id = create_crawl_job(
            team_id="team-1",
            triggered_by="user-1",
            source_url="https://example.com",
        )
        update_crawl_job(job_id, status="failed", error_message="Connection refused")
        job = get_crawl_job(job_id)
        assert job["status"] == "failed"
        assert job["error_message"] == "Connection refused"

    def test_get_jobs_by_team(self, tmp_db):
        create_crawl_job("team-1", "user-1", "https://a.com")
        create_crawl_job("team-1", "user-1", "https://b.com")
        create_crawl_job("team-2", "user-2", "https://c.com")

        team1_jobs = get_crawl_jobs("team-1")
        team2_jobs = get_crawl_jobs("team-2")
        assert len(team1_jobs) == 2
        assert len(team2_jobs) == 1


class TestParseSitemap:
    @pytest.mark.asyncio
    async def test_parses_simple_sitemap(self, httpx_mock):
        sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url><loc>https://example.com/page1</loc></url>
            <url><loc>https://example.com/page2</loc></url>
            <url><loc>https://example.com/page3</loc></url>
        </urlset>"""
        httpx_mock.add_response(
            url="https://example.com/sitemap.xml",
            text=sitemap_xml,
        )
        urls = await parse_sitemap("https://example.com/sitemap.xml")
        assert len(urls) == 3
        assert "https://example.com/page1" in urls
        assert "https://example.com/page2" in urls
        assert "https://example.com/page3" in urls

    @pytest.mark.asyncio
    async def test_handles_sitemap_fetch_failure(self, httpx_mock):
        httpx_mock.add_response(
            url="https://example.com/sitemap.xml",
            status_code=500,
        )
        urls = await parse_sitemap("https://example.com/sitemap.xml")
        assert urls == []
```

- [ ] **Step 2: Add test fixtures for tmp_db and httpx_mock to conftest.py**

Add the following to `backend/tests/conftest.py`:

```python
# backend/tests/conftest.py — append these fixtures

import os
import tempfile
import pytest

# httpx_mock is provided by pytest-httpx (add to requirements.txt: pytest-httpx==0.34.0)


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Create a temporary SQLite database with all tables for testing."""
    db_path = str(tmp_path / "test.sqlite3")
    monkeypatch.setattr("config.settings", _make_test_settings(db_path))

    from db.sqlite import get_connection, run_migrations
    run_migrations()
    yield db_path


def _make_test_settings(db_path: str):
    """Create test settings with a temp database path."""
    from config import Settings
    return Settings(
        admin_email="admin@test.com",
        admin_password="testpass",
        jwt_secret="test-secret",
        jwt_expiry_minutes=60,
        api_host="127.0.0.1",
        api_port=8000,
        data_dir=str(os.path.dirname(db_path)),
        sqlite_path=db_path,
        # Add all other fields from Settings with test defaults
        crawl_max_depth=2,
        crawl_max_pages=100,
        crawl_respect_robots=True,
        crawl_refresh_interval_hours=24,
        gdrive_service_account_json="",
    )
```

> Note: Add `pytest-httpx==0.34.0` and `pytest-asyncio==0.24.0` to `requirements.txt` if not already present.

- [ ] **Step 3: Run the integration tests**

Run: `cd backend && python3 -m pytest tests/test_crawler.py -v`
Expected: All unit tests and integration tests pass.

- [ ] **Step 4: Commit**

```bash
cd backend
git add tests/test_crawler.py tests/conftest.py requirements.txt
git commit -m "test: add crawler integration tests with mock HTTP and temp DB"
```

---

## Group C: Google Drive Connector

### Task 5: Google Drive Connector

**Files:**
- Create: `backend/tests/test_gdrive.py`
- Create: `backend/ingestion/gdrive.py`

- [ ] **Step 1: Write failing tests for Google Drive connector**

```python
# backend/tests/test_gdrive.py
"""Unit tests for the Google Drive connector."""

import pytest
from unittest.mock import patch, MagicMock
from ingestion.gdrive import (
    get_export_mime_type,
    is_google_workspace_file,
    get_file_extension,
    build_drive_service,
)


class TestExportMimeType:
    def test_google_docs_exports_as_docx(self):
        mime = get_export_mime_type("application/vnd.google-apps.document")
        assert mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    def test_google_sheets_exports_as_xlsx(self):
        mime = get_export_mime_type("application/vnd.google-apps.spreadsheet")
        assert mime == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    def test_google_slides_exports_as_pptx(self):
        mime = get_export_mime_type("application/vnd.google-apps.presentation")
        assert mime == "application/vnd.openxmlformats-officedocument.presentationml.presentation"

    def test_unknown_type_returns_none(self):
        mime = get_export_mime_type("application/pdf")
        assert mime is None


class TestIsGoogleWorkspaceFile:
    def test_google_docs(self):
        assert is_google_workspace_file("application/vnd.google-apps.document") is True

    def test_google_sheets(self):
        assert is_google_workspace_file("application/vnd.google-apps.spreadsheet") is True

    def test_google_slides(self):
        assert is_google_workspace_file("application/vnd.google-apps.presentation") is True

    def test_pdf_is_not_workspace(self):
        assert is_google_workspace_file("application/pdf") is False

    def test_folder_is_not_workspace(self):
        assert is_google_workspace_file("application/vnd.google-apps.folder") is False


class TestGetFileExtension:
    def test_docx_for_google_docs(self):
        ext = get_file_extension("application/vnd.google-apps.document")
        assert ext == ".docx"

    def test_xlsx_for_google_sheets(self):
        ext = get_file_extension("application/vnd.google-apps.spreadsheet")
        assert ext == ".xlsx"

    def test_pptx_for_google_slides(self):
        ext = get_file_extension("application/vnd.google-apps.presentation")
        assert ext == ".pptx"

    def test_pdf_from_native_mime(self):
        ext = get_file_extension("application/pdf")
        assert ext == ".pdf"

    def test_unknown_mime(self):
        ext = get_file_extension("application/octet-stream")
        assert ext == ""


class TestBuildDriveService:
    def test_raises_when_no_credentials(self):
        """Should raise ValueError when no service account JSON is configured."""
        with patch("ingestion.gdrive.settings") as mock_settings:
            mock_settings.gdrive_service_account_json = ""
            with pytest.raises(ValueError, match="GDRIVE_SERVICE_ACCOUNT_JSON"):
                build_drive_service()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python3 -m pytest tests/test_gdrive.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ingestion.gdrive'`

- [ ] **Step 3: Implement the Google Drive connector**

```python
# backend/ingestion/gdrive.py
"""Google Drive connector for downloading and syncing files.

Authenticates via Service Account JSON. Exports Google Workspace files
(Docs, Sheets, Slides) to standard formats and downloads native files directly.
All files are passed through the standard document parser pipeline.
"""

import io
import json
import logging
import mimetypes
import uuid
from pathlib import Path

from config import settings
from db.sqlite import get_connection
from ingestion.crawler import create_crawl_job, update_crawl_job

logger = logging.getLogger(__name__)

# Google Workspace MIME type → export MIME type mapping
GOOGLE_EXPORT_MAP: dict[str, str] = {
    "application/vnd.google-apps.document": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.google-apps.spreadsheet": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.google-apps.presentation": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

# Google Workspace MIME type → file extension
GOOGLE_EXTENSION_MAP: dict[str, str] = {
    "application/vnd.google-apps.document": ".docx",
    "application/vnd.google-apps.spreadsheet": ".xlsx",
    "application/vnd.google-apps.presentation": ".pptx",
}

# MIME types to skip (folders, forms, etc.)
GOOGLE_SKIP_TYPES: set[str] = {
    "application/vnd.google-apps.folder",
    "application/vnd.google-apps.form",
    "application/vnd.google-apps.map",
    "application/vnd.google-apps.site",
    "application/vnd.google-apps.shortcut",
}


def get_export_mime_type(google_mime: str) -> str | None:
    """Get the export MIME type for a Google Workspace file. Returns None for non-Workspace types."""
    return GOOGLE_EXPORT_MAP.get(google_mime)


def is_google_workspace_file(mime_type: str) -> bool:
    """Check if a MIME type is a Google Workspace type that needs export."""
    return mime_type in GOOGLE_EXPORT_MAP


def get_file_extension(mime_type: str) -> str:
    """Get file extension for a MIME type. Handles both Google Workspace and native types."""
    if mime_type in GOOGLE_EXTENSION_MAP:
        return GOOGLE_EXTENSION_MAP[mime_type]
    ext = mimetypes.guess_extension(mime_type)
    return ext if ext else ""


def build_drive_service():
    """Build a Google Drive API service using Service Account credentials.

    Raises ValueError if GDRIVE_SERVICE_ACCOUNT_JSON is not configured.
    """
    if not settings.gdrive_service_account_json:
        raise ValueError(
            "GDRIVE_SERVICE_ACCOUNT_JSON is not configured. "
            "Set the path to your service account JSON file in .env."
        )

    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    sa_json_path = settings.gdrive_service_account_json
    # Support both file path and inline JSON
    if sa_json_path.strip().startswith("{"):
        info = json.loads(sa_json_path)
        credentials = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )
    else:
        credentials = service_account.Credentials.from_service_account_file(
            sa_json_path, scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )

    return build("drive", "v3", credentials=credentials)


def list_files_in_folder(service, folder_id: str) -> list[dict]:
    """List all files in a Google Drive folder (non-recursive).

    Returns list of dicts with keys: id, name, mimeType, modifiedTime.
    """
    results: list[dict] = []
    page_token = None

    while True:
        response = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            spaces="drive",
            fields="nextPageToken, files(id, name, mimeType, modifiedTime, size)",
            pageToken=page_token,
            pageSize=100,
        ).execute()

        files = response.get("files", [])
        results.extend(files)
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return results


def download_file(service, file_id: str, mime_type: str) -> bytes:
    """Download a native file from Google Drive. Returns file bytes."""
    from googleapiclient.http import MediaIoBaseDownload

    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue()


def export_file(service, file_id: str, export_mime: str) -> bytes:
    """Export a Google Workspace file to a standard format. Returns file bytes."""
    from googleapiclient.http import MediaIoBaseDownload

    request = service.files().export_media(fileId=file_id, mimeType=export_mime)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue()


def store_gdrive_doc(
    team_id: str,
    file_name: str,
    gdrive_file_id: str,
    file_format: str,
    content_hash: str,
    uploaded_by: str,
) -> tuple[str, bool]:
    """Store a Google Drive file in source_docs. Returns (doc_id, is_new_or_changed).

    Skips if content_hash matches existing record for same gdrive file ID.
    """
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT doc_id, content_hash FROM source_docs "
            "WHERE team_id = ? AND source_type = 'gdrive' AND source_ref = ?",
            (team_id, gdrive_file_id),
        ).fetchone()

        if existing:
            if existing["content_hash"] == content_hash:
                return existing["doc_id"], False
            conn.execute(
                "UPDATE source_docs SET content_hash = ?, modified_at = datetime('now'), "
                "status = 'pending', file_name = ? WHERE doc_id = ?",
                (content_hash, file_name, existing["doc_id"]),
            )
            conn.commit()
            return existing["doc_id"], True

        doc_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO source_docs (doc_id, team_id, source_type, source_ref, file_name, "
            "file_format, content_hash, uploaded_by, crawled_at, status) "
            "VALUES (?, ?, 'gdrive', ?, ?, ?, ?, ?, datetime('now'), 'pending')",
            (doc_id, team_id, gdrive_file_id, file_name, file_format, content_hash, uploaded_by),
        )
        conn.commit()
        return doc_id, True
    finally:
        conn.close()


async def sync_gdrive_folder(
    team_id: str,
    user_id: str,
    folder_id: str,
) -> str:
    """Sync all files from a Google Drive folder to the team's knowledge base.

    Returns the job_id for tracking.
    """
    import hashlib

    job_id = create_crawl_job(
        team_id=team_id,
        triggered_by=user_id,
        source_url=f"gdrive://{folder_id}",
        job_type="gdrive",
        config={"folder_id": folder_id},
    )

    try:
        service = build_drive_service()
        files = list_files_in_folder(service, folder_id)
        pages_found = 0

        for gfile in files:
            mime_type = gfile["mimeType"]

            # Skip unsupported types
            if mime_type in GOOGLE_SKIP_TYPES:
                logger.info("Skipping unsupported type %s: %s", mime_type, gfile["name"])
                continue

            try:
                if is_google_workspace_file(mime_type):
                    export_mime = get_export_mime_type(mime_type)
                    file_bytes = export_file(service, gfile["id"], export_mime)
                    ext = get_file_extension(mime_type)
                    file_name = gfile["name"] + ext
                else:
                    file_bytes = download_file(service, gfile["id"], mime_type)
                    ext = get_file_extension(mime_type)
                    file_name = gfile["name"]

                content_hash = hashlib.sha256(file_bytes).hexdigest()
                file_format = ext.lstrip(".")

                doc_id, is_new = store_gdrive_doc(
                    team_id, file_name, gfile["id"], file_format, content_hash, user_id
                )

                if is_new:
                    # Save file to upload dir and run through parser
                    upload_dir = Path(settings.data_dir) / "uploads" / team_id
                    upload_dir.mkdir(parents=True, exist_ok=True)
                    file_path = upload_dir / f"{doc_id}{ext}"
                    file_path.write_bytes(file_bytes)

                    # Index through standard pipeline
                    from ingestion.parser import parse_document
                    from ingestion.chunker import chunk_text
                    from db.chromadb import upsert_chunks
                    from db.falkordb import upsert_entities

                    text = parse_document(str(file_path), file_format)
                    if text:
                        chunks = chunk_text(text, doc_id=doc_id, team_id=team_id)
                        if chunks:
                            await upsert_chunks(chunks, team_id)
                            await upsert_entities(chunks, team_id)

                    # Mark as indexed
                    conn = get_connection()
                    try:
                        conn.execute(
                            "UPDATE source_docs SET status = 'indexed' WHERE doc_id = ?",
                            (doc_id,),
                        )
                        conn.commit()
                    finally:
                        conn.close()

                pages_found += 1
                update_crawl_job(job_id, pages_found=pages_found)

            except Exception as e:
                logger.error("Error processing GDrive file %s: %s", gfile["name"], e)
                continue

        update_crawl_job(job_id, status="done", pages_found=pages_found)

    except Exception as e:
        logger.error("GDrive sync job %s failed: %s", job_id, e)
        update_crawl_job(job_id, status="failed", error_message=str(e))

    return job_id
```

- [ ] **Step 4: Run the tests**

Run: `cd backend && python3 -m pytest tests/test_gdrive.py -v`
Expected: All 10 tests pass.

- [ ] **Step 5: Commit**

```bash
cd backend
git add ingestion/gdrive.py tests/test_gdrive.py
git commit -m "feat: add Google Drive connector with workspace file export"
```

---

## Group D: Ingestion API Endpoints

### Task 6: Crawl & GDrive API Routes

**Files:**
- Modify: `backend/api/routes/ingest.py`
- Create: `backend/tests/test_ingest_api_crawl.py`

- [ ] **Step 1: Write failing API tests for crawl and gdrive endpoints**

```python
# backend/tests/test_ingest_api_crawl.py
"""API tests for crawl and Google Drive ingestion endpoints."""

import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient


class TestCrawlUrlEndpoint:
    @pytest.mark.asyncio
    async def test_trigger_url_crawl(self, auth_client_team_lead):
        """Team Lead can trigger a URL crawl."""
        client, team_id, headers = auth_client_team_lead

        with patch("api.routes.ingest.run_crawl_job", new_callable=AsyncMock) as mock_crawl:
            mock_crawl.return_value = "job-123"
            response = await client.post(
                f"/team/{team_id}/ingest/url",
                json={"url": "https://example.com", "max_depth": 1, "max_pages": 10},
                headers=headers,
            )
        assert response.status_code == 202
        body = response.json()
        assert body["job_id"] == "job-123"
        assert body["status"] == "accepted"

    @pytest.mark.asyncio
    async def test_trigger_url_crawl_requires_team_lead(self, auth_client_user):
        """Regular user cannot trigger a URL crawl."""
        client, team_id, headers = auth_client_user
        response = await client.post(
            f"/team/{team_id}/ingest/url",
            json={"url": "https://example.com"},
            headers=headers,
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_trigger_url_crawl_validates_url(self, auth_client_team_lead):
        """URL must be a valid HTTP(S) URL."""
        client, team_id, headers = auth_client_team_lead
        response = await client.post(
            f"/team/{team_id}/ingest/url",
            json={"url": "not-a-url"},
            headers=headers,
        )
        assert response.status_code == 422


class TestGDriveEndpoint:
    @pytest.mark.asyncio
    async def test_trigger_gdrive_sync(self, auth_client_team_lead):
        """Team Lead can trigger Google Drive sync."""
        client, team_id, headers = auth_client_team_lead

        with patch("api.routes.ingest.sync_gdrive_folder", new_callable=AsyncMock) as mock_sync:
            mock_sync.return_value = "job-456"
            response = await client.post(
                f"/team/{team_id}/ingest/gdrive",
                json={"folder_id": "abc123folder"},
                headers=headers,
            )
        assert response.status_code == 202
        body = response.json()
        assert body["job_id"] == "job-456"

    @pytest.mark.asyncio
    async def test_trigger_gdrive_requires_team_lead(self, auth_client_user):
        """Regular user cannot trigger Google Drive sync."""
        client, team_id, headers = auth_client_user
        response = await client.post(
            f"/team/{team_id}/ingest/gdrive",
            json={"folder_id": "abc123folder"},
            headers=headers,
        )
        assert response.status_code == 403


class TestIngestStatusEndpoint:
    @pytest.mark.asyncio
    async def test_get_ingest_status(self, auth_client_team_lead):
        """Team Lead can view ingestion job status."""
        client, team_id, headers = auth_client_team_lead

        with patch("api.routes.ingest.get_crawl_jobs") as mock_jobs:
            mock_jobs.return_value = [
                {
                    "job_id": "job-1",
                    "team_id": team_id,
                    "source_url": "https://example.com",
                    "job_type": "url",
                    "status": "done",
                    "pages_found": 5,
                    "started_at": "2026-05-31T10:00:00",
                    "finished_at": "2026-05-31T10:01:00",
                }
            ]
            response = await client.get(
                f"/team/{team_id}/ingest/status",
                headers=headers,
            )
        assert response.status_code == 200
        body = response.json()
        assert len(body["jobs"]) == 1
        assert body["jobs"][0]["status"] == "done"

    @pytest.mark.asyncio
    async def test_ingest_status_requires_team_lead_or_member(self, auth_client_user):
        """Regular team members can view ingestion status."""
        client, team_id, headers = auth_client_user

        with patch("api.routes.ingest.get_crawl_jobs") as mock_jobs:
            mock_jobs.return_value = []
            response = await client.get(
                f"/team/{team_id}/ingest/status",
                headers=headers,
            )
        # Users can view status (read-only), but can't trigger
        assert response.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python3 -m pytest tests/test_ingest_api_crawl.py -v`
Expected: FAIL — routes not yet added

- [ ] **Step 3: Add crawl and gdrive routes to `ingest.py`**

Add the following routes to `backend/api/routes/ingest.py`:

```python
# backend/api/routes/ingest.py — add these imports and routes

import asyncio
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, field_validator

from auth.middleware import get_current_user, require_team_lead, require_team_member
from ingestion.crawler import run_crawl_job, get_crawl_jobs
from ingestion.gdrive import sync_gdrive_folder

router = APIRouter()


# === Request/Response Models ===


class CrawlUrlRequest(BaseModel):
    url: str
    max_depth: int | None = None
    max_pages: int | None = None
    use_js: bool = False

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("URL must use http or https scheme")
        if not parsed.netloc:
            raise ValueError("URL must have a valid domain")
        return v


class GDriveSyncRequest(BaseModel):
    folder_id: str


class JobAcceptedResponse(BaseModel):
    job_id: str
    status: str = "accepted"


class IngestStatusResponse(BaseModel):
    jobs: list[dict]


# === Routes ===


@router.post(
    "/team/{team_id}/ingest/url",
    response_model=JobAcceptedResponse,
    status_code=202,
)
async def trigger_url_crawl(
    team_id: str,
    body: CrawlUrlRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_team_lead),
):
    """Trigger a URL crawl for a team. Team Lead only."""
    job_id = await run_crawl_job(
        team_id=team_id,
        user_id=user["user_id"],
        source_url=body.url,
        max_depth=body.max_depth,
        max_pages=body.max_pages,
        use_js=body.use_js,
    )
    return JobAcceptedResponse(job_id=job_id)


@router.post(
    "/team/{team_id}/ingest/gdrive",
    response_model=JobAcceptedResponse,
    status_code=202,
)
async def trigger_gdrive_sync(
    team_id: str,
    body: GDriveSyncRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_team_lead),
):
    """Trigger Google Drive sync for a team. Team Lead only."""
    job_id = await sync_gdrive_folder(
        team_id=team_id,
        user_id=user["user_id"],
        folder_id=body.folder_id,
    )
    return JobAcceptedResponse(job_id=job_id)


@router.get(
    "/team/{team_id}/ingest/status",
    response_model=IngestStatusResponse,
)
async def get_ingest_status(
    team_id: str,
    user: dict = Depends(require_team_member),
):
    """Get ingestion job status for a team. Any team member can view."""
    jobs = get_crawl_jobs(team_id)
    return IngestStatusResponse(jobs=jobs)
```

- [ ] **Step 4: Run the API tests**

Run: `cd backend && python3 -m pytest tests/test_ingest_api_crawl.py -v`
Expected: All 6 tests pass.

- [ ] **Step 5: Commit**

```bash
cd backend
git add api/routes/ingest.py tests/test_ingest_api_crawl.py
git commit -m "feat: add crawl and gdrive ingestion API endpoints"
```

---

## Group E: Scheduled Recrawl (APScheduler)

### Task 7: APScheduler Integration

**Files:**
- Modify: `backend/api/server.py`
- Create: `backend/tests/test_scheduler.py`

- [ ] **Step 1: Write failing test for scheduler setup**

```python
# backend/tests/test_scheduler.py
"""Tests for APScheduler crawl refresh job."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestSchedulerSetup:
    def test_scheduler_creates_crawl_refresh_job(self):
        """Verify the scheduler registers a crawl refresh job."""
        with patch("apscheduler.schedulers.asyncio.AsyncIOScheduler") as MockScheduler:
            mock_instance = MagicMock()
            MockScheduler.return_value = mock_instance

            from api.server import setup_scheduler
            setup_scheduler(mock_instance)

            mock_instance.add_job.assert_called()
            # Verify the job was added with correct interval
            call_args = mock_instance.add_job.call_args
            assert call_args is not None


class TestCrawlRefreshJob:
    @pytest.mark.asyncio
    async def test_refresh_recrawls_due_urls(self, tmp_db):
        """Crawl refresh job should recrawl URLs that are past their refresh interval."""
        from api.server import crawl_refresh_job
        from ingestion.crawler import create_crawl_job

        # Create a completed crawl job that is due for refresh
        from db.sqlite import get_connection
        conn = get_connection()
        conn.execute(
            "INSERT INTO crawl_jobs (job_id, team_id, triggered_by, source_url, "
            "job_type, status, pages_found, started_at, finished_at) "
            "VALUES ('old-job', 'team-1', 'user-1', 'https://example.com', "
            "'url', 'done', 3, datetime('now', '-48 hours'), datetime('now', '-48 hours'))",
        )
        conn.commit()
        conn.close()

        with patch("api.server.run_crawl_job", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = "new-job-id"
            await crawl_refresh_job()
            # Should have been called since the job is older than refresh interval
            # (48 hours > 24 hour default)
            mock_run.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python3 -m pytest tests/test_scheduler.py -v`
Expected: FAIL — `setup_scheduler` and `crawl_refresh_job` not yet defined

- [ ] **Step 3: Add APScheduler setup to `api/server.py`**

Add the following to `backend/api/server.py`:

```python
# backend/api/server.py — add scheduler setup

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from config import settings
from db.sqlite import get_connection

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def setup_scheduler(sched: AsyncIOScheduler) -> None:
    """Configure scheduled jobs for crawl refresh."""
    sched.add_job(
        crawl_refresh_job,
        "interval",
        hours=settings.crawl_refresh_interval_hours,
        id="crawl_refresh",
        replace_existing=True,
    )
    logger.info(
        "Crawl refresh job scheduled every %d hours",
        settings.crawl_refresh_interval_hours,
    )


async def crawl_refresh_job() -> None:
    """Recrawl URLs that are past their refresh interval.

    Finds all completed crawl jobs where finished_at is older than
    CRAWL_REFRESH_INTERVAL_HOURS and triggers a new crawl.
    """
    from ingestion.crawler import run_crawl_job

    conn = get_connection()
    try:
        hours = settings.crawl_refresh_interval_hours
        rows = conn.execute(
            "SELECT DISTINCT source_url, team_id, triggered_by, config_json "
            "FROM crawl_jobs "
            "WHERE status = 'done' "
            "AND job_type IN ('url', 'recursive', 'sitemap') "
            "AND finished_at < datetime('now', ? || ' hours')",
            (f"-{hours}",),
        ).fetchall()
    finally:
        conn.close()

    for row in rows:
        try:
            import json
            config = json.loads(row["config_json"]) if row["config_json"] else {}
            await run_crawl_job(
                team_id=row["team_id"],
                user_id=row["triggered_by"],
                source_url=row["source_url"],
                max_depth=config.get("max_depth"),
                max_pages=config.get("max_pages"),
                use_js=config.get("use_js", False),
            )
            logger.info("Recrawled %s for team %s", row["source_url"], row["team_id"])
        except Exception as e:
            logger.error("Failed to recrawl %s: %s", row["source_url"], e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: start/stop scheduler."""
    setup_scheduler(scheduler)
    scheduler.start()
    logger.info("APScheduler started")
    yield
    scheduler.shutdown()
    logger.info("APScheduler stopped")


# Update the FastAPI app factory to use the lifespan
# def create_app() -> FastAPI:
#     app = FastAPI(title="MemMesh API", lifespan=lifespan)
#     # ... existing route registration ...
#     return app
```

- [ ] **Step 4: Run the scheduler tests**

Run: `cd backend && python3 -m pytest tests/test_scheduler.py -v`
Expected: Both tests pass.

- [ ] **Step 5: Commit**

```bash
cd backend
git add api/server.py tests/test_scheduler.py
git commit -m "feat: add APScheduler for periodic crawl refresh"
```

---

## Group F: Frontend — Crawl Management UI

### Task 8: TypeScript Types & API Client Updates

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add crawl and gdrive types to `types.ts`**

Append to `frontend/src/lib/types.ts`:

```typescript
// frontend/src/lib/types.ts — append these types

export interface CrawlJob {
  job_id: string;
  team_id: string;
  triggered_by: string;
  source_url: string;
  job_type: 'url' | 'sitemap' | 'recursive' | 'gdrive';
  status: 'running' | 'done' | 'failed';
  pages_found: number;
  error_message: string | null;
  config_json: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface CrawlUrlRequest {
  url: string;
  max_depth?: number;
  max_pages?: number;
  use_js?: boolean;
}

export interface GDriveSyncRequest {
  folder_id: string;
}

export interface JobAcceptedResponse {
  job_id: string;
  status: string;
}

export interface IngestStatusResponse {
  jobs: CrawlJob[];
}
```

- [ ] **Step 2: Add API client methods to `api.ts`**

Append to `frontend/src/lib/api.ts`:

```typescript
// frontend/src/lib/api.ts — append these methods

export async function triggerUrlCrawl(
  teamId: string,
  request: CrawlUrlRequest
): Promise<JobAcceptedResponse> {
  const response = await fetchWithAuth(`/team/${teamId}/ingest/url`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw new Error(`Failed to trigger URL crawl: ${response.statusText}`);
  }
  return response.json();
}

export async function triggerGDriveSync(
  teamId: string,
  request: GDriveSyncRequest
): Promise<JobAcceptedResponse> {
  const response = await fetchWithAuth(`/team/${teamId}/ingest/gdrive`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw new Error(`Failed to trigger GDrive sync: ${response.statusText}`);
  }
  return response.json();
}

export async function getIngestStatus(teamId: string): Promise<IngestStatusResponse> {
  const response = await fetchWithAuth(`/team/${teamId}/ingest/status`);
  if (!response.ok) {
    throw new Error(`Failed to get ingest status: ${response.statusText}`);
  }
  return response.json();
}
```

- [ ] **Step 3: Commit**

```bash
cd frontend
git add src/lib/types.ts src/lib/api.ts
git commit -m "feat: add crawl and gdrive TypeScript types and API client"
```

---

### Task 9: Crawl Manager Component

**Files:**
- Create: `frontend/src/routes/dashboard/ingest/CrawlManager.svelte`

- [ ] **Step 1: Create the CrawlManager component**

```svelte
<!-- frontend/src/routes/dashboard/ingest/CrawlManager.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { triggerUrlCrawl, getIngestStatus } from '$lib/api';
  import type { CrawlJob, CrawlUrlRequest } from '$lib/types';

  export let teamId: string;
  export let isTeamLead: boolean = false;

  let url = '';
  let maxDepth = 2;
  let maxPages = 100;
  let useJs = false;
  let jobs: CrawlJob[] = [];
  let loading = false;
  let submitting = false;
  let error = '';
  let pollInterval: ReturnType<typeof setInterval> | null = null;

  onMount(() => {
    loadJobs();
    // Poll for status updates every 10 seconds
    pollInterval = setInterval(loadJobs, 10000);
    return () => {
      if (pollInterval) clearInterval(pollInterval);
    };
  });

  async function loadJobs() {
    loading = true;
    try {
      const response = await getIngestStatus(teamId);
      jobs = response.jobs.filter((j) => j.job_type !== 'gdrive');
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load jobs';
    } finally {
      loading = false;
    }
  }

  async function handleSubmit() {
    if (!url.trim()) return;
    error = '';
    submitting = true;

    try {
      const request: CrawlUrlRequest = {
        url: url.trim(),
        max_depth: maxDepth,
        max_pages: maxPages,
        use_js: useJs,
      };
      await triggerUrlCrawl(teamId, request);
      url = '';
      await loadJobs();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to start crawl';
    } finally {
      submitting = false;
    }
  }

  async function handleRecrawl(job: CrawlJob) {
    error = '';
    try {
      const config = job.config_json ? JSON.parse(job.config_json) : {};
      await triggerUrlCrawl(teamId, {
        url: job.source_url,
        max_depth: config.max_depth,
        max_pages: config.max_pages,
        use_js: config.use_js ?? false,
      });
      await loadJobs();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to recrawl';
    }
  }

  function formatDate(dateStr: string | null): string {
    if (!dateStr) return '—';
    return new Date(dateStr).toLocaleString();
  }

  function getStatusClass(status: string): string {
    switch (status) {
      case 'running':
        return 'status-running';
      case 'done':
        return 'status-done';
      case 'failed':
        return 'status-failed';
      default:
        return '';
    }
  }
</script>

<div class="crawl-manager">
  <h3>Website Crawl</h3>

  {#if isTeamLead}
    <form class="crawl-form" on:submit|preventDefault={handleSubmit}>
      <div class="form-row">
        <label for="crawl-url">Website URL</label>
        <input
          id="crawl-url"
          type="url"
          bind:value={url}
          placeholder="https://example.com"
          required
          disabled={submitting}
        />
      </div>

      <div class="form-row form-row-inline">
        <div class="form-field">
          <label for="crawl-depth">Max Depth</label>
          <select id="crawl-depth" bind:value={maxDepth} disabled={submitting}>
            <option value={0}>Single Page</option>
            <option value={1}>1 Level</option>
            <option value={2}>2 Levels</option>
            <option value={3}>3 Levels</option>
          </select>
        </div>

        <div class="form-field">
          <label for="crawl-pages">Max Pages</label>
          <input
            id="crawl-pages"
            type="number"
            bind:value={maxPages}
            min="1"
            max="500"
            disabled={submitting}
          />
        </div>

        <div class="form-field">
          <label class="checkbox-label">
            <input type="checkbox" bind:checked={useJs} disabled={submitting} />
            JS Rendering
          </label>
        </div>
      </div>

      <button type="submit" class="btn btn-primary" disabled={submitting || !url.trim()}>
        {submitting ? 'Starting…' : 'Start Crawl'}
      </button>
    </form>
  {/if}

  {#if error}
    <div class="error-banner" role="alert">{error}</div>
  {/if}

  <div class="jobs-list">
    <h4>Crawl Jobs</h4>
    {#if loading && jobs.length === 0}
      <p class="loading-text">Loading…</p>
    {:else if jobs.length === 0}
      <p class="empty-text">No crawl jobs yet.</p>
    {:else}
      <table class="jobs-table" role="table">
        <thead>
          <tr>
            <th>URL</th>
            <th>Type</th>
            <th>Status</th>
            <th>Pages</th>
            <th>Started</th>
            <th>Finished</th>
            {#if isTeamLead}
              <th>Actions</th>
            {/if}
          </tr>
        </thead>
        <tbody>
          {#each jobs as job (job.job_id)}
            <tr>
              <td class="url-cell" title={job.source_url}>
                {job.source_url.length > 50
                  ? job.source_url.slice(0, 50) + '…'
                  : job.source_url}
              </td>
              <td>{job.job_type}</td>
              <td>
                <span class="status-badge {getStatusClass(job.status)}">
                  {job.status}
                </span>
              </td>
              <td>{job.pages_found ?? 0}</td>
              <td>{formatDate(job.started_at)}</td>
              <td>{formatDate(job.finished_at)}</td>
              {#if isTeamLead}
                <td>
                  {#if job.status !== 'running'}
                    <button
                      class="btn btn-sm btn-secondary"
                      on:click={() => handleRecrawl(job)}
                    >
                      Recrawl
                    </button>
                  {/if}
                </td>
              {/if}
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>
</div>

<style>
  .crawl-manager {
    padding: var(--spacing-md, 1rem);
  }

  .crawl-form {
    background: var(--surface, #1a1a1f);
    border: 1px solid var(--border, #2a2a2f);
    border-radius: var(--radius-md, 8px);
    padding: var(--spacing-md, 1rem);
    margin-bottom: var(--spacing-md, 1rem);
  }

  .form-row {
    margin-bottom: var(--spacing-sm, 0.5rem);
  }

  .form-row label {
    display: block;
    margin-bottom: 4px;
    font-size: 0.875rem;
    color: var(--text-secondary, #a0a0a0);
  }

  .form-row input[type='url'],
  .form-row input[type='number'] {
    width: 100%;
    padding: 8px 12px;
    background: var(--background, #0f0f11);
    border: 1px solid var(--border, #2a2a2f);
    border-radius: var(--radius-sm, 4px);
    color: var(--text, #e8e4da);
    font-size: 0.875rem;
  }

  .form-row-inline {
    display: flex;
    gap: var(--spacing-md, 1rem);
    align-items: flex-end;
  }

  .form-field {
    flex: 1;
  }

  .form-field select {
    width: 100%;
    padding: 8px 12px;
    background: var(--background, #0f0f11);
    border: 1px solid var(--border, #2a2a2f);
    border-radius: var(--radius-sm, 4px);
    color: var(--text, #e8e4da);
    font-size: 0.875rem;
  }

  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 6px;
    cursor: pointer;
    font-size: 0.875rem;
    color: var(--text-secondary, #a0a0a0);
    padding-bottom: 8px;
  }

  .btn {
    padding: 8px 16px;
    border: none;
    border-radius: var(--radius-sm, 4px);
    cursor: pointer;
    font-size: 0.875rem;
    transition: opacity 0.15s;
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-primary {
    background: var(--accent, #f5a623);
    color: var(--background, #0f0f11);
    font-weight: 600;
  }

  .btn-secondary {
    background: var(--surface, #1a1a1f);
    border: 1px solid var(--border, #2a2a2f);
    color: var(--text, #e8e4da);
  }

  .btn-sm {
    padding: 4px 8px;
    font-size: 0.75rem;
  }

  .error-banner {
    background: #3d1515;
    border: 1px solid #5c2020;
    border-radius: var(--radius-sm, 4px);
    padding: 8px 12px;
    color: #f5a0a0;
    margin-bottom: var(--spacing-md, 1rem);
    font-size: 0.875rem;
  }

  .jobs-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
  }

  .jobs-table th,
  .jobs-table td {
    padding: 8px 12px;
    text-align: left;
    border-bottom: 1px solid var(--border, #2a2a2f);
  }

  .jobs-table th {
    color: var(--text-secondary, #a0a0a0);
    font-weight: 500;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .url-cell {
    max-width: 300px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .status-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 500;
  }

  .status-running {
    background: #1a3a2a;
    color: #4ade80;
  }

  .status-done {
    background: #1a2a3a;
    color: #60a5fa;
  }

  .status-failed {
    background: #3d1515;
    color: #f87171;
  }

  .loading-text,
  .empty-text {
    color: var(--text-secondary, #a0a0a0);
    font-size: 0.875rem;
    padding: var(--spacing-md, 1rem) 0;
  }
</style>
```

- [ ] **Step 2: Commit**

```bash
cd frontend
git add src/routes/dashboard/ingest/CrawlManager.svelte
git commit -m "feat: add CrawlManager component for website crawl UI"
```

---

### Task 10: Google Drive Connect Component

**Files:**
- Create: `frontend/src/routes/dashboard/ingest/GDriveConnect.svelte`

- [ ] **Step 1: Create the GDriveConnect component**

```svelte
<!-- frontend/src/routes/dashboard/ingest/GDriveConnect.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { triggerGDriveSync, getIngestStatus } from '$lib/api';
  import type { CrawlJob } from '$lib/types';

  export let teamId: string;
  export let isTeamLead: boolean = false;

  let folderId = '';
  let jobs: CrawlJob[] = [];
  let loading = false;
  let syncing = false;
  let error = '';
  let showSetup = false;

  onMount(() => {
    loadJobs();
  });

  async function loadJobs() {
    loading = true;
    try {
      const response = await getIngestStatus(teamId);
      jobs = response.jobs.filter((j) => j.job_type === 'gdrive');
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load sync status';
    } finally {
      loading = false;
    }
  }

  async function handleSync() {
    if (!folderId.trim()) return;
    error = '';
    syncing = true;

    try {
      await triggerGDriveSync(teamId, { folder_id: folderId.trim() });
      await loadJobs();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to start sync';
    } finally {
      syncing = false;
    }
  }

  async function handleResync(job: CrawlJob) {
    error = '';
    try {
      const config = job.config_json ? JSON.parse(job.config_json) : {};
      if (config.folder_id) {
        await triggerGDriveSync(teamId, { folder_id: config.folder_id });
        await loadJobs();
      }
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to resync';
    }
  }

  function formatDate(dateStr: string | null): string {
    if (!dateStr) return '—';
    return new Date(dateStr).toLocaleString();
  }

  function getStatusClass(status: string): string {
    switch (status) {
      case 'running':
        return 'status-running';
      case 'done':
        return 'status-done';
      case 'failed':
        return 'status-failed';
      default:
        return '';
    }
  }
</script>

<div class="gdrive-connect">
  <h3>Google Drive</h3>

  {#if isTeamLead}
    <div class="setup-section">
      <button
        class="btn btn-text"
        on:click={() => (showSetup = !showSetup)}
        aria-expanded={showSetup}
      >
        {showSetup ? '▾' : '▸'} Setup Instructions
      </button>

      {#if showSetup}
        <div class="setup-instructions">
          <ol>
            <li>
              Go to the <a
                href="https://console.cloud.google.com/iam-admin/serviceaccounts"
                target="_blank"
                rel="noopener noreferrer">Google Cloud Console</a
              > and create a Service Account.
            </li>
            <li>Download the Service Account JSON key file.</li>
            <li>
              Set the <code>GDRIVE_SERVICE_ACCOUNT_JSON</code> environment variable to the path of
              the JSON key file (or paste the JSON content directly).
            </li>
            <li>
              Share the target Google Drive folder with the Service Account email address (grant
              "Viewer" access).
            </li>
            <li>
              Copy the folder ID from the Google Drive URL (the part after
              <code>/folders/</code>).
            </li>
          </ol>
        </div>
      {/if}

      <form class="sync-form" on:submit|preventDefault={handleSync}>
        <div class="form-row">
          <label for="folder-id">Google Drive Folder ID</label>
          <input
            id="folder-id"
            type="text"
            bind:value={folderId}
            placeholder="e.g. 1AbCdEfGhIjKlMnOpQrStUvWxYz"
            required
            disabled={syncing}
          />
        </div>

        <button type="submit" class="btn btn-primary" disabled={syncing || !folderId.trim()}>
          {syncing ? 'Syncing…' : 'Sync Folder'}
        </button>
      </form>
    </div>
  {/if}

  {#if error}
    <div class="error-banner" role="alert">{error}</div>
  {/if}

  <div class="sync-history">
    <h4>Sync History</h4>
    {#if loading && jobs.length === 0}
      <p class="loading-text">Loading…</p>
    {:else if jobs.length === 0}
      <p class="empty-text">No Google Drive syncs yet.</p>
    {:else}
      <div class="sync-cards">
        {#each jobs as job (job.job_id)}
          <div class="sync-card">
            <div class="sync-card-header">
              <span class="status-badge {getStatusClass(job.status)}">{job.status}</span>
              <span class="sync-date">{formatDate(job.started_at)}</span>
            </div>
            <div class="sync-card-body">
              <p class="sync-stat">
                <strong>{job.pages_found ?? 0}</strong> files synced
              </p>
              {#if job.error_message}
                <p class="sync-error">{job.error_message}</p>
              {/if}
            </div>
            {#if isTeamLead && job.status !== 'running'}
              <div class="sync-card-footer">
                <button class="btn btn-sm btn-secondary" on:click={() => handleResync(job)}>
                  Re-sync
                </button>
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  </div>
</div>

<style>
  .gdrive-connect {
    padding: var(--spacing-md, 1rem);
  }

  .setup-section {
    margin-bottom: var(--spacing-md, 1rem);
  }

  .btn-text {
    background: none;
    border: none;
    color: var(--accent, #f5a623);
    cursor: pointer;
    font-size: 0.875rem;
    padding: 4px 0;
    margin-bottom: var(--spacing-sm, 0.5rem);
  }

  .setup-instructions {
    background: var(--surface, #1a1a1f);
    border: 1px solid var(--border, #2a2a2f);
    border-radius: var(--radius-md, 8px);
    padding: var(--spacing-md, 1rem);
    margin-bottom: var(--spacing-md, 1rem);
    font-size: 0.875rem;
    line-height: 1.6;
  }

  .setup-instructions ol {
    padding-left: 1.5rem;
    margin: 0;
  }

  .setup-instructions li {
    margin-bottom: 8px;
  }

  .setup-instructions code {
    background: var(--background, #0f0f11);
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 0.8rem;
  }

  .setup-instructions a {
    color: var(--accent, #f5a623);
  }

  .sync-form {
    background: var(--surface, #1a1a1f);
    border: 1px solid var(--border, #2a2a2f);
    border-radius: var(--radius-md, 8px);
    padding: var(--spacing-md, 1rem);
    margin-bottom: var(--spacing-md, 1rem);
  }

  .form-row {
    margin-bottom: var(--spacing-sm, 0.5rem);
  }

  .form-row label {
    display: block;
    margin-bottom: 4px;
    font-size: 0.875rem;
    color: var(--text-secondary, #a0a0a0);
  }

  .form-row input[type='text'] {
    width: 100%;
    padding: 8px 12px;
    background: var(--background, #0f0f11);
    border: 1px solid var(--border, #2a2a2f);
    border-radius: var(--radius-sm, 4px);
    color: var(--text, #e8e4da);
    font-size: 0.875rem;
    font-family: monospace;
  }

  .btn {
    padding: 8px 16px;
    border: none;
    border-radius: var(--radius-sm, 4px);
    cursor: pointer;
    font-size: 0.875rem;
    transition: opacity 0.15s;
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-primary {
    background: var(--accent, #f5a623);
    color: var(--background, #0f0f11);
    font-weight: 600;
  }

  .btn-secondary {
    background: var(--surface, #1a1a1f);
    border: 1px solid var(--border, #2a2a2f);
    color: var(--text, #e8e4da);
  }

  .btn-sm {
    padding: 4px 8px;
    font-size: 0.75rem;
  }

  .error-banner {
    background: #3d1515;
    border: 1px solid #5c2020;
    border-radius: var(--radius-sm, 4px);
    padding: 8px 12px;
    color: #f5a0a0;
    margin-bottom: var(--spacing-md, 1rem);
    font-size: 0.875rem;
  }

  .sync-cards {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-sm, 0.5rem);
  }

  .sync-card {
    background: var(--surface, #1a1a1f);
    border: 1px solid var(--border, #2a2a2f);
    border-radius: var(--radius-md, 8px);
    padding: var(--spacing-sm, 0.5rem) var(--spacing-md, 1rem);
  }

  .sync-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
  }

  .sync-date {
    font-size: 0.75rem;
    color: var(--text-secondary, #a0a0a0);
  }

  .sync-stat {
    font-size: 0.875rem;
    margin: 0;
  }

  .sync-error {
    font-size: 0.75rem;
    color: #f87171;
    margin: 4px 0 0;
  }

  .sync-card-footer {
    margin-top: 8px;
    padding-top: 8px;
    border-top: 1px solid var(--border, #2a2a2f);
  }

  .status-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 500;
  }

  .status-running {
    background: #1a3a2a;
    color: #4ade80;
  }

  .status-done {
    background: #1a2a3a;
    color: #60a5fa;
  }

  .status-failed {
    background: #3d1515;
    color: #f87171;
  }

  .loading-text,
  .empty-text {
    color: var(--text-secondary, #a0a0a0);
    font-size: 0.875rem;
    padding: var(--spacing-md, 1rem) 0;
  }
</style>
```

- [ ] **Step 2: Commit**

```bash
cd frontend
git add src/routes/dashboard/ingest/GDriveConnect.svelte
git commit -m "feat: add GDriveConnect component for Google Drive sync UI"
```

---

### Task 11: Integrate Components into Ingestion Page

**Files:**
- Modify: `frontend/src/routes/dashboard/ingest/+page.svelte`

- [ ] **Step 1: Update the ingestion page to include crawl and gdrive tabs**

```svelte
<!-- frontend/src/routes/dashboard/ingest/+page.svelte -->
<script lang="ts">
  import { page } from '$app/stores';
  import CrawlManager from './CrawlManager.svelte';
  import GDriveConnect from './GDriveConnect.svelte';

  // These would come from the layout/auth store in the real app
  export let data;

  $: teamId = $page.params.team_id ?? data?.teamId ?? '';
  $: isTeamLead = data?.isTeamLead ?? false;

  let activeTab: 'upload' | 'crawl' | 'gdrive' = 'upload';

  const tabs = [
    { id: 'upload' as const, label: 'File Upload' },
    { id: 'crawl' as const, label: 'Website Crawl' },
    { id: 'gdrive' as const, label: 'Google Drive' },
  ];
</script>

<div class="ingest-page">
  <h2>Ingestion Management</h2>

  <nav class="tab-bar" role="tablist" aria-label="Ingestion source tabs">
    {#each tabs as tab (tab.id)}
      <button
        role="tab"
        class="tab-button"
        class:active={activeTab === tab.id}
        aria-selected={activeTab === tab.id}
        on:click={() => (activeTab = tab.id)}
      >
        {tab.label}
      </button>
    {/each}
  </nav>

  <div class="tab-content" role="tabpanel">
    {#if activeTab === 'upload'}
      <!-- Existing upload UI from previous phases -->
      <div class="upload-placeholder">
        <p>File upload interface (implemented in Phase 3)</p>
      </div>
    {:else if activeTab === 'crawl'}
      <CrawlManager {teamId} {isTeamLead} />
    {:else if activeTab === 'gdrive'}
      <GDriveConnect {teamId} {isTeamLead} />
    {/if}
  </div>
</div>

<style>
  .ingest-page {
    max-width: 960px;
    margin: 0 auto;
    padding: var(--spacing-lg, 1.5rem);
  }

  .ingest-page h2 {
    margin-bottom: var(--spacing-md, 1rem);
  }

  .tab-bar {
    display: flex;
    gap: 0;
    border-bottom: 1px solid var(--border, #2a2a2f);
    margin-bottom: var(--spacing-md, 1rem);
  }

  .tab-button {
    padding: 10px 20px;
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--text-secondary, #a0a0a0);
    cursor: pointer;
    font-size: 0.875rem;
    font-weight: 500;
    transition: color 0.15s, border-color 0.15s;
  }

  .tab-button:hover {
    color: var(--text, #e8e4da);
  }

  .tab-button.active {
    color: var(--accent, #f5a623);
    border-bottom-color: var(--accent, #f5a623);
  }

  .tab-content {
    min-height: 400px;
  }

  .upload-placeholder {
    padding: var(--spacing-lg, 1.5rem);
    text-align: center;
    color: var(--text-secondary, #a0a0a0);
  }
</style>
```

- [ ] **Step 2: Commit**

```bash
cd frontend
git add src/routes/dashboard/ingest/+page.svelte
git commit -m "feat: integrate crawl and gdrive components into ingestion page"
```

---

## Group G: E2E Tests

### Task 12: Playwright E2E Tests

**Files:**
- Create: `frontend/tests/e2e/crawl.spec.ts`

- [ ] **Step 1: Write Playwright E2E test for crawl workflow**

```typescript
// frontend/tests/e2e/crawl.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Website Crawl', () => {
  test.beforeEach(async ({ page }) => {
    // Login as team lead
    await page.goto('/login');
    await page.getByLabel('Email').fill('teamlead@test.com');
    await page.getByLabel('Password').fill('testpassword');
    await page.getByRole('button', { name: 'Login' }).click();
    await page.waitForURL('/dashboard');
  });

  test('submit website URL and observe crawl completion', async ({ page }) => {
    // Navigate to ingestion page
    await page.goto('/dashboard/ingest');

    // Click the Website Crawl tab
    await page.getByRole('tab', { name: 'Website Crawl' }).click();

    // Fill in the URL form
    await page.getByLabel('Website URL').fill('https://example.com');

    // Select depth
    await page.getByLabel('Max Depth').selectOption('1');

    // Submit
    await page.getByRole('button', { name: 'Start Crawl' }).click();

    // Verify the job appears in the list
    await expect(page.getByText('example.com')).toBeVisible({ timeout: 10000 });

    // Wait for status to change from running to done
    await expect(page.getByText('done')).toBeVisible({ timeout: 30000 });
  });

  test('crawl job shows page count', async ({ page }) => {
    await page.goto('/dashboard/ingest');
    await page.getByRole('tab', { name: 'Website Crawl' }).click();

    // Check that jobs table has pages column
    const table = page.locator('.jobs-table');
    await expect(table.getByText('Pages')).toBeVisible();
  });

  test('recrawl button triggers new crawl', async ({ page }) => {
    await page.goto('/dashboard/ingest');
    await page.getByRole('tab', { name: 'Website Crawl' }).click();

    // If there are existing jobs with a Recrawl button
    const recrawlButton = page.getByRole('button', { name: 'Recrawl' }).first();
    if (await recrawlButton.isVisible()) {
      await recrawlButton.click();

      // Verify a new running job appears
      await expect(page.getByText('running')).toBeVisible({ timeout: 5000 });
    }
  });

  test('regular user cannot see crawl form', async ({ page, context }) => {
    // Login as regular user
    await context.clearCookies();
    await page.goto('/login');
    await page.getByLabel('Email').fill('user@test.com');
    await page.getByLabel('Password').fill('testpassword');
    await page.getByRole('button', { name: 'Login' }).click();
    await page.waitForURL('/dashboard');

    await page.goto('/dashboard/ingest');
    await page.getByRole('tab', { name: 'Website Crawl' }).click();

    // Form should not be visible for regular users
    await expect(page.getByLabel('Website URL')).not.toBeVisible();
    // But jobs table should still be visible (read-only)
    await expect(page.getByText('Crawl Jobs')).toBeVisible();
  });
});

test.describe('Google Drive Sync', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Email').fill('teamlead@test.com');
    await page.getByLabel('Password').fill('testpassword');
    await page.getByRole('button', { name: 'Login' }).click();
    await page.waitForURL('/dashboard');
  });

  test('shows setup instructions', async ({ page }) => {
    await page.goto('/dashboard/ingest');
    await page.getByRole('tab', { name: 'Google Drive' }).click();

    // Expand setup instructions
    await page.getByText('Setup Instructions').click();

    // Verify instructions are visible
    await expect(page.getByText('Service Account')).toBeVisible();
    await expect(page.getByText('GDRIVE_SERVICE_ACCOUNT_JSON')).toBeVisible();
  });

  test('folder ID input and sync button', async ({ page }) => {
    await page.goto('/dashboard/ingest');
    await page.getByRole('tab', { name: 'Google Drive' }).click();

    // Fill folder ID
    await page.getByLabel('Google Drive Folder ID').fill('1AbCdEfG');

    // Sync button should be enabled
    const syncButton = page.getByRole('button', { name: 'Sync Folder' });
    await expect(syncButton).toBeEnabled();
  });
});
```

- [ ] **Step 2: Run the E2E tests (requires running server)**

Run: `cd frontend && npx playwright test tests/e2e/crawl.spec.ts --reporter=list`
Expected: Tests run (may need a running backend + seeded test data to pass fully).

- [ ] **Step 3: Commit**

```bash
cd frontend
git add tests/e2e/crawl.spec.ts
git commit -m "test: add Playwright E2E tests for crawl and gdrive workflows"
```

---

## Final Verification

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && python3 -m pytest tests/ -v`
Expected: All tests pass, including new crawler and gdrive tests.

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors.

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: Phase 8 — Website Crawl & Google Drive integration complete"
```
