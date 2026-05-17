import pytest
from unittest.mock import patch, MagicMock
from agents.retrieval.multi_hop import MultiHopRetriever, MultiHopResult
from db.citation import CitationResult


@pytest.fixture
def mock_graph_store():
    store = MagicMock()
    store.fetch_subgraph.return_value = [
        {"source": "Alice", "relationship_path": ["WORKS_AT"], "target": "Acme", "target_type": "ORG"},
    ]
    return store


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    return llm


@pytest.mark.unit
def test_multi_hop_returns_result_with_hops(mock_graph_store, mock_llm):
    retriever = MultiHopRetriever(
        graph_store=mock_graph_store,
        model=mock_llm,
        max_hops=3,
    )

    with patch.object(retriever, "_extract_entities", return_value=["Alice"]):
        with patch.object(retriever, "_select_entities", return_value=["Acme"]):
            with patch.object(retriever, "_should_terminate", return_value=True):
                result = retriever.run("What does Alice do?")

    assert isinstance(result, MultiHopResult)
    assert result.hops_taken >= 1
    assert "Alice" in result.entities_expanded


@pytest.mark.unit
def test_multi_hop_stops_on_termination(mock_graph_store, mock_llm):
    retriever = MultiHopRetriever(
        graph_store=mock_graph_store,
        model=mock_llm,
        max_hops=5,
    )

    with patch.object(retriever, "_extract_entities", return_value=["Alice"]):
        with patch.object(retriever, "_select_entities", return_value=["Acme"]):
            with patch.object(retriever, "_should_terminate", return_value=True):
                result = retriever.run("What does Alice do?")

    assert result.hops_taken == 1


@pytest.mark.unit
def test_multi_hop_respects_max_hops(mock_graph_store, mock_llm):
    retriever = MultiHopRetriever(
        graph_store=mock_graph_store,
        model=mock_llm,
        max_hops=2,
    )

    with patch.object(retriever, "_extract_entities", return_value=["Alice"]):
        with patch.object(retriever, "_select_entities", return_value=["Acme"]):
            with patch.object(retriever, "_should_terminate", return_value=False):
                result = retriever.run("What does Alice do?")

    assert result.hops_taken == 2


@pytest.mark.unit
def test_multi_hop_fallback_on_llm_failure(mock_graph_store, mock_llm):
    retriever = MultiHopRetriever(
        graph_store=mock_graph_store,
        model=mock_llm,
        max_hops=3,
    )

    with patch.object(retriever, "_extract_entities", side_effect=Exception("LLM failed")):
        result = retriever.run("What does Alice do?")

    assert isinstance(result, MultiHopResult)
    assert result.hops_taken == 0


@pytest.mark.unit
def test_multi_hop_deduplicates_results(mock_graph_store, mock_llm):
    mock_graph_store.fetch_subgraph.return_value = [
        {"source": "Alice", "relationship_path": ["WORKS_AT"], "target": "Acme", "target_type": "ORG"},
        {"source": "Alice", "relationship_path": ["WORKS_AT"], "target": "Acme", "target_type": "ORG"},
    ]

    retriever = MultiHopRetriever(
        graph_store=mock_graph_store,
        model=mock_llm,
        max_hops=1,
    )

    with patch.object(retriever, "_extract_entities", return_value=["Alice"]):
        with patch.object(retriever, "_select_entities", return_value=[]):
            with patch.object(retriever, "_should_terminate", return_value=True):
                result = retriever.run("test")

    unique_keys = set()
    for r in result.results:
        key = (r.entity_name, r.relationship, tuple(r.connected_entities))
        unique_keys.add(key)

    assert len(unique_keys) == 1
