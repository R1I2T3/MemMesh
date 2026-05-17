import pytest
from unittest.mock import patch, MagicMock
from db.dependencies import vector_search_with_rewriting


@pytest.mark.unit
def test_retrieval_deduplicates_by_id():
    mock_store = MagicMock()
    mock_store.search.side_effect = [
        [
            {"id": "uuid-1", "text": "result A", "source": "doc1"},
            {"id": "uuid-2", "text": "result B", "source": "doc2"},
        ],
        [
            {"id": "uuid-2", "text": "result B duplicate", "source": "doc2"},
            {"id": "uuid-3", "text": "result C", "source": "doc3"},
        ],
        [
            {"id": "uuid-1", "text": "result A duplicate", "source": "doc1"},
            {"id": "uuid-4", "text": "result D", "source": "doc4"},
        ],
    ]

    mock_rewriter = MagicMock()
    mock_rewriter.rewrite.return_value = MagicMock(
        step_back_query="broader query",
        alternative_queries=["alt query 1"],
    )

    with patch("db.dependencies.QueryRewriter", return_value=mock_rewriter):
        with patch("db.dependencies.embed_chunks", return_value=[{"embedding": [0.1] * 768}]):
            result = vector_search_with_rewriting("original query", mock_store, top_k=2)

    assert len(result) == 4
    ids = [r["id"] for r in result]
    assert ids.count("uuid-1") == 1
    assert ids.count("uuid-2") == 1


@pytest.mark.unit
def test_retrieval_empty_store_returns_empty():
    mock_store = MagicMock()
    mock_store.search.return_value = []

    mock_rewriter = MagicMock()
    mock_rewriter.rewrite.return_value = MagicMock(
        step_back_query="broader",
        alternative_queries=[],
    )

    with patch("db.dependencies.QueryRewriter", return_value=mock_rewriter):
        with patch("db.dependencies.embed_chunks", return_value=[{"embedding": [0.1] * 768}]):
            result = vector_search_with_rewriting("query", mock_store, top_k=5)

    assert result == []


@pytest.mark.unit
def test_retrieval_embedding_failure_returns_error():
    mock_store = MagicMock()

    with patch("db.dependencies.embed_chunks", return_value=[]):
        result = vector_search_with_rewriting("query", mock_store, top_k=5)

    assert "Vector search failed" in result


@pytest.mark.unit
def test_retrieval_preserves_original_results_first():
    mock_store = MagicMock()
    mock_store.search.side_effect = [
        [{"id": "uuid-1", "text": "original result", "source": "doc1"}],
        [{"id": "uuid-2", "text": "stepback result", "source": "doc2"}],
    ]

    mock_rewriter = MagicMock()
    mock_rewriter.rewrite.return_value = MagicMock(
        step_back_query="broader",
        alternative_queries=[],
    )

    with patch("db.dependencies.QueryRewriter", return_value=mock_rewriter):
        with patch("db.dependencies.embed_chunks", return_value=[{"embedding": [0.1] * 768}]):
            result = vector_search_with_rewriting("query", mock_store, top_k=5)

    assert result[0]["id"] == "uuid-1"
    assert result[1]["id"] == "uuid-2"
