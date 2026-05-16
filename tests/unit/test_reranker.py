from utils.fusion.reranker import HybridRetriever


def test_rerank_results_empty():
    retriever = HybridRetriever()
    results = retriever.rerank_results("test query", [], [])
    assert results == []


def test_rerank_results_deduplication():
    retriever = HybridRetriever()
    graph_res = ["Document A", "Document B"]
    vector_res = ["Document B", "Document C"]

    # "Document B" is duplicated, should only appear once.
    results = retriever.rerank_results("test query", graph_res, vector_res, top_k=5)

    assert len(results) == 3
    assert "Document A" in results
    assert "Document B" in results
    assert "Document C" in results


def test_rerank_results_truncation():
    retriever = HybridRetriever()
    graph_res = ["Doc 1", "Doc 2", "Doc 3"]
    vector_res = ["Doc 4", "Doc 5"]

    # We ask for top 2
    results = retriever.rerank_results("test query", graph_res, vector_res, top_k=2)
    assert len(results) == 2
