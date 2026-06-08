from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END

class AgentState(TypedDict):
    query: str
    history: List[Dict[str, Any]]
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
    query_to_route = state["query"]
    if state.get("rewritten_queries") and len(state["rewritten_queries"]) > 0:
        query_to_route = state["rewritten_queries"][0]
    decision = route_query(query_to_route)
    return {"route": decision.route}

def vector_retrieve_node(state: AgentState) -> Dict[str, Any]:
    import os
    if os.environ.get("MOCK_LLM") == "true":
        return {"retrieved_chunks": [{"text": "mock vector chunk", "score": 0.9}]}
    
    from backend.db.weaviate import get_weaviate_mgr
    from backend.agents.retriever import retrieve_parent_documents
    
    weaviate_mgr = get_weaviate_mgr()
    query_to_use = state["query"]
    if state.get("rewritten_queries") and len(state["rewritten_queries"]) > 0:
        query_to_use = state["rewritten_queries"][0]
        
    chunks = retrieve_parent_documents(
        weaviate_mgr=weaviate_mgr,
        tenant_id=state["active_team_id"],
        query=query_to_use,
        current_user_id=state["user_id"]
    )
    return {"retrieved_chunks": chunks}

def graph_retrieve_node(state: AgentState) -> Dict[str, Any]:
    # Mock retrieval: in future tasks, this will query Neo4j for entities and relations
    return {"retrieved_triples": [["MockSubject", "MockPredicate", "MockObject"]]}

def hybrid_retrieve_node(state: AgentState) -> Dict[str, Any]:
    import os
    if os.environ.get("MOCK_LLM") == "true":
        return {
            "retrieved_chunks": [{"text": "mock hybrid chunk", "score": 0.8}],
            "retrieved_triples": [["MockSubject", "MockPredicate", "MockObject"]]
        }
    
    from backend.db.weaviate import get_weaviate_mgr
    from backend.agents.retriever import retrieve_parent_documents
    
    weaviate_mgr = get_weaviate_mgr()
    query_to_use = state["query"]
    if state.get("rewritten_queries") and len(state["rewritten_queries"]) > 0:
        query_to_use = state["rewritten_queries"][0]
        
    chunks = retrieve_parent_documents(
        weaviate_mgr=weaviate_mgr,
        tenant_id=state["active_team_id"],
        query=query_to_use,
        current_user_id=state["user_id"]
    )
    return {
        "retrieved_chunks": chunks,
        "retrieved_triples": [["MockSubject", "MockPredicate", "MockObject"]]
    }

def crag_check_node(state: AgentState) -> Dict[str, Any]:
    from backend.agents.crag import evaluate_retrieval
    return evaluate_retrieval(state)

def web_search_node(state: AgentState) -> Dict[str, Any]:
    from backend.agents.web_search import web_search_fallback
    return web_search_fallback(state)

def synthesize_node(state: AgentState) -> Dict[str, Any]:
    history_context = ""
    if state.get("history"):
        history_context = "\n".join(
            f"{m['role']}: {m['content']}" for m in state["history"]
        )
    return {
        "raw_response": f"Mock response for query: {state['query']}\n\n{history_context}",
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
    """Lazily compile and cache the LangGraph workflow."""
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
