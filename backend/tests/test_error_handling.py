import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from fastapi.exceptions import HTTPException, RequestValidationError
from unittest.mock import patch, MagicMock

from backend.main import app
from backend.db.mysql import get_db
from backend.middleware.error_handler import (
    global_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)

# ----------------- Unhandled Exception & Handler Tests -----------------

# Define a test app to verify custom error handlers in isolation
test_error_app = FastAPI()
test_error_app.add_exception_handler(Exception, global_exception_handler)
test_error_app.add_exception_handler(HTTPException, http_exception_handler)
test_error_app.add_exception_handler(RequestValidationError, validation_exception_handler)

@test_error_app.get("/trigger-500")
def trigger_500():
    raise RuntimeError("Something broke unexpectedly!")

@test_error_app.get("/trigger-400")
def trigger_400():
    raise HTTPException(status_code=400, detail="Custom bad request")

@test_error_app.get("/trigger-validation")
def trigger_validation(param: int):
    return {"param": param}


def test_global_exception_handler_returns_500():
    client = TestClient(test_error_app, raise_server_exceptions=False)
    response = client.get("/trigger-500")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}


def test_http_exception_handler_returns_correct_code():
    client = TestClient(test_error_app, raise_server_exceptions=False)
    response = client.get("/trigger-400")
    assert response.status_code == 400
    assert response.json() == {"detail": "Custom bad request"}


def test_validation_exception_handler_returns_422():
    client = TestClient(test_error_app, raise_server_exceptions=False)
    response = client.get("/trigger-validation?param=not-an-int")
    assert response.status_code == 422
    # Verify we get validation detail from FastAPI
    assert "detail" in response.json()


# ----------------- Health Check Endpoint Tests -----------------

@pytest.fixture
def mock_health_services():
    with patch("backend.agents.memory.get_redis_client") as mock_redis, \
         patch("backend.db.weaviate.get_weaviate_mgr") as mock_weaviate, \
         patch("backend.db.neo4j.Neo4jManager") as mock_neo4j:
         
        # Mock Redis
        mock_redis_client = MagicMock()
        mock_redis_client.ping.return_value = True
        mock_redis.return_value = mock_redis_client
        
        # Mock Weaviate
        mock_weaviate_mgr = MagicMock()
        mock_weaviate_mgr.client.is_live.return_value = True
        mock_weaviate.return_value = mock_weaviate_mgr
        
        # Mock Neo4j
        mock_neo4j_instance = MagicMock()
        mock_neo4j.return_value = mock_neo4j_instance
        
        yield {
            "redis": mock_redis_client,
            "weaviate": mock_weaviate_mgr,
            "neo4j": mock_neo4j_instance,
        }


def test_health_check_all_ok(mock_health_services):
    # Mock MySQL DB
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.get("/api/health")
    
    app.dependency_overrides.clear()
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["services"] == {
        "mysql": "ok",
        "redis": "ok",
        "weaviate": "ok",
        "neo4j": "ok"
    }
    
    # Ensure Neo4j was closed
    mock_health_services["neo4j"].close.assert_called_once()


def test_health_check_mysql_fails(mock_health_services):
    mock_db = MagicMock()
    mock_db.execute.side_effect = Exception("MySQL down")
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.get("/api/health")
    
    app.dependency_overrides.clear()
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["services"] == {
        "mysql": "error",
        "redis": "ok",
        "weaviate": "ok",
        "neo4j": "ok"
    }


def test_health_check_redis_fails(mock_health_services):
    mock_health_services["redis"].ping.return_value = False
    
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.get("/api/health")
    
    app.dependency_overrides.clear()
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["services"] == {
        "mysql": "ok",
        "redis": "error",
        "weaviate": "ok",
        "neo4j": "ok"
    }


def test_health_check_weaviate_fails(mock_health_services):
    mock_health_services["weaviate"].client.is_live.return_value = False
    
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.get("/api/health")
    
    app.dependency_overrides.clear()
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["services"] == {
        "mysql": "ok",
        "redis": "ok",
        "weaviate": "error",
        "neo4j": "ok"
    }


def test_health_check_neo4j_fails(mock_health_services):
    mock_health_services["neo4j"].driver.verify_connectivity.side_effect = Exception("Neo4j connection error")
    
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.get("/api/health")
    
    app.dependency_overrides.clear()
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["services"] == {
        "mysql": "ok",
        "redis": "ok",
        "weaviate": "ok",
        "neo4j": "error"
    }
    
    # Ensure Neo4j close was still called in finally block
    mock_health_services["neo4j"].close.assert_called_once()
