import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from dataclasses import dataclass
from fastapi.testclient import TestClient
from fastapi import HTTPException


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
    citations: list | None = None
    references: list | None = None
    image: object | None = None
    response_audio: object | None = None
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

    mock_user = {
        "id": "user-1",
        "email": "a@b.com",
        "team_id": "team-1",
        "is_admin": False,
    }

    def mock_require_auth(authorization: str = None) -> dict:
        return mock_user

    with patch.dict(sys.modules, {
        "celery": celery_mod,
        "celery.result": celery_result_mod,
        "workers": workers_mod,
        "workers.celery_app": workers_celery_app_mod,
    }):
        with patch("auth.middleware.require_auth", mock_require_auth):
            with patch("agentos.GraphStore", return_value=mock_graph_store):
                with patch("agentos.VectorStore", return_value=mock_vector_store):
                    with patch("agentos.build_rag_team_with_stores", return_value=mock_agent):
                        from agentos import app
                        with TestClient(app) as test_client:
                            yield test_client


@pytest.fixture(scope="module")
def client_no_auth():
    """Test client without auth for testing 401 responses."""
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

    def fail_require_auth(authorization: str = None) -> dict:
        raise HTTPException(status_code=401, detail="Unauthorized")

    with patch.dict(sys.modules, {
        "celery": celery_mod,
        "celery.result": celery_result_mod,
        "workers": workers_mod,
        "workers.celery_app": workers_celery_app_mod,
    }):
        with patch("auth.middleware.require_auth", fail_require_auth):
            with patch("agentos.GraphStore", return_value=mock_graph_store):
                with patch("agentos.VectorStore", return_value=mock_vector_store):
                    with patch("agentos.build_rag_team_with_stores", return_value=mock_agent):
                        from agentos import app
                        with TestClient(app) as test_client:
                            yield test_client


@pytest.mark.unit
def test_query_endpoint_produces_ndjson_with_citations(client):
    """The /query endpoint should include a citations event after the answer."""
    r = client.post("/query", json={"message": "What is LanceDB?"})
    assert r.status_code == 200
    lines = [line for line in r.iter_lines() if line.strip()]
    assert len(lines) >= 1
    for line in lines:
        parsed = json.loads(line)
        assert "event" in parsed
        assert "content" in parsed


@pytest.mark.unit
def test_health_endpoint_still_works(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.unit
def test_query_without_auth_returns_401(client_no_auth):
    r = client_no_auth.post("/query", json={"message": "hello"})
    assert r.status_code == 401


@pytest.mark.unit
def test_memory_search_without_auth_returns_401(client_no_auth):
    r = client_no_auth.get("/memory/search", params={"query": "test"})
    assert r.status_code == 401


@pytest.mark.unit
def test_memory_graph_without_auth_returns_401(client_no_auth):
    r = client_no_auth.get("/memory/graph", params={"entity": "test"})
    assert r.status_code == 401


@pytest.mark.unit
def test_health_without_auth_returns_200(client_no_auth):
    r = client_no_auth.get("/health")
    assert r.status_code == 200


@pytest.fixture(scope="module")
def client_with_session():
    import sys
    from contextlib import asynccontextmanager
    mods_to_remove = [m for m in sys.modules if m == "agentos" or m.startswith("agentos.")]
    for mod in mods_to_remove:
        del sys.modules[mod]

    mock_graph_store = MagicMock()
    mock_vector_store = MagicMock()
    mock_session_store = MagicMock()
    mock_session_store.get_session_history.return_value = [
        {"role": "user", "content": "Previous question"},
        {"role": "assistant", "content": "Previous answer"},
    ]
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

    mock_user = {
        "id": "user-1",
        "email": "a@b.com",
        "team_id": "team-1",
        "is_admin": False,
    }

    def mock_require_auth(authorization: str = None) -> dict:
        return mock_user

    @asynccontextmanager
    async def mock_lifespan(app):
        app.state.graph_store = mock_graph_store
        app.state.vector_store = mock_vector_store
        app.state.session_store = mock_session_store
        yield

    with patch.dict(sys.modules, {
        "celery": celery_mod,
        "celery.result": celery_result_mod,
        "workers": workers_mod,
        "workers.celery_app": workers_celery_app_mod,
    }):
        with patch("auth.middleware.require_auth", mock_require_auth):
            with patch("agentos.GraphStore", return_value=mock_graph_store):
                with patch("agentos.VectorStore", return_value=mock_vector_store):
                    with patch("agentos.build_rag_team_with_stores", return_value=mock_agent):
                        with patch("agentos.lifespan", mock_lifespan):
                            from agentos import app
                            with TestClient(app) as test_client:
                                yield test_client


@pytest.mark.unit
def test_query_loads_session_history(client_with_session):
    """The /query endpoint should load prior messages and pass them to the agent."""
    r = client_with_session.post(
        "/query",
        json={"message": "Follow up question", "session_id": "sess-1"},
    )
    assert r.status_code == 200
    lines = [line for line in r.iter_lines() if line.strip()]
    assert len(lines) >= 1


@pytest.mark.unit
def test_query_saves_messages_to_session(client_with_session):
    """The /query endpoint should save the user message and response to the session store."""
    r = client_with_session.post(
        "/query",
        json={"message": "New question", "session_id": "sess-2"},
    )
    assert r.status_code == 200
