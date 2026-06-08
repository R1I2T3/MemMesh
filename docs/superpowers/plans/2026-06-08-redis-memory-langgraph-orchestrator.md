# Redis Session Memory & LangGraph Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Redis session memory with chronological ordering, query routing, query rewriting, and a lazy-compiled LangGraph orchestrator with skeleton nodes.

**Architecture:** 
- A `RedisMemory` client that stores chat history as a Redis list using `RPUSH`, trims it using `LTRIM`, and sets a key-level TTL.
- A query `router` and `rewriter` utilizing LangChain's Gemini model with Pydantic structured output.
- A lazy-loaded LangGraph `StateGraph` compiling upon first call to avoid startup dependencies.

**Tech Stack:** Python, Redis, LangChain, LangGraph, Pydantic, Pytest

---

## Task 1: Write and Verify Redis Memory Tests

**Files:**
- Create: `backend/tests/test_memory.py`

- [ ] **Step 1: Write memory unit tests**
  Create `backend/tests/test_memory.py` with tests asserting:
  - `test_chat_history_ordering` validates that messages are pushed with `rpush` and retrieved chronologically.
  - `test_save_message_uses_rpush` asserts that `rpush` is called instead of `lpush`.
  - `test_ttl_is_set_on_save` asserts that `expire` is called with the specified session TTL (7 days).

  ```python
  import json
  from unittest.mock import patch, MagicMock
  from backend.agents.memory import RedisMemory

  def test_chat_history_ordering():
      """Verify messages are returned in chronological order (oldest first)."""
      with patch("backend.agents.memory.redis.from_url") as mock_from_url:
          mock_client = MagicMock()
          mock_from_url.return_value = mock_client
          
          # Simulate oldest-first order (e.g. from RPUSH + LRANGE -N -1)
          mock_client.lrange.return_value = [
              json.dumps({"role": "user", "content": "first"}),
              json.dumps({"role": "assistant", "content": "second"}),
              json.dumps({"role": "user", "content": "third"}),
          ]
          
          mem = RedisMemory()
          history = mem.get_history("session-123", limit=3)
          
          assert len(history) == 3
          assert history[0]["content"] == "first"
          assert history[1]["content"] == "second"
          assert history[2]["content"] == "third"
          mock_client.lrange.assert_called_with("chat_history:session-123", -3, -1)

  def test_save_message_uses_rpush():
      """Verify RPUSH is used (not LPUSH) to maintain chronological order."""
      with patch("backend.agents.memory.redis.from_url") as mock_from_url:
          mock_client = MagicMock()
          mock_from_url.return_value = mock_client
          
          mem = RedisMemory()
          mem.save_message("session-123", "user", "hello")
          
          mock_client.rpush.assert_called_once_with(
              "chat_history:session-123",
              json.dumps({"role": "user", "content": "hello"})
          )
          mock_client.lpush.assert_not_called()

  def test_ttl_is_set_on_save():
      """Verify session keys get a TTL to prevent unbounded Redis memory."""
      with patch("backend.agents.memory.redis.from_url") as mock_from_url:
          mock_client = MagicMock()
          mock_from_url.return_value = mock_client
          
          mem = RedisMemory()
          mem.save_message("session-123", "user", "hello")
          
          mock_client.expire.assert_called_once_with(
              "chat_history:session-123",
              RedisMemory.SESSION_TTL
          )
          mock_client.ltrim.assert_called_once_with(
              "chat_history:session-123",
              -RedisMemory.MAX_LENGTH,
              -1
          )
  ```

- [ ] **Step 2: Run tests and verify they fail (TDD)**
  Run: `uv run pytest backend/tests/test_memory.py -v`
  Expected: Failure because `backend.agents.memory` does not exist yet.

---

## Task 2: Implement Redis Memory

**Files:**
- Create: `backend/agents/memory.py`

- [ ] **Step 1: Write the RedisMemory class**
  Implement the Redis memory client with `rpush`, `ltrim`, and `expire` to maintain session-level chat histories.

  ```python
  import json
  import redis
  from backend.config import settings

  class RedisMemory:
      SESSION_TTL = 7 * 24 * 3600  # 7 days
      MAX_LENGTH = 20

      def __init__(self):
          self.client = redis.from_url(settings.REDIS_URL, decode_responses=True)

      def get_history(self, session_id: str, limit: int = 10) -> list[dict]:
          key = f"chat_history:{session_id}"
          messages = self.client.lrange(key, -limit, -1)
          return [json.loads(m) for m in messages]

      def save_message(self, session_id: str, role: str, content: str):
          key = f"chat_history:{session_id}"
          self.client.rpush(key, json.dumps({"role": role, "content": content}))
          self.client.ltrim(key, -self.MAX_LENGTH, -1)
          self.client.expire(key, self.SESSION_TTL)
  ```

- [ ] **Step 2: Run tests and verify they pass**
  Run: `uv run pytest backend/tests/test_memory.py -v`
  Expected: PASS

---

