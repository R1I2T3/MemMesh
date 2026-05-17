import datetime
import logging
from agents.extractor_agent import ExtractorAgent

logger = logging.getLogger(__name__)

class MemoryManager:
    """
    Handles the lifecycle of memories in the GraphRAG system.
    """
    def __init__(self, graph_store, vector_store):
        self.graph = graph_store
        self.vector = vector_store

    def merge_duplicate_entities(self, similarity_threshold=0.85):
        """
        Entity Resolution / Graph Deduplication:
        Finds nodes with similar labels/names and merges their relationships.
        Uses APOC's mergeNodes to combine duplicates and preserve all relationships.
        """
        logger.info("Starting Entity Resolution/Deduplication job...")
        merge_query = """
        MATCH (a:Entity), (b:Entity)
        WHERE a.name <> b.name AND (
            toLower(a.name) CONTAINS toLower(b.name)
            OR toLower(b.name) CONTAINS toLower(a.name)
        )
        WITH a, b LIMIT 100
        CALL apoc.refactor.mergeNodes([a, b], {properties: "discard", mergeRels: true}) YIELD node
        RETURN node
        """
        self.graph.run_query(merge_query)
        logger.info("Entity resolution completed.")

    def apply_memory_decay(self, decay_days=30):
        """
        Memory Decay / Forgetting Mechanism:
        Reduces the weight of old memories or deletes them if their TTL has expired
        and they haven't been accessed recently.
        """
        logger.info(f"Applying memory decay for memories older than {decay_days} days...")
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=decay_days)
        cutoff_iso = cutoff_date.isoformat()

        # 1. Decay Vector Store (LanceDB) — delete low-importance stale records
        self.vector.table.delete(
            f"last_accessed < '{cutoff_iso}' AND importance_score < 0.3"
        )

        # 2. Decay Graph Store (Neo4j) — detach delete stale low-importance memories
        decay_query = """
        MATCH (m:Memory)
        WHERE m.last_accessed < $cutoff_date AND m.importance_score < 0.3
        DETACH DELETE m
        """
        self.graph.run_query(decay_query, {"cutoff_date": cutoff_iso})
        logger.info("Memory decay applied.")

    def consolidate_session_memories(self, session_id):
        """
        Memory Consolidation & Summarization:
        Takes a raw session chat log, extracts core long-term facts,
        updates stores, and deletes the verbose raw logs.
        """
        logger.info(f"Consolidating memory for session {session_id}...")

        # 1. Fetch raw logs for session from vector store
        raw_logs = self.vector.table.search().where(
            f"session_id = '{session_id}' AND role = 'raw'"
        ).to_list()

        if not raw_logs:
            logger.info(f"No raw logs found for session {session_id}.")
            return

        # 2. Concatenate raw text for summarization
        session_text = "\n".join(record.get("text", "") for record in raw_logs)

        # 3. Use extractor agent to summarize into key semantic facts
        extractor = ExtractorAgent()
        triples = extractor.extract(session_text)

        # 4. Insert extracted facts into Graph store
        if triples:
            self.graph.upsert_triples(triples, context_id=session_id)

        # 5. Mark raw logs as consolidated (update metadata)
        raw_ids = [record.get("id") for record in raw_logs if record.get("id")]
        if raw_ids:
            id_list = ", ".join(f"'{rid}'" for rid in raw_ids)
            self.vector.table.delete(f"id IN ({id_list})")

        logger.info(f"Session {session_id} consolidation completed. Extracted {len(triples)} facts.")
