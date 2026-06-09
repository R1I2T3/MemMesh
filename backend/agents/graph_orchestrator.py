import asyncio
from typing import TypedDict, List, Dict, Any, AsyncGenerator
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

def _retrieve_all(state: AgentState) -> Dict[str, Any]:
    import re
    from backend.db.weaviate import get_weaviate_mgr
    from backend.db.neo4j import Neo4jManager
    from backend.agents.retriever import retrieve_parent_documents

    query = state["query"]
    if state.get("rewritten_queries") and len(state["rewritten_queries"]) > 0:
        query = state["rewritten_queries"][0]

    chunks = retrieve_parent_documents(
        weaviate_mgr=get_weaviate_mgr(),
        tenant_id=state["active_team_id"],
        query=query,
        current_user_id=state["user_id"]
    )

    STOP_WORDS = {"what", "is", "your", "who", "the", "a", "an", "of", "and", "in", "to", "for", "with", "on", "at", "by", "from", "how", "why", "are", "you", "i", "me", "my", "we", "us", "our"}
    words = re.findall(r"\b\w+\b", query.lower())
    keywords = [w for w in words if w not in STOP_WORDS and len(w) > 2]

    triples = []
    if keywords:
        try:
            triples = Neo4jManager.get_instance().query_relationships(
                team_id=state["active_team_id"],
                keywords=keywords
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.exception("Graph retrieval from Neo4j failed.")

    return {"retrieved_chunks": chunks, "retrieved_triples": triples}

def vector_retrieve_node(state: AgentState) -> Dict[str, Any]:
    import os
    if os.environ.get("MOCK_LLM") == "true":
        return {"retrieved_chunks": [{"text": "mock vector chunk", "score": 0.9}]}
    return _retrieve_all(state)

def graph_retrieve_node(state: AgentState) -> Dict[str, Any]:
    import os
    if os.environ.get("MOCK_LLM") == "true":
        return {"retrieved_triples": [["MockSubject", "MockPredicate", "MockObject"]]}
    return _retrieve_all(state)

def hybrid_retrieve_node(state: AgentState) -> Dict[str, Any]:
    import os
    if os.environ.get("MOCK_LLM") == "true":
        return {
            "retrieved_chunks": [{"text": "mock hybrid chunk", "score": 0.8}],
            "retrieved_triples": [["MockSubject", "MockPredicate", "MockObject"]]
        }
    return _retrieve_all(state)

def crag_check_node(state: AgentState) -> Dict[str, Any]:
    from backend.agents.crag import evaluate_retrieval
    return evaluate_retrieval(state)

def web_search_node(state: AgentState) -> Dict[str, Any]:
    from backend.agents.web_search import web_search_fallback
    return web_search_fallback(state)

async def synthesize_node(state: AgentState) -> Dict[str, Any]:
    import os
    history_context = ""
    if state.get("history"):
        history_context = "\n".join(
            f"{m['role']}: {m['content']}" for m in state["history"]
        )

    if os.environ.get("MOCK_LLM") == "true":
        query_lower = state['query'].lower()
        if "trigger unsafe response" in query_lower:
            response = "This response is offensive and toxic."
        elif "trigger output pii" in query_lower:
            response = "The email address is secret.agent@gmail.com."
        else:
            response = f"Mock response for query: {state['query']}\n\n{history_context}".strip()

        return {
            "raw_response": response,
            "citations": [{"source": "mock_source"}]
        }

    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.prompts import ChatPromptTemplate
    
    # 1. Prepare retrieved context — all items numbered continuously
    citations = []
    ctx_parts = []

    if state.get("retrieved_chunks"):
        for chunk in state["retrieved_chunks"]:
            n = len(ctx_parts) + 1
            ctx_parts.append(f"[{n}] {chunk.get('text', chunk.get('content', ''))}")
            citations.append({
                "id": n,
                "parent_id": chunk.get("parent_id", ""),
                "page_number": chunk.get("page_number", 1),
                "bbox": chunk.get("bbox", [])
            })

    if state.get("web_search_results"):
        for web_res in state["web_search_results"]:
            n = len(ctx_parts) + 1
            ctx_parts.append(f"[{n}] {web_res.get('text', '')}")
            citations.append({
                "source": "web",
                "text": web_res.get("text", ""),
                "url": web_res.get("url", "")
            })

    if state.get("retrieved_triples"):
        for triple in state["retrieved_triples"]:
            n = len(ctx_parts) + 1
            ctx_parts.append(f"[{n}] {triple[0]} --({triple[1]})--> {triple[2]}")
            citations.append({
                "id": n,
                "source": "knowledge_graph",
                "text": f"{triple[0]} --({triple[1]})--> {triple[2]}"
            })

    context_docs = "\n".join(ctx_parts)
        
    # Build complete prompt template
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", (
            "You are a helpful enterprise assistant. Answer the user query using the provided context "
            "and conversation history.\n\n"
            "Context:\n{context_docs}\n\n"
            "Conversation History:\n{history}\n\n"
            "You MUST cite your sources using the number in brackets, e.g. [1], [2], etc. "
            "after each relevant sentence or claim. Every factual claim should be supported by a citation."
        )),
        ("user", "{query}")
    ])
    
    try:
        from backend.config import settings
        llm = ChatGoogleGenerativeAI(model=settings.GEMINI_MODEL, temperature=0.3, google_api_key=settings.GEMINI_API_KEY)
        chain = prompt_template | llm
        
        response_content = ""
        async for chunk in chain.astream({
            "context_docs": context_docs or "No context retrieved.",
            "history": history_context or "No history.",
            "query": state["query"]
        }):
            raw = chunk.content
            if isinstance(raw, list):
                response_content += "".join(
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in raw
                )
            else:
                response_content += str(raw) if raw is not None else ""
            
        return {
            "raw_response": response_content,
            "citations": citations
        }
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.exception("Synthesis LLM call failed.")
        return {
            "raw_response": f"Error during response synthesis: {e}",
            "citations": citations
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


async def ainvoke_with_events(state: AgentState) -> AsyncGenerator[str, None]:
    from backend.agents.telemetry import (
        TelemetryEvent, TextChunkEvent, CitationEvent,
        SessionEvent, DoneEvent, ErrorEvent
    )
    graph = get_graph()
    streamed_any_tokens = False

    try:
        async for event in graph.astream_events(state, version="v2"):
            kind = event.get("event")
            name = event.get("name")
            
            if kind == "on_chain_start" and name == "LangGraph":
                yield TelemetryEvent("input_guard", "checking query safety").to_sse()
                
            elif kind in ("on_chain_start", "on_node_start"):
                if name == "rewrite":
                    yield TelemetryEvent("rewriter", "generating query variants").to_sse()
                elif name in ("vector_retrieve", "graph_retrieve", "hybrid_retrieve"):
                    route_name = name.split("_")[0]
                    yield TelemetryEvent("router", f"routed to {route_name}").to_sse()
                elif name == "crag_check":
                    yield TelemetryEvent("crag_eval", "evaluating relevance").to_sse()
                elif name == "web_search":
                    yield TelemetryEvent("crag_eval", "relevance below threshold - triggering web search").to_sse()
                elif name == "synthesize":
                    yield TelemetryEvent("synthesis", "generating response").to_sse()
                    
            elif kind == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                node = event.get("metadata", {}).get("langgraph_node", "")
                if chunk and node == "synthesize":
                    raw = chunk.content if hasattr(chunk, "content") else (chunk.get("content") if isinstance(chunk, dict) else None)
                    if raw is None:
                        continue
                    if isinstance(raw, list):
                        content = "".join(
                            block.get("text", "") if isinstance(block, dict) else str(block)
                            for block in raw
                        )
                    else:
                        content = str(raw)
                    if content:
                        streamed_any_tokens = True
                        yield TextChunkEvent(content).to_sse()
                        
            elif kind == "on_chain_end" and (name == "LangGraph" or not event.get("parent_ids")):
                final_state = event["data"].get("output")
                if final_state:
                    raw_response = final_state.get("raw_response", "")
                    citations = final_state.get("citations", [])
                    session_id = final_state.get("session_id", state.get("session_id", "default-session"))
                    
                    if not streamed_any_tokens:
                        for chunk in _chunk_text(raw_response):
                            yield TextChunkEvent(chunk).to_sse()
                            await asyncio.sleep(0)
                            
                    for citation in citations:
                        yield CitationEvent(
                            source=citation.get("source", "vector"),
                            doc_name=citation.get("doc_name", ""),
                            page=citation.get("page_number", 0),
                            url=citation.get("url", ""),
                            triple=citation.get("triple", None)
                        ).to_sse()
                        
                    yield SessionEvent(session_id).to_sse()
                    yield DoneEvent().to_sse()
    except Exception as e:
        yield ErrorEvent(str(e)).to_sse()

def _chunk_text(text: str, size: int = 5) -> List[str]:
    words = text.split()
    for i in range(0, len(words), size):
        yield " ".join(words[i:i+size]) + " "

