from unittest.mock import MagicMock, patch
from backend.db.neo4j import Neo4jManager

def test_neo4j_manager_lifecycle():
    with patch("backend.db.neo4j.GraphDatabase.driver") as mock_driver:
        manager = Neo4jManager()
        assert manager.driver is not None
        manager.close()
        mock_driver.return_value.close.assert_called_once()

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
