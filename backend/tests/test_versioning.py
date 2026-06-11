"""Tests for document versioning utilities (content hash, version detection)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.ingestion.versioning import (
    compute_content_hash,
    detect_version_change,
)


class TestComputeContentHash:
    def test_returns_hex_string(self):
        result = compute_content_hash(b"hello world")
        assert isinstance(result, str)
        assert len(result) == 64

    def test_same_content_same_hash(self):
        assert compute_content_hash(b"abc") == compute_content_hash(b"abc")

    def test_different_content_different_hash(self):
        assert compute_content_hash(b"abc") != compute_content_hash(b"xyz")

    def test_empty_bytes(self):
        result = compute_content_hash(b"")
        assert isinstance(result, str)
        assert len(result) == 64


class MockSourceDoc:
    """Minimal SourceDoc-like object for testing."""

    def __init__(self, doc_id, team_id, file_name, content_hash, version_number):
        self.doc_id = doc_id
        self.team_id = team_id
        self.file_name = file_name
        self.content_hash = content_hash
        self.version_number = version_number


class TestDetectVersionChange:
    def test_returns_none_when_no_existing_doc(self):
        """No prior SourceDoc → no version change."""
        with patch("backend.ingestion.versioning.SessionLocal") as MockSession:
            mock_db = MagicMock()
            MockSession.return_value = mock_db
            mock_query = mock_db.query.return_value
            mock_filter = mock_query.filter_by.return_value
            mock_filter.with_for_update.return_value.order_by.return_value.first.return_value = None

            result = detect_version_change(
                team_id="team-1",
                filename="doc.pdf",
                new_hash="newhash123",
            )

        assert result is None

    def test_returns_none_when_hash_matches(self):
        """Same content hash → no version change."""
        existing = MockSourceDoc(
            doc_id="doc-001",
            team_id="team-1",
            file_name="doc.pdf",
            content_hash="newhash123",
            version_number=2,
        )
        with patch("backend.ingestion.versioning.SessionLocal") as MockSession:
            mock_db = MagicMock()
            MockSession.return_value = mock_db
            mock_db.query.return_value.filter_by.return_value.with_for_update.return_value.order_by.return_value.first.return_value = existing

            result = detect_version_change(
                team_id="team-1",
                filename="doc.pdf",
                new_hash="newhash123",
            )

        assert result is None

    def test_returns_version_info_when_hash_differs(self):
        """Different content hash → version change detected."""
        existing = MockSourceDoc(
            doc_id="doc-001",
            team_id="team-1",
            file_name="doc.pdf",
            content_hash="oldhash456",
            version_number=2,
        )
        with patch("backend.ingestion.versioning.SessionLocal") as MockSession:
            mock_db = MagicMock()
            MockSession.return_value = mock_db
            mock_db.query.return_value.filter_by.return_value.with_for_update.return_value.order_by.return_value.first.return_value = existing

            result = detect_version_change(
                team_id="team-1",
                filename="doc.pdf",
                new_hash="newhash789",
            )

        assert result == {
            "previous_version_id": "doc-001",
            "previous_version": 2,
            "new_version": 3,
        }

    def test_queries_source_doc_by_team_and_filename(self):
        """Verify the query uses correct filters."""
        with patch("backend.ingestion.versioning.SessionLocal") as MockSession:
            mock_db = MagicMock()
            MockSession.return_value = mock_db

            detect_version_change(
                team_id="team-x",
                filename="report.docx",
                new_hash="somehash",
            )

        mock_db.query.assert_called_once()
        mock_db.query.return_value.filter_by.assert_called_once_with(
            team_id="team-x",
            file_name="report.docx",
        )
        mock_db.query.return_value.filter_by.return_value.with_for_update.assert_called_once()
        mock_db.query.return_value.filter_by.return_value.with_for_update.return_value.order_by.assert_called_once()

    def test_closes_db_session(self):
        """Session is always closed after detection."""
        with patch("backend.ingestion.versioning.SessionLocal") as MockSession:
            mock_db = MagicMock()
            MockSession.return_value = mock_db
            mock_db.query.return_value.filter_by.return_value.with_for_update.return_value.order_by.return_value.first.return_value = None

            detect_version_change(team_id="t", filename="f.pdf", new_hash="h")

        mock_db.close.assert_called_once()

    def test_closes_db_session_on_exception(self):
        """Session is closed even if an exception occurs."""
        with patch("backend.ingestion.versioning.SessionLocal") as MockSession:
            mock_db = MagicMock()
            MockSession.return_value = mock_db
            mock_db.query.side_effect = Exception("query failed")

            with pytest.raises(Exception, match="query failed"):
                detect_version_change(team_id="t", filename="f.pdf", new_hash="h")

        mock_db.close.assert_called_once()
