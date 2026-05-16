import os
import logging
from db.vector_store import VectorStore
from utils.embedder import embed_chunks

logger = logging.getLogger(__name__)

def vector_search(query: str, top_k: int = 5) -> str:
    """Searches the vector database for semantically similar chunks."""
    try:
        # Initialize VectorStore singleton-esque instance (could be injected for higher scale)
        store = VectorStore(path=os.getenv("LANCEDB_PATH", "./data/lancedb"))
        
        # embed_chunks expects a Dict schema with 'text'
        embedded = embed_chunks([{"text": query}])
        if not embedded or "embedding" not in embedded[0]:
            return "Vector search failed: Could not generate embedding."
            
        results = store.search(query_vector=embedded[0]["embedding"], top_k=top_k)
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
