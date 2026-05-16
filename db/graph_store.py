import logging
from typing import Dict, Any, List, Optional
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)

class GraphStore:
    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j"):
        """
        Initializes the Neo4j Graph Store with a thread-safe connection pool 
        for high-throughput agentic workflows.
        """
        try:
            # Configure driver with connection pooling optimizations
            self.driver = GraphDatabase.driver(
                uri, 
                auth=(user, password),
                max_connection_lifetime=3600,
                max_connection_pool_size=100,
                connection_acquisition_timeout=60.0
            )
            self.database = database
            # Verify connection
            self.driver.verify_connectivity()
            logger.info("Successfully connected to Neo4j Graph Engine.")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise ConnectionError(f"Neo4j connection failed: {e}") from e

    def close(self):
        if self.driver:
            self.driver.close()

    def run_query(self, cypher: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Executes a generic Cypher query securely and maps records to dicts."""
        parameters = parameters or {}
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(cypher, parameters)
                return [record.data() for record in result]
        except Exception as e:
            logger.error(f"Cypher query execution failed: {e}")
            raise

    def upsert_triples(self, triples: List[Dict[str, Any]], context_id: Optional[str] = None):
        """
        Batch ingests triples (subject, relationship, object).
        Links edges to a vector `context_id` (LanceDB tracking) enabling Graph-Vector Hybrid leaps.
        
        Expected triple format:
        {
            "subject": "EntityA",
            "subject_type": "Person", # optional
            "relationship": "KNOWS",
            "object": "EntityB",
            "object_type": "Location", # optional
            "properties": {"confidence": 0.9} # optional
        }
        """
        if not triples:
            return
            
        # IMPORTANT ENTERPRISE DESIGN DECISION:
        # Standard Neo4j does NOT allow parameterizing relationship types (e.g. `-[r:$type]->`).
        # Using string interpolation for relationship types destroys query plan caching and invites injection hooks.
        # Instead, we construct a normalized architecture via a `RELATES_TO` global edge 
        # and store the dynamic ontology label as the `type` property. 
        # This yields extremely high throughput capabilities natively linking context IDs.
        query = """
        UNWIND $triples AS t
        
        // Merge Subject
        MERGE (s:Entity {name: t.subject})
        SET s.type = coalesce(t.subject_type, s.type, 'UNKNOWN'),
            s.last_updated = timestamp()
        
        // Merge Object
        MERGE (o:Entity {name: t.object})
        SET o.type = coalesce(t.object_type, o.type, 'UNKNOWN'),
            o.last_updated = timestamp()
        
        // Merge Normalized Edge
        MERGE (s)-[r:RELATES_TO {type: t.relationship}]->(o)
        SET r += coalesce(t.properties, {}),
            r.context_id = coalesce($context_id, r.context_id),
            r.last_updated = timestamp()
        """
        
        self.run_query(query, {"triples": triples, "context_id": context_id})
        logger.debug(f"Upserted {len(triples)} triples to Neo4j.")

    def fetch_subgraph(self, entity_name: str, depth: int = 2) -> List[Dict[str, Any]]:
        """
        Retrieves the local relational subgraph around an entity, crucial for RAG context bridging.
        """
        query = """
        MATCH (n:Entity {name: $name})-[r:RELATES_TO*1..$depth]-(m:Entity)
        RETURN n.name AS source, 
               [rel IN r | rel.type] AS relationship_path, 
               m.name AS target, 
               m.type AS target_type
        LIMIT 50
        """
        return self.run_query(query, {"name": entity_name, "depth": depth})
