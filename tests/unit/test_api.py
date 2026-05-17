import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from dataclasses import dataclass
from fastapi.testclient import TestClient
import tools.graph_tool as graph_tool_module

@dataclass
class MockStreamEvent:
    event: str = "run_content"
    content: str = "mocked grounded answer"
    content_type: str = "str"
    created_at: int = 1234567890
    agent_id: str = "test-agent"
    agent_name: str = "Graph-RAG Master"
    run_id: str | None = None
    parent_run_id: str | None = None
    session_id: str | None = None
    workflow_id: str | None = None
    workflow_run_id: str | None = None
    step_id: str | None = None
    step_name: str | None = None
    step_index: int | None = None
    nested_depth: int = 0
    tools: list | None = None
    reasoning_content: str | None = None
    model_provider_data: dict | None = None
    citations: object | None = None
    response_audio: object | None = None
    image: object | None = None
    references: list | None = None
    additional_input: list | None = None
    reasoning_steps: list | None = None
    reasoning_messages: list | None = None
    workflow_agent: bool = False

async def mock_arun_stream(*args, **kwargs):
    yield MockStreamEvent()

@pytest.fixture
def client():
    with patch("agents.rag_team.build_rag_team") as mock_build:
        mock_agent = MagicMock()
        mock_agent.arun = mock_arun_stream
        mock_build.return_value = mock_agent

        mock_graph_store = MagicMock()
        with patch.object(graph_tool_module, "_store", mock_graph_store):
            from agentos import app
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
def test_query_streams_ndjson_lines(client):
    r = client.post("/query", json={"message": "What is LanceDB?"})
    assert r.status_code == 200
    lines = [line for line in r.iter_lines() if line.strip()]
    assert len(lines) >= 1
    import json
    for line in lines:
        parsed = json.loads(line)
        assert "event" in parsed
        assert "content" in parsed

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
