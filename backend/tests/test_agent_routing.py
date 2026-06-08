import pytest
from unittest.mock import patch, MagicMock
from backend.agents.router import RouteDecision, route_query
from backend.agents.rewriter import rewrite_query, QueryRewriterOutput
from backend.agents.graph_orchestrator import get_graph

def test_router_output():
    with patch("backend.agents.router.ChatGoogleGenerativeAI") as mock_llm_cls:
        mock_llm = MagicMock()
        mock_llm_cls.return_value = mock_llm
        
        mock_structured = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured
        route_decision = RouteDecision(
            route="graph",
            reasoning="Relational query request"
        )
        mock_structured.invoke.return_value = route_decision
        mock_structured.return_value = route_decision
        
        res = route_query("How is Alice connected to Bob?")
        assert res.route == "graph"
        assert res.reasoning == "Relational query request"
        mock_llm_cls.assert_called_once_with(model="gemini-1.5-flash", temperature=0)

def test_router_exception_fallback():
    with patch("backend.agents.router.ChatGoogleGenerativeAI") as mock_llm_cls:
        mock_llm = MagicMock()
        mock_llm_cls.return_value = mock_llm
        mock_llm.with_structured_output.side_effect = Exception("API connection timeout")
        
        res = route_query("How is Alice connected to Bob?")
        assert res.route == "hybrid"
        assert "Fallback" in res.reasoning

def test_rewriter_output():
    with patch("backend.agents.rewriter.ChatGoogleGenerativeAI") as mock_llm_cls:
        mock_llm = MagicMock()
        mock_llm_cls.return_value = mock_llm
        
        mock_structured = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured
        rewriter_output = QueryRewriterOutput(
            rewritten_queries=["Alice Bob relationship", "connection Alice Bob"]
        )
        mock_structured.invoke.return_value = rewriter_output
        mock_structured.return_value = rewriter_output
        
        res = rewrite_query("How is Alice connected to Bob?")
        assert len(res) == 2
        assert "Alice Bob relationship" in res

def test_rewriter_exception_fallback():
    with patch("backend.agents.rewriter.ChatGoogleGenerativeAI") as mock_llm_cls:
        mock_llm = MagicMock()
        mock_llm_cls.return_value = mock_llm
        mock_llm.with_structured_output.side_effect = Exception("Rate limit exceeded")
        
        res = rewrite_query("How is Alice connected to Bob?")
        assert len(res) == 1
        assert res[0] == "How is Alice connected to Bob?"

def test_graph_execution_hybrid_route():
    with patch("backend.agents.router.ChatGoogleGenerativeAI") as mock_router_llm_cls, \
         patch("backend.agents.rewriter.ChatGoogleGenerativeAI") as mock_rewriter_llm_cls:
        
        # Setup rewriter mock
        mock_rewriter_llm = MagicMock()
        mock_rewriter_llm_cls.return_value = mock_rewriter_llm
        mock_rewriter_structured = MagicMock()
        mock_rewriter_llm.with_structured_output.return_value = mock_rewriter_structured
        rewriter_output = QueryRewriterOutput(
            rewritten_queries=["rewritten query 1"]
        )
        mock_rewriter_structured.invoke.return_value = rewriter_output
        mock_rewriter_structured.return_value = rewriter_output
        
        # Setup router mock
        mock_router_llm = MagicMock()
        mock_router_llm_cls.return_value = mock_router_llm
        mock_router_structured = MagicMock()
        mock_router_llm.with_structured_output.return_value = mock_router_structured
        route_decision = RouteDecision(
            route="hybrid",
            reasoning="Uses both structures"
        )
        mock_router_structured.invoke.return_value = route_decision
        mock_router_structured.return_value = route_decision
        
        # Get compiled graph
        graph = get_graph()
        
        initial_state = {
            "query": "Who is Bob?",
            "history": [],
            "rewritten_queries": [],
            "active_team_id": "team-abc",
            "user_id": "user-123",
            "session_id": "session-456",
            "route": "",
            "retrieved_chunks": [],
            "retrieved_triples": [],
            "web_search_results": [],
            "final_context": [],
            "raw_response": "",
            "citations": [],
            "relevance_pass": True
        }
        
        result = graph.invoke(initial_state)
        
        assert result["route"] == "hybrid"
        assert len(result["rewritten_queries"]) == 1
        assert result["rewritten_queries"][0] == "rewritten query 1"
        assert len(result["retrieved_chunks"]) > 0
        assert result["retrieved_chunks"][0]["text"] == "mock hybrid chunk"
        assert len(result["retrieved_triples"]) > 0
        assert result["retrieved_triples"][0] == ["MockSubject", "MockPredicate", "MockObject"]
        assert "Mock response" in result["raw_response"]
