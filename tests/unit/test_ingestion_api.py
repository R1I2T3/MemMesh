import io
import sys
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from contextlib import asynccontextmanager


def _make_mock_module(name, **attrs):
    """Create a mock module and register it in sys.modules."""
    mod = MagicMock()
    for key, val in attrs.items():
        setattr(mod, key, val)
    return mod


def _make_require_auth_bypass():
    """Return a require_auth replacement that returns a fake authenticated user."""
    from fastapi import Header
    def bypass(authorization: str = Header(None)) -> dict:
        return {"id": "test-user", "team_id": "test-team", "is_admin": True}
    return bypass


def _make_require_auth_fail():
    """Return a require_auth replacement that always raises 401."""
    from fastapi import Header, HTTPException
    def fail(authorization: str = Header(None)) -> dict:
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    return fail


@asynccontextmanager
async def noop_lifespan(app):
    yield


@pytest.fixture
def client():
    for mod_name in list(sys.modules.keys()):
        if mod_name == "agentos" or mod_name.startswith("agentos."):
            del sys.modules[mod_name]

    mock_graph_store = MagicMock()
    mock_vector_store = MagicMock()
    mock_send_task_result = MagicMock()
    mock_send_task_result.id = "test-task-123"
    mock_celery_app = MagicMock()
    mock_celery_app.send_task.return_value = mock_send_task_result

    mock_async_result = MagicMock()

    mock_db_graph_store = _make_mock_module("db.graph_store", GraphStore=MagicMock(return_value=mock_graph_store))
    mock_db_vector_store = _make_mock_module("db.vector_store", VectorStore=MagicMock(return_value=mock_vector_store))
    mock_db_session_store = _make_mock_module("db.session_store", SessionStore=MagicMock(return_value=MagicMock()))
    mock_db_deps = _make_mock_module(
        "db.dependencies",
        get_graph_store=MagicMock(return_value=mock_graph_store),
        get_vector_store=MagicMock(return_value=mock_vector_store),
        build_rag_team_with_stores=MagicMock(return_value=MagicMock()),
        set_graph_store_ctx=MagicMock(),
        set_vector_store_ctx=MagicMock(),
        set_citations_ctx=MagicMock(),
        get_citations_ctx=MagicMock(return_value=[]),
    )

    mock_db_auth_store = _make_mock_module("db.auth_store", AuthStore=MagicMock())

    with patch.dict(sys.modules, {
        "celery": MagicMock(),
        "celery.result": _make_mock_module("celery.result", AsyncResult=mock_async_result),
        "workers": _make_mock_module("workers"),
        "workers.celery_app": _make_mock_module("workers.celery_app", celery_app=mock_celery_app),
        "db": _make_mock_module("db"),
        "db.graph_store": mock_db_graph_store,
        "db.vector_store": mock_db_vector_store,
        "db.session_store": mock_db_session_store,
        "db.dependencies": mock_db_deps,
        "db.auth_store": mock_db_auth_store,
    }):
        import agentos
        agentos.celery_app = mock_celery_app
        agentos.AsyncResult = mock_async_result
        agentos.app.router.lifespan_context = noop_lifespan
        from agentos import app

        app.dependency_overrides[agentos.require_auth] = _make_require_auth_bypass()

        with TestClient(app) as test_client:
            yield test_client, mock_celery_app, mock_async_result


@pytest.fixture
def client_no_auth_ingest():
    for mod_name in list(sys.modules.keys()):
        if mod_name == "agentos" or mod_name.startswith("agentos."):
            del sys.modules[mod_name]

    mock_graph_store = MagicMock()
    mock_vector_store = MagicMock()
    mock_send_task_result = MagicMock()
    mock_send_task_result.id = "test-task-123"
    mock_celery_app = MagicMock()
    mock_celery_app.send_task.return_value = mock_send_task_result

    mock_async_result = MagicMock()

    mock_db_graph_store = _make_mock_module("db.graph_store", GraphStore=MagicMock(return_value=mock_graph_store))
    mock_db_vector_store = _make_mock_module("db.vector_store", VectorStore=MagicMock(return_value=mock_vector_store))
    mock_db_session_store = _make_mock_module("db.session_store", SessionStore=MagicMock(return_value=MagicMock()))
    mock_db_deps = _make_mock_module(
        "db.dependencies",
        get_graph_store=MagicMock(return_value=mock_graph_store),
        get_vector_store=MagicMock(return_value=mock_vector_store),
        build_rag_team_with_stores=MagicMock(return_value=MagicMock()),
        set_graph_store_ctx=MagicMock(),
        set_vector_store_ctx=MagicMock(),
        set_citations_ctx=MagicMock(),
        get_citations_ctx=MagicMock(return_value=[]),
    )

    mock_db_auth_store = _make_mock_module("db.auth_store", AuthStore=MagicMock())

    with patch.dict(sys.modules, {
        "celery": MagicMock(),
        "celery.result": _make_mock_module("celery.result", AsyncResult=mock_async_result),
        "workers": _make_mock_module("workers"),
        "workers.celery_app": _make_mock_module("workers.celery_app", celery_app=mock_celery_app),
        "db": _make_mock_module("db"),
        "db.graph_store": mock_db_graph_store,
        "db.vector_store": mock_db_vector_store,
        "db.session_store": mock_db_session_store,
        "db.dependencies": mock_db_deps,
        "db.auth_store": mock_db_auth_store,
    }):
        import agentos
        agentos.celery_app = mock_celery_app
        agentos.AsyncResult = mock_async_result
        agentos.app.router.lifespan_context = noop_lifespan
        from agentos import app

        app.dependency_overrides[agentos.require_auth] = _make_require_auth_fail()

        with TestClient(app) as test_client:
            yield test_client


