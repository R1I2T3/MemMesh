import pytest
from unittest.mock import MagicMock, patch

@pytest.fixture
def mock_driver():
    with patch("db.graph_store.GraphDatabase") as MockDB:
        mock_drv = MagicMock()
        MockDB.driver.return_value = mock_drv
        yield MockDB, mock_drv

@pytest.mark.unit
def test_run_query_calls_session_with_correct_cypher(mock_driver):
    MockDB, mock_drv = mock_driver
    mock_session = mock_drv.session.return_value.__enter__.return_value
    mock_result = MagicMock()
    # Mocking standard Neo4j Record structure
    first_record = MagicMock()
    first_record.data.return_value = {"s": "result"}
    mock_result.__iter__.return_value = [first_record]
    mock_session.run.return_value = mock_result
    
    from db.graph_store import GraphStore
    store = GraphStore(uri="bolt://localhost:7687", user="neo4j", password="pwd")
    res = store.run_query("MATCH (n) RETURN n", {})
    
    mock_session.run.assert_called_once_with("MATCH (n) RETURN n", {})
    assert res == [{"s": "result"}]

@pytest.mark.unit
def test_connection_failure_raises_connection_error():
    with patch("db.graph_store.GraphDatabase") as MockDB:
        MockDB.driver.side_effect = Exception("Connection refused")
        from db.graph_store import GraphStore
        with pytest.raises(ConnectionError, match="Neo4j connection failed"):
            GraphStore(uri="bolt://bad-host:7687", user="neo", password="pwd")

@pytest.mark.unit
def test_upsert_triples_validates_batching(mock_driver):
    MockDB, mock_drv = mock_driver
    mock_session = mock_drv.session.return_value.__enter__.return_value
    
    from db.graph_store import GraphStore
    store = GraphStore(uri="bolt://localhost:7687", user="neo4j", password="pwd")
    triples = [
        {"subject": "LanceDB", "relationship": "USED_BY", "object": "Graph-RAG"}
    ]
    # Pass a vector context ID to test the hybridization leap
    store.upsert_triples(triples, context_id="vec-1234")
    
    call_args = mock_session.run.call_args
    assert "UNWIND $triples AS t" in call_args[0][0]
    assert call_args[0][1]["context_id"] == "vec-1234"
    assert len(call_args[0][1]["triples"]) == 1

@pytest.mark.unit
def test_fetch_subgraph_formats_correctly(mock_driver):
    MockDB, mock_drv = mock_driver
    mock_session = mock_drv.session.return_value.__enter__.return_value
    from db.graph_store import GraphStore
    store = GraphStore(uri="bolt://localhost:7687", user="neo4j", password="pwd")
    
    store.fetch_subgraph("Agent", depth=3)
    call_args = mock_session.run.call_args
    assert "MATCH (n:Entity {name: $name})-[r:RELATES_TO*1..$depth]-(m:Entity)" in call_args[0][0]
    assert call_args[0][1]["name"] == "Agent"
    assert call_args[0][1]["depth"] == 3
