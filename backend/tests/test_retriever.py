from unittest.mock import MagicMock
from backend.agents.retriever import retrieve_parent_documents

def test_retrieve_parent_documents_success():
    mock_weaviate = MagicMock()
    mock_weaviate.hybrid_search.return_value = [
        {"parent_id": "doc-abc", "text": "chunk of abc", "page_number": 1, "bbox": []},
        {"parent_id": "doc-xyz", "text": "chunk of xyz", "page_number": 2, "bbox": []},
    ]

    results = retrieve_parent_documents(
        weaviate_mgr=mock_weaviate,
        tenant_id="team-1",
        query="test query",
        current_user_id="user-123"
    )

    assert len(results) == 2
    assert results[0]["parent_id"] == "doc-abc"
    assert results[0]["text"] == "chunk of abc"
    assert results[1]["parent_id"] == "doc-xyz"
    assert results[1]["text"] == "chunk of xyz"

    mock_weaviate.hybrid_search.assert_called_once_with("team-1", "test query", "user-123")

def test_retrieve_parent_documents_empty_weaviate():
    mock_weaviate = MagicMock()
    mock_weaviate.hybrid_search.return_value = []

    results = retrieve_parent_documents(
        weaviate_mgr=mock_weaviate,
        tenant_id="team-1",
        query="test query",
        current_user_id="user-123"
    )
    assert results == []