@pytest.mark.unit
def test_ingest_valid_file_returns_task_id(client):
    test_client, mock_celery_app, _ = client
    file_content = b"%PDF-1.4 fake pdf content"
    r = test_client.post(
        "/ingest",
        files={"file": ("test.pdf", file_content, "application/pdf")},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["task_id"] == "test-task-123"
    assert data["status"] == "pending"


@pytest.mark.unit
def test_ingest_unsupported_file_type_returns_400(client):
    test_client, _, _ = client
    file_content = b"some content"
    r = test_client.post(
        "/ingest",
        files={"file": ("test.xyz", file_content, "application/octet-stream")},
    )
    assert r.status_code == 400
    assert "Unsupported file type" in r.json()["detail"]


@pytest.mark.unit
def test_ingest_empty_file_returns_400(client):
    test_client, _, _ = client
    r = test_client.post(
        "/ingest",
        files={"file": ("test.txt", b"", "text/plain")},
    )
    assert r.status_code == 400
    assert "Empty file" in r.json()["detail"]


@pytest.mark.unit
def test_ingest_no_file_returns_422(client):
    test_client, _, _ = client
    r = test_client.post("/ingest")
    assert r.status_code == 422


@pytest.mark.unit
def test_ingest_calls_celery_with_correct_args(client):
    test_client, mock_celery_app, _ = client
    file_content = b"markdown content here"
    r = test_client.post(
        "/ingest",
        files={"file": ("notes.md", file_content, "text/markdown")},
        params={"multimodal": "true"},
    )
    assert r.status_code == 200
    mock_celery_app.send_task.assert_called_once()
    call_args = mock_celery_app.send_task.call_args
    assert call_args[0][0] == "workers.tasks.process_document_ingestion"
    assert call_args[1]["args"][1] is True


@pytest.mark.unit
def test_ingest_celery_unavailable_returns_503(client):
    test_client, mock_celery_app, _ = client
    mock_celery_app.send_task.side_effect = Exception("broker down")
    file_content = b"some content"
    r = test_client.post(
        "/ingest",
        files={"file": ("test.txt", file_content, "text/plain")},
    )
    assert r.status_code == 503
    assert "Celery broker unavailable" in r.json()["detail"]


@pytest.mark.unit
def test_ingest_status_completed(client):
    test_client, _, mock_async_result = client
    mock_result = MagicMock()
    mock_result.state = "SUCCESS"
    mock_result.result = {"chunks_count": 5, "triples_count": 3, "source": "test.pdf"}
    mock_async_result.return_value = mock_result

    r = test_client.get("/ingest/test-task-123")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "completed"
    assert data["result"]["chunks_count"] == 5
    assert data["result"]["triples_count"] == 3


@pytest.mark.unit
def test_ingest_status_failed(client):
    test_client, _, mock_async_result = client
    mock_result = MagicMock()
    mock_result.state = "FAILURE"
    mock_result.result = Exception("embedding failed")
    mock_async_result.return_value = mock_result

    r = test_client.get("/ingest/failed-task-456")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "failed"
    assert "error" in data


@pytest.mark.unit
def test_ingest_status_pending(client):
    test_client, _, mock_async_result = client
    mock_result = MagicMock()
    mock_result.state = "PENDING"
    mock_result.result = None
    mock_async_result.return_value = mock_result

    r = test_client.get("/ingest/pending-task-789")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "pending"
    assert "result" not in data


@pytest.mark.unit
def test_ingest_status_running(client):
    test_client, _, mock_async_result = client
    mock_result = MagicMock()
    mock_result.state = "STARTED"
    mock_result.result = None
    mock_async_result.return_value = mock_result

    r = test_client.get("/ingest/running-task-000")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "running"


@pytest.mark.unit
def test_ingest_without_auth_returns_401(client_no_auth_ingest):
    r = client_no_auth_ingest.post("/ingest", files={"file": ("test.txt", b"content")})
    assert r.status_code == 401


@pytest.mark.unit
def test_ingest_status_without_auth_returns_401(client_no_auth_ingest):
    r = client_no_auth_ingest.get("/ingest/some-task-id")
    assert r.status_code == 401


@pytest.mark.unit
def test_ingest_accepts_all_supported_extensions(client):
    test_client, mock_celery_app, _ = client
    supported = [
        ("test.pdf", b"pdf", "application/pdf"),
        ("test.docx", b"docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("test.pptx", b"pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        ("test.xml", b"<root/>", "application/xml"),
        ("test.eml", b"email content", "message/rfc822"),
        ("test.txt", b"text", "text/plain"),
        ("test.md", b"markdown", "text/markdown"),
        ("test.csv", b"a,b\n1,2", "text/csv"),
        ("test.xlsx", b"xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("test.json", b"{}", "application/json"),
    ]
    for filename, content, content_type in supported:
        mock_celery_app.send_task.reset_mock()
        mock_celery_app.send_task.return_value = MagicMock(id="task")
        r = test_client.post(
            "/ingest",
            files={"file": (filename, content, content_type)},
        )
        assert r.status_code == 200, f"Failed for {filename}"
