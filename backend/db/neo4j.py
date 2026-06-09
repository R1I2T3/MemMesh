import logging
from neo4j import GraphDatabase
from neo4j.exceptions import ClientError, DatabaseError
from backend.config import settings

logger = logging.getLogger(__name__)

_neo4j_mgr = None

class Neo4jManager:
    _multidb_supported: bool | None = None

    def __init__(self):
        self.driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
        global _neo4j_mgr
        _neo4j_mgr = self

    @classmethod
    def get_instance(cls) -> "Neo4jManager":
        global _neo4j_mgr
        if _neo4j_mgr is None:
            _neo4j_mgr = cls()
        return _neo4j_mgr

    def close(self):
        self.driver.close()

    def _get_session(self, team_id: str):
        db_name = f"team-{team_id}"
        
        if Neo4jManager._multidb_supported is False:
            return self.driver.session()

        if Neo4jManager._multidb_supported is None:
            test_session = None
            try:
                # Test connection / database capability
                test_session = self.driver.session(database=db_name)
                test_session.run("RETURN 1").consume()
                Neo4jManager._multidb_supported = True
            except (ClientError, DatabaseError) as e:
                logger.warning(
                    "Multi-database not supported, falling back to default db globally. Error: %s",
                    e
                )
                Neo4jManager._multidb_supported = False
            except Exception as e:
                logger.warning(
                    "Transient error testing Neo4j multi-database support: %s", e
                )
                if test_session:
                    try:
                        test_session.close()
                    except Exception:
                        pass
                return self.driver.session()
            finally:
                if test_session:
                    try:
                        test_session.close()
                    except Exception:
                        pass

        if Neo4jManager._multidb_supported is True:
            try:
                return self.driver.session(database=db_name)
            except Exception as e:
                logger.warning("Failed to open session for database '%s', falling back: %s", db_name, e)
                return self.driver.session()

        return self.driver.session()

    def write_entity(self, team_id: str, entity_id: str, name: str, entity_type: str, source_doc_id: str):
        query = (
            "MERGE (e:Entity {id: $id, team_id: $team_id}) "
            "ON CREATE SET e.name = $name, e.type = $type, e.importance_score = 1.0, "
            "e.source_doc_id = $doc_id, e.created_at = datetime()"
        )
        with self._get_session(team_id) as session:
            session.run(
                query,
                id=entity_id,
                team_id=team_id,
                name=name,
                type=entity_type,
                doc_id=source_doc_id
            )

    def write_relationship(self, team_id: str, source_id: str, target_id: str, rel_type: str):
        query = (
            "MATCH (a:Entity {id: $source_id, team_id: $team_id}), "
            "(b:Entity {id: $target_id, team_id: $team_id}) "
            "MERGE (a)-[r:RELATES_TO {type: $type, team_id: $team_id}]->(b) "
            "ON CREATE SET r.weight = 1.0, r.created_at = datetime(), r.source = 'ingestion'"
        )
        with self._get_session(team_id) as session:
            session.run(
                query,
                source_id=source_id,
                target_id=target_id,
                team_id=team_id,
                type=rel_type
            )

    def write_entities_batch(self, team_id: str, entities: list[dict], source_doc_id: str):
        query = (
            "UNWIND $entities AS e "
            "MERGE (n:Entity {id: e.id, team_id: $team_id}) "
            "ON CREATE SET n.name = e.name, n.type = e.type, "
            "n.importance_score = 1.0, n.source_doc_id = $doc_id, "
            "n.created_at = datetime()"
        )
        with self._get_session(team_id) as session:
            session.run(
                query,
                entities=[{"id": e["id"], "name": e["name"], "type": e.get("type", "Concept")}
                          for e in entities if isinstance(e, dict) and e.get("id") and e.get("name")],
                team_id=team_id,
                doc_id=source_doc_id
            )

    def write_relationships_batch(self, team_id: str, relationships: list[dict]):
        query = (
            "UNWIND $relationships AS r "
            "MATCH (a:Entity {id: r.source_id, team_id: $team_id}), "
            "(b:Entity {id: r.target_id, team_id: $team_id}) "
            "MERGE (a)-[rel:RELATES_TO {type: r.type, team_id: $team_id}]->(b) "
            "ON CREATE SET rel.weight = 1.0, rel.created_at = datetime(), rel.source = 'ingestion'"
        )
        with self._get_session(team_id) as session:
            session.run(
                query,
                relationships=[{"source_id": r["source_id"], "target_id": r["target_id"], "type": r.get("type", "RELATES_TO")}
                              for r in relationships if isinstance(r, dict) and r.get("source_id") and r.get("target_id")],
                team_id=team_id
            )

    def get_entities(self, team_id: str) -> list[dict]:
        query = (
            "MATCH (e:Entity {team_id: $team_id}) "
            "RETURN e.id AS id, e.name AS name, e.type AS type, "
            "e.importance_score AS importance_score, e.source_doc_id AS source_doc_id"
        )
        with self._get_session(team_id) as session:
            result = session.run(query, team_id=team_id)
            return [dict(record) for record in result]

    def query_relationships(self, team_id: str, keywords: list[str]) -> list[list[str]]:
        if not keywords:
            return []
        cypher_query = (
            "MATCH (a:Entity {team_id: $team_id})-[r:RELATES_TO]->(b:Entity {team_id: $team_id}) "
            "WHERE any(k in $keywords WHERE toLower(coalesce(a.name, '')) CONTAINS k OR toLower(coalesce(b.name, '')) CONTAINS k "
            "OR toLower(coalesce(a.id, '')) CONTAINS k OR toLower(coalesce(b.id, '')) CONTAINS k) "
            "RETURN a.name AS source, r.type AS type, b.name AS target "
            "LIMIT 20"
        )
        with self._get_session(team_id) as session:
            result = session.run(cypher_query, team_id=team_id, keywords=[k.lower() for k in keywords])
            return [[record["source"], record["type"], record["target"]] for record in result]

    def clear_graph(self, team_id: str):
        query = "MATCH (e:Entity {team_id: $team_id}) DETACH DELETE e"
        with self._get_session(team_id) as session:
            session.run(query, team_id=team_id)
