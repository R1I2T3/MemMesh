import os
from contextvars import ContextVar
from typing import Generator

from fastapi import Depends, Request

from db.graph_store import GraphStore
from db.vector_store import VectorStore
from db.citation import CitationResult
from utils.embedder import get_embedder_client
from agents.router.query_rewriter import QueryRewriter
from utils.embedder import embed_chunks

# Context variables for per-request store access (works with agno tools)
_graph_store_ctx: ContextVar[GraphStore | None] = ContextVar("graph_store", default=None)
_vector_store_ctx: ContextVar[VectorStore | None] = ContextVar("vector_store", default=None)
_citations_ctx: ContextVar[list] = ContextVar("citations", default=[])


def get_graph_store_ctx() -> GraphStore | None:
    return _graph_store_ctx.get()


def get_vector_store_ctx() -> VectorStore | None:
    return _vector_store_ctx.get()


def set_graph_store_ctx(store: GraphStore):
    _graph_store_ctx.set(store)


def set_vector_store_ctx(store: VectorStore):
    _vector_store_ctx.set(store)


def set_citations_ctx(citations: list):
    _citations_ctx.set(citations)


def get_citations_ctx() -> list:
    return _citations_ctx.get()


async def get_graph_store(request: Request) -> GraphStore:
    """FastAPI dependency that yields the shared GraphStore from app state."""
    store: GraphStore = request.app.state.graph_store
    return store


async def get_vector_store(request: Request) -> VectorStore:
    """FastAPI dependency that yields the shared VectorStore from app state."""
    store: VectorStore = request.app.state.vector_store
    return store


async def get_embedder():
    """FastAPI dependency that yields a shared Google GenAI embedder client."""
    client = get_embedder_client()
    return client


def vector_search_with_rewriting(query: str, vector_store, top_k: int = 5) -> list:
    """
    Enhanced vector search with query rewriting for improved recall.
    Returns List[CitationResult] with full citation metadata.
    """
    import logging
    logger = logging.getLogger(__name__)
    try:
        rewriter = QueryRewriter()
        rewrite_result = rewriter.rewrite(query)

        all_queries = [query, rewrite_result.step_back_query] + rewrite_result.alternative_queries

        seen_ids = set()
        combined_results: list[CitationResult] = []
        any_embedded = False

        for q in all_queries:
            embedded = embed_chunks([{"text": q}])
            if not embedded or "embedding" not in embedded[0]:
                continue

            any_embedded = True
            results = vector_store.search(query_vector=embedded[0]["embedding"], top_k=top_k)
            for r in results:
                rid = r.get("id")
                if rid and rid not in seen_ids:
                    seen_ids.add(rid)
                    citation = CitationResult.from_vector_result(r)
                    combined_results.append(citation)

        if not any_embedded:
            return []

        return combined_results
    except Exception as e:
        logger.error(f"Vector search with rewriting failed: {e}")
        return []


def build_rag_team_with_stores(graph_store: GraphStore, vector_store: VectorStore):
    """
    Builds a RAG team agent with tools bound to the provided store instances.
    Uses closures so tools have access to the correct stores without globals.
    Includes multi-hop pre-retrieval and citation tracking.
    """
    from agno.agent import Agent
    from agno.models.google import Gemini
    from agents.retrieval.multi_hop import MultiHopRetriever

    def vector_search_tool(query: str, top_k: int = 5) -> str:
        """Searches the vector database with query rewriting for improved recall."""
        citations = vector_search_with_rewriting(query, vector_store, top_k=top_k)
        existing = get_citations_ctx()
        existing.extend(citations)
        if not citations:
            return "Vector search: no results found."
        return "\n".join(f"[{c.id}] {c.content}" for c in citations)

    def lookup_entity(entity: str) -> str:
        """Looks up a single entity's direct relationships in the graph (depth=1)."""
        import logging
        logger = logging.getLogger(__name__)
        try:
            results = graph_store.fetch_subgraph(entity, depth=1)
            if not results:
                return f"Graph lookup: no relationships found for '{entity}'."

            citations = [CitationResult.from_graph_result(r, hop=0) for r in results]
            existing = get_citations_ctx()
            existing.extend(citations)

            lines = []
            for row in results:
                src = row.get("source", "")
                tgt = row.get("target", "")
                path = row.get("relationship_path", [])
                rel_str = "-[" + ", ".join(path) + "]->" if path else "-->"
                lines.append(f"{src} {rel_str} {tgt} ({row.get('target_type', 'UNKNOWN')})")

            return "Graph context:\n" + "\n".join(lines)
        except Exception as e:
            logger.error(f"Graph lookup failed: {e}")
            return f"Graph lookup error: {str(e)}"

    # Multi-hop pre-retrieval
    multi_hop_retriever = MultiHopRetriever(
        graph_store=graph_store,
        model=Gemini(id="gemini-3.0-flash"),
        max_hops=5,
    )

    agent = Agent(
        name="Graph-RAG Master",
        model=Gemini(id="gemini-3.0-flash"),
        description="""You are a senior intelligent backend researcher.
        You have access to a Hybrid Memory Engine composed of a Vector Database and a Graph Database.
        When asked a question:
        1. Use vector_search to find unstructured textual context.
        2. Use lookup_entity to explore specific entity relationships in the graph.
        3. Synthesize a pristine, grounded answer strictly based on the extracted memory.""",
        tools=[vector_search_tool, lookup_entity],
    )
    return agent
