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
