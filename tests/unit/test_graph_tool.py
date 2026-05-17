import pytest
from unittest.mock import patch, MagicMock
import tools.graph_tool as graph_tool_module

@pytest.mark.unit
def test_graph_tool_returns_relationships():
    mock_store = MagicMock()
    mock_store.fetch_subgraph.return_value = [
        {"source": "LanceDB", "relationship_path": ["STORES"], "target": "vectors", "target_type": "DATA"}
    ]

    with patch.object(graph_tool_module, "_store", mock_store):
        from tools.graph_tool import graph_search
        result = graph_search("LanceDB")

        assert "LanceDB" in result
        assert "-[STORES]-> vectors" in result

@pytest.mark.unit
def test_graph_tool_unknown_entity_returns_empty_message():
    mock_store = MagicMock()
    mock_store.fetch_subgraph.return_value = []

    with patch.object(graph_tool_module, "_store", mock_store):
        from tools.graph_tool import graph_search
        result = graph_search("UnknownEntity999")
        assert "no relationships" in result.lower()

@pytest.mark.unit
def test_graph_tool_not_initialized_raises():
    with patch.object(graph_tool_module, "_store", None):
        from tools.graph_tool import graph_search, get_graph_store
        with pytest.raises(RuntimeError, match="not initialized"):
            get_graph_store()
