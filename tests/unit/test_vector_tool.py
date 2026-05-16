import pytest
from unittest.mock import patch, MagicMock

@pytest.mark.unit
@patch("tools.vector_tool.VectorStore")
@patch("tools.vector_tool.embed_chunks")
def test_vector_tool_returns_formatted_string(mock_embed, MockStore):
    mock_embed.return_value = [{"text": "query", "embedding": [0.1] * 768}]
    mock_store_inst = MagicMock()
    mock_store_inst.search.return_value = [
        {"text": "LanceDB represents vector embeddings natively.", "source": "docs.pdf"}
    ]
    MockStore.return_value = mock_store_inst
    
    from tools.vector_tool import vector_search
    result = vector_search("What is LanceDB?")
    
    assert "Vector context" in result
    assert "[docs.pdf]" in result
    assert "LanceDB represents vector embeddings" in result

@pytest.mark.unit
@patch("tools.vector_tool.VectorStore")
@patch("tools.vector_tool.embed_chunks")
def test_vector_tool_empty_store_returns_message(mock_embed, MockStore):
    mock_embed.return_value = [{"text": "query", "embedding": [0.0] * 768}]
    mock_store_inst = MagicMock()
    mock_store_inst.search.return_value = []
    MockStore.return_value = mock_store_inst
    
    from tools.vector_tool import vector_search
    result = vector_search("unknown query")
    assert "no results" in result.lower()
