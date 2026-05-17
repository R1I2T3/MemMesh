import pytest
from unittest.mock import patch, MagicMock
import tools.vector_tool as vector_tool_module

@pytest.mark.unit
@patch("tools.vector_tool.embed_chunks")
def test_vector_tool_returns_formatted_string(mock_embed):
    mock_embed.return_value = [{"text": "query", "embedding": [0.1] * 768}]
    mock_store = MagicMock()
    mock_store.search.return_value = [
        {"text": "LanceDB represents vector embeddings natively.", "source": "docs.pdf"}
    ]

    with patch.object(vector_tool_module, "_store", mock_store):
        from tools.vector_tool import vector_search
        result = vector_search("What is LanceDB?")

        assert "Vector context" in result
        assert "[docs.pdf]" in result
        assert "LanceDB represents vector embeddings" in result

@pytest.mark.unit
@patch("tools.vector_tool.embed_chunks")
def test_vector_tool_empty_store_returns_message(mock_embed):
    mock_embed.return_value = [{"text": "query", "embedding": [0.0] * 768}]
    mock_store = MagicMock()
    mock_store.search.return_value = []

    with patch.object(vector_tool_module, "_store", mock_store):
        from tools.vector_tool import vector_search
        result = vector_search("unknown query")
        assert "no results" in result.lower()

@pytest.mark.unit
def test_vector_tool_not_initialized_raises():
    with patch.object(vector_tool_module, "_store", None):
        from tools.vector_tool import get_vector_store
        with pytest.raises(RuntimeError, match="not initialized"):
            get_vector_store()
