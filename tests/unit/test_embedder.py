import pytest
from unittest.mock import patch, MagicMock

@pytest.mark.unit
def test_returns_one_vector_per_chunk():
    mock_chunks = [{"chunk_index": 0, "text": "chunk one", "source": "test.txt"},
                   {"chunk_index": 1, "text": "chunk two", "source": "test.txt"}]
                   
    with patch("utils.embedder.genai.Client") as MockClient:
        mock_client_instance = MagicMock()
        mock_response = MagicMock()
        # Mock embeddings
        emb1 = MagicMock(); emb1.values = [0.1] * 768
        emb2 = MagicMock(); emb2.values = [0.2] * 768
        mock_response.embeddings = [emb1, emb2]
        
        mock_client_instance.models.embed_content.return_value = mock_response
        MockClient.return_value = mock_client_instance
        
        from utils.embedder import embed_chunks
        result = embed_chunks(mock_chunks)
        
        assert len(result) == 2
        assert "embedding" in result[0]
        assert result[0]["embedding"] == [0.1] * 768

@pytest.mark.unit
def test_each_vector_has_correct_dimension():
    with patch("utils.embedder.genai.Client") as MockClient:
        mock_client_instance = MagicMock()
        mock_response = MagicMock()
        emb1 = MagicMock(); emb1.values = [0.1] * 768
        mock_response.embeddings = [emb1]
        mock_client_instance.models.embed_content.return_value = mock_response
        MockClient.return_value = mock_client_instance
        
        from utils.embedder import embed_chunks
        result = embed_chunks([{"text": "single chunk"}])
        assert len(result[0]["embedding"]) == 768

@pytest.mark.unit
def test_empty_input_returns_empty_list():
    from utils.embedder import embed_chunks
    assert embed_chunks([]) == []

@pytest.mark.unit
def test_api_failure_raises_runtime_error():
    with patch("utils.embedder.genai.Client") as MockClient:
        mock_client_instance = MagicMock()
        mock_client_instance.models.embed_content.side_effect = Exception("API down")
        MockClient.return_value = mock_client_instance
        
        from utils.embedder import embed_chunks
        with pytest.raises(RuntimeError, match="Embedding failed"):
            embed_chunks([{"text": "some text"}])
