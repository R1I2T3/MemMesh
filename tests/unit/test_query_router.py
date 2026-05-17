import pytest
from unittest.mock import patch, MagicMock
from agents.router.query_router import QueryRouter


@pytest.fixture
def mock_router():
    """Patch Agent so QueryRouter can be instantiated without hitting the real LLM."""
    with patch("agents.router.query_router.Agent") as MockAgent:
        mock_agent_instance = MagicMock()
        MockAgent.return_value = mock_agent_instance
        yield mock_agent_instance


def test_classify_query_graph(mock_router):
    mock_decision = MagicMock()
    mock_decision.content.route = "graph"
    mock_router.run.return_value = mock_decision

    query = "What is the relationship between FastAPI and Neo4j?"
    result = QueryRouter().classify_query(query)
    assert result == "graph"


def test_classify_query_vector(mock_router):
    mock_decision = MagicMock()
    mock_decision.content.route = "vector"
    mock_router.run.return_value = mock_decision

    query = "Can you summarize what we talked about yesterday?"
    result = QueryRouter().classify_query(query)
    assert result == "vector"


def test_classify_query_hybrid(mock_router):
    mock_decision = MagicMock()
    mock_decision.content.route = "hybrid"
    mock_router.run.return_value = mock_decision

    query = "Hello, what's up?"
    result = QueryRouter().classify_query(query)
    assert result == "hybrid"


def test_classify_query_mixed(mock_router):
    mock_decision = MagicMock()
    mock_decision.content.route = "hybrid"
    mock_router.run.return_value = mock_decision

    query = "Summarize the relationship between Bob and Alice."
    result = QueryRouter().classify_query(query)
    assert result == "hybrid"


def test_fallback_classify_graph():
    query = "What is the relationship between FastAPI and Neo4j?"
    result = QueryRouter._fallback_classify(query)
    assert result == "graph"


def test_fallback_classify_vector():
    query = "Can you summarize what we talked about yesterday?"
    result = QueryRouter._fallback_classify(query)
    assert result == "vector"


def test_fallback_classify_hybrid():
    query = "Hello, what's up?"
    result = QueryRouter._fallback_classify(query)
    assert result == "hybrid"


def test_fallback_on_llm_failure():
    with patch("agents.router.query_router.Agent") as MockAgent:
        mock_agent_instance = MagicMock()
        mock_agent_instance.run.side_effect = Exception("LLM unavailable")
        MockAgent.return_value = mock_agent_instance

        router = QueryRouter()
        result = router.classify_query("Hello, what's up?")
        assert result == "hybrid"
