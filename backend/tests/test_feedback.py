import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app
from backend.auth.jwt import create_access_token
from backend.db.mysql import get_db, Base
from backend.models import UserFeedback

# Setup in-memory SQLite database for feedback tests
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
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)

client = TestClient(app)

def get_superadmin_headers():
    token = create_access_token({"sub": "test-admin", "role": "superadmin"})
    return {"Authorization": f"Bearer {token}"}

def get_user_headers():
    token = create_access_token({"sub": "test-user", "role": "user"})
    return {"Authorization": f"Bearer {token}"}

def test_submit_feedback_success():
    payload = {
        "query": "What is MemMesh?",
        "response": "MemMesh is a memory retrieval augmented generation system.",
        "rating": 1,
        "trace_id": "trace-123456"
    }
    response = client.post("/api/feedback", json=payload, headers=get_user_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "submitted"
    assert "feedback_id" in data

    # Verify db entry
    db = TestingSessionLocal()
    feedback = db.query(UserFeedback).filter_by(feedback_id=data["feedback_id"]).first()
    assert feedback is not None
    assert feedback.query == payload["query"]
    assert feedback.response == payload["response"]
    assert feedback.rating == 1
    assert feedback.trace_id == "trace-123456"
    db.close()

def test_submit_feedback_invalid_rating():
    payload = {
        "query": "What is MemMesh?",
        "response": "MemMesh is RAG.",
        "rating": 5,  # Invalid
        "trace_id": "trace-123456"
    }
    response = client.post("/api/feedback", json=payload, headers=get_user_headers())
    assert response.status_code == 400
    assert "Rating must be 1 or -1" in response.json()["detail"]

def test_submit_feedback_unauthorized():
    payload = {
        "query": "What is MemMesh?",
        "response": "MemMesh is RAG.",
        "rating": -1,
        "trace_id": "trace-123456"
    }
    response = client.post("/api/feedback", json=payload)  # No auth headers
    assert response.status_code == 401

def test_run_eval_no_feedback():
    response = client.post("/api/eval", headers=get_superadmin_headers())
    assert response.status_code == 200
    assert response.json() == {"status": "skipped", "reason": "No feedback found"}

def test_run_eval_success():
    # Insert some feedback first
    db = TestingSessionLocal()
    feedback1 = UserFeedback(
        feedback_id="fb-1",
        query="What is RAG?",
        response="Retrieval Augmented Generation.",
        rating=1,
        trace_id="t-1"
    )
    feedback2 = UserFeedback(
        feedback_id="fb-2",
        query="Explain Vector DB.",
        response="A database for high-dimensional vectors.",
        rating=-1,
        trace_id="t-2"
    )
    db.add(feedback1)
    db.add(feedback2)
    db.commit()
    db.close()

    response = client.post("/api/eval", headers=get_superadmin_headers())
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2

    # Verify response structure and mocked fallback values
    item1 = [x for x in data if x["feedback_id"] == "fb-1"][0]
    assert item1["query"] == "What is RAG?"
    assert item1["response"] == "Retrieval Augmented Generation."
    assert item1["rating"] == 1
    assert item1["faithfulness_score"] == 0.85
    assert item1["relevancy_score"] == 0.90
    assert "Mocked" in item1["reason"]

    item2 = [x for x in data if x["feedback_id"] == "fb-2"][0]
    assert item2["query"] == "Explain Vector DB."
    assert item2["response"] == "A database for high-dimensional vectors."
    assert item2["rating"] == -1
    assert item2["faithfulness_score"] == 0.85
    assert item2["relevancy_score"] == 0.90
    assert "Mocked" in item2["reason"]

def test_run_eval_unauthorized_user():
    response = client.post("/api/eval", headers=get_user_headers())
    assert response.status_code == 403

def test_run_eval_unauthorized_anonymous():
    response = client.post("/api/eval")
    assert response.status_code == 401
