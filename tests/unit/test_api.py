import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

@pytest.fixture
def client():
    # We patch build_rag_team and agentos at import level
    with patch("agents.rag_team.build_rag_team") as mock_build:
        mock_agent = MagicMock()
        mock_agent.run.return_value = MagicMock(content="mocked grounded answer")
        mock_build.return_value = mock_agent
        
        # Now import app (this evaluates rag_team = build_rag_team())
        from agentos import app
        # Replace the instantiated rag_team with our mock directly in the module
        with patch("agentos.rag_team", mock_agent):
            yield TestClient(app)

@pytest.mark.unit
def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

@pytest.mark.unit
def test_query_valid_body_returns_200(client):
    r = client.post("/query", json={"message": "What is LanceDB?"})
    assert r.status_code == 200
    text = "".join(r.iter_text())
    assert "mocked grounded answer" in text

@pytest.mark.unit
def test_query_missing_message_returns_422(client):
    r = client.post("/query", json={})
    assert r.status_code == 422

@pytest.mark.unit
def test_memory_search_returns_list(client):
    with patch("agentos.vector_search", return_value="[mock.pdf] context vector"):
        r = client.get("/memory/search", params={"query": "LanceDB"})
        assert r.status_code == 200
        assert "context vector" in r.json()["results"]

@pytest.mark.unit
def test_memory_graph_returns_relationships(client):
    with patch("agentos.graph_search", return_value="Graph context: node -> node"):
        r = client.get("/memory/graph", params={"entity": "LanceDB"})
        assert r.status_code == 200
        assert "Graph context" in r.json()["results"]

@pytest.mark.unit
def test_new_session_returns_unique_id(client):
    r1 = client.post("/session/new")
    r2 = client.post("/session/new")
    assert r1.status_code == 200
    assert r1.json()["session_id"] != r2.json()["session_id"]
