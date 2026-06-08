import logging
from neo4j import GraphDatabase
from neo4j.exceptions import ClientError, DatabaseError
from backend.config import settings

logger = logging.getLogger(__name__)

class Neo4jManager:
    _multidb_supported: bool | None = None

    def __init__(self):
        self.driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )

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

    def get_entities(self, team_id: str) -> list[dict]:
        query = (
            "MATCH (e:Entity {team_id: $team_id}) "
            "RETURN e.id AS id, e.name AS name, e.type AS type, "
            "e.importance_score AS importance_score, e.source_doc_id AS source_doc_id"
        )
        with self._get_session(team_id) as session:
            result = session.run(query, team_id=team_id)
            return [dict(record) for record in result]

    def clear_graph(self, team_id: str):
        query = "MATCH (e:Entity {team_id: $team_id}) DETACH DELETE e"
        with self._get_session(team_id) as session:
            session.run(query, team_id=team_id)
