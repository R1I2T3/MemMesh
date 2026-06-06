# backend/tests/test_chromadb.py
"""Integration tests for ChromaDB team-scoped wrapper."""

import pytest
from chromadb.utils import embedding_functions

import db.chromadb
from db.chromadb import (
    get_or_create_collection,
    upsert_chunks,
    query_collection,
    delete_collection,
    ChromaDBClient,
)
from ingestion.chunker import Chunk


@pytest.fixture(scope="module", autouse=True)
def force_local_embeddings():
    """Force tests to use local DefaultEmbeddingFunction even if GEMINI_API_KEY is set."""
    db.chromadb._EF_OVERRIDE = embedding_functions.DefaultEmbeddingFunction()
    yield
    db.chromadb._EF_OVERRIDE = None


@pytest.fixture(autouse=True)
def cleanup_chroma():
    """Reset the ChromaDB client (and its in-memory state) after each test."""
    yield
    ChromaDBClient.reset()


class TestGetOrCreateCollection:
    def test_creates_collection(self):
        col = get_or_create_collection("test_team_1")
        assert col is not None
        assert col.name == "team_test_team_1"

    def test_same_team_returns_same_collection(self):
        col1 = get_or_create_collection("test_team_2")
        col2 = get_or_create_collection("test_team_2")
        assert col1.name == col2.name


class TestUpsertAndQuery:
    def test_upsert_single_chunk(self):
        chunks = [
            Chunk(
                chunk_id="c1",
                text="The capital of France is Paris.",
                team_id="team_a",
                source_doc_id="doc1",
                index=0,
                char_offset=0,
                page_number=1,
                section_heading=None,
            )
        ]
        upsert_chunks("team_a", chunks)
        results = query_collection("team_a", "capital of France", n_results=1)
        assert len(results) == 1
        assert results[0]["chunk_id"] == "c1"
        assert results[0]["text"] == "The capital of France is Paris."

    def test_upsert_multiple_chunks_and_query(self):
        chunks = [
            Chunk(
                chunk_id="c10",
                text="Python is a programming language.",
                team_id="team_b",
                source_doc_id="doc2",
                index=0,
                char_offset=0,
                page_number=1,
                section_heading=None,
            ),
            Chunk(
                chunk_id="c11",
                text="JavaScript runs in the browser.",
                team_id="team_b",
                source_doc_id="doc2",
                index=1,
                char_offset=50,
                page_number=1,
                section_heading=None,
            ),
        ]
        upsert_chunks("team_b", chunks)
        results = query_collection("team_b", "programming language", n_results=2)
        assert len(results) == 2
        # Python chunk should rank higher for "programming language"
        assert results[0]["chunk_id"] == "c10"

    def test_query_returns_metadata(self):
        chunks = [
            Chunk(
                chunk_id="c20",
                text="Machine learning is a subset of AI.",
                team_id="team_c",
                source_doc_id="doc3",
                index=0,
                char_offset=0,
                page_number=3,
                section_heading="ML Basics",
            ),
        ]
        upsert_chunks("team_c", chunks)
        results = query_collection("team_c", "machine learning", n_results=1)
        assert results[0]["source_doc_id"] == "doc3"
        assert results[0]["page_number"] == 3
        assert results[0]["section_heading"] == "ML Basics"


class TestTeamIsolation:
    def test_teams_cannot_see_each_others_data(self):
        chunks_a = [
            Chunk(
                chunk_id="iso_a",
                text="Secret data for team alpha.",
                team_id="alpha",
                source_doc_id="doc_alpha",
                index=0,
                char_offset=0,
                page_number=1,
                section_heading=None,
            ),
        ]
        chunks_b = [
            Chunk(
                chunk_id="iso_b",
                text="Secret data for team beta.",
                team_id="beta",
                source_doc_id="doc_beta",
                index=0,
                char_offset=0,
                page_number=1,
                section_heading=None,
            ),
        ]
        upsert_chunks("alpha", chunks_a)
        upsert_chunks("beta", chunks_b)

        results_a = query_collection("alpha", "secret data", n_results=5)
        results_b = query_collection("beta", "secret data", n_results=5)

        # Each team should only see their own data
        assert all(r["team_id"] == "alpha" for r in results_a)
        assert all(r["team_id"] == "beta" for r in results_b)


class TestDeleteCollection:
    def test_delete_removes_collection(self):
        chunks = [
            Chunk(
                chunk_id="del1",
                text="Data to be deleted.",
                team_id="doomed",
                source_doc_id="doc_doom",
                index=0,
                char_offset=0,
                page_number=1,
                section_heading=None,
            ),
        ]
        upsert_chunks("doomed", chunks)
        delete_collection("doomed")

        # Querying after deletion should return empty
        results = query_collection("doomed", "deleted", n_results=5)
        assert results == []

