import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, MagicMock

from backend.main import app
from backend.auth.jwt import create_access_token
from backend.db.mysql import get_db, Base
from backend.models import Message
from sqlalchemy.pool import StaticPool

# Setup in-memory SQLite database for query tests
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(autouse=True)
def setup_db_and_dependencies():
    # Recreate tables cleanly for every test
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)

client = TestClient(app)

def get_auth_headers(user_id="test-user", role="user"):
    token = create_access_token({"sub": user_id, "role": role})
    return {"Authorization": f"Bearer {token}"}

def test_query_auth_required():
    res = client.get("/api/query?q=hello")
    assert res.status_code == 401

def test_query_input_validation():
    headers = get_auth_headers()
    # Query too short (less than 3 chars)
    res = client.get("/api/query?q=hi", headers=headers)
    assert res.status_code == 422
    
    # Query too long (greater than 2000 chars)
    long_q = "a" * 2001
    res = client.get(f"/api/query?q={long_q}", headers=headers)
    assert res.status_code == 422

@patch("backend.api.routes.query.RedisMemory")
@patch("backend.api.routes.query.get_graph")
def test_linear_query_flow(mock_get_graph, mock_redis_memory_cls):
    # Setup LangGraph mock
    mock_graph = MagicMock()
    mock_get_graph.return_value = mock_graph
    mock_graph.invoke.return_value = {"raw_response": "LangGraph mock response"}

    # Setup Redis memory mock
    mock_redis = MagicMock()
    mock_redis_memory_cls.return_value = mock_redis
    mock_redis.get_history.return_value = [{"role": "user", "content": "hi"}]

    headers = get_auth_headers()
    res = client.get("/api/query?q=what is this&session_id=session-123", headers=headers)
    assert res.status_code == 200
    
    data = res.json()
    assert data["response"] == "LangGraph mock response"
    assert data["session_id"] == "session-123"
    assert "message_id" in data
    assert "user_message_id" in data
    assert data["parent_message_id"] == data["user_message_id"]

    # Verify Redis save was called since parent_msg_id is None
    mock_redis.save_message.assert_any_call("session-123", "user", "what is this")
    mock_redis.save_message.assert_any_call("session-123", "assistant", "LangGraph mock response")

@patch("backend.api.routes.query.RedisMemory")
@patch("backend.api.routes.query.get_graph")
def test_branching_query_flow(mock_get_graph, mock_redis_memory_cls):
    # Setup database with existing parent message
    db = TestingSessionLocal()
    parent_msg = Message(
        message_id="parent-msg-123",
        session_id="session-123",
        parent_message_id=None,
        role="assistant",
        content="This is parent content"
    )
    db.add(parent_msg)
    db.commit()

    mock_graph = MagicMock()
    mock_get_graph.return_value = mock_graph
    mock_graph.invoke.return_value = {"raw_response": "Branched answer"}

    mock_redis = MagicMock()
    mock_redis_memory_cls.return_value = mock_redis

    headers = get_auth_headers()
    res = client.get(
        "/api/query?q=branched question&session_id=session-123&parent_msg_id=parent-msg-123",
        headers=headers
    )
    assert res.status_code == 200
    
    data = res.json()
    assert data["response"] == "Branched answer"
    assert "message_id" in data
    assert "user_message_id" in data

    # Verify Redis save was NOT called since parent_msg_id is provided
    mock_redis.save_message.assert_not_called()

    # Verify context history sent to graph was correct (traversed up to root)
    # The history should contain [{"role": "assistant", "content": "This is parent content"}]
    called_state = mock_graph.invoke.call_args[0][0]
    assert called_state["history"] == [{"role": "assistant", "content": "This is parent content"}]

def test_get_chat_messages():
    db = TestingSessionLocal()
    m1 = Message(message_id="m1", session_id="sess-abc", parent_message_id=None, role="user", content="msg 1")
    m2 = Message(message_id="m2", session_id="sess-abc", parent_message_id="m1", role="assistant", content="msg 2")
    m3 = Message(message_id="m3", session_id="sess-other", parent_message_id=None, role="user", content="other msg")
    db.add_all([m1, m2, m3])
    db.commit()

    headers = get_auth_headers()
    res = client.get("/api/chat/messages?session_id=sess-abc", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["messages"]) == 2
    assert data["messages"][0]["message_id"] == "m1"
    assert data["messages"][1]["message_id"] == "m2"

def test_get_chat_sessions():
    db = TestingSessionLocal()
    m1 = Message(message_id="m1", session_id="sess-abc", parent_message_id=None, role="user", content="msg 1")
    m2 = Message(message_id="m2", session_id="sess-xyz", parent_message_id=None, role="user", content="msg 2")
    db.add_all([m1, m2])
    db.commit()

    headers = get_auth_headers()
    res = client.get("/api/chat/sessions", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "sess-abc" in data["sessions"]
    assert "sess-xyz" in data["sessions"]
