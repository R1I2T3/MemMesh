import pytest
from unittest.mock import patch, MagicMock
from db.dependencies import vector_search_with_rewriting
from db.citation import CitationResult


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
    ids = [r.id for r in result]
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
def test_retrieval_embedding_failure_returns_empty():
    mock_store = MagicMock()

    with patch("db.dependencies.embed_chunks", return_value=[]):
        result = vector_search_with_rewriting("query", mock_store, top_k=5)

    assert result == []


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

    assert result[0].id == "uuid-1"
    assert result[1].id == "uuid-2"


@pytest.mark.unit
def test_vector_search_returns_citation_results():
    mock_store = MagicMock()
    mock_store.search.return_value = [
        {"id": "uuid-1", "text": "result A", "source": "doc1", "chunk_index": 0, "distance": 0.1},
    ]

    mock_rewriter = MagicMock()
    mock_rewriter.rewrite.return_value = MagicMock(
        step_back_query="broader",
        alternative_queries=[],
    )

    with patch("db.dependencies.QueryRewriter", return_value=mock_rewriter):
        with patch("db.dependencies.embed_chunks", return_value=[{"embedding": [0.1] * 768}]):
            result = vector_search_with_rewriting("query", mock_store, top_k=1)

    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], CitationResult)
    assert result[0].id == "uuid-1"
    assert result[0].type == "vector"


@pytest.mark.unit
def test_lookup_entity_returns_citation_results():
    from db.dependencies import build_rag_team_with_stores

    mock_graph = MagicMock()
    mock_graph.fetch_subgraph.return_value = [
        {"source": "Alice", "relationship_path": ["WORKS_AT"], "target": "Acme", "target_type": "ORG"},
    ]
    mock_vector = MagicMock()

    team = build_rag_team_with_stores(mock_graph, mock_vector)

    lookup_tool = None
    for tool in team.tools:
        if tool.__name__ == "lookup_entity":
            lookup_tool = tool
            break

    assert lookup_tool is not None
    result = lookup_tool("Alice")
    assert isinstance(result, str)
    assert "Alice" in result
    assert "Acme" in result