## Task 3: Implement Query Router and Rewriter

**Files:**
- Create: `backend/agents/router.py`
- Create: `backend/agents/rewriter.py`

- [ ] **Step 1: Write routing node in `backend/agents/router.py`**
  ```python
  from typing import Literal
  from pydantic import BaseModel, Field
  from langchain_google_genai import ChatGoogleGenerativeAI

  class RouteDecision(BaseModel):
      route: Literal["vector", "graph", "hybrid"] = Field(
          description="Select the routing destination. Use 'vector' for unstructured queries/text retrieval, 'graph' for relational/knowledge queries, or 'hybrid' for a mix of both."
      )
      reasoning: str = Field(description="Explanation for why this route was selected.")

  def route_query(query: str, model_name: str = "gemini-1.5-flash") -> RouteDecision:
      llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)
      structured_llm = llm.with_structured_output(RouteDecision)
      
      prompt = f"Analyze the following query and decide the best routing destination: '{query}'"
      return structured_llm.invoke(prompt)
  ```

- [ ] **Step 2: Write query rewriter in `backend/agents/rewriter.py`**
  ```python
  from typing import List
  from pydantic import BaseModel, Field
  from langchain_google_genai import ChatGoogleGenerativeAI

  class QueryRewriterOutput(BaseModel):
      rewritten_queries: List[str] = Field(
          description="A list of 2-3 rewritten queries, including variants or step-back queries, to improve retrieval performance."
      )

  def rewrite_query(query: str, model_name: str = "gemini-1.5-flash") -> List[str]:
      llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)
      structured_llm = llm.with_structured_output(QueryRewriterOutput)
      
      prompt = f"Analyze the user's query and generate 2-3 rewritten versions (variants or step-back queries) to improve retrieval: '{query}'"
      result = structured_llm.invoke(prompt)
      return result.rewritten_queries
  ```

---

## Task 4: Write Agent Routing and Graph Orchestrator Tests

**Files:**
- Create: `backend/tests/test_agent_routing.py`

- [ ] **Step 1: Write test cases**
  Write tests that verify router, rewriter, and the LangGraph orchestrator end-to-end with mock LLM calls.

  ```python
  import pytest
  from unittest.mock import patch, MagicMock
  from backend.agents.router import RouteDecision, route_query
  from backend.agents.rewriter import rewrite_query
  from backend.agents.graph_orchestrator import get_graph

  def test_router_output():
      with patch("backend.agents.router.ChatGoogleGenerativeAI") as mock_llm_cls:
          mock_llm = MagicMock()
          mock_llm_cls.return_value = mock_llm
          
          mock_structured = MagicMock()
          mock_llm.with_structured_output.return_value = mock_structured
          mock_structured.invoke.return_value = RouteDecision(
              route="graph",
              reasoning="Relational query request"
          )
          
          res = route_query("How is Alice connected to Bob?")
          assert res.route == "graph"
          assert res.reasoning == "Relational query request"
          mock_llm_cls.assert_called_once_with(model="gemini-1.5-flash", temperature=0)

  def test_rewriter_output():
      with patch("backend.agents.rewriter.ChatGoogleGenerativeAI") as mock_llm_cls:
          mock_llm = MagicMock()
          mock_llm_cls.return_value = mock_llm
          
          from backend.agents.rewriter import QueryRewriterOutput
          mock_structured = MagicMock()
          mock_llm.with_structured_output.return_value = mock_structured
          mock_structured.invoke.return_value = QueryRewriterOutput(
              rewritten_queries=["Alice Bob relationship", "connection Alice Bob"]
          )
          
          res = rewrite_query("How is Alice connected to Bob?")
          assert len(res) == 2
          assert "Alice Bob relationship" in res

  def test_graph_execution_hybrid_route():
      with patch("backend.agents.router.ChatGoogleGenerativeAI") as mock_router_llm_cls, \
           patch("backend.agents.rewriter.ChatGoogleGenerativeAI") as mock_rewriter_llm_cls:
          
          # Setup rewriter mock
          mock_rewriter_llm = MagicMock()
          mock_rewriter_llm_cls.return_value = mock_rewriter_llm
          from backend.agents.rewriter import QueryRewriterOutput
          mock_rewriter_structured = MagicMock()
          mock_rewriter_llm.with_structured_output.return_value = mock_rewriter_structured
          mock_rewriter_structured.invoke.return_value = QueryRewriterOutput(
              rewritten_queries=["rewritten query 1"]
          )
          
          # Setup router mock
          mock_router_llm = MagicMock()
          mock_router_llm_cls.return_value = mock_router_llm
          mock_router_structured = MagicMock()
          mock_router_llm.with_structured_output.return_value = mock_router_structured
          mock_router_structured.invoke.return_value = RouteDecision(
              route="hybrid",
              reasoning="Uses both structures"
          )
          
          # Get compiled graph
          graph = get_graph()
          
          initial_state = {
              "query": "Who is Bob?",
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
  ```

