from unittest.mock import patch, MagicMock
from backend.db.weaviate import WeaviateManager

def test_weaviate_manager_init():
    with patch('backend.db.weaviate.weaviate.connect_to_local') as mock_connect:
        mock_connect.return_value = MagicMock()
        manager = WeaviateManager()
        assert manager.client is not None

def test_insert_chunks_batches_correctly():
    with patch('backend.db.weaviate.weaviate.connect_to_local') as mock_connect:
        mock_connect.return_value = MagicMock()
        manager = WeaviateManager()
        chunks = [{"text": f"chunk {i}", "parent_id": "p1", "page_number": 1, "bbox": []} for i in range(5)]
        manager.insert_chunks("team-1", chunks, ["user-1", "public"])

def test_ensure_schema():
    with patch('backend.db.weaviate.weaviate.connect_to_local') as mock_connect:
        mock_client = MagicMock()
        mock_connect.return_value = mock_client
        
        # Test case 1: collection exists
        mock_client.collections.exists.return_value = True
        manager = WeaviateManager()
        manager.ensure_schema()
        mock_client.collections.create.assert_not_called()
        
        # Test case 2: collection does not exist
        mock_client.collections.exists.return_value = False
        manager.ensure_schema()
        mock_client.collections.create.assert_called_once()

def test_create_tenant():
    with patch('backend.db.weaviate.weaviate.connect_to_local') as mock_connect:
        mock_client = MagicMock()
        mock_connect.return_value = mock_client
        manager = WeaviateManager()
        manager.create_tenant("team-1")
        mock_client.collections.get.assert_called_with("DocumentChunk")
        mock_client.collections.get.return_value.tenants.create.assert_called_once()

def test_hybrid_search():
    with patch('backend.db.weaviate.weaviate.connect_to_local') as mock_connect:
        mock_client = MagicMock()
        mock_connect.return_value = mock_client
        
        # Setup mock return values for search objects
        mock_obj = MagicMock()
        mock_obj.properties = {
            "text": "some text",
            "parent_id": "parent-123",
            "page_number": 2,
            "bbox": [1.0, 2.0, 3.0, 4.0]
        }
        mock_client.collections.get.return_value.with_tenant.return_value.query.hybrid.return_value.objects = [mock_obj]
        
        manager = WeaviateManager()
        results = manager.hybrid_search("team-1", "query", "user-1", limit=3)
        assert len(results) == 1
        assert results[0]["text"] == "some text"
        assert results[0]["parent_id"] == "parent-123"
        assert results[0]["page_number"] == 2
        assert results[0]["bbox"] == [1.0, 2.0, 3.0, 4.0]
