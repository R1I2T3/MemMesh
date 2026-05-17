import os
import logging
from db.graph_store import GraphStore
from db.dependencies import get_graph_store_ctx

logger = logging.getLogger(__name__)

_store: GraphStore | None = None


def init_graph_store() -> GraphStore:
    """Initialize the shared GraphStore singleton (legacy, kept for backward compat)."""
    global _store
    if _store is None:
        _store = GraphStore(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password"),
        )
    return _store


def get_graph_store() -> GraphStore:
    """Get the GraphStore: prefers context var, falls back to singleton."""
    ctx_store = get_graph_store_ctx()
    if ctx_store is not None:
        return ctx_store
    if _store is None:
        raise RuntimeError(
            "GraphStore not initialized. Call init_graph_store() first or set the context variable."
        )
    return _store


def close_graph_store():
    """Close the shared GraphStore singleton."""
    global _store
    if _store is not None:
        _store.close()
        _store = None


def graph_search(entity: str, depth: int = 2) -> str:
    """Searches the graph database for relationships connected to an entity."""
    try:
        store = get_graph_store()
        results = store.fetch_subgraph(entity, depth=depth)

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
