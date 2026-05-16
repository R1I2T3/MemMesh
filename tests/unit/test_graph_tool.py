import pytest
from unittest.mock import patch, MagicMock

@pytest.mark.unit
@patch("tools.graph_tool.GraphStore")
def test_graph_tool_returns_relationships(MockStore):
    mock_store_inst = MagicMock()
    mock_store_inst.fetch_subgraph.return_value = [
        {"source": "LanceDB", "relationship_path": ["STORES"], "target": "vectors", "target_type": "DATA"}
    ]
    MockStore.return_value = mock_store_inst
    
    from tools.graph_tool import graph_search
    result = graph_search("LanceDB")
    
    assert "LanceDB" in result
    assert "-[STORES]-> vectors" in result

@pytest.mark.unit
@patch("tools.graph_tool.GraphStore")
def test_graph_tool_unknown_entity_returns_empty_message(MockStore):
    mock_store_inst = MagicMock()
    mock_store_inst.fetch_subgraph.return_value = []
    MockStore.return_value = mock_store_inst
    
    from tools.graph_tool import graph_search
    result = graph_search("UnknownEntity999")
    assert "no relationships" in result.lower()
