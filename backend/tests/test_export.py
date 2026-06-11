import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.main import app
from backend.auth.jwt import create_access_token
from backend.db.mysql import get_db, Base
from backend.models import Message

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
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
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)


def get_user_headers():
    token = create_access_token({"sub": "test-user", "role": "user"})
    return {"Authorization": f"Bearer {token}"}


def seed_message(db, message_id="msg-1", session_id="session-1", user_id="test-user",
                 role="user", content="Hello", citations=None):
    msg = Message(
        message_id=message_id,
        session_id=session_id,
        user_id=user_id,
        role=role,
        content=content,
        citations=citations,
    )
    db.add(msg)
    db.commit()


# --- Renderer Tests ---

def test_render_markdown_returns_string():
    from backend.export.renderers import render_markdown
    messages = [
        {"role": "user", "content": "Hello", "citations": None},
        {"role": "assistant", "content": "Hi there", "citations": [{"source": "doc1"}]},
    ]
    result = render_markdown(messages, "Test Session")
    assert isinstance(result, str)
    assert "# Test Session" in result
    assert "Hello" in result
    assert "Hi there" in result
    assert "User" in result
    assert "Assistant" in result
    assert "Citations: 1" in result
    assert "Exported:" in result


def test_render_json_returns_valid_json():
    from backend.export.renderers import render_json
    messages = [
        {"role": "user", "content": "Hello", "citations": None},
    ]
    result = render_json(messages)
    data = json.loads(result)
    assert "messages" in data
    assert "exported_at" in data
    assert len(data["messages"]) == 1
    assert data["messages"][0]["content"] == "Hello"


def test_render_pdf_raises_if_weasyprint_missing():
    from backend.export.renderers import render_pdf
    with pytest.raises(RuntimeError, match="weasyprint is required"):
        render_pdf([], "Test")


# --- API Endpoint Tests ---

def test_export_md_returns_markdown():
    db = TestingSessionLocal()
    seed_message(db)
    db.close()

    res = client.post(
        "/api/chat/sessions/session-1/export?format=md",
        headers=get_user_headers(),
    )
    assert res.status_code == 200
    assert "text/markdown" in res.headers["content-type"]
    assert "Hello" in res.text


def test_export_json_returns_json():
    db = TestingSessionLocal()
    seed_message(db)
    db.close()

    res = client.post(
        "/api/chat/sessions/session-1/export?format=json",
        headers=get_user_headers(),
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/json"
    data = res.json()
    assert "messages" in data
    assert len(data["messages"]) == 1


def test_export_returns_content_disposition():
    db = TestingSessionLocal()
    seed_message(db)
    db.close()

    res = client.post(
        "/api/chat/sessions/session-1/export?format=md",
        headers=get_user_headers(),
    )
    assert "Content-Disposition" in res.headers
    assert "attachment" in res.headers["content-disposition"]
    assert "session-1.md" in res.headers["content-disposition"]


def test_export_requires_auth():
    res = client.post("/api/chat/sessions/session-1/export?format=md")
    assert res.status_code == 401


def test_export_404_for_missing_session():
    res = client.post(
        "/api/chat/sessions/nonexistent/export?format=md",
        headers=get_user_headers(),
    )
    assert res.status_code == 404


def test_export_filters_by_user():
    db = TestingSessionLocal()
    seed_message(db, user_id="other-user")
    db.close()

    res = client.post(
        "/api/chat/sessions/session-1/export?format=md",
        headers=get_user_headers(),
    )
    assert res.status_code == 404