- [ ] **Step 2: Run tests and verify failure**
  Run: `uv run pytest backend/tests/test_agent_routing.py -v`
  Expected: Failure because `backend.agents.graph_orchestrator` does not exist yet.

---

## Task 5: Implement LangGraph Orchestrator

**Files:**
- Create: `backend/agents/graph_orchestrator.py`

- [ ] **Step 1: Write orchestrator module**
  Write lazy compiler function `get_graph()`, state schema, and node/edge functions.

  ```python
  from typing import TypedDict, List, Dict, Any
  from langgraph.graph import StateGraph, END

  class AgentState(TypedDict):
      query: str
      rewritten_queries: List[str]
      active_team_id: str
      user_id: str
      session_id: str
      route: str                           # 'vector' | 'graph' | 'hybrid'
      retrieved_chunks: List[Dict[str, Any]] # Collected text segments
      retrieved_triples: List[List[str]]   # Graph relationships [Subject, Predicate, Object]
      web_search_results: List[Dict[str, Any]]
      final_context: List[Dict[str, Any]]  # Combined, fused, and reranked context
      raw_response: str
      citations: List[Dict[str, Any]]
      relevance_pass: bool                 # Result of the CRAG check

  # Nodes
  def rewrite_node(state: AgentState) -> Dict[str, Any]:
      from backend.agents.rewriter import rewrite_query
      rewritten = rewrite_query(state["query"])
      return {"rewritten_queries": rewritten}

  def route_node(state: AgentState) -> Dict[str, Any]:
      from backend.agents.router import route_query
      decision = route_query(state["query"])
      return {"route": decision.route}

  def vector_retrieve_node(state: AgentState) -> Dict[str, Any]:
      # Mock retrieval
      return {"retrieved_chunks": [{"text": "mock vector chunk", "score": 0.9}]}

  def graph_retrieve_node(state: AgentState) -> Dict[str, Any]:
      # Mock retrieval
      return {"retrieved_triples": [["MockSubject", "MockPredicate", "MockObject"]]}

  def hybrid_retrieve_node(state: AgentState) -> Dict[str, Any]:
      # Mock retrieval
      return {
          "retrieved_chunks": [{"text": "mock hybrid chunk", "score": 0.8}],
          "retrieved_triples": [["MockSubject", "MockPredicate", "MockObject"]]
      }

  def crag_check_node(state: AgentState) -> Dict[str, Any]:
      # Mock relevance check, defaults to True for test simplicity
      return {"relevance_pass": True}

  def web_search_node(state: AgentState) -> Dict[str, Any]:
      return {"web_search_results": [{"title": "mock web result", "snippet": "mock content"}]}

  def synthesize_node(state: AgentState) -> Dict[str, Any]:
      # Mock synthesis response
      return {
          "raw_response": f"Mock response for query: {state['query']}",
          "citations": [{"source": "mock_source"}]
      }

  # Conditional routing functions
  def route_router(state: AgentState) -> str:
      route = state.get("route")
      if route == "vector":
          return "vector_retrieve"
      elif route == "graph":
          return "graph_retrieve"
      else:
          return "hybrid_retrieve"

  def route_crag(state: AgentState) -> str:
      if not state.get("relevance_pass", True):
          return "web_search"
      return "synthesize"

  _compiled_graph = None

  def get_graph():
      global _compiled_graph
      if _compiled_graph is not None:
          return _compiled_graph
          
      workflow = StateGraph(AgentState)
      
      # Add nodes
      workflow.add_node("rewrite", rewrite_node)
      workflow.add_node("route", route_node)
      workflow.add_node("vector_retrieve", vector_retrieve_node)
      workflow.add_node("graph_retrieve", graph_retrieve_node)
      workflow.add_node("hybrid_retrieve", hybrid_retrieve_node)
      workflow.add_node("crag_check", crag_check_node)
      workflow.add_node("web_search", web_search_node)
      workflow.add_node("synthesize", synthesize_node)
      
      # Define execution graph
      workflow.set_entry_point("rewrite")
      workflow.add_edge("rewrite", "route")
      
      workflow.add_conditional_edges(
          "route",
          route_router,
          {
              "vector_retrieve": "vector_retrieve",
              "graph_retrieve": "graph_retrieve",
              "hybrid_retrieve": "hybrid_retrieve"
          }
      )
      
      workflow.add_edge("vector_retrieve", "crag_check")
      workflow.add_edge("graph_retrieve", "crag_check")
      workflow.add_edge("hybrid_retrieve", "crag_check")
      
      workflow.add_conditional_edges(
          "crag_check",
          route_crag,
          {
              "web_search": "web_search",
              "synthesize": "synthesize"
          }
      )
      
      workflow.add_edge("web_search", "synthesize")
      workflow.add_edge("synthesize", END)
      
      _compiled_graph = workflow.compile()
      return _compiled_graph
  ```

- [ ] **Step 2: Run all backend tests and verify they pass**
  Run: `uv run pytest backend/tests/ -v`
  Expected: All tests pass.
