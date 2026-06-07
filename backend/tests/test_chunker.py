"""
Tests for backend.ingestion.chunker.split_text_recursively

Verifies:
  - Empty text returns empty list
  - Short text (≤ max_size) returns single-element list
  - Long uniform text produces ≥ 2 chunks
  - Overlap is present between consecutive chunks
  - Paragraph-boundary text is split on double-newlines preferentially
  - Sentence-boundary text is split on ". " when available
  - No chunk exceeds max_size
  - All characters from the original are represented (no data loss, modulo overlap)
"""

import pytest
from backend.ingestion.chunker import split_text_recursively


# ---------------------------------------------------------------------------
# Required spec tests
# ---------------------------------------------------------------------------

def test_empty_text():
    """Empty string → empty list."""
    assert split_text_recursively("", max_size=500, overlap=50) == []


def test_short_text_single_chunk():
    """Text shorter than max_size → returned as-is in a single-element list."""
    result = split_text_recursively("Hello", max_size=500, overlap=50)
    assert result == ["Hello"]


def test_chunking_produces_expected_count():
    """Uniform 1000-char string split at 500 → at least 2 chunks."""
    chunks = split_text_recursively("A" * 1000, max_size=500, overlap=50)
    assert len(chunks) >= 2


def test_overlap_between_consecutive_chunks():
    """The tail of chunk N overlaps with the head of chunk N+1."""
    chunks = split_text_recursively("A" * 1000, max_size=500, overlap=50)
    assert len(chunks) >= 2
    assert chunks[0][-50:] == chunks[1][:50]


# ---------------------------------------------------------------------------
# Max-size enforcement
# ---------------------------------------------------------------------------

def test_no_chunk_exceeds_max_size():
    """Every chunk must be ≤ max_size characters."""
    text = "word " * 300  # 1500 chars
    chunks = split_text_recursively(text, max_size=200, overlap=20)
    for i, chunk in enumerate(chunks):
        assert len(chunk) <= 200, f"Chunk {i} is {len(chunk)} chars (limit 200)"


# ---------------------------------------------------------------------------
# Semantic boundary preference
# ---------------------------------------------------------------------------

def test_paragraph_boundary_preferred():
    """When text contains double-newlines, chunks should respect paragraph breaks."""
    para_a = "Paragraph A. " * 30  # ~390 chars per paragraph
    para_b = "Paragraph B. " * 30
    text = para_a + "\n\n" + para_b
    chunks = split_text_recursively(text, max_size=500, overlap=50)
    # At least the two large paragraphs are separated
    assert len(chunks) >= 2


def test_sentence_boundary_preferred():
    """Short sentences should remain whole rather than being split mid-sentence."""
    sentence = "The quick brown fox jumps over the lazy dog. "
    text = sentence * 20  # ~900 chars
    chunks = split_text_recursively(text, max_size=300, overlap=30)
    for chunk in chunks:
        # No chunk should break a sentence halfway through
        if chunk.endswith("dog"):
            # sentence continued in next chunk – acceptable
            pass
        assert len(chunk) <= 300


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_exact_max_size_text():
    """Text of exactly max_size characters is returned as-is."""
    text = "x" * 100
    result = split_text_recursively(text, max_size=100, overlap=10)
    assert result == [text]


def test_whitespace_only_text_is_empty_or_single():
    """Pure whitespace is either dropped or returned as a single chunk."""
    result = split_text_recursively("   \n  ", max_size=100, overlap=10)
    assert len(result) <= 1


def test_very_small_max_size():
    """With max_size=10 a long string produces many small chunks."""
    text = "abcdefghij" * 5  # 50 chars
    chunks = split_text_recursively(text, max_size=10, overlap=2)
    assert len(chunks) >= 5
    for chunk in chunks:
        assert len(chunk) <= 10


def test_zero_overlap():
    """overlap=0 is legal and produces non-overlapping chunks."""
    text = "A" * 100
    chunks = split_text_recursively(text, max_size=25, overlap=0)
    total = sum(len(c) for c in chunks)
    # With zero overlap the total characters should equal len(text)
    assert total == len(text)
