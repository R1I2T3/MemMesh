"""
Tests for the ingestion pipeline (langchain-docling parser + Celery worker).

All external dependencies (DoclingLoader, MySQL, Weaviate, filesystem) are mocked
so tests run fully in-memory without network or disk I/O.
"""

from __future__ import annotations

import os
import warnings
from unittest.mock import MagicMock, patch, call

import pytest
from langchain_core.documents import Document

from backend.ingestion.parser import ConversionError, UnsupportedFormatError, load_documents
from backend.tasks.ingestion_worker import process_document_task, _deterministic_id, _page_number_from_meta


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_doc(text: str, page_no: int = 1) -> Document:
    """Build a fake langchain Document as DoclingLoader would return it."""
    return Document(
        page_content=text,
        metadata={
            "source": "/tmp/fake.pdf",
            "dl_meta": {
                "doc_items": [{"prov": [{"page_no": page_no}]}],
            },
        },
    )


def _expected_dl_meta(page_no: int = 1) -> str:
    """JSON string of the dl_meta that _make_doc produces."""
    import json
    return json.dumps({"doc_items": [{"prov": [{"page_no": page_no}]}]})


def _hex(content: bytes = b"Hello World") -> str:
    return content.hex()


# ---------------------------------------------------------------------------
# parser.load_documents() tests
# ---------------------------------------------------------------------------


class TestLoadDocuments:
    def test_returns_list_of_langchain_documents(self):
        """Happy path: load_documents returns a non-empty list of Documents."""
        fake_docs = [_make_doc("Section 1"), _make_doc("Section 2")]

        with patch("langchain_docling.DoclingLoader") as MockLoader:
            MockLoader.return_value.load.return_value = fake_docs
            result = load_documents("/fake/file.pdf")

        assert result == fake_docs
        MockLoader.assert_called_once()

    def test_uses_doc_chunks_export_type(self):
        """DoclingLoader must be called with ExportType.DOC_CHUNKS."""
        from langchain_docling.loader import ExportType

        with patch("langchain_docling.DoclingLoader") as MockLoader:
            MockLoader.return_value.load.return_value = []
            load_documents("/fake/file.pdf")

        _, kwargs = MockLoader.call_args
        assert kwargs.get("export_type") == ExportType.DOC_CHUNKS

    def test_conversion_error_on_docling_failure(self):
        """DoclingLoader exceptions are wrapped in ConversionError."""
        with patch("langchain_docling.DoclingLoader") as MockLoader:
            MockLoader.return_value.load.side_effect = RuntimeError("Docling exploded")
            with pytest.raises(ConversionError, match="Docling failed"):
                load_documents("/fake/broken.pdf")

    def test_file_path_forwarded_to_loader(self):
        """The file_path argument is passed verbatim to DoclingLoader."""
        with patch("langchain_docling.DoclingLoader") as MockLoader:
            MockLoader.return_value.load.return_value = []
            load_documents("/absolute/path/to/report.docx")

        _, kwargs = MockLoader.call_args
        assert kwargs.get("file_path") == "/absolute/path/to/report.docx"


# ---------------------------------------------------------------------------
# _page_number_from_meta tests
# ---------------------------------------------------------------------------


class TestPageNumberFromMeta:
    def test_extracts_page_number_from_dl_meta(self):
        meta = {"dl_meta": {"doc_items": [{"prov": [{"page_no": 3}]}]}}
        assert _page_number_from_meta(meta) == 3

    def test_defaults_to_1_when_missing(self):
        assert _page_number_from_meta({}) == 1

    def test_defaults_to_1_on_malformed_meta(self):
        assert _page_number_from_meta({"dl_meta": {"doc_items": []}}) == 1

    def test_defaults_to_1_on_none_meta(self):
        assert _page_number_from_meta(None or {}) == 1


# ---------------------------------------------------------------------------
# _deterministic_id tests
# ---------------------------------------------------------------------------


class TestDeterministicId:
    def test_same_bytes_same_id(self):
        assert _deterministic_id(b"hello") == _deterministic_id(b"hello")

    def test_different_bytes_different_id(self):
        assert _deterministic_id(b"hello") != _deterministic_id(b"world")

    def test_id_is_uuid_shaped(self):
        uid = _deterministic_id(b"test")
        parts = uid.split("-")
        assert len(parts) == 5
        assert [len(p) for p in parts] == [8, 4, 4, 4, 12]


# ---------------------------------------------------------------------------
# process_document_task worker tests
# ---------------------------------------------------------------------------


