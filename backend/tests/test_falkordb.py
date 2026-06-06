# backend/tests/test_falkordb.py
"""Integration tests for FalkorDB wrapper with team_id enforcement."""

import pytest

from db.falkordb import (
    get_graph,
    create_entity,
    create_relationship,
    query_entities,
    query_related_entities,
    delete_team_data,
    Entity,
    Relationship,
    FalkorDBManager,
)


@pytest.fixture(autouse=True)
def cleanup_graph():
    """Clean up after each test."""
    yield
    FalkorDBManager.reset()


class TestCreateEntity:
    def test_create_entity(self):
        entity = Entity(
            id="e1",
            name="Paris",
            type="City",
            team_id="team1",
            source_doc_id="doc1",
            importance_score=0.8,
        )
        create_entity(entity)
        results = query_entities("team1", "Paris")
        assert len(results) >= 1
        assert results[0]["name"] == "Paris"
        assert results[0]["team_id"] == "team1"

    def test_create_entity_without_team_id_raises(self):
        entity = Entity(
            id="e2",
            name="London",
            type="City",
            team_id="",  # Empty team_id
            source_doc_id="doc1",
            importance_score=0.5,
        )
        with pytest.raises(ValueError, match="team_id"):
            create_entity(entity)


class TestCreateRelationship:
    def test_create_relationship(self):
        entity_a = Entity(
            id="r_e1", name="France", type="Country",
            team_id="team2", source_doc_id="doc2", importance_score=0.9,
        )
        entity_b = Entity(
            id="r_e2", name="Paris", type="City",
            team_id="team2", source_doc_id="doc2", importance_score=0.8,
        )
        create_entity(entity_a)
        create_entity(entity_b)

        rel = Relationship(
            source_id="r_e1",
            target_id="r_e2",
            type="CAPITAL_OF",
            team_id="team2",
            weight=1.0,
            source="ingestion",
        )
        create_relationship(rel)

        related = query_related_entities("team2", "r_e1")
        assert len(related) >= 1

    def test_relationship_without_team_id_raises(self):
        rel = Relationship(
            source_id="x1",
            target_id="x2",
            type="KNOWS",
            team_id="",
            weight=0.5,
            source="ingestion",
        )
        with pytest.raises(ValueError, match="team_id"):
            create_relationship(rel)


class TestTeamIsolation:
    def test_query_only_returns_own_team(self):
        entity_a = Entity(
            id="iso_1", name="Classified Alpha", type="Secret",
            team_id="alpha_team", source_doc_id="doc_a", importance_score=0.5,
        )
        entity_b = Entity(
            id="iso_2", name="Classified Beta", type="Secret",
            team_id="beta_team", source_doc_id="doc_b", importance_score=0.5,
        )
        create_entity(entity_a)
        create_entity(entity_b)

        results_a = query_entities("alpha_team", "Classified")
        results_b = query_entities("beta_team", "Classified")

        assert all(r["team_id"] == "alpha_team" for r in results_a)
        assert all(r["team_id"] == "beta_team" for r in results_b)


class TestDeleteTeamData:
    def test_delete_removes_team_entities(self):
        entity = Entity(
            id="del_e1", name="Temporary", type="Temp",
            team_id="doomed_team", source_doc_id="doc_doom", importance_score=0.3,
        )
        create_entity(entity)

        # Verify it exists
        results = query_entities("doomed_team", "Temporary")
        assert len(results) >= 1

        # Delete team data
        delete_team_data("doomed_team")

        # Verify it's gone
        results = query_entities("doomed_team", "Temporary")
        assert len(results) == 0
