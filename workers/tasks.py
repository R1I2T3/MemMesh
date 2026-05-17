import os
import logging
from workers.celery_app import celery_app
from db.lifecycle.memory_manager import MemoryManager
from db.graph_store import GraphStore
from db.vector_store import VectorStore
from utils.chunker import extract_text_from_file, chunk_text
from utils.embedder import embed_chunks
from agents.extractor_agent import ExtractorAgent

logger = logging.getLogger(__name__)

# Initialize shared stores once when the Celery worker starts
graph_store = GraphStore(
    uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    user=os.getenv("NEO4J_USER", "neo4j"),
    password=os.getenv("NEO4J_PASSWORD", "password"),
)
vector_store = VectorStore(path=os.getenv("LANCEDB_PATH", "./data/lancedb"))
memory_manager = MemoryManager(graph_store, vector_store)


@celery_app.task(bind=True, max_retries=3)
def process_document_ingestion(self, document_path: str, multimodal: bool = False):
    """
    Asynchronous Ingestion Worker for large documents/PDFs/Markdown.
    Full pipeline: extract -> chunk -> embed -> vector insert -> extract triples -> graph insert.
    """
    logger.info(f"Starting async ingestion for {document_path}")

    try:
        # 1. Extract text from file
        text = extract_text_from_file(document_path)
        if not text or not text.strip():
            logger.warning(f"No text extracted from {document_path}")
            os.remove(document_path)
            return {"chunks_count": 0, "triples_count": 0, "source": os.path.basename(document_path)}

        source_name = os.path.basename(document_path)

        # 2. Chunk the text
        chunks = chunk_text(text, source_metadata=source_name)
        if not chunks:
            logger.warning(f"No chunks produced from {document_path}")
            os.remove(document_path)
            return {"chunks_count": 0, "triples_count": 0, "source": source_name}

        # 3. Embed chunks
        embedded_chunks = embed_chunks(chunks)

        # 4. Insert into vector store
        vector_store.insert(embedded_chunks)
        logger.info(f"Inserted {len(embedded_chunks)} chunks into vector store")

        # 5. Extract triples from full text
        full_text = "\n".join(c["text"] for c in chunks)
        extractor = ExtractorAgent()
        triples = extractor.extract(full_text)

        # 6. Insert triples into graph store
        if triples:
            graph_store.upsert_triples(triples, context_id=document_path)
            logger.info(f"Inserted {len(triples)} triples into graph store")

        # 7. Clean up staging file
        os.remove(document_path)

        logger.info(f"Successfully ingested {document_path}")
        return {
            "chunks_count": len(embedded_chunks),
            "triples_count": len(triples),
            "source": source_name,
        }
    except Exception as exc:
        logger.error(f"Ingestion failed: {exc}")
        # Clean up on failure too
        try:
            os.remove(document_path)
        except OSError:
            pass
        self.retry(exc=exc, countdown=60)


@celery_app.task
def trigger_memory_decay():
    """Background Cron Task for Memory Decay"""
    memory_manager.apply_memory_decay(decay_days=30)


@celery_app.task
def trigger_graph_deduplication():
    """Background Cron Task for Graph Deduplication"""
    memory_manager.merge_duplicate_entities(similarity_threshold=0.85)


@celery_app.task
def consolidate_session_task(session_id: str):
    """Background Task triggered post-session to consolidate memories"""
    memory_manager.consolidate_session_memories(session_id)
