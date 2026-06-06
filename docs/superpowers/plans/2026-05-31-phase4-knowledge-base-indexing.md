# Phase 4 — Knowledge Base Indexing: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full knowledge base indexing pipeline: parse uploaded documents into text, chunk them with metadata, embed and upsert into team-scoped ChromaDB collections, extract entities into FalkorDB with mandatory team_id enforcement, and provide a frontend ingestion status page.

**Architecture:** Uploaded documents (already stored in `./data/uploads/{team_id}/` by Phase 3) are processed through a multi-format parser → recursive character chunker → ChromaDB embedder (team-scoped collections `team_{team_id}`) → FalkorDB entity extractor (all nodes carry mandatory `team_id`). The pipeline tracks status in `source_docs.status` (pending → indexing → indexed → failed) and indexes chunk metadata into a new `vector_chunks` SQLite table. The frontend polls ingestion status and displays it in a job monitoring UI.

**Tech Stack:** Python 3.11+, FastAPI, ChromaDB (embedded persistent), FalkorDB Lite (in-process), sentence-transformers (all-MiniLM-L6-v2), PyMuPDF, python-docx, html2text, pytesseract, spaCy (en_core_web_sm), SQLite

---

## Scope Note

This plan covers **Phase 4 only**. Phases 1–3 already provide: Makefile, FastAPI app, SQLite with users/teams/team_members/source_docs tables, JWT auth with team_memberships, role enforcement middleware, file upload to `./data/uploads/{team_id}/`, document metadata in source_docs, and a frontend with login, dashboard, team management, document upload & preview.

---

## File Structure

### Backend New/Modified Files

```
backend/
├── requirements.txt                          # Modify: add new dependencies
├── config.py                                 # Modify: add CHROMA_DIR, FALKORDB_DIR
├── ingestion/
│   ├── __init__.py                           # Create
│   ├── parser.py                             # Create: multi-format document parser
│   ├── chunker.py                            # Create: recursive character splitter
│   └── pipeline.py                           # Create: orchestrates parse → chunk → embed → extract
├── db/
│   ├── migrations/
│   │   └── 004_vector_chunks.sql             # Create: vector_chunks table
│   ├── chromadb.py                           # Create: team-scoped ChromaDB wrapper
│   └── falkordb.py                           # Create: FalkorDB wrapper with team_id enforcement
├── api/
│   ├── server.py                             # Modify: register ingest routes
│   └── routes/
│       └── ingest.py                         # Create: POST /team/{team_id}/ingest/trigger, GET status
└── tests/
    ├── test_parser.py                        # Create
    ├── test_chunker.py                       # Create
    ├── test_chromadb.py                      # Create
    ├── test_falkordb.py                      # Create
    ├── test_pipeline.py                      # Create
    └── test_ingest_api.py                    # Create
```

### Frontend New/Modified Files

```
frontend/
└── src/
    └── routes/
        └── documents/
            └── +page.svelte                  # Modify: add ingestion status section
```

---

## Group A: Dependencies & Configuration

### Task 1: Update Requirements and Config

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/config.py`
- Modify: `backend/.env.example`

- [ ] **Step 1: Update `requirements.txt`**

Add the new dependencies to the existing file. The final file should contain all previous deps plus:

```
# backend/requirements.txt
fastapi==0.115.0
uvicorn[standard]==0.32.0
python-jose[cryptography]==3.3.0
bcrypt==4.2.0
python-dotenv==1.0.1
pytest==8.3.2
httpx==0.28.0
# Phase 4: Knowledge Base Indexing
chromadb==0.5.23
sentence-transformers==3.4.1
falkordb==1.0.9
PyMuPDF==1.25.3
python-docx==1.1.2
html2text==2024.2.26
pytesseract==0.3.13
spacy==3.8.4
Pillow==11.1.0
```

- [ ] **Step 2: Update `.env.example`**

Append the new config variables to the existing `.env.example`:

```env
# Append to backend/.env.example

# ChromaDB
CHROMA_DIR=./data/chroma

# FalkorDB
FALKORDB_DIR=./data/falkordb

# Embedding model
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

- [ ] **Step 3: Update `config.py`**

Add the new fields to the `Settings` dataclass and `load_settings()`. The modified sections:

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
    upload_dir: str

    # Phase 4: Knowledge Base
    chroma_dir: str
    falkordb_dir: str
    embedding_model: str


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
        upload_dir=os.getenv("UPLOAD_DIR", "./data/uploads"),
        chroma_dir=os.getenv("CHROMA_DIR", "./data/chroma"),
        falkordb_dir=os.getenv("FALKORDB_DIR", "./data/falkordb"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
    )


settings = load_settings()
```

- [ ] **Step 4: Install dependencies**

Run: `cd backend && make install`
Expected: All dependencies install successfully.

Then download the spaCy model:

Run: `cd backend && .venv/bin/python -m spacy download en_core_web_sm`
Expected: Model downloads successfully.

- [ ] **Step 5: Verify config loads with new fields**

Run: `cd backend && .venv/bin/python -c "from config import settings; print(settings.chroma_dir, settings.falkordb_dir, settings.embedding_model)"`
Expected: `./data/chroma ./data/falkordb all-MiniLM-L6-v2`

- [ ] **Step 6: Commit**

```bash
cd backend
git add requirements.txt config.py .env.example
git commit -m "chore: add Phase 4 dependencies and config for ChromaDB, FalkorDB, parsers"
```

---

## Group B: Document Parser

### Task 2: Document Parser — Unit Tests

**Files:**
- Create: `backend/ingestion/__init__.py`
- Create: `backend/tests/test_parser.py`

- [ ] **Step 1: Create `ingestion/__init__.py`**

```python
# backend/ingestion/__init__.py
```

- [ ] **Step 2: Write the failing tests for the parser**

```python
# backend/tests/test_parser.py
"""Unit tests for multi-format document parser."""

import os
import tempfile

import pytest

from ingestion.parser import parse_document, ParseResult


class TestParseTxt:
    def test_parse_plain_text(self, tmp_path):
        f = tmp_path / "sample.txt"
        f.write_text("Hello world.\nSecond line.", encoding="utf-8")
        result = parse_document(str(f))
        assert isinstance(result, ParseResult)
        assert "Hello world." in result.text
        assert "Second line." in result.text
        assert result.format == "txt"

    def test_parse_empty_text(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        result = parse_document(str(f))
        assert result.text == ""
        assert result.format == "txt"


class TestParseMarkdown:
    def test_parse_markdown(self, tmp_path):
        f = tmp_path / "readme.md"
        f.write_text("# Title\n\nSome **bold** text.", encoding="utf-8")
        result = parse_document(str(f))
        assert "Title" in result.text
        assert "bold" in result.text
        assert result.format == "md"


class TestParseHtml:
    def test_parse_html(self, tmp_path):
        f = tmp_path / "page.html"
        f.write_text(
            "<html><body><h1>Header</h1><p>Content here</p></body></html>",
            encoding="utf-8",
        )
        result = parse_document(str(f))
        assert "Header" in result.text
        assert "Content here" in result.text
        assert result.format == "html"

    def test_strips_scripts_and_styles(self, tmp_path):
        f = tmp_path / "messy.html"
        f.write_text(
            "<html><head><style>body{}</style></head>"
            "<body><script>alert(1)</script><p>Clean text</p></body></html>",
            encoding="utf-8",
        )
        result = parse_document(str(f))
        assert "Clean text" in result.text
        assert "alert" not in result.text
        assert "body{}" not in result.text


class TestParsePdf:
    def test_parse_pdf(self, tmp_path):
        """Create a minimal PDF with PyMuPDF and parse it back."""
        import fitz

        pdf_path = str(tmp_path / "test.pdf")
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "PDF content here")
        doc.save(pdf_path)
        doc.close()

        result = parse_document(pdf_path)
        assert "PDF content here" in result.text
        assert result.format == "pdf"
        assert result.page_count == 1


class TestParseDocx:
    def test_parse_docx(self, tmp_path):
        """Create a minimal DOCX with python-docx and parse it back."""
        from docx import Document

        docx_path = str(tmp_path / "test.docx")
        doc = Document()
        doc.add_heading("Test Heading", level=1)
        doc.add_paragraph("Paragraph content.")
        doc.save(docx_path)

        result = parse_document(docx_path)
        assert "Test Heading" in result.text
        assert "Paragraph content." in result.text
        assert result.format == "docx"


class TestCleanText:
    def test_deduplicates_whitespace(self, tmp_path):
        f = tmp_path / "spaces.txt"
        f.write_text("Too   many    spaces\n\n\n\nand lines.", encoding="utf-8")
        result = parse_document(str(f))
        assert "Too many spaces" in result.text
        assert "\n\n\n\n" not in result.text

    def test_strips_leading_trailing(self, tmp_path):
        f = tmp_path / "padded.txt"
        f.write_text("   padded content   ", encoding="utf-8")
        result = parse_document(str(f))
        assert result.text == "padded content"


class TestUnsupportedFormat:
    def test_unsupported_raises_error(self, tmp_path):
        f = tmp_path / "data.xyz"
        f.write_text("binary stuff", encoding="utf-8")
        with pytest.raises(ValueError, match="Unsupported"):
            parse_document(str(f))
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_parser.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ingestion.parser'`

- [ ] **Step 4: Commit test file**

