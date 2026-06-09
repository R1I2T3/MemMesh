import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.tasks.decay_worker import decay_memory_weights
from backend.tasks.drift_worker import check_data_drift
from backend.models import UserFeedback, Team
from backend.auth.jwt import create_access_token

client = TestClient(app)

@pytest.fixture
def mock_db():
    with patch("backend.tasks.decay_worker.SessionLocal") as mock_session_local, \
         patch("backend.tasks.drift_worker.SessionLocal") as mock_session_local_drift:
        mock_db_session = MagicMock()
        mock_session_local.return_value = mock_db_session
        mock_session_local_drift.return_value = mock_db_session
        yield mock_db_session

@pytest.fixture
def superadmin_token():
    return create_access_token({"sub": "admin-123", "role": "superadmin"})

@pytest.fixture
def normal_user_token():
    return create_access_token({"sub": "user-123", "role": "user"})

def test_decay_celery_task_logic(mock_db):
    team1 = Team(team_id="team-1", name="Team 1")
    team2 = Team(team_id="team-2", name="Team 2")
    mock_db.query.return_value.all.return_value = [team1, team2]
    
    with patch("backend.tasks.decay_worker.Neo4jManager") as mock_neo4j, \
         patch("backend.tasks.decay_worker.WeaviateManager") as mock_weaviate:
        
        mock_neo4j_instance = MagicMock()
        mock_neo4j.return_value = mock_neo4j_instance
        
        mock_weaviate_instance = MagicMock()
        mock_weaviate.return_value = mock_weaviate_instance
        
        # Mock Weaviate collections and search results
        mock_obj = MagicMock()
        mock_obj.uuid = "chunk-uuid-123"
        mock_obj.properties = {"importance_score": 1.0}
        
        mock_collection = MagicMock()
        mock_collection.query.fetch_objects.return_value.objects = [mock_obj]
        mock_weaviate_instance.client.collections.get.return_value.with_tenant.return_value = mock_collection
        
        result = decay_memory_weights()
        
        assert result["status"] == "success"
        assert result["processed_teams"] == 2
        assert mock_neo4j_instance.close.called
        assert mock_weaviate_instance.close.called
        
        # Verify Weaviate update was called with decayed importance score
        mock_collection.data.update.assert_called_with(
            uuid="chunk-uuid-123",
            properties={"importance_score": 0.9}
        )

def test_drift_celery_task_insufficient_data(mock_db):
    mock_db.query.return_value.order_by.return_value.all.return_value = []
    result = check_data_drift()
    assert result["drift_detected"] is False
    assert "Insufficient data" in result["reason"]

def test_drift_celery_task_sufficient_data_no_drift(mock_db):
    f1 = UserFeedback(feedback_id="1", query="hello world", rating=1)
    f2 = UserFeedback(feedback_id="2", query="hello world", rating=1)
    mock_db.query.return_value.order_by.return_value.all.return_value = [f1, f2]
    
    result = check_data_drift()
    assert result["drift_detected"] is False
    assert result["metrics"]["avg_length_last"] == 11.0
    assert result["metrics"]["avg_length_prev"] == 11.0

def test_drift_celery_task_with_drift(mock_db):
    last_group = [UserFeedback(feedback_id="1", query="a" * 100, rating=1)]
    prev_group = [UserFeedback(feedback_id="2", query="a", rating=-1)]
    
    mock_db.query.return_value.order_by.return_value.all.return_value = last_group + prev_group
    
    result = check_data_drift()
    assert result["drift_detected"] is True
    assert result["metrics"]["length_difference"] == 99.0
    assert result["metrics"]["rating_difference"] == 2.0

@patch("backend.api.routes.decay.decay_memory_weights.delay")
def test_api_trigger_decay_superadmin(mock_delay, superadmin_token):
    mock_task = MagicMock()
    mock_task.id = "decay-task-uuid"
    mock_delay.return_value = mock_task
    
    response = client.post(
        "/api/decay/trigger",
        headers={"Authorization": f"Bearer {superadmin_token}"}
    )
    assert response.status_code == 200
    assert response.json() == {"status": "triggered", "task_id": "decay-task-uuid"}

def test_api_trigger_decay_forbidden(normal_user_token):
    response = client.post(
        "/api/decay/trigger",
        headers={"Authorization": f"Bearer {normal_user_token}"}
    )
    assert response.status_code == 403

def test_api_trigger_decay_unauthorized():
    response = client.post("/api/decay/trigger")
    assert response.status_code == 401

@patch("backend.api.routes.decay.AsyncResult")
def test_api_get_status_superadmin(mock_async_result, superadmin_token):
    mock_res = MagicMock()
    mock_res.state = "SUCCESS"
    mock_res.ready.return_value = True
    mock_res.result = {"status": "success", "processed_teams": 1}
    mock_async_result.return_value = mock_res
    
    response = client.get(
        "/api/decay/status/task-123",
        headers={"Authorization": f"Bearer {superadmin_token}"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "SUCCESS"
    assert response.json()["result"] == {"status": "success", "processed_teams": 1}
