import pytest
from db.vector_store import VectorStore

@pytest.fixture
def store(tmp_path):
    """Provides an isolated LanceDB vector store for unit tests."""
    return VectorStore(path=str(tmp_path / "lancedb"))

@pytest.mark.unit
def test_table_is_created_on_init(store):
    assert store.table is not None
    assert store.table.name == "memory_chunks"

@pytest.mark.unit
def test_insert_and_retrieve_by_id(store):
    record = {
        "id": "abc123",
        "text": "Enterprise LanceDB integration active.",
        "embedding": [0.1] * 768,
        "source": "arch.pdf",
        "chunk_index": 0,
        "custom_relational_tag": "Node A"
    }
    store.insert([record])
    results = store.search_by_id("abc123")
    
    assert len(results) == 1
    assert results[0]["text"] == "Enterprise LanceDB integration active."
    assert "metadata" in results[0]
    assert results[0]["metadata"].get("custom_relational_tag") == "Node A"

@pytest.mark.unit
def test_ann_search_on_empty_table_returns_empty(store):
    results = store.search(query_vector=[0.0] * 768, top_k=5)
    assert results == []

@pytest.mark.unit
def test_auto_id_generation_and_metadata_bundling(store):
    record = {
        "text": "Implicit ID generation text.",
        "embedding": [0.5] * 768,
        "source": "auto.docx",
        "chunk_index": 5,
        "author": "Alice"
    }
    store.insert([record])
    results = store.search(query_vector=[0.5] * 768, top_k=1)
    
    assert len(results) == 1
    assert "id" in results[0]
    assert len(results[0]["id"]) > 5 # ID was generated
    assert results[0]["metadata"].get("author") == "Alice"

@pytest.mark.unit
def test_schema_rejects_missing_embedding(store):
    # Pyarrow/LanceDB should reject an insert missing the strictly-typed embedding
    bad_record = {"id": "bad", "text": "Missing embedding vector"}
    with pytest.raises(Exception):
        store.insert([bad_record])
