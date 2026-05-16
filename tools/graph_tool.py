import os
import logging
from db.graph_store import GraphStore

logger = logging.getLogger(__name__)

def graph_search(entity: str, depth: int = 2) -> str:
    """Searches the graph database for relationships connected to an entity."""
    try:
        store = GraphStore(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password")
        )
        
        results = store.fetch_subgraph(entity, depth=depth)
        store.close() # Clean up connection pool after task
        
        if not results:
            return f"Graph search: no relationships found for '{entity}'."
            
        lines = []
        for row in results:
            # Expected schema from GraphStore.fetch_subgraph:
            # {source: "...", relationship_path: ["...", "..."], target: "...", target_type: "..."}
            src = row.get("source", "")
            tgt = row.get("target", "")
            path = row.get("relationship_path", [])
            
            # Format path e.g., --[KNOWS, WORKED_WITH]-->
            if path:
                rel_str = "-[" + ", ".join(path) + "]->"
            else:
                rel_str = "-->"
                
            lines.append(f"{src} {rel_str} {tgt} ({row.get('target_type', 'UNKNOWN')})")
            
        return "Graph context:\n" + "\n".join(lines)
    except Exception as e:
        logger.error(f"Graph search failed: {e}")
        return f"Graph search error: {str(e)}"

