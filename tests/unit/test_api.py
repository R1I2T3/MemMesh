import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from dataclasses import dataclass
from fastapi.testclient import TestClient


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


@pytest.fixture(scope="module")
def client():
    import sys
    mods_to_remove = [m for m in sys.modules if m == "agentos" or m.startswith("agentos.")]
    for mod in mods_to_remove:
        del sys.modules[mod]

    mock_graph_store = MagicMock()
    mock_vector_store = MagicMock()
    mock_agent = MagicMock()
    mock_agent.arun = mock_arun_stream

    mock_celery_app = MagicMock()
    mock_async_result = MagicMock()

    celery_mod = MagicMock()
    celery_result_mod = MagicMock()
    celery_result_mod.AsyncResult = mock_async_result
    workers_mod = MagicMock()
    workers_celery_app_mod = MagicMock()
    workers_celery_app_mod.celery_app = mock_celery_app

    with patch.dict(sys.modules, {
        "celery": celery_mod,
        "celery.result": celery_result_mod,
        "workers": workers_mod,
        "workers.celery_app": workers_celery_app_mod,
    }):
        with patch("agentos.GraphStore", return_value=mock_graph_store):
            with patch("agentos.VectorStore", return_value=mock_vector_store):
                with patch("agentos.build_rag_team_with_stores", return_value=mock_agent):
                    from agentos import app

                    with TestClient(app) as test_client:
                        yield test_client


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
    with patch("utils.embedder.embed_chunks", return_value=[{"text": "LanceDB", "embedding": [0.1] * 768}]):
        r = client.get("/memory/search", params={"query": "LanceDB"})
        assert r.status_code == 200
        assert "results" in r.json()


@pytest.mark.unit
def test_memory_graph_returns_relationships(client):
    r = client.get("/memory/graph", params={"entity": "LanceDB"})
    assert r.status_code == 200
    assert "results" in r.json()


@pytest.mark.unit
def test_new_session_returns_unique_id(client):
    r1 = client.post("/session/new")
    r2 = client.post("/session/new")
    assert r1.status_code == 200
    assert r1.json()["session_id"] != r2.json()["session_id"]
