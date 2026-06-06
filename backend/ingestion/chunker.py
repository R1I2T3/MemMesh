# backend/ingestion/chunker.py
"""Structure-aware text chunker powered by Docling's HybridChunker.

Chunks a DoclingDocument (or falls back to plain text) into overlapping
segments with rich metadata: team_id, source_doc_id, page_number,
section_heading, char_offset, and a deterministic chunk_id.
"""

import hashlib
import re
from dataclasses import dataclass
from typing import Any


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


def _generate_chunk_id(team_id: str, source_doc_id: str, index: int) -> str:
    """Generate a deterministic chunk ID based on team, doc, and index."""
    raw = f"{team_id}:{source_doc_id}:{index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Docling HybridChunker path
# ---------------------------------------------------------------------------

def _chunk_with_hybrid(
    doc: Any,
    text: str,
    team_id: str,
    source_doc_id: str,
    max_tokens: int,
) -> list[Chunk]:
    """Use Docling HybridChunker to produce structure-aware chunks."""
    from docling.chunking import HybridChunker

    chunker = HybridChunker(
        tokenizer="sentence-transformers/all-MiniLM-L6-v2",
        max_tokens=max_tokens,
        merge_peers=True,
    )

    raw_chunks = list(chunker.chunk(doc))
    chunks: list[Chunk] = []

    for i, raw in enumerate(raw_chunks):
        chunk_text_str = chunker.serialize(raw)
        if not chunk_text_str.strip():
            continue

        # Page number — take the first page mentioned in provenance
        page_number = 1
        try:
            prov = raw.meta.doc_items[0].prov
            if prov:
                page_number = prov[0].page_no
        except Exception:
            pass

        # Section heading — from the chunk's headings list
        section_heading: str | None = None
        try:
            headings = raw.meta.headings
            if headings:
                section_heading = headings[-1]
        except Exception:
            pass

        # char_offset — locate the chunk text in the full document text
        char_offset = text.find(chunk_text_str[:40])
        if char_offset < 0:
            char_offset = 0

        chunks.append(
            Chunk(
                chunk_id=_generate_chunk_id(team_id, source_doc_id, i),
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


# ---------------------------------------------------------------------------
# Plain-text fallback (recursive character splitter)
# ---------------------------------------------------------------------------

_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


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

    separator = ""
    for sep in separators:
        if sep == "" or sep in text:
            separator = sep
            break

    parts = text.split(separator) if separator else list(text)

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
            if current_chunk.strip():
                chunks.append((current_chunk.strip(), current_offset))
            if chunk_overlap > 0 and len(current_chunk) > chunk_overlap:
                overlap_text = current_chunk[-chunk_overlap:]
                current_chunk = overlap_text + piece
                current_offset = running_offset - len(overlap_text)
            else:
                current_chunk = piece
                current_offset = running_offset

        running_offset += len(piece)

    if current_chunk.strip():
        chunks.append((current_chunk.strip(), current_offset))

    return chunks


def _detect_page_number(text: str, char_offset: int) -> int:
    """Detect page number by counting form-feed characters before the offset."""
    prefix = text[:char_offset]
    return prefix.count("\f") + 1


def _detect_section_heading(text: str, char_offset: int) -> str | None:
    """Find the most recent markdown heading before the chunk offset."""
    prefix = text[:char_offset]
    headings = re.findall(r"^#+\s+(.+)$", prefix, re.MULTILINE)
    return headings[-1] if headings else None


def _chunk_with_character_splitter(
    text: str,
    team_id: str,
    source_doc_id: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[Chunk]:
    """Fallback: character-based recursive splitter."""
    raw_chunks = _split_text_recursive(text, chunk_size, chunk_overlap)
    chunks: list[Chunk] = []

    for i, (chunk_text_str, char_offset) in enumerate(raw_chunks):
        chunks.append(
            Chunk(
                chunk_id=_generate_chunk_id(team_id, source_doc_id, i),
                text=chunk_text_str,
                team_id=team_id,
                source_doc_id=source_doc_id,
                index=i,
                char_offset=char_offset,
                page_number=_detect_page_number(text, char_offset),
                section_heading=_detect_section_heading(text, char_offset),
            )
        )

    return chunks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chunk_text(
    text: str,
    team_id: str,
    source_doc_id: str,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
    doc: Any | None = None,
) -> list[Chunk]:
    """Split text into chunks with metadata.

    Uses Docling's HybridChunker when a DoclingDocument is provided (``doc``),
    giving structure-aware, token-counted splits. Falls back to a recursive
    character splitter when ``doc`` is None.

    Args:
        text: The full document text (used as fallback and for char_offset lookup).
        team_id: Team that owns this document.
        source_doc_id: ID of the source document.
        chunk_size: Maximum characters per chunk for the fallback splitter (default 512).
            When HybridChunker is used this maps to ``max_tokens``.
        chunk_overlap: Character overlap for the fallback splitter (default 64).
        doc: Optional DoclingDocument from ``parse_document()``. When present,
            HybridChunker is used instead of the character splitter.

    Returns:
        List of Chunk objects with metadata.
    """
    if not text.strip():
        return []

    if doc is not None:
        try:
            return _chunk_with_hybrid(doc, text, team_id, source_doc_id, max_tokens=chunk_size)
        except Exception:
            # If HybridChunker fails for any reason, fall through to character splitter
            pass

    return _chunk_with_character_splitter(text, team_id, source_doc_id, chunk_size, chunk_overlap)
