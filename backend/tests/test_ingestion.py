"""
Integration tests for the ingestion pipeline (parser + Celery worker).

All external dependencies (Docling, MySQL, Weaviate, filesystem) are mocked so
tests run fully in-memory without network or disk I/O.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch, call

import pytest
from backend.ingestion.parser import (
    ConversionError,
    UnsupportedFormatError,
    parse_file_to_markdown,
)
from backend.tasks.ingestion_worker import process_document_task
from backend.models import ParentDocument


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


class TestParseFileToMarkdown:
    def test_docling_native_pdf(self, tmp_path):
        """PDF files are routed through Docling."""
        fake_pdf = tmp_path / "report.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 fake")

        with patch("backend.ingestion.parser._convert_with_docling") as mock_convert:
            mock_convert.return_value = "# Report\nSome content."
            result = parse_file_to_markdown(str(fake_pdf))

        assert result == "# Report\nSome content."
        mock_convert.assert_called_once_with(str(fake_pdf))

    def test_json_returned_as_fenced_block(self, tmp_path):
        """JSON files are read as plain text and returned as a fenced code block."""
        json_file = tmp_path / "data.json"
        json_file.write_text('{"key": "value"}', encoding="utf-8")

        result = parse_file_to_markdown(str(json_file))

        assert "```json" in result
        assert '"key": "value"' in result

    def test_xml_returned_as_fenced_block(self, tmp_path):
        """XML files are read as plain text and returned as a fenced code block."""
        xml_file = tmp_path / "data.xml"
        xml_file.write_text("<root><item>1</item></root>", encoding="utf-8")

        result = parse_file_to_markdown(str(xml_file))

        assert "```xml" in result
        assert "<root>" in result

    def test_zip_extracts_text_members(self, tmp_path):
        """ZIP archives are unpacked and text members are concatenated."""
        import zipfile

        zip_path = tmp_path / "bundle.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("notes.txt", "Hello from zip!")
            zf.writestr("readme.md", "# README\nContent here")

        result = parse_file_to_markdown(str(zip_path))

        assert "Hello from zip!" in result
        assert "# README" in result

    def test_unsupported_archive_raises(self, tmp_path):
        """7z/rar archives raise UnsupportedFormatError."""
        rar_file = tmp_path / "archive.rar"
        rar_file.write_bytes(b"Rar!")

        with pytest.raises(UnsupportedFormatError, match=".rar"):
            parse_file_to_markdown(str(rar_file))

    def test_google_workspace_raises(self, tmp_path):
        """Google Workspace formats raise UnsupportedFormatError with advice."""
        gsheet = tmp_path / "spreadsheet.gsheet"
        gsheet.write_bytes(b"{}");

        with pytest.raises(UnsupportedFormatError, match="Google Workspace"):
            parse_file_to_markdown(str(gsheet))

    def test_file_not_found_raises(self):
        """Non-existent path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            parse_file_to_markdown("/does/not/exist.pdf")

    def test_docling_failure_raises_conversion_error(self, tmp_path):
        """When Docling raises an exception it is wrapped in ConversionError."""
        pdf = tmp_path / "broken.pdf"
        pdf.write_bytes(b"not a pdf")

        # DocumentConverter is imported lazily inside _convert_with_docling,
        # so we must patch it at the source module, not the parser module.
        with patch("docling.document_converter.DocumentConverter") as MockDC:
            MockDC.return_value.convert.side_effect = RuntimeError("Docling exploded")
            with pytest.raises(ConversionError):
                parse_file_to_markdown(str(pdf))

    def test_docx_routed_through_docling(self, tmp_path):
        """DOCX files use Docling (not the legacy fallback)."""
        docx = tmp_path / "report.docx"
        docx.write_bytes(b"PK fake docx")

        with patch("backend.ingestion.parser._convert_with_docling") as mock_convert:
            mock_convert.return_value = "# DOCX content"
            result = parse_file_to_markdown(str(docx))

        assert result == "# DOCX content"


# ---------------------------------------------------------------------------
# Worker task tests
# ---------------------------------------------------------------------------


