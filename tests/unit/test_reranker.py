import pytest
from unittest.mock import MagicMock, patch
from utils.fusion.reranker import HybridRetriever


@pytest.fixture
def mock_cross_encoder():
    with patch("utils.fusion.reranker.CrossEncoder") as MockCrossEncoder:
        mock_instance = MagicMock()
        MockCrossEncoder.return_value = mock_instance
        yield mock_instance


def test_rerank_results_empty(mock_cross_encoder):
    retriever = HybridRetriever()
    results = retriever.rerank_results("test query", [], [])
    assert results == []


def test_rerank_results_deduplication(mock_cross_encoder):
    mock_cross_encoder.predict.return_value = [0.8, 0.6, 0.9]

    retriever = HybridRetriever()
    graph_res = ["Document A", "Document B"]
    vector_res = ["Document B", "Document C"]

    results = retriever.rerank_results("test query", graph_res, vector_res, top_k=5)

    assert len(results) == 3
    assert "Document A" in results
    assert "Document B" in results
    assert "Document C" in results


def test_rerank_results_truncation(mock_cross_encoder):
    mock_cross_encoder.predict.return_value = [0.5, 0.7, 0.3, 0.9, 0.1]

    retriever = HybridRetriever()
    graph_res = ["Doc 1", "Doc 2", "Doc 3"]
    vector_res = ["Doc 4", "Doc 5"]

    results = retriever.rerank_results("test query", graph_res, vector_res, top_k=2)
    assert len(results) == 2


def test_rerank_results_ordered_by_score(mock_cross_encoder):
    mock_cross_encoder.predict.return_value = [0.3, 0.9, 0.1, 0.7]

    retriever = HybridRetriever()
    graph_res = ["Low score doc", "High score doc"]
    vector_res = ["Very low score doc", "Medium score doc"]

    results = retriever.rerank_results("test query", graph_res, vector_res, top_k=4)

    assert results[0] == "High score doc"
    assert results[1] == "Medium score doc"
    assert results[2] == "Low score doc"
    assert results[3] == "Very low score doc"


def test_cross_encoder_loaded_on_init(mock_cross_encoder):
    retriever = HybridRetriever()
    assert retriever.reranker is not None
    assert retriever.reranker.predict is not None
