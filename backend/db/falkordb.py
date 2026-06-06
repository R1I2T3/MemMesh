# backend/db/falkordb.py
"""FalkorDB wrapper with mandatory team_id enforcement.

All nodes carry a mandatory `team_id` property.
All queries enforce WHERE team_id filter (defense-in-depth: raises error if missing).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from redislite.falkordb_client import FalkorDB, Graph

from config import settings


@dataclass
class Entity:
    """Represents a knowledge graph entity."""

    id: str
    name: str
    type: str
    team_id: str
    source_doc_id: str
    importance_score: float = 0.5


@dataclass
class Relationship:
    """Represents a relationship between two entities."""

    source_id: str
    target_id: str
    type: str
    team_id: str
    weight: float = 1.0
    source: str = "ingestion"


class FalkorDBManager:
    """Singleton FalkorDB connection manager."""

    _db: FalkorDB | None = None
    _graph: Graph | None = None
    _lock = threading.RLock()

    @classmethod
    def get_db(cls) -> FalkorDB:
        """Get or create the FalkorDB instance. Thread-safe."""
        with cls._lock:
            if cls._db is None:
                falkor_path = Path(settings.falkordb_dir)
                falkor_path.mkdir(parents=True, exist_ok=True)
                db_file = falkor_path / "falkordb.db"
                cls._db = FalkorDB(str(db_file), protocol=2)
            return cls._db

    @classmethod
    def get_graph(cls, name: str = "memmesh") -> Graph:
        """Get or create the named graph. Thread-safe."""
        with cls._lock:
            if cls._graph is None:
                db = cls.get_db()
                cls._graph = db.select_graph(name)
            return cls._graph

    @classmethod
    def reset(cls) -> None:
        """Reset connections (for testing). Thread-safe."""
        with cls._lock:
            if cls._graph is not None:
                try:
                    cls._graph.delete()
                except Exception:
                    pass
            cls._graph = None
            cls._db = None


def _validate_team_id(team_id: str) -> None:
    """Defense-in-depth: raise error if team_id is missing or empty."""
    if not team_id or not team_id.strip():
        raise ValueError(
            "team_id is required for all FalkorDB operations. "
            "This is a security violation — never query without team_id."
        )


def get_graph(name: str = "memmesh") -> Graph:
    """Get the named graph instance."""
    return FalkorDBManager.get_graph(name)


def create_entity(entity: Entity) -> None:
    """Create or update an Entity node in the graph.

    Args:
        entity: Entity dataclass with mandatory team_id.

    Raises:
        ValueError: If team_id is empty.
    """
    _validate_team_id(entity.team_id)

    graph = get_graph()
    now = datetime.now(timezone.utc).isoformat()

    query = """
    MERGE (e:Entity {id: $id, team_id: $team_id})
    SET e.name = $name,
        e.type = $type,
        e.source_doc_id = $source_doc_id,
        e.importance_score = $importance_score,
        e.created_at = $created_at
    """
    graph.query(
        query,
        params={
            "id": entity.id,
            "name": entity.name,
            "type": entity.type,
            "team_id": entity.team_id,
            "source_doc_id": entity.source_doc_id,
            "importance_score": entity.importance_score,
            "created_at": now,
        },
    )


def create_relationship(rel: Relationship) -> None:
    """Create a RELATES_TO relationship between two entities.

    Args:
        rel: Relationship dataclass with mandatory team_id.

    Raises:
        ValueError: If team_id is empty.
    """
    _validate_team_id(rel.team_id)

    graph = get_graph()
    now = datetime.now(timezone.utc).isoformat()

    query = """
    MATCH (a:Entity {id: $source_id, team_id: $team_id})
    MATCH (b:Entity {id: $target_id, team_id: $team_id})
    MERGE (a)-[r:RELATES_TO]->(b)
    SET r.type = $rel_type,
        r.team_id = $team_id,
        r.weight = $weight,
        r.source = $source,
        r.created_at = $created_at
    """
    graph.query(
        query,
        params={
            "source_id": rel.source_id,
            "target_id": rel.target_id,
            "rel_type": rel.type,
            "team_id": rel.team_id,
            "weight": rel.weight,
            "source": rel.source,
            "created_at": now,
        },
    )


def query_entities(
    team_id: str,
    name_query: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Query entities by name within a team.

    Args:
        team_id: Mandatory team filter.
        name_query: Substring to match against entity names.
        limit: Maximum results.

    Returns:
        List of entity dicts.

    Raises:
        ValueError: If team_id is empty.
    """
    _validate_team_id(team_id)

    graph = get_graph()
    query = """
    MATCH (e:Entity)
    WHERE e.team_id = $team_id AND e.name CONTAINS $name_query
    RETURN e.id AS id, e.name AS name, e.type AS type,
           e.team_id AS team_id, e.source_doc_id AS source_doc_id,
           e.importance_score AS importance_score
    LIMIT $limit
    """
    result = graph.query(
        query,
        params={
            "team_id": team_id,
            "name_query": name_query,
            "limit": limit,
        },
    )

    entities = []
    if result and result.result_set:
        for record in result.result_set:
            entities.append(
                {
                    "id": record[0],
                    "name": record[1],
                    "type": record[2],
                    "team_id": record[3],
                    "source_doc_id": record[4],
                    "importance_score": record[5],
                }
            )

    return entities


def query_related_entities(
    team_id: str,
    entity_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Query entities related to a given entity, scoped to a team.

    Args:
        team_id: Mandatory team filter.
        entity_id: The entity to find relationships for.
        limit: Maximum results.

    Returns:
        List of dicts with related entity info and relationship type.

    Raises:
        ValueError: If team_id is empty.
    """
    _validate_team_id(team_id)

    graph = get_graph()
    query = """
    MATCH (a:Entity {id: $entity_id, team_id: $team_id})
          -[r:RELATES_TO]->
          (b:Entity {team_id: $team_id})
    RETURN b.id AS id, b.name AS name, b.type AS type,
           b.team_id AS team_id, r.type AS rel_type, r.weight AS weight
    LIMIT $limit
    """
    result = graph.query(
        query,
        params={
            "entity_id": entity_id,
            "team_id": team_id,
            "limit": limit,
        },
    )

    related = []
    if result and result.result_set:
        for record in result.result_set:
            related.append(
                {
                    "id": record[0],
                    "name": record[1],
                    "type": record[2],
                    "team_id": record[3],
                    "rel_type": record[4],
                    "weight": record[5],
                }
            )

    return related


def delete_team_data(team_id: str) -> None:
    """Delete all nodes and relationships for a team.

    Called when a team is deleted.

    Args:
        team_id: The team whose data to purge.

    Raises:
        ValueError: If team_id is empty.
    """
    _validate_team_id(team_id)

    graph = get_graph()

    # Delete relationships first, then nodes
    graph.query(
        """
        MATCH (e:Entity {team_id: $team_id})-[r]-()
        DELETE r
        """,
        params={"team_id": team_id},
    )

    graph.query(
        """
        MATCH (e:Entity {team_id: $team_id})
        DELETE e
        """,
        params={"team_id": team_id},
    )
