# backend/ingestion/chunker.py
"""Recursive character text chunker with metadata.

Splits text into overlapping chunks of configurable size.
Each chunk carries team_id, source_doc_id, page_number, section_heading, and char_offset.
"""

import hashlib
import re
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
