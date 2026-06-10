import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime, timedelta, timezone
from backend.main import app
from backend.auth.jwt import create_access_token
from backend.db.mysql import get_db, Base
from backend.models import AuditLog, UserFeedback

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
    with patch("backend.api.routes.analytics.get_redis_client") as mock_redis:
        mock_redis_instance = MagicMock()
        mock_redis.get.return_value = None
        mock_redis_instance.get.return_value = None
        mock_redis.return_value = mock_redis_instance
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


# --- Analytics API Tests ---

def test_analytics_requires_superadmin():
    res = client.get("/api/admin/analytics", headers=get_user_headers())
    assert res.status_code == 403


def test_analytics_returns_placeholder_when_no_data():
    res = client.get("/api/admin/analytics", headers=get_superadmin_headers())
    assert res.status_code == 200
    data = res.json()
    assert data["message"] == "No analytics data yet. First aggregation runs hourly."


def test_analytics_returns_cached_data():
    import json
    fake_data = {
        "queries_last_hour": 10,
        "queries_last_day": 50,
        "avg_latency_ms": 123.45,
        "unique_users_last_day": 5,
        "positive_feedback": 8,
        "total_feedback": 10,
    }

    with patch("backend.api.routes.analytics.get_redis_client") as mock_redis:
        mock_instance = MagicMock()
        mock_instance.get.return_value = json.dumps(fake_data)
        mock_redis.return_value = mock_instance

        res = client.get("/api/admin/analytics", headers=get_superadmin_headers())
        assert res.status_code == 200
        assert res.json() == fake_data


# --- Analytics Worker Tests ---

def test_aggregate_hourly_with_data():
    db = TestingSessionLocal()
    now = datetime.now(timezone.utc)

    for i in range(5):
        db.add(AuditLog(
            id=i + 1,
            user_id=f"user_{i % 2}",
            team_id="team_1",
            query_text=f"query_{i}",
            latency_ms=100 + i * 10,
            created_at=now - timedelta(minutes=30),
        ))
    db.commit()

    db.add(UserFeedback(
        feedback_id="fb_1",
        query="test query",
        response="test response",
        rating=1,
        trace_id="trace_1",
        created_at=now - timedelta(hours=12),
    ))
    db.add(UserFeedback(
        feedback_id="fb_2",
        query="test query 2",
        response="test response 2",
        rating=-1,
        trace_id="trace_2",
        created_at=now - timedelta(hours=12),
    ))
    db.add(UserFeedback(
        feedback_id="fb_3",
        query="test query 3",
        response="test response 3",
        rating=1,
        trace_id="trace_3",
        created_at=now - timedelta(hours=12),
    ))
    db.commit()

    from backend.tasks.analytics_worker import aggregate_hourly

    result = aggregate_hourly(db=db)
    db.close()

    assert result["queries_last_hour"] == 5
    assert result["queries_last_day"] == 5
    assert result["avg_latency_ms"] == 120.0
    assert result["unique_users_last_day"] == 2
    assert result["positive_feedback"] == 2
    assert result["total_feedback"] == 3


def test_aggregate_hourly_empty_db():
    db = TestingSessionLocal()
    from backend.tasks.analytics_worker import aggregate_hourly

    result = aggregate_hourly(db=db)
    db.close()

    assert result["queries_last_hour"] == 0
    assert result["queries_last_day"] == 0
    assert result["avg_latency_ms"] == 0.0
    assert result["unique_users_last_day"] == 0
    assert result["positive_feedback"] == 0
    assert result["total_feedback"] == 0
