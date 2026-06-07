"""
Semantic-aware recursive text chunker.

Splits text by paragraph, sentence, then character boundaries in priority order,
producing chunks of at most `max_size` characters with `overlap` characters of
context carry-over between consecutive chunks.

Priority split sequence:
  1.  Double-newline  (paragraph boundary)
  2.  Single-newline  (line boundary)
  3.  ". "            (sentence boundary)
  4.  " "             (word boundary)
  5.  ""              (character boundary, last-resort)
"""

from __future__ import annotations

import re

_SEPARATORS: list[str] = ["\n\n", "\n", ". ", " ", ""]


def _split_by_separator(text: str, separator: str) -> list[str]:
    """Split text on `separator` while preserving the separator at the end
    of each piece (keeps context for downstream consumers)."""
    if separator == "":
        # Character-level fallback – just return individual characters
        return list(text)
    if separator == ". ":
        # Keep the period attached to its sentence.
        parts = re.split(r"(?<=\. )", text)
    else:
        parts = text.split(separator)
    return [p for p in parts if p]


def _merge_splits(splits: list[str], max_size: int, overlap: int) -> list[str]:
    """Greedily merge small splits into chunks that fit within `max_size`.

    When a new chunk starts, it begins with the last `overlap` characters of the
    previous chunk to preserve context continuity.
    """
    chunks: list[str] = []
    current = ""

    for part in splits:
        if len(current) + len(part) <= max_size:
            current += part
        else:
            if current:
                chunks.append(current)
                # Carry-over: start next chunk from the tail of the previous one
                current = current[-overlap:] if overlap else ""
            # If the single part is itself larger than max_size, recurse
            if len(part) > max_size:
                sub = split_text_recursively(part, max_size=max_size, overlap=overlap)
                if sub:
                    # All but the last sub-chunk are fully-formed; append them.
                    chunks.extend(sub[:-1])
                    current = (current[-overlap:] if overlap else "") + sub[-1]
                    # Trim if still too long (rare edge case)
                    if len(current) > max_size:
                        chunks.append(current[:max_size])
                        current = current[-overlap:] if overlap else ""
            else:
                current += part

    if current:
        chunks.append(current)

    return chunks


def split_text_recursively(
    text: str,
    max_size: int = 512,
    overlap: int = 64,
    _depth: int = 0,
) -> list[str]:
    """Split `text` into chunks of at most `max_size` characters with
    `overlap` characters of context carry-over between adjacent chunks.

    The function tries separators in decreasing semantic granularity:
    paragraph → line → sentence → word → character.

    Args:
        text:      The input text to chunk.
        max_size:  Maximum number of characters per chunk. Must be > overlap.
        overlap:   Number of trailing characters to carry forward into the
                   next chunk for context continuity.

    Returns:
        List of non-empty string chunks, each ≤ max_size characters (except
        in the degenerate case where a single token exceeds max_size at the
        character-level separator, which is treated as a single chunk).
    """
    if not text:
        return []
    if len(text) <= max_size:
        return [text]

    separator = _SEPARATORS[min(_depth, len(_SEPARATORS) - 1)]
    splits = _split_by_separator(text, separator)

    if len(splits) == 1 and _depth < len(_SEPARATORS) - 1:
        # This separator didn't help; try the next one.
        return split_text_recursively(text, max_size=max_size, overlap=overlap, _depth=_depth + 1)

    merged = _merge_splits(splits, max_size=max_size, overlap=overlap)
    # Any merged piece that is still too large needs another round with a
    # finer-grained separator.
    result: list[str] = []
    for piece in merged:
        if len(piece) > max_size and _depth < len(_SEPARATORS) - 1:
            result.extend(
                split_text_recursively(
                    piece, max_size=max_size, overlap=overlap, _depth=_depth + 1
                )
            )
        else:
            result.append(piece)

    return [c for c in result if c]
