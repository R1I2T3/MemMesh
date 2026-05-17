import os
from contextvars import ContextVar
from typing import Generator

from fastapi import Depends, Request

from db.graph_store import GraphStore
from db.vector_store import VectorStore
from utils.embedder import get_embedder_client
from agents.router.query_rewriter import QueryRewriter
from utils.embedder import embed_chunks

# Context variables for per-request store access (works with agno tools)
_graph_store_ctx: ContextVar[GraphStore | None] = ContextVar("graph_store", default=None)
_vector_store_ctx: ContextVar[VectorStore | None] = ContextVar("vector_store", default=None)


def get_graph_store_ctx() -> GraphStore | None:
    return _graph_store_ctx.get()


def get_vector_store_ctx() -> VectorStore | None:
    return _vector_store_ctx.get()


def set_graph_store_ctx(store: GraphStore):
    _graph_store_ctx.set(store)


def set_vector_store_ctx(store: VectorStore):
    _vector_store_ctx.set(store)


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


def vector_search_with_rewriting(query: str, vector_store, top_k: int = 5) -> list | str:
    """
    Enhanced vector search with query rewriting for improved recall.
    Rewrites the query into step-back + alternatives, searches all variants,
    deduplicates by id, and returns the combined list of results.
    Returns an error string on failure.
    """
    import logging
    logger = logging.getLogger(__name__)
    try:
        rewriter = QueryRewriter()
        rewrite_result = rewriter.rewrite(query)

        all_queries = [query, rewrite_result.step_back_query] + rewrite_result.alternative_queries

        seen_ids = set()
        combined_results = []
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
                    combined_results.append(r)

        if not any_embedded:
            return "Vector search failed: Could not generate embedding."

        return combined_results
    except Exception as e:
        logger.error(f"Vector search with rewriting failed: {e}")
        return f"Vector search failed: {str(e)}"


def build_rag_team_with_stores(graph_store: GraphStore, vector_store: VectorStore):
    """
    Builds a RAG team agent with tools bound to the provided store instances.
    Uses closures so tools have access to the correct stores without globals.
    """
    from agno.agent import Agent
    from agno.models.google import Gemini

    def vector_search_tool(query: str, top_k: int = 5) -> str:
        """Searches the vector database for semantically similar chunks."""
        import logging
        logger = logging.getLogger(__name__)
        try:
            from utils.embedder import embed_chunks_with_client

            embedded = embed_chunks_with_client([{"text": query}])
            if not embedded or "embedding" not in embedded[0]:
                return "Vector search failed: Could not generate embedding."

            results = vector_store.search(query_vector=embedded[0]["embedding"], top_k=top_k)
            if not results:
                return f"Vector search: no results found for '{query}'."

            lines = []
            for r in results:
                source = r.get("source", "unknown")
                text = r.get("text", "")
                lines.append(f"[{source}] {text}")

            return "Vector context:\n" + "\n---\n".join(lines)
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return f"Vector search error: {str(e)}"

    def graph_search_tool(entity: str, depth: int = 2) -> str:
        """Searches the graph database for relationships connected to an entity."""
        import logging
        logger = logging.getLogger(__name__)
        try:
            results = graph_store.fetch_subgraph(entity, depth=depth)

            if not results:
                return f"Graph search: no relationships found for '{entity}'."

            lines = []
            for row in results:
                src = row.get("source", "")
                tgt = row.get("target", "")
                path = row.get("relationship_path", [])

                if path:
                    rel_str = "-[" + ", ".join(path) + "]->"
                else:
                    rel_str = "-->"

                lines.append(f"{src} {rel_str} {tgt} ({row.get('target_type', 'UNKNOWN')})")

            return "Graph context:\n" + "\n".join(lines)
        except Exception as e:
            logger.error(f"Graph search failed: {e}")
            return f"Graph search error: {str(e)}"

    agent = Agent(
        name="Graph-RAG Master",
        model=Gemini(id="gemini-3.0-flash"),
        description="""You are a senior intelligent backend researcher.
        You have access to a Hybrid Memory Engine composed of a Vector Database and a Graph Database.
        When asked a question:
        1. Use vector_search to find unstructured textual context.
        2. Use graph_search to traverse exact entity relationships.
        3. Synthesize a pristine, grounded answer strictly based on the extracted memory.""",
        tools=[vector_search_tool, graph_search_tool],
    )
    return agent
