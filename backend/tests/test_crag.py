import os
import pytest
from unittest.mock import patch, MagicMock
from backend.agents.crag import evaluate_retrieval, RelevanceGrade
from backend.agents.web_search import web_search_fallback

def test_crag_evaluator_mock_mode_relevant():
    with patch.dict(os.environ, {"MOCK_LLM": "true"}):
        state = {
            "query": "What is Python?",
            "retrieved_chunks": [{"text": "Python is a programming language"}]
        }
        res = evaluate_retrieval(state)
        assert res["relevance_pass"] is True
        assert "CRAG score: 0.9" in res["telemetry_log"]

def test_crag_evaluator_mock_mode_irrelevant():
    with patch.dict(os.environ, {"MOCK_LLM": "true"}):
        state = {
            "query": "irrelevant query",
            "retrieved_chunks": [{"text": "Python is a programming language"}]
        }
        res = evaluate_retrieval(state)
        assert res["relevance_pass"] is False
        assert "CRAG score: 0.1" in res["telemetry_log"]

def test_crag_evaluator_mock_mode_no_chunks():
    with patch.dict(os.environ, {"MOCK_LLM": "true"}):
        state = {
            "query": "What is Python?",
            "retrieved_chunks": []
        }
        res = evaluate_retrieval(state)
        assert res["relevance_pass"] is False

def test_crag_evaluator_real_mode_relevant():
    with patch.dict(os.environ, {"MOCK_LLM": "false"}):
        with patch("backend.agents.crag.ChatGoogleGenerativeAI") as mock_llm_cls:
            mock_llm = MagicMock()
            mock_llm_cls.return_value = mock_llm
            mock_structured = MagicMock()
            mock_llm.with_structured_output.return_value = mock_structured
            
            relevance_grade = RelevanceGrade(
                score=0.8,
                reasoning="Context is highly relevant."
            )
            mock_structured.invoke.return_value = relevance_grade
            mock_structured.return_value = relevance_grade
            
            state = {
                "query": "What is Python?",
                "retrieved_chunks": [{"text": "Python is a programming language"}]
            }
            res = evaluate_retrieval(state)
            assert res["relevance_pass"] is True
            assert "0.8" in res["telemetry_log"]

def test_crag_evaluator_real_mode_irrelevant():
    with patch.dict(os.environ, {"MOCK_LLM": "false"}):
        with patch("backend.agents.crag.ChatGoogleGenerativeAI") as mock_llm_cls:
            mock_llm = MagicMock()
            mock_llm_cls.return_value = mock_llm
            mock_structured = MagicMock()
            mock_llm.with_structured_output.return_value = mock_structured
            
            relevance_grade = RelevanceGrade(
                score=0.2,
                reasoning="Context is about Java, not Python."
            )
            mock_structured.invoke.return_value = relevance_grade
            mock_structured.return_value = relevance_grade
            
            state = {
                "query": "What is Python?",
                "retrieved_chunks": [{"text": "Java is another language"}]
            }
            res = evaluate_retrieval(state)
            assert res["relevance_pass"] is False
            assert "0.2" in res["telemetry_log"]

def test_web_search_fallback_mock_mode():
    with patch.dict(os.environ, {"MOCK_LLM": "true"}):
        state = {
            "query": "some query",
            "rewritten_queries": ["rewritten query"]
        }
        res = web_search_fallback(state)
        assert len(res["web_search_results"]) == 1
        assert "Mock web search result" in res["web_search_results"][0]["text"]
        assert "rewritten query" in res["web_search_results"][0]["url"]

def test_web_search_fallback_real_mode():
    with patch.dict(os.environ, {"MOCK_LLM": "false"}):
        # We try to patch DuckDuckGoSearchRun
        with patch("langchain_community.tools.DuckDuckGoSearchRun") as mock_search_cls:
            mock_search = MagicMock()
            mock_search_cls.return_value = mock_search
            mock_search.run.return_value = "Search result from DuckDuckGo"
            
            state = {
                "query": "DuckDuckGo search test",
                "rewritten_queries": []
            }
            res = web_search_fallback(state)
            assert len(res["web_search_results"]) == 1
            assert res["web_search_results"][0]["text"] == "Search result from DuckDuckGo"
            assert res["web_search_results"][0]["source"] == "web"
