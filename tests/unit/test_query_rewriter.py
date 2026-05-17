import pytest
from unittest.mock import patch, MagicMock
from agents.router.query_rewriter import QueryRewriter, RewritingResult


@pytest.fixture
def mock_agent():
    with patch("agents.router.query_rewriter.Agent") as MockAgent:
        mock_instance = MagicMock()
        MockAgent.return_value = mock_instance
        yield mock_instance


@pytest.mark.unit
def test_rewrite_returns_structured_result(mock_agent):
    mock_decision = MagicMock()
    mock_decision.content.step_back_query = "What are knowledge retrieval systems?"
    mock_decision.content.alternative_queries = [
        "How does semantic search work?",
        "Explain vector database retrieval",
    ]
    mock_agent.run.return_value = mock_decision

    rewriter = QueryRewriter()
    result = rewriter.rewrite("How do RAG systems use embeddings?")

    assert isinstance(result, RewritingResult)
    assert result.step_back_query == "What are knowledge retrieval systems?"
    assert len(result.alternative_queries) == 2


@pytest.mark.unit
def test_rewrite_produces_different_step_back(mock_agent):
    mock_decision = MagicMock()
    mock_decision.content.step_back_query = "What is machine learning?"
    mock_decision.content.alternative_queries = ["Define ML"]
    mock_agent.run.return_value = mock_decision

    rewriter = QueryRewriter()
    result = rewriter.rewrite("How does gradient descent work?")

    assert result.step_back_query != "How does gradient descent work?"


@pytest.mark.unit
def test_rewrite_fallback_on_llm_failure():
    with patch("agents.router.query_rewriter.Agent") as MockAgent:
        mock_instance = MagicMock()
        mock_instance.run.side_effect = Exception("LLM unavailable")
        MockAgent.return_value = mock_instance

        rewriter = QueryRewriter()
        result = rewriter.rewrite("test query")

        assert result.step_back_query == "test query"
        assert result.alternative_queries == []


@pytest.mark.unit
def test_rewrite_empty_response_returns_original():
    with patch("agents.router.query_rewriter.Agent") as MockAgent:
        mock_instance = MagicMock()
        mock_instance.run.return_value = MagicMock(content=None)
        MockAgent.return_value = mock_instance

        rewriter = QueryRewriter()
        result = rewriter.rewrite("test query")

        assert result.step_back_query == "test query"
        assert result.alternative_queries == []