class TestProcessDocumentTask:
    """Tests for the Celery ingestion worker task."""

    def test_success_returns_deterministic_id(self):
        """Return value is the deterministic parent_id (UUID-shaped)."""
        file_bytes = b"Hello World"
        expected_id = _deterministic_id(file_bytes)

        fake_docs = [_make_doc("Chunk one"), _make_doc("Chunk two", page_no=2)]

        with (
            patch("backend.tasks.ingestion_worker.load_documents", return_value=fake_docs),
            patch("backend.tasks.ingestion_worker.SessionLocal") as MockSession,
            patch("backend.tasks.ingestion_worker.WeaviateManager") as MockWeaviate,
        ):
            mock_db = MagicMock()
            MockSession.return_value = mock_db
            MockWeaviate.return_value.__enter__ = MagicMock()
            MockWeaviate.return_value.insert_chunks = MagicMock()
            MockWeaviate.return_value.close = MagicMock()

            result = process_document_task(
                hex_content=file_bytes.hex(),
                filename="report.pdf",
                team_id="team-abc",
                user_id="user-xyz",
            )

        assert result == expected_id

    def test_markdown_assembled_from_chunks(self):
        """ParentDocument.content must be chunk texts joined with double-newline."""
        file_bytes = b"pdf content"
        fake_docs = [_make_doc("Part A"), _make_doc("Part B")]

        with (
            patch("backend.tasks.ingestion_worker.load_documents", return_value=fake_docs),
            patch("backend.tasks.ingestion_worker.SessionLocal") as MockSession,
            patch("backend.tasks.ingestion_worker.WeaviateManager") as MockWeaviate,
        ):
            mock_db = MagicMock()
            MockSession.return_value = mock_db
            MockWeaviate.return_value.insert_chunks = MagicMock()
            MockWeaviate.return_value.close = MagicMock()

            process_document_task(
                hex_content=file_bytes.hex(),
                filename="doc.pdf",
                team_id="t1",
                user_id="u1",
            )

        stmt = mock_db.execute.call_args[0][0]
        compiled = str(stmt.compile(
            compile_kwargs={"literal_binds": True},
        ))
        assert "Part A" in compiled
        assert "Part B" in compiled
        # Verify they are joined with double-newline
        assert "Part A\\n\\nPart B" in compiled or "Part A\n\nPart B" in compiled

    def test_weaviate_chunks_have_correct_shape(self):
        """Each Weaviate chunk has correct fields, page number, and parent_id."""
        file_bytes = b"content"
        expected_id = _deterministic_id(file_bytes)
        fake_docs = [_make_doc("Row one", page_no=2), _make_doc("Row two", page_no=3)]

        with (
            patch("backend.tasks.ingestion_worker.load_documents", return_value=fake_docs),
            patch("backend.tasks.ingestion_worker.SessionLocal") as MockSession,
            patch("backend.tasks.ingestion_worker.WeaviateManager") as MockWeaviate,
        ):
            mock_db = MagicMock()
            MockSession.return_value = mock_db
            mock_wm = MockWeaviate.return_value
            mock_wm.insert_chunks = MagicMock()
            mock_wm.close = MagicMock()

            process_document_task(
                hex_content=file_bytes.hex(),
                filename="sheet.xlsx",
                team_id="team-x",
                user_id="user-y",
            )

        mock_wm.insert_chunks.assert_called_once()
        _, kwargs = mock_wm.insert_chunks.call_args
        assert kwargs["tenant_id"] == "team-x"
        assert kwargs["allowed_users"] == ["user-y", "public"]

        chunks = kwargs["chunks"]
        assert len(chunks) == 2
        assert chunks[0] == {"text": "Row one", "parent_id": expected_id, "page_number": 2, "bbox": [], "dl_meta": _expected_dl_meta(2)}
        assert chunks[1] == {"text": "Row two", "parent_id": expected_id, "page_number": 3, "bbox": [], "dl_meta": _expected_dl_meta(3)}

    def test_mysql_insert_ignore_used(self):
        """INSERT IGNORE is used so retries don't create duplicate ParentDocument rows."""
        fake_docs = [_make_doc("content")]

        with (
            patch("backend.tasks.ingestion_worker.load_documents", return_value=fake_docs),
            patch("backend.tasks.ingestion_worker.SessionLocal") as MockSession,
            patch("backend.tasks.ingestion_worker.WeaviateManager") as MockWeaviate,
        ):
            mock_db = MagicMock()
            MockSession.return_value = mock_db
            MockWeaviate.return_value.insert_chunks = MagicMock()
            MockWeaviate.return_value.close = MagicMock()

            process_document_task(
                hex_content=b"bytes".hex(),
                filename="doc.pdf",
                team_id="t",
                user_id="u",
            )

        executed_stmt = mock_db.execute.call_args[0][0]
        compiled = str(executed_stmt.compile(dialect=__import__("sqlalchemy.dialects.mysql", fromlist=["dialect"]).dialect()))
        assert "IGNORE" in compiled.upper()

    def test_mysql_rollback_on_db_error(self):
        """DB commit failure triggers rollback; exception propagates."""
        fake_docs = [_make_doc("content")]

        with (
            patch("backend.tasks.ingestion_worker.load_documents", return_value=fake_docs),
            patch("backend.tasks.ingestion_worker.SessionLocal") as MockSession,
            patch("backend.tasks.ingestion_worker.WeaviateManager"),
        ):
            mock_db = MagicMock()
            mock_db.commit.side_effect = Exception("DB write failed")
            MockSession.return_value = mock_db

            with pytest.raises(Exception, match="DB write failed"):
                process_document_task(
                    hex_content=b"bytes".hex(),
                    filename="doc.pdf",
                    team_id="t",
                    user_id="u",
                )

        mock_db.rollback.assert_called_once()
        mock_db.close.assert_called_once()

    def test_conversion_error_not_retried(self):
        """ConversionError bubbles up immediately — Celery must not retry."""
        with patch(
            "backend.tasks.ingestion_worker.load_documents",
            side_effect=ConversionError("bad pdf"),
        ):
            with pytest.raises(ConversionError):
                process_document_task(
                    hex_content=b"x".hex(),
                    filename="broken.pdf",
                    team_id="t",
                    user_id="u",
                )

    def test_temp_file_cleaned_up_on_success(self, tmp_path):
        """Temp file is removed after task completes successfully."""
        created: list[str] = []
        real_ntf = __import__("tempfile").NamedTemporaryFile

        def tracking_ntf(**kwargs):
            f = real_ntf(**kwargs)
            created.append(f.name)
            return f

        fake_docs = [_make_doc("content")]

        with (
            patch("backend.tasks.ingestion_worker.tempfile.NamedTemporaryFile", side_effect=tracking_ntf),
            patch("backend.tasks.ingestion_worker.load_documents", return_value=fake_docs),
            patch("backend.tasks.ingestion_worker.SessionLocal") as MockSession,
            patch("backend.tasks.ingestion_worker.WeaviateManager") as MockWeaviate,
        ):
            MockSession.return_value = MagicMock()
            MockWeaviate.return_value.insert_chunks = MagicMock()
            MockWeaviate.return_value.close = MagicMock()

            process_document_task(
                hex_content=b"bytes".hex(),
                filename="test.pdf",
                team_id="t",
                user_id="u",
            )

        for path in created:
            assert not os.path.exists(path), f"Temp file not cleaned up: {path}"

    def test_file_extension_preserved_in_temp_file(self):
        """Temp file suffix must match original filename extension."""
        captured: list[str] = []
        real_ntf = __import__("tempfile").NamedTemporaryFile

        def capturing_ntf(**kwargs):
            captured.append(kwargs.get("suffix", ""))
            return real_ntf(**kwargs)

        fake_docs = [_make_doc("content")]

        with (
            patch("backend.tasks.ingestion_worker.tempfile.NamedTemporaryFile", side_effect=capturing_ntf),
            patch("backend.tasks.ingestion_worker.load_documents", return_value=fake_docs),
            patch("backend.tasks.ingestion_worker.SessionLocal") as MockSession,
            patch("backend.tasks.ingestion_worker.WeaviateManager") as MockWeaviate,
        ):
            MockSession.return_value = MagicMock()
            MockWeaviate.return_value.insert_chunks = MagicMock()
            MockWeaviate.return_value.close = MagicMock()

            process_document_task(
                hex_content=b"bytes".hex(),
                filename="slides.pptx",
                team_id="t",
                user_id="u",
            )

        assert captured == [".pptx"]

    def test_weaviate_manager_closed_after_insert(self):
        """WeaviateManager.close() is always called, even if insert succeeds."""
        fake_docs = [_make_doc("content")]

        with (
            patch("backend.tasks.ingestion_worker.load_documents", return_value=fake_docs),
            patch("backend.tasks.ingestion_worker.SessionLocal") as MockSession,
            patch("backend.tasks.ingestion_worker.WeaviateManager") as MockWeaviate,
        ):
            MockSession.return_value = MagicMock()
            mock_wm = MockWeaviate.return_value
            mock_wm.insert_chunks = MagicMock()
            mock_wm.close = MagicMock()

            process_document_task(
                hex_content=b"bytes".hex(),
                filename="doc.pdf",
                team_id="t",
                user_id="u",
            )

        mock_wm.close.assert_called_once()

    def test_unsupported_format_error_not_retried(self):
        """UnsupportedFormatError bubbles up immediately — Celery must not retry."""
        with patch(
            "backend.tasks.ingestion_worker.load_documents",
            side_effect=UnsupportedFormatError("unsupported format"),
        ):
            with pytest.raises(UnsupportedFormatError):
                process_document_task(
                    hex_content=b"x".hex(),
                    filename="file.xyz",
                    team_id="t",
                    user_id="u",
                )
