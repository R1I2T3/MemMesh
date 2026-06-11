from unittest.mock import MagicMock, patch
from backend.db.neo4j import Neo4jManager

def test_neo4j_manager_lifecycle():
    with patch("backend.db.neo4j.GraphDatabase.driver") as mock_driver:
        manager = Neo4jManager()
        assert manager.driver is not None
        manager.close()
        mock_driver.return_value.close.assert_called_once()

def test_get_entities_for_explore_with_query():
    Neo4jManager._multidb_supported = None
    with patch("backend.db.neo4j.GraphDatabase.driver") as mock_driver:
        mock_session = MagicMock()
        mock_session.__enter__.return_value = mock_session
        mock_driver.return_value.session.return_value = mock_session

        mock_record = {"id": "e1", "name": "Entity 1", "type": "Concept", "score": 1.0}
        mock_result = MagicMock()
        mock_result.__iter__.return_value = [mock_record]
        mock_session.run.return_value = mock_result

        manager = Neo4jManager()
        results = manager.get_entities_for_explore("team-1", "entity", 10)

        assert len(results) == 1
        assert results[0]["id"] == "e1"
        assert results[0]["name"] == "Entity 1"
        mock_session.run.assert_called_once()
        call_kwargs = mock_session.run.call_args[1]
        assert call_kwargs["q"] == "entity"
        assert call_kwargs["limit"] == 10


def test_get_entities_for_explore_without_query():
    Neo4jManager._multidb_supported = None
    with patch("backend.db.neo4j.GraphDatabase.driver") as mock_driver:
        mock_session = MagicMock()
        mock_session.__enter__.return_value = mock_session
        mock_driver.return_value.session.return_value = mock_session

        mock_record = {"id": "e2", "name": "Entity 2", "type": "Person", "score": 2.5}
        mock_result = MagicMock()
        mock_result.__iter__.return_value = [mock_record]
        mock_session.run.return_value = mock_result

        manager = Neo4jManager()
        results = manager.get_entities_for_explore("team-1", "", 50)

        assert len(results) == 1
        assert results[0]["score"] == 2.5


def test_get_relationships_for_explore_with_query():
    Neo4jManager._multidb_supported = None
    with patch("backend.db.neo4j.GraphDatabase.driver") as mock_driver:
        mock_session = MagicMock()
        mock_session.__enter__.return_value = mock_session
        mock_driver.return_value.session.return_value = mock_session

        mock_record = {"source": "e1", "type": "WORKS_AT", "target": "e2"}
        mock_result = MagicMock()
        mock_result.__iter__.return_value = [mock_record]
        mock_session.run.return_value = mock_result

        manager = Neo4jManager()
        results = manager.get_relationships_for_explore("team-1", "entity", 10)

        assert len(results) == 1
        assert results[0]["source"] == "e1"
        assert results[0]["type"] == "WORKS_AT"
        assert results[0]["target"] == "e2"


def test_get_relationships_for_explore_without_query():
    Neo4jManager._multidb_supported = None
    with patch("backend.db.neo4j.GraphDatabase.driver") as mock_driver:
        mock_session = MagicMock()
        mock_session.__enter__.return_value = mock_session
        mock_driver.return_value.session.return_value = mock_session

        mock_record = {"source": "e3", "type": "RELATES_TO", "target": "e4"}
        mock_result = MagicMock()
        mock_result.__iter__.return_value = [mock_record]
        mock_session.run.return_value = mock_result

        manager = Neo4jManager()
        results = manager.get_relationships_for_explore("team-1", "", 50)

        assert len(results) == 1


def test_neo4j_write_and_get_entities():
    Neo4jManager._multidb_supported = None
    with patch("backend.db.neo4j.GraphDatabase.driver") as mock_driver:
        mock_session = MagicMock()
        mock_session.__enter__.return_value = mock_session
        mock_driver.return_value.session.return_value = mock_session
        
        # Setup mock get_entities return
        mock_record = {
            "id": "e1",
            "name": "Entity 1",
            "type": "Concept",
            "importance_score": 1.0,
            "source_doc_id": "doc123"
        }
        # In python driver, session.run returns an object that yields records
        mock_result = MagicMock()
        mock_result.__iter__.return_value = [mock_record]
        mock_session.run.return_value = mock_result

        manager = Neo4jManager()
        manager.write_entity("team-1", "e1", "Entity 1", "Concept", "doc123")
        manager.write_relationship("team-1", "e1", "e2", "ASSOCIATED_WITH")
        entities = manager.get_entities("team-1")

        assert len(entities) == 1
        assert entities[0]["id"] == "e1"
        
        manager.clear_graph("team-1")
        # Verify run calls
        assert mock_session.run.call_count >= 4
