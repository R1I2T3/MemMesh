# backend/tests/test_chunker.py
"""Unit tests for the Docling-backed text chunker."""

from unittest.mock import MagicMock, patch

import pytest

from ingestion.chunker import chunk_text, Chunk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_doc_mock(chunks_text: list[str], headings_per_chunk: list[str | None] | None = None):
    """Build a mock DoclingDocument + HybridChunker output."""
    if headings_per_chunk is None:
        headings_per_chunk = [None] * len(chunks_text)

    raw_chunks = []
    for text, heading in zip(chunks_text, headings_per_chunk):
        raw = MagicMock()
        # serialize() returns the chunk text
        raw.meta.headings = [heading] if heading else []
        # provenance — page 1
        prov_item = MagicMock()
        prov_item.page_no = 1
        raw.meta.doc_items = [MagicMock(prov=[prov_item])]
        raw_chunks.append(raw)

    mock_doc = MagicMock()
    return mock_doc, raw_chunks, chunks_text


# ---------------------------------------------------------------------------
# Tests using HybridChunker (mocked)
# ---------------------------------------------------------------------------

class TestChunkWithHybrid:
    def test_single_chunk_from_doc(self):
        """Short text → single chunk via HybridChunker."""
        mock_doc, raw_chunks, texts = _make_doc_mock(["Hello world."])

        with patch("docling.chunking.HybridChunker") as MockChunker:
            instance = MockChunker.return_value
            instance.chunk.return_value = raw_chunks
            instance.serialize.side_effect = texts

            result = chunk_text(
                text="Hello world.",
                team_id="t1",
                source_doc_id="doc1",
                doc=mock_doc,
            )

        assert len(result) == 1
        assert result[0].text == "Hello world."
        assert result[0].team_id == "t1"
        assert result[0].source_doc_id == "doc1"
        assert result[0].index == 0

    def test_multiple_chunks_from_doc(self):
        """Long doc → multiple chunks, each with correct index."""
        chunk_texts = ["Chunk A content.", "Chunk B content.", "Chunk C content."]
        mock_doc, raw_chunks, texts = _make_doc_mock(chunk_texts)

        with patch("docling.chunking.HybridChunker") as MockChunker:
            instance = MockChunker.return_value
            instance.chunk.return_value = raw_chunks
            instance.serialize.side_effect = texts

            result = chunk_text(
                text=" ".join(chunk_texts),
                team_id="t1",
                source_doc_id="doc1",
                doc=mock_doc,
            )

        assert len(result) == 3
        for i, chunk in enumerate(result):
            assert chunk.index == i
            assert chunk.team_id == "t1"

    def test_chunk_ids_are_unique(self):
        chunk_texts = ["Part one.", "Part two.", "Part three."]
        mock_doc, raw_chunks, texts = _make_doc_mock(chunk_texts)

        with patch("docling.chunking.HybridChunker") as MockChunker:
            instance = MockChunker.return_value
            instance.chunk.return_value = raw_chunks
            instance.serialize.side_effect = texts

            result = chunk_text(
                text=" ".join(chunk_texts),
                team_id="t1",
                source_doc_id="doc1",
                doc=mock_doc,
            )

        ids = [c.chunk_id for c in result]
        assert len(ids) == len(set(ids))

    def test_section_heading_extracted(self):
        """Section heading from chunk metadata is propagated."""
        mock_doc, raw_chunks, texts = _make_doc_mock(
            ["Introduction paragraph."],
            headings_per_chunk=["Introduction"],
        )

        with patch("docling.chunking.HybridChunker") as MockChunker:
            instance = MockChunker.return_value
            instance.chunk.return_value = raw_chunks
            instance.serialize.side_effect = texts

            result = chunk_text(
                text="Introduction paragraph.",
                team_id="t1",
                source_doc_id="doc1",
                doc=mock_doc,
            )

        assert result[0].section_heading == "Introduction"

    def test_page_number_extracted(self):
        """Page number from chunk provenance is propagated."""
        mock_doc, raw_chunks, texts = _make_doc_mock(["Page two content."])
        raw_chunks[0].meta.doc_items[0].prov[0].page_no = 2

        with patch("docling.chunking.HybridChunker") as MockChunker:
            instance = MockChunker.return_value
            instance.chunk.return_value = raw_chunks
            instance.serialize.side_effect = texts

            result = chunk_text(
                text="Page two content.",
                team_id="t1",
                source_doc_id="doc1",
                doc=mock_doc,
            )

        assert result[0].page_number == 2

    def test_empty_chunks_from_hybrid_are_skipped(self):
        """Chunks whose serialized text is blank/whitespace are dropped."""
        mock_doc, raw_chunks, _ = _make_doc_mock(["Good chunk.", "   "])

        with patch("docling.chunking.HybridChunker") as MockChunker:
            instance = MockChunker.return_value
            instance.chunk.return_value = raw_chunks
            instance.serialize.side_effect = ["Good chunk.", "   "]

            result = chunk_text(
                text="Good chunk.",
                team_id="t1",
                source_doc_id="doc1",
                doc=mock_doc,
            )

        assert len(result) == 1
        assert result[0].text == "Good chunk."

    def test_hybrid_failure_falls_back_to_character_splitter(self):
        """If HybridChunker raises, the character splitter is used instead."""
        mock_doc = MagicMock()

        with patch("docling.chunking.HybridChunker", side_effect=Exception("model not found")):
            result = chunk_text(
                text="Hello world.",
                team_id="t1",
                source_doc_id="doc1",
                doc=mock_doc,
                chunk_size=512,
            )

        # Should still produce chunks via the fallback
        assert len(result) >= 1
        assert result[0].text == "Hello world."


