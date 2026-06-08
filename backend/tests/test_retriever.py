import pytest
from unittest.mock import MagicMock
from backend.agents.retriever import retrieve_parent_documents
from backend.models import ParentDocument, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def test_retrieve_parent_documents_success():
    # Setup clean SQLite in-memory DB for tests
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    
    # Add dummy parent documents
    with TestingSession() as session:
        session.add(ParentDocument(parent_id="doc-abc", filename="doc1.pdf", content="Content of Doc ABC", team_id="team-1"))
        session.add(ParentDocument(parent_id="doc-xyz", filename="doc2.pdf", content="Content of Doc XYZ", team_id="team-1"))
        session.commit()

    # Mock Weaviate hybrid search
    mock_weaviate = MagicMock()
    mock_weaviate.hybrid_search.return_value = [
        {"parent_id": "doc-abc", "text": "chunk of abc"},
        {"parent_id": "doc-xyz", "text": "chunk of xyz"},
    ]

    # Patch SessionLocal inside retriever module using monkeypatch
    with pytest.MonkeyPatch.context() as mp:
        import backend.agents.retriever
        mp.setattr(backend.agents.retriever, "SessionLocal", TestingSession)

        results = retrieve_parent_documents(
            weaviate_mgr=mock_weaviate,
            tenant_id="team-1",
            query="test query",
            current_user_id="user-123"
        )

        assert len(results) == 2
        assert results[0]["parent_id"] == "doc-abc"
        assert results[0]["text"] == "Content of Doc ABC"
        assert results[0]["content"] == "Content of Doc ABC"
        assert results[1]["parent_id"] == "doc-xyz"
        assert results[1]["text"] == "Content of Doc XYZ"
        assert results[1]["content"] == "Content of Doc XYZ"

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