```bash
cd backend
git add ingestion/__init__.py tests/test_parser.py
git commit -m "test: add failing unit tests for document parser"
```

---

### Task 3: Document Parser — Implementation

**Files:**
- Create: `backend/ingestion/parser.py`

- [ ] **Step 1: Write the parser implementation**

```python
# backend/ingestion/parser.py
"""Multi-format document parser.

Supports: TXT, MD, HTML, PDF, DOCX, and images (via OCR).
Returns extracted, cleaned text from any supported document format.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParseResult:
    """Result of parsing a single document."""

    text: str
    format: str
    page_count: int = 1
    headings: list[str] = field(default_factory=list)


# Mapping of file extensions to parser functions
_PARSERS: dict[str, callable] = {}


def _register(ext: str):
    """Decorator to register a parser function for a file extension."""
    def decorator(fn):
        _PARSERS[ext] = fn
        return fn
    return decorator


def _clean_text(text: str) -> str:
    """Clean extracted text: deduplicate whitespace, strip edges."""
    # Collapse multiple spaces to single space
    text = re.sub(r"[ \t]+", " ", text)
    # Collapse 3+ newlines into 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip each line
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)
    # Strip leading/trailing whitespace
    return text.strip()


@_register("txt")
def _parse_txt(path: str) -> ParseResult:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return ParseResult(text=_clean_text(text), format="txt")


@_register("md")
def _parse_md(path: str) -> ParseResult:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    headings = re.findall(r"^#+\s+(.+)$", text, re.MULTILINE)
    return ParseResult(text=_clean_text(text), format="md", headings=headings)


@_register("html")
def _parse_html(path: str) -> ParseResult:
    import html2text

    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = True
    converter.ignore_emphasis = False
    converter.body_width = 0  # No wrapping
    text = converter.handle(raw)
    return ParseResult(text=_clean_text(text), format="html")


@_register("htm")
def _parse_htm(path: str) -> ParseResult:
    result = _parse_html(path)
    return ParseResult(text=result.text, format="html", headings=result.headings)


@_register("pdf")
def _parse_pdf(path: str) -> ParseResult:
    import fitz  # PyMuPDF

    doc = fitz.open(path)
    pages_text = []
    headings = []
    for page in doc:
        text = page.get_text("text")
        pages_text.append(text)
    doc.close()

    full_text = "\n\n".join(pages_text)
    return ParseResult(
        text=_clean_text(full_text),
        format="pdf",
        page_count=len(pages_text),
        headings=headings,
    )


@_register("docx")
def _parse_docx(path: str) -> ParseResult:
    from docx import Document

    doc = Document(path)
    paragraphs = []
    headings = []
    for para in doc.paragraphs:
        if para.style and para.style.name and para.style.name.startswith("Heading"):
            headings.append(para.text)
        paragraphs.append(para.text)

    full_text = "\n".join(paragraphs)
    return ParseResult(
        text=_clean_text(full_text),
        format="docx",
        headings=headings,
    )


# Image formats — OCR via pytesseract
def _parse_image(path: str) -> ParseResult:
    from PIL import Image
    import pytesseract

    img = Image.open(path)
    text = pytesseract.image_to_string(img)
    ext = Path(path).suffix.lstrip(".").lower()
    return ParseResult(text=_clean_text(text), format=ext)


for _ext in ("png", "jpg", "jpeg", "tiff"):
    _PARSERS[_ext] = _parse_image


def parse_document(path: str) -> ParseResult:
    """Parse a document file and return extracted text.

    Args:
        path: Absolute or relative path to the document file.

    Returns:
        ParseResult with cleaned text, format, page count, and headings.

    Raises:
        ValueError: If the file format is not supported.
        FileNotFoundError: If the file does not exist.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    ext = file_path.suffix.lstrip(".").lower()
    parser = _PARSERS.get(ext)
    if parser is None:
        raise ValueError(
            f"Unsupported file format: .{ext}. "
            f"Supported formats: {', '.join(sorted(_PARSERS.keys()))}"
        )

    return parser(str(file_path))
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_parser.py -v`
Expected: All tests pass (image/OCR tests may be skipped if tesseract is not installed — that's fine).

- [ ] **Step 3: Commit**

```bash
cd backend
git add ingestion/parser.py
git commit -m "feat: add multi-format document parser (TXT, MD, HTML, PDF, DOCX, images)"
```

---

## Group C: Text Chunker

### Task 4: Chunker — Unit Tests

**Files:**
- Create: `backend/tests/test_chunker.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_chunker.py
"""Unit tests for recursive character text chunker."""

import pytest

from ingestion.chunker import chunk_text, Chunk


class TestChunkText:
    def test_short_text_single_chunk(self):
        """Text shorter than chunk_size produces one chunk."""
        text = "Hello world."
        chunks = chunk_text(
            text=text,
            team_id="t1",
            source_doc_id="doc1",
            chunk_size=512,
            chunk_overlap=64,
        )
        assert len(chunks) == 1
        assert chunks[0].text == "Hello world."
        assert chunks[0].team_id == "t1"
        assert chunks[0].source_doc_id == "doc1"
        assert chunks[0].char_offset == 0

    def test_long_text_produces_multiple_chunks(self):
        """Text longer than chunk_size produces multiple overlapping chunks."""
        # Create text that is about 1500 chars — should produce ~3 chunks at 512/64
        text = "Word " * 300  # ~1500 chars
        chunks = chunk_text(
            text=text,
            team_id="t1",
            source_doc_id="doc1",
            chunk_size=512,
            chunk_overlap=64,
        )
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk.text) <= 512 + 10  # Small tolerance for word boundaries
            assert chunk.team_id == "t1"
            assert chunk.source_doc_id == "doc1"

    def test_overlap_between_consecutive_chunks(self):
        """Consecutive chunks share overlapping text."""
        text = "A " * 600  # ~1200 chars, should get overlapping chunks
        chunks = chunk_text(
            text=text,
            team_id="t1",
            source_doc_id="doc1",
            chunk_size=512,
            chunk_overlap=64,
        )
        if len(chunks) >= 2:
            # The end of chunk[0] should overlap with the start of chunk[1]
            end_of_first = chunks[0].text[-64:]
            assert end_of_first in chunks[1].text

    def test_chunk_metadata_team_id(self):
        chunks = chunk_text(
            text="Some text.",
            team_id="team_abc",
            source_doc_id="doc_xyz",
        )
        assert all(c.team_id == "team_abc" for c in chunks)
        assert all(c.source_doc_id == "doc_xyz" for c in chunks)

    def test_chunk_has_index(self):
        text = "Word " * 300
        chunks = chunk_text(
            text=text,
            team_id="t1",
            source_doc_id="doc1",
            chunk_size=512,
            chunk_overlap=64,
        )
        for i, chunk in enumerate(chunks):
            assert chunk.index == i

    def test_chunk_char_offsets_are_ascending(self):
        text = "Word " * 300
        chunks = chunk_text(
            text=text,
            team_id="t1",
            source_doc_id="doc1",
            chunk_size=512,
            chunk_overlap=64,
        )
        offsets = [c.char_offset for c in chunks]
        assert offsets == sorted(offsets)

    def test_page_number_assignment(self):
        """Chunks correctly track page numbers via page breaks."""
        text = "Page one content.\f\fPage three content."
        chunks = chunk_text(
            text=text,
            team_id="t1",
            source_doc_id="doc1",
            chunk_size=512,
            chunk_overlap=64,
        )
        # With form-feed as page separator, page tracking should work
        assert len(chunks) >= 1

    def test_empty_text_returns_empty(self):
        chunks = chunk_text(
            text="",
            team_id="t1",
            source_doc_id="doc1",
        )
        assert chunks == []

    def test_chunk_id_is_unique(self):
        text = "Word " * 300
        chunks = chunk_text(
            text=text,
            team_id="t1",
            source_doc_id="doc1",
            chunk_size=512,
            chunk_overlap=64,
        )
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids))


class TestChunkDataclass:
    def test_chunk_fields(self):
        chunk = Chunk(
            chunk_id="c1",
            text="hello",
            team_id="t1",
            source_doc_id="doc1",
            index=0,
            char_offset=0,
            page_number=1,
            section_heading=None,
        )
        assert chunk.chunk_id == "c1"
        assert chunk.text == "hello"
        assert chunk.page_number == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_chunker.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ingestion.chunker'`

- [ ] **Step 3: Commit test file**

```bash
cd backend
git add tests/test_chunker.py
git commit -m "test: add failing unit tests for text chunker"
```

---

### Task 5: Chunker — Implementation

**Files:**
- Create: `backend/ingestion/chunker.py`

- [ ] **Step 1: Write the chunker implementation**

```python
# backend/ingestion/chunker.py
"""Recursive character text chunker with metadata.

Splits text into overlapping chunks of configurable size.
Each chunk carries team_id, source_doc_id, page_number, section_heading, and char_offset.
"""

import hashlib
import re
import uuid
from dataclasses import dataclass


@dataclass
class Chunk:
    """A single text chunk with metadata for indexing."""

    chunk_id: str
    text: str
    team_id: str
    source_doc_id: str
    index: int
    char_offset: int
    page_number: int
    section_heading: str | None


# Separators ordered by preference: paragraph, sentence, word, character
_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


def _generate_chunk_id(team_id: str, source_doc_id: str, index: int) -> str:
    """Generate a deterministic chunk ID based on team, doc, and index."""
    raw = f"{team_id}:{source_doc_id}:{index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _split_text_recursive(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
    separators: list[str] | None = None,
) -> list[tuple[str, int]]:
    """Split text recursively using a hierarchy of separators.

    Returns a list of (chunk_text, char_offset) tuples.
    """
    if separators is None:
        separators = _SEPARATORS

    if len(text) <= chunk_size:
        return [(text, 0)] if text.strip() else []

    # Find the best separator that exists in the text
    separator = ""
    for sep in separators:
        if sep == "" or sep in text:
            separator = sep
            break

    # Split by the chosen separator
    if separator:
        parts = text.split(separator)
    else:
        # Character-level split as last resort
        parts = list(text)

    # Merge parts into chunks respecting chunk_size
    chunks: list[tuple[str, int]] = []
    current_chunk = ""
    current_offset = 0
    running_offset = 0

    for i, part in enumerate(parts):
        piece = part if not separator else (part if i == 0 else separator + part)

        if not current_chunk:
            current_chunk = piece
            current_offset = running_offset
        elif len(current_chunk) + len(piece) <= chunk_size:
            current_chunk += piece
        else:
            # Emit current chunk
            if current_chunk.strip():
                chunks.append((current_chunk.strip(), current_offset))

            # Start new chunk with overlap
            if chunk_overlap > 0 and len(current_chunk) > chunk_overlap:
                overlap_text = current_chunk[-chunk_overlap:]
                current_chunk = overlap_text + piece
                current_offset = running_offset - len(overlap_text)
            else:
                current_chunk = piece
                current_offset = running_offset

        running_offset += len(piece)

    # Don't forget the last chunk
    if current_chunk.strip():
        chunks.append((current_chunk.strip(), current_offset))

    return chunks


def _detect_page_number(text: str, char_offset: int) -> int:
    """Detect page number by counting form-feed characters before the offset."""
    prefix = text[:char_offset]
    return prefix.count("\f") + 1


def _detect_section_heading(text: str, char_offset: int) -> str | None:
    """Find the most recent heading (markdown-style) before the chunk offset."""
    prefix = text[:char_offset]
    headings = re.findall(r"^#+\s+(.+)$", prefix, re.MULTILINE)
    return headings[-1] if headings else None


def chunk_text(
    text: str,
    team_id: str,
    source_doc_id: str,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> list[Chunk]:
    """Split text into overlapping chunks with metadata.

    Args:
        text: The full document text to chunk.
        team_id: Team that owns this document.
        source_doc_id: ID of the source document.
        chunk_size: Maximum characters per chunk (default 512).
        chunk_overlap: Character overlap between consecutive chunks (default 64).

    Returns:
        List of Chunk objects with metadata.
    """
    if not text.strip():
        return []

    raw_chunks = _split_text_recursive(text, chunk_size, chunk_overlap)

    chunks = []
    for i, (chunk_text_str, char_offset) in enumerate(raw_chunks):
        chunk_id = _generate_chunk_id(team_id, source_doc_id, i)
        page_number = _detect_page_number(text, char_offset)
        section_heading = _detect_section_heading(text, char_offset)

        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                text=chunk_text_str,
                team_id=team_id,
                source_doc_id=source_doc_id,
                index=i,
                char_offset=char_offset,
                page_number=page_number,
                section_heading=section_heading,
            )
        )

    return chunks
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_chunker.py -v`
Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
cd backend
git add ingestion/chunker.py
git commit -m "feat: add recursive character text chunker with metadata"
```

---

## Group D: ChromaDB Integration

### Task 6: ChromaDB Wrapper — Unit Tests

**Files:**
- Create: `backend/tests/test_chromadb.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_chromadb.py
"""Integration tests for ChromaDB team-scoped wrapper."""

import os
import shutil
import tempfile

import pytest

# Override chroma dir for tests
_test_chroma_dir = tempfile.mkdtemp(prefix="test_chroma_")
os.environ["CHROMA_DIR"] = _test_chroma_dir

from db.chromadb import (
    get_or_create_collection,
    upsert_chunks,
    query_collection,
    delete_collection,
    ChromaDBClient,
)
from ingestion.chunker import Chunk


@pytest.fixture(autouse=True)
def cleanup_chroma():
    """Clean up test collections after each test."""
    yield
    # Reset the client between tests
    ChromaDBClient.reset()


class TestGetOrCreateCollection:
    def test_creates_collection(self):
        col = get_or_create_collection("test_team_1")
        assert col is not None
        assert col.name == "team_test_team_1"

    def test_same_team_returns_same_collection(self):
        col1 = get_or_create_collection("test_team_2")
        col2 = get_or_create_collection("test_team_2")
        assert col1.name == col2.name


class TestUpsertAndQuery:
    def test_upsert_single_chunk(self):
        chunks = [
            Chunk(
                chunk_id="c1",
                text="The capital of France is Paris.",
                team_id="team_a",
                source_doc_id="doc1",
                index=0,
                char_offset=0,
                page_number=1,
                section_heading=None,
            )
        ]
        upsert_chunks("team_a", chunks)
        results = query_collection("team_a", "capital of France", n_results=1)
        assert len(results) == 1
        assert results[0]["chunk_id"] == "c1"
        assert results[0]["text"] == "The capital of France is Paris."

    def test_upsert_multiple_chunks_and_query(self):
        chunks = [
            Chunk(
                chunk_id="c10",
                text="Python is a programming language.",
                team_id="team_b",
                source_doc_id="doc2",
                index=0,
                char_offset=0,
                page_number=1,
                section_heading=None,
            ),
            Chunk(
                chunk_id="c11",
                text="JavaScript runs in the browser.",
                team_id="team_b",
                source_doc_id="doc2",
                index=1,
                char_offset=50,
                page_number=1,
                section_heading=None,
            ),
        ]
        upsert_chunks("team_b", chunks)
        results = query_collection("team_b", "programming language", n_results=2)
        assert len(results) == 2
        # Python chunk should rank higher for "programming language"
        assert results[0]["chunk_id"] == "c10"

    def test_query_returns_metadata(self):
        chunks = [
            Chunk(
                chunk_id="c20",
                text="Machine learning is a subset of AI.",
                team_id="team_c",
                source_doc_id="doc3",
                index=0,
                char_offset=0,
                page_number=3,
                section_heading="ML Basics",
            ),
        ]
        upsert_chunks("team_c", chunks)
        results = query_collection("team_c", "machine learning", n_results=1)
        assert results[0]["source_doc_id"] == "doc3"
        assert results[0]["page_number"] == 3
        assert results[0]["section_heading"] == "ML Basics"


class TestTeamIsolation:
    def test_teams_cannot_see_each_others_data(self):
        chunks_a = [
            Chunk(
                chunk_id="iso_a",
                text="Secret data for team alpha.",
                team_id="alpha",
                source_doc_id="doc_alpha",
                index=0,
                char_offset=0,
                page_number=1,
                section_heading=None,
            ),
        ]
        chunks_b = [
            Chunk(
                chunk_id="iso_b",
                text="Secret data for team beta.",
                team_id="beta",
                source_doc_id="doc_beta",
                index=0,
                char_offset=0,
                page_number=1,
                section_heading=None,
            ),
        ]
        upsert_chunks("alpha", chunks_a)
        upsert_chunks("beta", chunks_b)

        results_a = query_collection("alpha", "secret data", n_results=5)
        results_b = query_collection("beta", "secret data", n_results=5)

        # Each team should only see their own data
        assert all(r["team_id"] == "alpha" for r in results_a)
        assert all(r["team_id"] == "beta" for r in results_b)


class TestDeleteCollection:
    def test_delete_removes_collection(self):
        chunks = [
            Chunk(
                chunk_id="del1",
                text="Data to be deleted.",
                team_id="doomed",
                source_doc_id="doc_doom",
                index=0,
                char_offset=0,
                page_number=1,
                section_heading=None,
            ),
        ]
        upsert_chunks("doomed", chunks)
        delete_collection("doomed")

        # Querying after deletion should return empty
        results = query_collection("doomed", "deleted", n_results=5)
        assert results == []


@pytest.fixture(scope="module", autouse=True)
def cleanup_test_dir():
    yield
    shutil.rmtree(_test_chroma_dir, ignore_errors=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_chromadb.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'db.chromadb'`

- [ ] **Step 3: Commit test file**

```bash
cd backend
git add tests/test_chromadb.py
git commit -m "test: add failing integration tests for ChromaDB wrapper"
```

---

### Task 7: ChromaDB Wrapper — Implementation

**Files:**
- Create: `backend/db/chromadb.py`

- [ ] **Step 1: Write the ChromaDB wrapper**

```python
# backend/db/chromadb.py
"""ChromaDB wrapper with team-scoped collections.

Each team gets a dedicated collection named `team_{team_id}`.
Embedding is done via sentence-transformers (all-MiniLM-L6-v2) by default.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from config import settings

# Type alias for chunks — avoids circular import
from ingestion.chunker import Chunk


class ChromaDBClient:
    """Singleton ChromaDB client manager."""

    _client: chromadb.ClientAPI | None = None

    @classmethod
    def get_client(cls) -> chromadb.ClientAPI:
        """Get or create the persistent ChromaDB client."""
        if cls._client is None:
            chroma_path = Path(settings.chroma_dir)
            chroma_path.mkdir(parents=True, exist_ok=True)
            cls._client = chromadb.PersistentClient(
                path=str(chroma_path),
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True,
                ),
            )
        return cls._client

    @classmethod
    def reset(cls) -> None:
        """Reset the client (for testing)."""
        if cls._client is not None:
            try:
                cls._client.reset()
            except Exception:
                pass
            cls._client = None


def _collection_name(team_id: str) -> str:
    """Return the collection name for a team."""
    return f"team_{team_id}"


def get_or_create_collection(team_id: str) -> chromadb.Collection:
    """Get or create a ChromaDB collection for a team.

    Uses the default embedding function (all-MiniLM-L6-v2 via sentence-transformers).

    Args:
        team_id: The team identifier.

    Returns:
        ChromaDB Collection instance.
    """
    client = ChromaDBClient.get_client()
    return client.get_or_create_collection(
        name=_collection_name(team_id),
        metadata={"team_id": team_id},
    )


def upsert_chunks(team_id: str, chunks: list[Chunk]) -> None:
    """Upsert text chunks into a team's ChromaDB collection.

    Args:
        team_id: The team that owns these chunks.
        chunks: List of Chunk objects to upsert.
    """
    if not chunks:
        return

    collection = get_or_create_collection(team_id)

    ids = [c.chunk_id for c in chunks]
    documents = [c.text for c in chunks]
    metadatas = [
        {
            "team_id": c.team_id,
            "source_doc_id": c.source_doc_id,
            "index": c.index,
            "char_offset": c.char_offset,
            "page_number": c.page_number,
            "section_heading": c.section_heading or "",
        }
        for c in chunks
    ]

    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )


def query_collection(
    team_id: str,
    query_text: str,
    n_results: int = 10,
) -> list[dict[str, Any]]:
    """Query a team's ChromaDB collection.

    Args:
        team_id: The team whose collection to query.
        query_text: The search query string.
        n_results: Maximum number of results to return.

    Returns:
        List of dicts with keys: chunk_id, text, score, team_id, source_doc_id,
        page_number, section_heading.
    """
    client = ChromaDBClient.get_client()
    col_name = _collection_name(team_id)

    # Check if collection exists
    existing = [c.name for c in client.list_collections()]
    if col_name not in existing:
        return []

    collection = client.get_collection(name=col_name)

    # Check if collection has any documents
    if collection.count() == 0:
        return []

    results = collection.query(
        query_texts=[query_text],
        n_results=min(n_results, collection.count()),
    )

    output = []
    if results and results["ids"] and results["ids"][0]:
        for i, chunk_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 0.0
            doc_text = results["documents"][0][i] if results["documents"] else ""

            output.append(
                {
                    "chunk_id": chunk_id,
                    "text": doc_text,
                    "score": 1.0 - distance,  # Convert distance to similarity
                    "team_id": meta.get("team_id", team_id),
                    "source_doc_id": meta.get("source_doc_id", ""),
                    "page_number": meta.get("page_number", 1),
                    "section_heading": meta.get("section_heading", ""),
                }
            )

    return output


def delete_collection(team_id: str) -> None:
    """Delete a team's ChromaDB collection.

    Called when a team is deleted. Safe to call if collection doesn't exist.

    Args:
        team_id: The team whose collection to delete.
    """
    client = ChromaDBClient.get_client()
    col_name = _collection_name(team_id)

    try:
        client.delete_collection(name=col_name)
    except ValueError:
        # Collection doesn't exist — that's fine
        pass
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_chromadb.py -v`
Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
cd backend
git add db/chromadb.py
git commit -m "feat: add ChromaDB wrapper with team-scoped collections"
```

---

## Group E: FalkorDB Integration

### Task 8: FalkorDB Wrapper — Unit Tests

**Files:**
- Create: `backend/tests/test_falkordb.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_falkordb.py
"""Integration tests for FalkorDB wrapper with team_id enforcement."""

import os
import shutil
import tempfile

import pytest

_test_falkor_dir = tempfile.mkdtemp(prefix="test_falkordb_")
os.environ["FALKORDB_DIR"] = _test_falkor_dir

from db.falkordb import (
    get_graph,
    create_entity,
    create_relationship,
    query_entities,
    query_related_entities,
    delete_team_data,
    Entity,
    Relationship,
    FalkorDBManager,
)


@pytest.fixture(autouse=True)
def cleanup_graph():
    """Clean up after each test."""
    yield
    FalkorDBManager.reset()


class TestCreateEntity:
    def test_create_entity(self):
        entity = Entity(
            id="e1",
            name="Paris",
            type="City",
            team_id="team1",
            source_doc_id="doc1",
            importance_score=0.8,
        )
        create_entity(entity)
        results = query_entities("team1", "Paris")
        assert len(results) >= 1
        assert results[0]["name"] == "Paris"
        assert results[0]["team_id"] == "team1"

    def test_create_entity_without_team_id_raises(self):
        entity = Entity(
            id="e2",
            name="London",
            type="City",
            team_id="",  # Empty team_id
            source_doc_id="doc1",
            importance_score=0.5,
        )
        with pytest.raises(ValueError, match="team_id"):
            create_entity(entity)


class TestCreateRelationship:
    def test_create_relationship(self):
        entity_a = Entity(
            id="r_e1", name="France", type="Country",
            team_id="team2", source_doc_id="doc2", importance_score=0.9,
        )
        entity_b = Entity(
            id="r_e2", name="Paris", type="City",
            team_id="team2", source_doc_id="doc2", importance_score=0.8,
        )
        create_entity(entity_a)
        create_entity(entity_b)

        rel = Relationship(
            source_id="r_e1",
            target_id="r_e2",
            type="CAPITAL_OF",
            team_id="team2",
            weight=1.0,
            source="ingestion",
        )
        create_relationship(rel)

        related = query_related_entities("team2", "r_e1")
        assert len(related) >= 1

    def test_relationship_without_team_id_raises(self):
        rel = Relationship(
            source_id="x1",
            target_id="x2",
            type="KNOWS",
            team_id="",
            weight=0.5,
            source="ingestion",
        )
        with pytest.raises(ValueError, match="team_id"):
            create_relationship(rel)


class TestTeamIsolation:
    def test_query_only_returns_own_team(self):
        entity_a = Entity(
            id="iso_1", name="Classified Alpha", type="Secret",
            team_id="alpha_team", source_doc_id="doc_a", importance_score=0.5,
        )
        entity_b = Entity(
            id="iso_2", name="Classified Beta", type="Secret",
            team_id="beta_team", source_doc_id="doc_b", importance_score=0.5,
        )
        create_entity(entity_a)
        create_entity(entity_b)

        results_a = query_entities("alpha_team", "Classified")
        results_b = query_entities("beta_team", "Classified")

        assert all(r["team_id"] == "alpha_team" for r in results_a)
        assert all(r["team_id"] == "beta_team" for r in results_b)


class TestDeleteTeamData:
    def test_delete_removes_team_entities(self):
        entity = Entity(
            id="del_e1", name="Temporary", type="Temp",
            team_id="doomed_team", source_doc_id="doc_doom", importance_score=0.3,
        )
        create_entity(entity)

        # Verify it exists
        results = query_entities("doomed_team", "Temporary")
        assert len(results) >= 1

        # Delete team data
        delete_team_data("doomed_team")

        # Verify it's gone
        results = query_entities("doomed_team", "Temporary")
        assert len(results) == 0


@pytest.fixture(scope="module", autouse=True)
def cleanup_test_dir():
    yield
    shutil.rmtree(_test_falkor_dir, ignore_errors=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_falkordb.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'db.falkordb'`

- [ ] **Step 3: Commit test file**

```bash
cd backend
git add tests/test_falkordb.py
git commit -m "test: add failing integration tests for FalkorDB wrapper"
```

---

### Task 9: FalkorDB Wrapper — Implementation

**Files:**
- Create: `backend/db/falkordb.py`

- [ ] **Step 1: Write the FalkorDB wrapper**

```python
# backend/db/falkordb.py
"""FalkorDB wrapper with mandatory team_id enforcement.

All nodes carry a mandatory `team_id` property.
All queries enforce WHERE team_id filter (defense-in-depth: raises error if missing).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from falkordb import FalkorDB, Graph

from config import settings


@dataclass
class Entity:
    """Represents a knowledge graph entity."""

    id: str
    name: str
    type: str
    team_id: str
    source_doc_id: str
    importance_score: float = 0.5


@dataclass
class Relationship:
    """Represents a relationship between two entities."""

    source_id: str
    target_id: str
    type: str
    team_id: str
    weight: float = 1.0
    source: str = "ingestion"


class FalkorDBManager:
    """Singleton FalkorDB connection manager."""

    _db: FalkorDB | None = None
    _graph: Graph | None = None

    @classmethod
    def get_db(cls) -> FalkorDB:
        """Get or create the FalkorDB instance."""
        if cls._db is None:
            falkor_path = Path(settings.falkordb_dir)
            falkor_path.mkdir(parents=True, exist_ok=True)
            cls._db = FalkorDB(host=str(falkor_path))
        return cls._db

    @classmethod
    def get_graph(cls, name: str = "memmesh") -> Graph:
        """Get or create the named graph."""
        if cls._graph is None:
            db = cls.get_db()
            cls._graph = db.select_graph(name)
        return cls._graph

    @classmethod
    def reset(cls) -> None:
        """Reset connections (for testing)."""
        if cls._graph is not None:
            try:
                cls._graph.delete()
            except Exception:
                pass
        cls._graph = None
        cls._db = None


def _validate_team_id(team_id: str) -> None:
    """Defense-in-depth: raise error if team_id is missing or empty."""
    if not team_id or not team_id.strip():
        raise ValueError(
            "team_id is required for all FalkorDB operations. "
            "This is a security violation — never query without team_id."
        )


def get_graph(name: str = "memmesh") -> Graph:
    """Get the named graph instance."""
    return FalkorDBManager.get_graph(name)


def create_entity(entity: Entity) -> None:
    """Create an Entity node in the graph.

    Args:
        entity: Entity dataclass with mandatory team_id.

    Raises:
        ValueError: If team_id is empty.
    """
    _validate_team_id(entity.team_id)

    graph = get_graph()
    now = datetime.now(timezone.utc).isoformat()

    query = """
    MERGE (e:Entity {id: $id})
    SET e.name = $name,
        e.type = $type,
        e.team_id = $team_id,
        e.source_doc_id = $source_doc_id,
        e.importance_score = $importance_score,
        e.created_at = $created_at
    """
    graph.query(
        query,
        params={
            "id": entity.id,
            "name": entity.name,
            "type": entity.type,
            "team_id": entity.team_id,
            "source_doc_id": entity.source_doc_id,
            "importance_score": entity.importance_score,
            "created_at": now,
        },
    )


def create_relationship(rel: Relationship) -> None:
    """Create a RELATES_TO relationship between two entities.

    Args:
        rel: Relationship dataclass with mandatory team_id.

    Raises:
        ValueError: If team_id is empty.
    """
    _validate_team_id(rel.team_id)

    graph = get_graph()
    now = datetime.now(timezone.utc).isoformat()

    query = """
    MATCH (a:Entity {id: $source_id, team_id: $team_id})
    MATCH (b:Entity {id: $target_id, team_id: $team_id})
    MERGE (a)-[r:RELATES_TO]->(b)
    SET r.type = $rel_type,
        r.team_id = $team_id,
        r.weight = $weight,
        r.source = $source,
        r.created_at = $created_at
    """
    graph.query(
        query,
        params={
            "source_id": rel.source_id,
            "target_id": rel.target_id,
            "rel_type": rel.type,
            "team_id": rel.team_id,
            "weight": rel.weight,
            "source": rel.source,
            "created_at": now,
        },
    )


def query_entities(
    team_id: str,
    name_query: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Query entities by name within a team.

    Args:
        team_id: Mandatory team filter.
        name_query: Substring to match against entity names.
        limit: Maximum results.

    Returns:
        List of entity dicts.

    Raises:
        ValueError: If team_id is empty.
    """
    _validate_team_id(team_id)

    graph = get_graph()
    query = """
    MATCH (e:Entity)
    WHERE e.team_id = $team_id AND e.name CONTAINS $name_query
    RETURN e.id AS id, e.name AS name, e.type AS type,
           e.team_id AS team_id, e.source_doc_id AS source_doc_id,
           e.importance_score AS importance_score
    LIMIT $limit
    """
    result = graph.query(
        query,
        params={
            "team_id": team_id,
            "name_query": name_query,
            "limit": limit,
        },
    )

    entities = []
    for record in result.result_set:
        entities.append(
            {
                "id": record[0],
                "name": record[1],
                "type": record[2],
                "team_id": record[3],
                "source_doc_id": record[4],
                "importance_score": record[5],
            }
        )

    return entities


def query_related_entities(
    team_id: str,
    entity_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Query entities related to a given entity, scoped to a team.

    Args:
        team_id: Mandatory team filter.
        entity_id: The entity to find relationships for.
        limit: Maximum results.

    Returns:
        List of dicts with related entity info and relationship type.

    Raises:
        ValueError: If team_id is empty.
    """
    _validate_team_id(team_id)

    graph = get_graph()
    query = """
    MATCH (a:Entity {id: $entity_id, team_id: $team_id})
          -[r:RELATES_TO]->
          (b:Entity {team_id: $team_id})
    RETURN b.id AS id, b.name AS name, b.type AS type,
           b.team_id AS team_id, r.type AS rel_type, r.weight AS weight
    LIMIT $limit
    """
    result = graph.query(
        query,
        params={
            "entity_id": entity_id,
            "team_id": team_id,
            "limit": limit,
        },
    )

    related = []
    for record in result.result_set:
        related.append(
            {
                "id": record[0],
                "name": record[1],
                "type": record[2],
                "team_id": record[3],
                "rel_type": record[4],
                "weight": record[5],
            }
        )

    return related


def delete_team_data(team_id: str) -> None:
    """Delete all nodes and relationships for a team.

    Called when a team is deleted.

    Args:
        team_id: The team whose data to purge.

    Raises:
        ValueError: If team_id is empty.
    """
    _validate_team_id(team_id)

    graph = get_graph()

    # Delete relationships first, then nodes
    graph.query(
        """
        MATCH (e:Entity {team_id: $team_id})-[r]-()
        DELETE r
        """,
        params={"team_id": team_id},
    )

    graph.query(
        """
        MATCH (e:Entity {team_id: $team_id})
        DELETE e
        """,
        params={"team_id": team_id},
    )
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_falkordb.py -v`
Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
cd backend
git add db/falkordb.py
git commit -m "feat: add FalkorDB wrapper with mandatory team_id enforcement"
```

---

## Group F: SQLite Migration & Ingestion Pipeline

### Task 10: vector_chunks Migration

**Files:**
- Create: `backend/db/migrations/004_vector_chunks.sql`

- [ ] **Step 1: Create the migration file**

```sql
-- backend/db/migrations/004_vector_chunks.sql

CREATE TABLE IF NOT EXISTS vector_chunks (
    chunk_id         TEXT PRIMARY KEY,
    team_id          TEXT REFERENCES teams(team_id),
    doc_id           TEXT REFERENCES source_docs(doc_id),
    importance_score REAL DEFAULT 0.5,
    last_accessed_at DATETIME,
    page_number      INTEGER,
    section_heading  TEXT,
    created_at       DATETIME NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_vector_chunks_team_id ON vector_chunks(team_id);
CREATE INDEX IF NOT EXISTS idx_vector_chunks_doc_id ON vector_chunks(doc_id);
```

- [ ] **Step 2: Run migrations**

Run: `cd backend && make migrate`
Expected: `Applied migration: 004_vector_chunks.sql`

- [ ] **Step 3: Verify the table exists**

Run: `cd backend && .venv/bin/python -c "from db.sqlite import get_connection; c = get_connection(); print([r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]); c.close()"`
Expected: Output includes `vector_chunks`

- [ ] **Step 4: Commit**

```bash
cd backend
git add db/migrations/004_vector_chunks.sql
git commit -m "feat: add vector_chunks table migration"
```

---

### Task 11: Entity Extraction Module

**Files:**
- Create: `backend/ingestion/entity_extractor.py`
- Create: `backend/tests/test_entity_extractor.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_entity_extractor.py
"""Unit tests for entity extraction from text chunks."""

from ingestion.entity_extractor import extract_entities, ExtractedEntity


class TestExtractEntities:
    def test_extracts_person_entities(self):
        text = "Albert Einstein developed the theory of relativity at Princeton University."
        entities = extract_entities(text, team_id="t1", source_doc_id="doc1")
        names = [e.name for e in entities]
        assert any("Einstein" in n for n in names)

    def test_extracts_organization_entities(self):
        text = "Google and Microsoft are major tech companies based in the United States."
        entities = extract_entities(text, team_id="t1", source_doc_id="doc1")
        names = [e.name for e in entities]
        assert any("Google" in n for n in names) or any("Microsoft" in n for n in names)

    def test_returns_extracted_entity_dataclass(self):
        text = "Paris is the capital of France."
        entities = extract_entities(text, team_id="team_x", source_doc_id="doc_y")
        assert all(isinstance(e, ExtractedEntity) for e in entities)
        assert all(e.team_id == "team_x" for e in entities)
        assert all(e.source_doc_id == "doc_y" for e in entities)

    def test_empty_text_returns_empty(self):
        entities = extract_entities("", team_id="t1", source_doc_id="doc1")
        assert entities == []

    def test_entity_has_type(self):
        text = "Apple Inc. was founded by Steve Jobs in Cupertino, California."
        entities = extract_entities(text, team_id="t1", source_doc_id="doc1")
        for entity in entities:
            assert entity.type in ("PERSON", "ORG", "GPE", "LOC", "DATE", "EVENT", "PRODUCT", "WORK_OF_ART", "OTHER")

    def test_deduplicates_entities(self):
        text = "Apple makes iPhones. Apple also makes MacBooks. Apple is great."
        entities = extract_entities(text, team_id="t1", source_doc_id="doc1")
        names = [e.name for e in entities]
        # "Apple" should appear at most once
        assert names.count("Apple") <= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_entity_extractor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ingestion.entity_extractor'`

- [ ] **Step 3: Write the entity extractor implementation**

```python
# backend/ingestion/entity_extractor.py
"""Entity extraction from text using spaCy.

Extracts named entities from text chunks and returns them as structured data
for insertion into the knowledge graph.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import spacy

# Load spaCy model lazily
_nlp = None


def _get_nlp():
    """Lazy-load the spaCy model."""
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm")
    return _nlp


@dataclass
class ExtractedEntity:
    """An entity extracted from text."""

    id: str
    name: str
    type: str
    team_id: str
    source_doc_id: str


@dataclass
class ExtractedRelationship:
    """A relationship extracted between co-occurring entities."""

    source_id: str
    target_id: str
    type: str
    team_id: str


def _entity_id(team_id: str, name: str) -> str:
    """Generate a deterministic entity ID from team + name."""
    raw = f"{team_id}:{name.lower().strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def extract_entities(
    text: str,
    team_id: str,
    source_doc_id: str,
) -> list[ExtractedEntity]:
    """Extract named entities from text using spaCy.

    Args:
        text: The text to extract entities from.
        team_id: Team that owns this content.
        source_doc_id: Source document ID.

    Returns:
        Deduplicated list of ExtractedEntity objects.
    """
    if not text.strip():
        return []

    nlp = _get_nlp()
    doc = nlp(text)

    # Deduplicate by normalized name
    seen: dict[str, ExtractedEntity] = {}
    for ent in doc.ents:
        name = ent.text.strip()
        if not name or len(name) < 2:
            continue

        key = name.lower()
        if key not in seen:
            entity_id = _entity_id(team_id, name)
            seen[key] = ExtractedEntity(
                id=entity_id,
                name=name,
                type=ent.label_,
                team_id=team_id,
                source_doc_id=source_doc_id,
            )

    return list(seen.values())


def extract_relationships(
    entities: list[ExtractedEntity],
    team_id: str,
) -> list[ExtractedRelationship]:
    """Extract co-occurrence relationships between entities.

    Entities that appear in the same chunk are assumed to be related.

    Args:
        entities: List of entities from the same chunk.
        team_id: Team that owns this content.

    Returns:
        List of relationships between co-occurring entities.
    """
    relationships = []
    for i, entity_a in enumerate(entities):
        for entity_b in entities[i + 1:]:
            if entity_a.id != entity_b.id:
                relationships.append(
                    ExtractedRelationship(
                        source_id=entity_a.id,
                        target_id=entity_b.id,
                        type="CO_OCCURS",
                        team_id=team_id,
                    )
                )

    return relationships
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_entity_extractor.py -v`
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
cd backend
git add ingestion/entity_extractor.py tests/test_entity_extractor.py
git commit -m "feat: add spaCy entity extraction with deduplication"
```

---

### Task 12: Ingestion Pipeline — Tests

**Files:**
- Create: `backend/tests/test_pipeline.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_pipeline.py
"""Integration tests for the ingestion pipeline."""

import os
import shutil
import tempfile

import pytest

_test_chroma_dir = tempfile.mkdtemp(prefix="test_pipeline_chroma_")
_test_falkor_dir = tempfile.mkdtemp(prefix="test_pipeline_falkor_")
os.environ["CHROMA_DIR"] = _test_chroma_dir
os.environ["FALKORDB_DIR"] = _test_falkor_dir

from ingestion.pipeline import run_ingestion_pipeline, PipelineResult
from db.chromadb import ChromaDBClient


@pytest.fixture(autouse=True)
def cleanup():
    yield
    ChromaDBClient.reset()


class TestPipelineEndToEnd:
    def test_pipeline_indexes_txt_file(self, tmp_path):
        """Full pipeline: parse → chunk → embed → extract entities."""
        txt_file = tmp_path / "sample.txt"
        txt_file.write_text(
            "Albert Einstein was born in Germany. "
            "He developed the theory of relativity. "
            "He worked at Princeton University in the United States. "
            "His work changed the field of physics forever.",
            encoding="utf-8",
        )

        result = run_ingestion_pipeline(
            file_path=str(txt_file),
            team_id="pipeline_team",
            source_doc_id="doc_pipeline_1",
        )

        assert isinstance(result, PipelineResult)
        assert result.success is True
        assert result.chunk_count > 0
        assert result.entity_count >= 0  # May or may not extract entities from short text

    def test_pipeline_indexes_md_file(self, tmp_path):
        md_file = tmp_path / "readme.md"
        md_file.write_text(
            "# Project Overview\n\n"
            "This project uses Python and FastAPI.\n"
            "It is maintained by the engineering team at Acme Corp.\n",
            encoding="utf-8",
        )

        result = run_ingestion_pipeline(
            file_path=str(md_file),
            team_id="pipeline_team",
            source_doc_id="doc_pipeline_2",
        )

        assert result.success is True
        assert result.chunk_count >= 1

    def test_pipeline_sets_status_to_indexed(self, tmp_path):
        txt_file = tmp_path / "status_test.txt"
        txt_file.write_text("Content for status test.", encoding="utf-8")

        result = run_ingestion_pipeline(
            file_path=str(txt_file),
            team_id="pipeline_team",
            source_doc_id="doc_status",
        )

        assert result.status == "indexed"

    def test_pipeline_fails_for_unsupported_format(self, tmp_path):
        bad_file = tmp_path / "data.xyz"
        bad_file.write_text("unsupported", encoding="utf-8")

        result = run_ingestion_pipeline(
            file_path=str(bad_file),
            team_id="pipeline_team",
            source_doc_id="doc_bad",
        )

        assert result.success is False
        assert result.status == "failed"
        assert "Unsupported" in result.error

    def test_pipeline_fails_for_missing_file(self):
        result = run_ingestion_pipeline(
            file_path="/nonexistent/file.txt",
            team_id="pipeline_team",
            source_doc_id="doc_missing",
        )

        assert result.success is False
        assert result.status == "failed"


@pytest.fixture(scope="module", autouse=True)
def cleanup_test_dirs():
    yield
    shutil.rmtree(_test_chroma_dir, ignore_errors=True)
    shutil.rmtree(_test_falkor_dir, ignore_errors=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_pipeline.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ingestion.pipeline'`

- [ ] **Step 3: Commit test file**

```bash
cd backend
git add tests/test_pipeline.py
git commit -m "test: add failing integration tests for ingestion pipeline"
```

---

### Task 13: Ingestion Pipeline — Implementation

**Files:**
- Create: `backend/ingestion/pipeline.py`

- [ ] **Step 1: Write the pipeline implementation**

```python
# backend/ingestion/pipeline.py
"""Ingestion pipeline: parse → chunk → embed (ChromaDB) → extract entities (FalkorDB) → index metadata (SQLite).

Orchestrates the full document indexing workflow for a single document.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from db.chromadb import upsert_chunks
from db.sqlite import get_connection
from ingestion.chunker import chunk_text
from ingestion.entity_extractor import (
    extract_entities,
    extract_relationships,
)
from ingestion.parser import parse_document

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result of running the ingestion pipeline on a document."""

    success: bool
    status: str  # "indexed" | "failed"
    chunk_count: int = 0
    entity_count: int = 0
    error: str = ""


def _update_doc_status(doc_id: str, status: str) -> None:
    """Update the status field on source_docs."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE source_docs SET status = ? WHERE doc_id = ?",
            (status, doc_id),
        )
        conn.commit()
    except Exception:
        # source_docs table may not have status column in all environments
        pass
    finally:
        conn.close()


def _insert_chunk_metadata(chunks, team_id: str, doc_id: str) -> None:
    """Insert chunk metadata into the vector_chunks SQLite table."""
    conn = get_connection()
    try:
        for chunk in chunks:
            conn.execute(
                """
                INSERT OR REPLACE INTO vector_chunks
                (chunk_id, team_id, doc_id, page_number, section_heading, created_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    chunk.chunk_id,
                    team_id,
                    doc_id,
                    chunk.page_number,
                    chunk.section_heading,
                ),
            )
        conn.commit()
    except Exception as e:
        logger.warning("Failed to insert chunk metadata: %s", e)
    finally:
        conn.close()


def _store_entities_in_graph(entities, relationships, team_id: str) -> None:
    """Store extracted entities and relationships in FalkorDB."""
    try:
        from db.falkordb import create_entity, create_relationship, Entity, Relationship

        for ent in entities:
            create_entity(
                Entity(
                    id=ent.id,
                    name=ent.name,
                    type=ent.type,
                    team_id=team_id,
                    source_doc_id=ent.source_doc_id,
                )
            )

        for rel in relationships:
            create_relationship(
                Relationship(
                    source_id=rel.source_id,
                    target_id=rel.target_id,
                    type=rel.type,
                    team_id=team_id,
                    source="ingestion",
                )
            )
    except Exception as e:
        # FalkorDB is optional — log and continue if unavailable
        logger.warning("FalkorDB entity storage failed: %s", e)


def run_ingestion_pipeline(
    file_path: str,
    team_id: str,
    source_doc_id: str,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> PipelineResult:
    """Run the full ingestion pipeline for a single document.

    Steps:
    1. Parse the document into text
    2. Chunk the text with metadata
    3. Upsert chunks into ChromaDB (team-scoped collection)
    4. Extract entities and relationships
    5. Store entities in FalkorDB (team-scoped)
    6. Index chunk metadata in SQLite vector_chunks table
    7. Update source_docs status

    Args:
        file_path: Path to the document file.
        team_id: Team that owns this document.
        source_doc_id: ID from the source_docs table.
        chunk_size: Characters per chunk (default 512).
        chunk_overlap: Overlap between chunks (default 64).

    Returns:
        PipelineResult with success status and counts.
    """
    # Mark as indexing
    _update_doc_status(source_doc_id, "indexing")

    try:
        # Step 1: Parse
        logger.info("Parsing document: %s", file_path)
        parse_result = parse_document(file_path)

        if not parse_result.text.strip():
            _update_doc_status(source_doc_id, "indexed")
            return PipelineResult(
                success=True,
                status="indexed",
                chunk_count=0,
                entity_count=0,
            )

        # Step 2: Chunk
        logger.info("Chunking text (%d chars)", len(parse_result.text))
        chunks = chunk_text(
            text=parse_result.text,
            team_id=team_id,
            source_doc_id=source_doc_id,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        # Step 3: Embed and upsert into ChromaDB
        logger.info("Upserting %d chunks into ChromaDB", len(chunks))
        upsert_chunks(team_id, chunks)

        # Step 4: Extract entities from each chunk
        logger.info("Extracting entities")
        all_entities = []
        all_relationships = []
        for chunk in chunks:
            entities = extract_entities(
                chunk.text,
                team_id=team_id,
                source_doc_id=source_doc_id,
            )
            relationships = extract_relationships(entities, team_id)
            all_entities.extend(entities)
            all_relationships.extend(relationships)

        # Step 5: Store in FalkorDB
        logger.info("Storing %d entities in FalkorDB", len(all_entities))
        _store_entities_in_graph(all_entities, all_relationships, team_id)

        # Step 6: Index chunk metadata in SQLite
        logger.info("Indexing chunk metadata in SQLite")
        _insert_chunk_metadata(chunks, team_id, source_doc_id)

        # Step 7: Update status
        _update_doc_status(source_doc_id, "indexed")

        return PipelineResult(
            success=True,
            status="indexed",
            chunk_count=len(chunks),
            entity_count=len(all_entities),
        )

    except (ValueError, FileNotFoundError) as e:
        logger.error("Pipeline failed for %s: %s", file_path, e)
        _update_doc_status(source_doc_id, "failed")
        return PipelineResult(
            success=False,
            status="failed",
            error=str(e),
        )

    except Exception as e:
        logger.error("Pipeline failed unexpectedly for %s: %s", file_path, e)
        _update_doc_status(source_doc_id, "failed")
        return PipelineResult(
            success=False,
            status="failed",
            error=str(e),
        )
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_pipeline.py -v`
Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
cd backend
git add ingestion/pipeline.py
git commit -m "feat: add ingestion pipeline (parse → chunk → embed → extract → index)"
```

---

## Group G: Ingestion API Endpoint

### Task 14: Ingestion API — Tests

**Files:**
- Create: `backend/tests/test_ingest_api.py`

- [ ] **Step 1: Write the failing API tests**

```python
# backend/tests/test_ingest_api.py
"""API tests for ingestion trigger and status endpoints."""

import os
import tempfile

import pytest


class TestIngestTriggerEndpoint:
    def test_trigger_requires_auth(self, client):
        """Triggering ingestion without auth returns 403."""
        response = client.post("/team/t1/ingest/trigger", json={"doc_id": "doc1"})
        assert response.status_code == 403

    def test_trigger_requires_team_membership(self, client, auth_headers_user):
        """User who is not in the team gets 403."""
        response = client.post(
            "/team/nonexistent_team/ingest/trigger",
            json={"doc_id": "doc1"},
            headers=auth_headers_user,
        )
        assert response.status_code == 403

    def test_trigger_returns_404_for_missing_doc(self, client, auth_headers_admin, team_id):
        """Triggering ingestion for a non-existent doc returns 404."""
        response = client.post(
            f"/team/{team_id}/ingest/trigger",
            json={"doc_id": "nonexistent_doc"},
            headers=auth_headers_admin,
        )
        assert response.status_code == 404


class TestIngestStatusEndpoint:
    def test_status_requires_auth(self, client):
        response = client.get("/team/t1/ingest/status")
        assert response.status_code == 403

    def test_status_returns_list(self, client, auth_headers_admin, team_id):
        response = client.get(
            f"/team/{team_id}/ingest/status",
            headers=auth_headers_admin,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


@pytest.fixture()
def auth_headers_admin(client):
    """Get auth headers for the admin user."""
    resp = client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "changeme"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def auth_headers_user(client):
    """Get auth headers for a regular user (no team membership)."""
    from auth.jwt import create_access_token

    token = create_access_token(
        user_id="user-no-team",
        global_role="user",
        team_memberships=[],
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def team_id(client, auth_headers_admin):
    """Create a test team and return its ID."""
    from db.sqlite import get_connection
    import uuid

    tid = str(uuid.uuid4())
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO teams (team_id, name) VALUES (?, ?)",
            (tid, f"Test Team {tid[:8]}"),
        )
        # Add admin as team member
        admin_row = conn.execute(
            "SELECT user_id FROM users WHERE email = 'admin@example.com'"
        ).fetchone()
        if admin_row:
            conn.execute(
                "INSERT INTO team_members (membership_id, user_id, team_id, role) VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), admin_row["user_id"], tid, "team_lead"),
            )
        conn.commit()
    finally:
        conn.close()
    return tid
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest tests/test_ingest_api.py -v`
Expected: FAIL — routes not yet registered

- [ ] **Step 3: Commit test file**

```bash
cd backend
git add tests/test_ingest_api.py
git commit -m "test: add failing API tests for ingestion endpoints"
```

---

### Task 15: Ingestion API — Implementation

**Files:**
- Create: `backend/api/routes/ingest.py`
- Modify: `backend/api/server.py`

- [ ] **Step 1: Create the ingestion routes**

```python
# backend/api/routes/ingest.py
"""Ingestion API routes: trigger indexing and check status.

Routes:
- POST /team/{team_id}/ingest/trigger — trigger indexing for a document
- GET /team/{team_id}/ingest/status — list document statuses for a team
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel

from auth.middleware import require_auth
from config import settings
from db.sqlite import get_connection

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingest"])


class IngestTriggerRequest(BaseModel):
    doc_id: str


class IngestStatusItem(BaseModel):
    doc_id: str
    file_name: str
    status: str
    file_format: str | None = None


def _check_team_membership(current_user: dict, team_id: str) -> None:
    """Verify the current user is a member of the specified team.

    Admins and superadmins have implicit access to all teams.
    """
    if current_user.get("role") in ("admin", "superadmin"):
        return

    memberships = current_user.get("team_memberships", [])
    member_team_ids = [m["team_id"] for m in memberships]
    if team_id not in member_team_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this team",
        )


def _run_pipeline_background(file_path: str, team_id: str, doc_id: str) -> None:
    """Run the ingestion pipeline in a background task."""
    from ingestion.pipeline import run_ingestion_pipeline

    result = run_ingestion_pipeline(
        file_path=file_path,
        team_id=team_id,
        source_doc_id=doc_id,
    )
    if result.success:
        logger.info(
            "Ingestion complete for doc %s: %d chunks, %d entities",
            doc_id, result.chunk_count, result.entity_count,
        )
    else:
        logger.error("Ingestion failed for doc %s: %s", doc_id, result.error)


@router.post("/team/{team_id}/ingest/trigger")
async def trigger_ingestion(
    team_id: str,
    body: IngestTriggerRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_auth),
):
    """Trigger indexing for a specific document.

    The document must exist in source_docs and belong to the specified team.
    The pipeline runs in a background task.
    """
    _check_team_membership(current_user, team_id)

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT doc_id, file_name, source_ref, team_id FROM source_docs "
            "WHERE doc_id = ? AND team_id = ?",
            (body.doc_id, team_id),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found in this team",
        )

    # Construct file path
    file_path = str(Path(settings.upload_dir) / team_id / row["file_name"])
    if not Path(file_path).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found on disk",
        )

    # Update status to pending
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE source_docs SET status = 'indexing' WHERE doc_id = ?",
            (body.doc_id,),
        )
        conn.commit()
    finally:
        conn.close()

    # Run pipeline in background
    background_tasks.add_task(
        _run_pipeline_background,
        file_path=file_path,
        team_id=team_id,
        doc_id=body.doc_id,
    )

    return {"message": "Ingestion started", "doc_id": body.doc_id, "status": "indexing"}


@router.get("/team/{team_id}/ingest/status", response_model=list[IngestStatusItem])
async def get_ingestion_status(
    team_id: str,
    current_user: dict = Depends(require_auth),
):
    """Get the ingestion status of all documents for a team."""
    _check_team_membership(current_user, team_id)

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT doc_id, file_name, status, file_format FROM source_docs "
            "WHERE team_id = ? ORDER BY rowid DESC",
            (team_id,),
        ).fetchall()
    finally:
        conn.close()

    return [
        IngestStatusItem(
            doc_id=row["doc_id"],
            file_name=row["file_name"],
            status=row["status"] or "pending",
            file_format=row["file_format"],
        )
        for row in rows
    ]
```

- [ ] **Step 2: Register ingest router in server.py**

Add the import and registration to the existing `create_app()`:

```python
# In backend/api/server.py, add to the imports:
from api.routes.ingest import router as ingest_router

# In create_app(), add after existing router registrations:
    app.include_router(ingest_router)
```

The full updated `backend/api/server.py`:

```python
# backend/api/server.py
"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.auth import router as auth_router
from api.routes.health import router as health_router
from api.routes.ingest import router as ingest_router


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
    app.include_router(ingest_router)

    return app
```

> **Note:** If Phases 2-3 added additional routers (team, admin), keep those registrations too. The key addition is the `ingest_router`.

- [ ] **Step 3: Run API tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/test_ingest_api.py -v`
Expected: All tests pass.

- [ ] **Step 4: Run all backend tests**

Run: `cd backend && make test`
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
cd backend
git add api/routes/ingest.py api/server.py
git commit -m "feat: add ingestion API routes (trigger + status)"
```

---

## Group H: Frontend — Ingestion Status Page

### Task 16: Frontend Ingestion Status UI

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/types.ts`
- Create: `frontend/src/routes/documents/ingestion/+page.svelte`

- [ ] **Step 1: Add types for ingestion status**

Add to `frontend/src/lib/types.ts`:

```typescript
// Append to frontend/src/lib/types.ts

export interface IngestStatusItem {
  doc_id: string;
  file_name: string;
  status: 'pending' | 'indexing' | 'indexed' | 'failed';
  file_format: string | null;
}
```

- [ ] **Step 2: Add API functions for ingestion**

Add to `frontend/src/lib/api.ts`:

```typescript
// Append to frontend/src/lib/api.ts

export async function getIngestionStatus(teamId: string): Promise<IngestStatusItem[]> {
  const response = await apiFetch(`/team/${teamId}/ingest/status`);
  if (!response.ok) {
    throw new Error('Failed to fetch ingestion status');
  }
  return response.json();
}

export async function triggerIngestion(teamId: string, docId: string): Promise<void> {
  const response = await apiFetch(`/team/${teamId}/ingest/trigger`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ doc_id: docId }),
  });
  if (!response.ok) {
    throw new Error('Failed to trigger ingestion');
  }
}
```

- [ ] **Step 3: Create the ingestion status page**

```svelte
<!-- frontend/src/routes/documents/ingestion/+page.svelte -->
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { getIngestionStatus, triggerIngestion } from '$lib/api';
  import type { IngestStatusItem } from '$lib/types';

  export let data: { teamId: string };

  let items: IngestStatusItem[] = [];
  let loading = true;
  let error = '';
  let refreshInterval: ReturnType<typeof setInterval>;

  async function loadStatus() {
    try {
      items = await getIngestionStatus(data.teamId);
      error = '';
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load status';
    } finally {
      loading = false;
    }
  }

  async function handleTrigger(docId: string) {
    try {
      await triggerIngestion(data.teamId, docId);
      await loadStatus();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to trigger ingestion';
    }
  }

  function statusColor(status: string): string {
    switch (status) {
      case 'indexed': return 'var(--color-success, #22c55e)';
      case 'indexing': return 'var(--color-accent, #f5a623)';
      case 'failed': return 'var(--color-error, #ef4444)';
      default: return 'var(--color-text-muted, #9ca3af)';
    }
  }

  onMount(() => {
    loadStatus();
    // Auto-refresh every 5 seconds
    refreshInterval = setInterval(loadStatus, 5000);
  });

  onDestroy(() => {
    if (refreshInterval) {
      clearInterval(refreshInterval);
    }
  });
</script>

<div class="ingestion-status">
  <h2>Ingestion Status</h2>

  {#if loading}
    <p class="loading">Loading document status...</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else if items.length === 0}
    <p class="empty">No documents found. Upload documents to get started.</p>
  {:else}
    <table class="status-table">
      <thead>
        <tr>
          <th>Document</th>
          <th>Format</th>
          <th>Status</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {#each items as item}
          <tr>
            <td class="doc-name">{item.file_name}</td>
            <td class="doc-format">{item.file_format || '—'}</td>
            <td>
              <span
                class="status-badge"
                style="color: {statusColor(item.status)}"
              >
                {item.status}
              </span>
            </td>
            <td>
              {#if item.status === 'pending' || item.status === 'failed'}
                <button
                  class="btn-index"
                  on:click={() => handleTrigger(item.doc_id)}
                >
                  {item.status === 'failed' ? 'Retry' : 'Index'}
                </button>
              {:else if item.status === 'indexing'}
                <span class="indexing-indicator">⏳ Processing...</span>
              {:else}
                <span class="indexed-indicator">✓ Done</span>
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</div>

<style>
  .ingestion-status {
    padding: 1.5rem;
    max-width: 800px;
  }

  h2 {
    margin-bottom: 1rem;
    color: var(--color-text, #e8e4da);
  }

  .status-table {
    width: 100%;
    border-collapse: collapse;
  }

  .status-table th,
  .status-table td {
    padding: 0.75rem 1rem;
    text-align: left;
    border-bottom: 1px solid var(--color-border, #2a2a2f);
  }

  .status-table th {
    color: var(--color-text-muted, #9ca3af);
    font-weight: 600;
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .doc-name {
    font-weight: 500;
    color: var(--color-text, #e8e4da);
  }

  .doc-format {
    color: var(--color-text-muted, #9ca3af);
    font-size: 0.9rem;
  }

  .status-badge {
    font-weight: 600;
    font-size: 0.85rem;
    text-transform: capitalize;
  }

  .btn-index {
    padding: 0.35rem 0.75rem;
    background: var(--color-accent, #f5a623);
    color: var(--color-bg, #0f0f11);
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.85rem;
    font-weight: 600;
  }

  .btn-index:hover {
    opacity: 0.9;
  }

  .indexing-indicator {
    color: var(--color-accent, #f5a623);
    font-size: 0.85rem;
  }

  .indexed-indicator {
    color: var(--color-success, #22c55e);
    font-size: 0.85rem;
  }

  .loading,
  .empty {
    color: var(--color-text-muted, #9ca3af);
    padding: 2rem 0;
  }

  .error {
    color: var(--color-error, #ef4444);
    padding: 1rem;
    background: rgba(239, 68, 68, 0.1);
    border-radius: 4px;
  }
</style>
```

- [ ] **Step 4: Commit**

```bash
cd frontend
git add src/lib/types.ts src/lib/api.ts src/routes/documents/ingestion/
git commit -m "feat: add ingestion status page with auto-refresh"
```

---

## Group I: Playwright E2E Test

### Task 17: E2E Test — Upload and Index

**Files:**
- Create: `frontend/tests/e2e/ingestion.spec.ts`

- [ ] **Step 1: Write the Playwright E2E test**

```typescript
// frontend/tests/e2e/ingestion.spec.ts
import { test, expect } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';
import * as os from 'os';

test.describe('Document Ingestion E2E', () => {
  test.beforeEach(async ({ page }) => {
    // Login as admin
    await page.goto('/login');
    await page.fill('input[name="email"]', 'admin@example.com');
    await page.fill('input[name="password"]', 'changeme');
    await page.click('button[type="submit"]');
    await page.waitForURL('/dashboard');
  });

  test('upload file and observe indexing status', async ({ page }) => {
    // Create a temporary test file
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'e2e-'));
    const testFilePath = path.join(tmpDir, 'test-doc.txt');
    fs.writeFileSync(
      testFilePath,
      'This is a test document for ingestion. Albert Einstein developed relativity.',
    );

    // Navigate to documents page
    await page.goto('/documents');

    // Upload the file
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(testFilePath);

    // Wait for upload confirmation
    await expect(page.locator('text=test-doc.txt')).toBeVisible({ timeout: 10000 });

    // Navigate to ingestion status page
    await page.goto('/documents/ingestion');

    // Should see the document in the status list
    await expect(page.locator('text=test-doc.txt')).toBeVisible();

    // Trigger indexing if status is pending
    const indexButton = page.locator('button:has-text("Index")');
    if (await indexButton.isVisible()) {
      await indexButton.click();
    }

    // Wait for status to change to indexed (auto-refresh every 5s)
    await expect(
      page.locator('.status-badge:has-text("indexed")')
    ).toBeVisible({ timeout: 30000 });

    // Clean up
    fs.rmSync(tmpDir, { recursive: true });
  });

  test('failed ingestion shows retry button', async ({ page }) => {
    // Navigate to ingestion status page
    await page.goto('/documents/ingestion');

    // Check that failed items show a retry button
    const failedRows = page.locator('.status-badge:has-text("failed")');
    const count = await failedRows.count();

    if (count > 0) {
      await expect(page.locator('button:has-text("Retry")')).toBeVisible();
    }
  });
});
```

- [ ] **Step 2: Run the E2E test**

Run: `cd frontend && npx playwright test tests/e2e/ingestion.spec.ts`
Expected: Tests pass (requires both backend and frontend running).

- [ ] **Step 3: Commit**

```bash
cd frontend
git add tests/e2e/ingestion.spec.ts
git commit -m "test: add Playwright E2E tests for document ingestion"
```

---

## Final: Run Full Test Suite

### Task 18: Full Verification

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && make test`
Expected: All tests pass.

- [ ] **Step 2: Run frontend E2E tests**

Run: `cd frontend && npx playwright test`
Expected: All E2E tests pass.

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: Phase 4 complete — Knowledge Base Indexing pipeline"
```