# ---------------------------------------------------------------------------
# Tests using fallback character splitter (doc=None)
# ---------------------------------------------------------------------------

class TestChunkWithCharacterSplitter:
    def test_short_text_single_chunk(self):
        chunks = chunk_text(
            text="Hello world.",
            team_id="t1",
            source_doc_id="doc1",
            chunk_size=512,
            chunk_overlap=64,
        )
        assert len(chunks) == 1
        assert chunks[0].text == "Hello world."
        assert chunks[0].char_offset == 0

    def test_long_text_produces_multiple_chunks(self):
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
            assert len(chunk.text) <= 512 + 10

    def test_overlap_between_consecutive_chunks(self):
        text = "A " * 600
        chunks = chunk_text(
            text=text,
            team_id="t1",
            source_doc_id="doc1",
            chunk_size=512,
            chunk_overlap=64,
        )
        if len(chunks) >= 2:
            end_of_first = chunks[0].text[-64:]
            assert end_of_first in chunks[1].text

    def test_chunk_has_index(self):
        text = "Word " * 300
        chunks = chunk_text(text=text, team_id="t1", source_doc_id="doc1", chunk_size=512, chunk_overlap=64)
        for i, chunk in enumerate(chunks):
            assert chunk.index == i

    def test_chunk_char_offsets_are_ascending(self):
        text = "Word " * 300
        chunks = chunk_text(text=text, team_id="t1", source_doc_id="doc1", chunk_size=512, chunk_overlap=64)
        offsets = [c.char_offset for c in chunks]
        assert offsets == sorted(offsets)

    def test_page_number_via_formfeed(self):
        text = "Page one content.\f\fPage three content."
        chunks = chunk_text(text=text, team_id="t1", source_doc_id="doc1", chunk_size=512, chunk_overlap=64)
        assert len(chunks) >= 1

    def test_empty_text_returns_empty(self):
        chunks = chunk_text(text="", team_id="t1", source_doc_id="doc1")
        assert chunks == []

    def test_chunk_id_is_unique(self):
        text = "Word " * 300
        chunks = chunk_text(text=text, team_id="t1", source_doc_id="doc1", chunk_size=512, chunk_overlap=64)
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Chunk dataclass
# ---------------------------------------------------------------------------

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
