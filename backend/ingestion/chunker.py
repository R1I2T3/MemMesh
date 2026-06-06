# backend/ingestion/chunker.py
"""Structure-aware text chunker powered by Docling's HybridChunker.

Chunks a DoclingDocument (or falls back to plain text) into overlapping
segments with rich metadata: team_id, source_doc_id, page_number,
section_heading, char_offset, and a deterministic chunk_id.
"""

import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Probe length used to locate a chunk's position in the source text when
# Docling provenance data is unavailable. Longer = fewer false matches.
_CHAR_OFFSET_PROBE_LEN = 80


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

def _char_offset_from_provenance(raw_chunk: Any) -> int | None:
    """Try to read char_span start from Docling chunk provenance."""
    try:
        prov = raw_chunk.meta.doc_items[0].prov
        if prov and hasattr(prov[0], "char_span"):
            return prov[0].char_span.start
    except Exception:
        pass
    return None


def _find_offset_in_text(text: str, chunk_text_str: str) -> int:
    """Find the position of chunk_text_str in text using a running search.

    Uses a prefix probe of length _CHAR_OFFSET_PROBE_LEN to reduce false
    matches. Returns 0 if not found.
    """
    probe = chunk_text_str[:_CHAR_OFFSET_PROBE_LEN]
    pos = text.find(probe)
    return max(pos, 0)


def _chunk_with_hybrid(
    doc: Any,
    text: str,
    team_id: str,
    source_doc_id: str,
    max_tokens: int,
    tokenizer: str,
) -> list[Chunk]:
    """Use Docling HybridChunker to produce structure-aware chunks."""
    from docling.chunking import HybridChunker

    chunker = HybridChunker(
        tokenizer=tokenizer,
        max_tokens=max_tokens,
        merge_peers=True,
    )

    raw_chunks = list(chunker.chunk(doc))
    chunks: list[Chunk] = []
    search_start = 0  # Track running position to avoid repeated false matches

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
            logger.debug("Could not read page_no for chunk %d", i, exc_info=True)

        # Section heading — from the chunk's headings list
        section_heading: str | None = None
        try:
            headings = raw.meta.headings
            if headings:
                section_heading = headings[-1]
        except Exception:
            logger.debug("Could not read headings for chunk %d", i, exc_info=True)

        # char_offset — prefer Docling provenance, fall back to text search
        char_offset = _char_offset_from_provenance(raw)
        if char_offset is None:
            # Search forward from where the last chunk was found to avoid
            # false matches on repeated phrases
            probe = chunk_text_str[:_CHAR_OFFSET_PROBE_LEN]
            pos = text.find(probe, search_start)
            char_offset = pos if pos >= 0 else search_start
        search_start = char_offset + 1

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


def _detect_page_number(text: str, char_offset: int, chunk_length: int = 0) -> int:
    """Detect page number by counting form-feed characters up to the chunk's end.

    Uses ``char_offset + chunk_length`` (the end of the chunk) rather than just
    the start, so chunks that cross a page break are attributed to the page on
    which their content ends. This is more accurate for RAG retrieval.
    """
    prefix = text[:char_offset + chunk_length]
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
                page_number=_detect_page_number(text, char_offset, len(chunk_text_str)),
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
    tokenizer: str | None = None,
) -> list[Chunk]:
    """Split text into chunks with metadata.

    Uses Docling's HybridChunker when a DoclingDocument is provided (``doc``),
    giving structure-aware, token-counted splits. Falls back to a recursive
    character splitter when ``doc`` is None or HybridChunker raises.

    Args:
        text: The full document text (used as fallback and for char_offset lookup).
        team_id: Team that owns this document.
        source_doc_id: ID of the source document.
        chunk_size: Max characters per chunk for the fallback splitter (default 512).
            Maps to ``max_tokens`` when HybridChunker is used.
        chunk_overlap: Character overlap for the fallback splitter (default 64).
        doc: Optional DoclingDocument from ``parse_document()``. When present,
            HybridChunker is used instead of the character splitter.
        tokenizer: HuggingFace tokenizer name for HybridChunker. Defaults to
            ``config.settings.chunker_tokenizer`` (env var CHUNKER_TOKENIZER).

    Returns:
        List of Chunk objects with metadata.
    """
    if not text.strip():
        return []

    if doc is not None:
        if tokenizer is None:
            try:
                from config import settings
                tokenizer = settings.chunker_tokenizer
            except Exception:
                tokenizer = "sentence-transformers/all-MiniLM-L6-v2"
                logger.debug("Could not read chunker_tokenizer from config; using default")

        try:
            return _chunk_with_hybrid(doc, text, team_id, source_doc_id, max_tokens=chunk_size, tokenizer=tokenizer)
        except Exception:
            logger.warning(
                "HybridChunker failed (tokenizer=%s); falling back to character splitter. "
                "Check that the tokenizer model is available.",
                tokenizer,
                exc_info=True,
            )

    return _chunk_with_character_splitter(text, team_id, source_doc_id, chunk_size, chunk_overlap)
