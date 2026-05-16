from agents.router.query_router import QueryRouter


def test_classify_query_graph():
    query = "What is the relationship between FastAPI and Neo4j?"
    result = QueryRouter.classify_query(query)
    assert result == "graph"


def test_classify_query_vector():
    query = "Can you summarize what we talked about yesterday?"
    result = QueryRouter.classify_query(query)
    assert result == "vector"


def test_classify_query_hybrid():
    query = "Hello, what's up?"
    result = QueryRouter.classify_query(query)
    assert result == "hybrid"


def test_classify_query_mixed():
    query = "Summarize the relationship between Bob and Alice."
    # Both "summarize" and "relationship" are present. Will default to hybrid or whichever scores higher
    # In our simple heuristic, they tie (score 1 each), so it falls back to hybrid.
    result = QueryRouter.classify_query(query)
    assert result == "hybrid"