class TestProcessDocumentTask:
    """Tests for the Celery ingestion worker task."""

    def _make_hex(self, content: bytes = b"Hello World") -> str:
        return content.hex()

    def test_success_returns_parent_uuid(self):
        """Happy-path: returns a UUID string of length 36."""
        with (
            patch("backend.tasks.ingestion_worker.parse_file_to_markdown") as mock_parse,
            patch("backend.tasks.ingestion_worker.SessionLocal") as MockSession,
            patch("backend.tasks.ingestion_worker.get_weaviate_mgr") as mock_weaviate,
        ):
            mock_parse.return_value = "# Doc\n" + "Content. " * 60  # > 512 chars
            mock_db = MagicMock()
            MockSession.return_value = mock_db
            mock_weaviate.return_value = MagicMock()

            result = process_document_task(
                hex_content=self._make_hex(),
                filename="report.pdf",
                team_id="team-abc",
                user_id="user-xyz",
            )

        assert isinstance(result, str)
        assert len(result) == 36  # UUID

    def test_parent_document_inserted_correctly(self):
        """ParentDocument is created with the correct attributes."""
        long_content = "Sentence about AI. " * 50  # ~950 chars
        with (
            patch("backend.tasks.ingestion_worker.parse_file_to_markdown") as mock_parse,
            patch("backend.tasks.ingestion_worker.SessionLocal") as MockSession,
            patch("backend.tasks.ingestion_worker.get_weaviate_mgr") as mock_weaviate,
        ):
            mock_parse.return_value = long_content
            mock_db = MagicMock()
            MockSession.return_value = mock_db
            mock_weaviate.return_value = MagicMock()

            parent_id = process_document_task(
                hex_content=self._make_hex(),
                filename="notes.docx",
                team_id="team-1",
                user_id="user-1",
            )

        doc: ParentDocument = mock_db.add.call_args[0][0]
        assert isinstance(doc, ParentDocument)
        assert doc.parent_id == parent_id
        assert doc.filename == "notes.docx"
        assert doc.team_id == "team-1"
        assert doc.content == long_content

        mock_db.commit.assert_called_once()
        mock_db.close.assert_called_once()

    def test_weaviate_chunks_have_correct_shape(self):
        """Each Weaviate chunk has required fields with correct types."""
        with (
            patch("backend.tasks.ingestion_worker.parse_file_to_markdown") as mock_parse,
            patch("backend.tasks.ingestion_worker.SessionLocal") as MockSession,
            patch("backend.tasks.ingestion_worker.get_weaviate_mgr") as mock_weaviate,
        ):
            mock_parse.return_value = "Word. " * 200  # 1200 chars
            mock_db = MagicMock()
            MockSession.return_value = mock_db
            mock_weaviate_mgr = MagicMock()
            mock_weaviate.return_value = mock_weaviate_mgr

            parent_id = process_document_task(
                hex_content=self._make_hex(),
                filename="doc.pdf",
                team_id="team-x",
                user_id="user-y",
            )

        mock_weaviate_mgr.insert_chunks.assert_called_once()
        _, kwargs = mock_weaviate_mgr.insert_chunks.call_args

        assert kwargs["tenant_id"] == "team-x"
        assert kwargs["allowed_users"] == ["user-y", "public"]
        chunks = kwargs["chunks"]
        assert len(chunks) > 0
        for chunk in chunks:
            assert "text" in chunk
            assert chunk["parent_id"] == parent_id
            assert chunk["page_number"] == 1
            assert chunk["bbox"] == []
            assert len(chunk["text"]) <= 512

    def test_temp_file_is_cleaned_up_on_success(self, tmp_path):
        """The temporary file should be removed after task completion."""
        created_paths: list[str] = []

        real_ntf = __import__("tempfile").NamedTemporaryFile

        def tracking_ntf(**kwargs):
            f = real_ntf(**kwargs)
            created_paths.append(f.name)
            return f

        with (
            patch("backend.tasks.ingestion_worker.tempfile.NamedTemporaryFile", side_effect=tracking_ntf),
            patch("backend.tasks.ingestion_worker.parse_file_to_markdown", return_value="content"),
            patch("backend.tasks.ingestion_worker.SessionLocal") as MockSession,
            patch("backend.tasks.ingestion_worker.get_weaviate_mgr") as mock_weaviate,
        ):
            MockSession.return_value = MagicMock()
            mock_weaviate.return_value = MagicMock()

            process_document_task(
                hex_content=self._make_hex(),
                filename="test.pdf",
                team_id="t",
                user_id="u",
            )

        for path in created_paths:
            assert not os.path.exists(path), f"Temp file not cleaned up: {path}"

    def test_mysql_rollback_on_db_error(self):
        """If the DB commit fails, rollback is called and the exception propagates."""
        with (
            patch("backend.tasks.ingestion_worker.parse_file_to_markdown", return_value="content"),
            patch("backend.tasks.ingestion_worker.SessionLocal") as MockSession,
            patch("backend.tasks.ingestion_worker.get_weaviate_mgr"),
        ):
            mock_db = MagicMock()
            mock_db.commit.side_effect = Exception("DB write failed")
            MockSession.return_value = mock_db

            with pytest.raises(Exception, match="DB write failed"):
                process_document_task(
                    hex_content=self._make_hex(),
                    filename="doc.pdf",
                    team_id="t",
                    user_id="u",
                )

            mock_db.rollback.assert_called_once()
            mock_db.close.assert_called_once()

    def test_unsupported_format_not_retried(self):
        """UnsupportedFormatError from the parser should bubble up, not trigger retry."""
        with patch(
            "backend.tasks.ingestion_worker.parse_file_to_markdown",
            side_effect=UnsupportedFormatError("bad format"),
        ):
            with pytest.raises(UnsupportedFormatError):
                process_document_task(
                    hex_content=self._make_hex(),
                    filename="file.rar",
                    team_id="t",
                    user_id="u",
                )

    def test_file_extension_preserved_in_temp_file(self):
        """Temp file must have the same suffix as the original filename."""
        captured_suffixes: list[str] = []
        real_ntf = __import__("tempfile").NamedTemporaryFile

        def capturing_ntf(**kwargs):
            captured_suffixes.append(kwargs.get("suffix", ""))
            return real_ntf(**kwargs)

        with (
            patch("backend.tasks.ingestion_worker.tempfile.NamedTemporaryFile", side_effect=capturing_ntf),
            patch("backend.tasks.ingestion_worker.parse_file_to_markdown", return_value="md"),
            patch("backend.tasks.ingestion_worker.SessionLocal") as MockSession,
            patch("backend.tasks.ingestion_worker.get_weaviate_mgr") as mock_weaviate,
        ):
            MockSession.return_value = MagicMock()
            mock_weaviate.return_value = MagicMock()

            process_document_task(
                hex_content=self._make_hex(),
                filename="presentation.pptx",
                team_id="t",
                user_id="u",
            )

        assert captured_suffixes == [".pptx"]
