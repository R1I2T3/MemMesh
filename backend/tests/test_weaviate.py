from unittest.mock import patch, MagicMock
from backend.db.weaviate import WeaviateManager
from weaviate.classes.tenants import Tenant

def test_weaviate_manager_init():
    with patch('backend.db.weaviate.weaviate.connect_to_local') as mock_connect:
        mock_connect.return_value = MagicMock()
        manager = WeaviateManager()
        assert manager.client is not None

def test_insert_chunks_batches_correctly():
    with patch('backend.db.weaviate.weaviate.connect_to_local') as mock_connect, \
         patch('backend.db.weaviate.WeaviateManager._get_embedding') as mock_get_embedding:
        
        mock_get_embedding.return_value = [0.1, 0.2, 0.3]
        mock_client = MagicMock()
        mock_connect.return_value = mock_client
        manager = WeaviateManager()
        
        # Setup mocks for collections and batching
        mock_collection = MagicMock()
        mock_client.collections.get.return_value.with_tenant.return_value = mock_collection
        mock_batch = MagicMock()
        mock_collection.batch.dynamic.return_value.__enter__.return_value = mock_batch
        
        chunks = [{"text": f"chunk {i}", "parent_id": "p1", "page_number": 1, "bbox": []} for i in range(5)]
        manager.insert_chunks("team-1", chunks, ["user-1", "public"])
        
        # Assertions
        mock_client.collections.get.assert_called_with("DocumentChunk")
        mock_client.collections.get.return_value.with_tenant.assert_called_with("team-1")
        mock_collection.batch.dynamic.assert_called_once()
        assert mock_batch.add_object.call_count == 5
        
        # Verify first call arguments
        mock_batch.add_object.assert_any_call(
            vector=[0.1, 0.2, 0.3],
            properties={
                "text": "chunk 0",
                "parent_id": "p1",
                "page_number": 1,
                "bbox": [],
                "dl_meta": "",
                "allowed_user_ids": ["user-1", "public"],
                "importance_score": 1.0,
            }
        )

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
        
        called_args = mock_client.collections.get.return_value.tenants.create.call_args[0][0]
        assert len(called_args) == 1
        assert isinstance(called_args[0], Tenant)
        assert called_args[0].name == "team-1"

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
        
        mock_hybrid = mock_client.collections.get.return_value.with_tenant.return_value.query.hybrid
        mock_hybrid.assert_called_once()
        kwargs = mock_hybrid.call_args[1]
        assert kwargs["query"] == "query"
        assert kwargs["alpha"] == 0.5
        assert kwargs["limit"] == 3
        assert kwargs["filters"] is not None
