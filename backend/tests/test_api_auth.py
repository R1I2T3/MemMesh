import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from backend.auth.middleware import get_current_user
from unittest.mock import patch

app = FastAPI()

@app.get("/test-protected")
def protected_route(user = Depends(get_current_user)):
    return {"user": user}

client = TestClient(app)

def test_protected_route_missing_header_returns_401():
    response = client.get("/test-protected")
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing or invalid authorization header"


@pytest.mark.anyio
async def test_lifespan_database_offline_graceful():
    from backend.main import lifespan

    with patch("backend.main.SessionLocal", side_effect=Exception("Connection refused")):
        async with lifespan(None):
            pass


@patch("backend.api.routes.auth.verify_password")
def test_login_always_calls_verify_password(mock_verify):
    from backend.api.routes.auth import router
    from backend.db.mysql import get_db

    class FakeQuery:
        def filter_by(self, **kwargs):
            return self

        def first(self):
            return None

    class FakeDb:
        def query(self, model):
            return FakeQuery()

    def override_get_db():
        yield FakeDb()

    mock_verify.return_value = False
    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[get_db] = override_get_db
    t_client = TestClient(test_app)

    response = t_client.post("/api/auth/login", json={"email": "nonexistent@memmesh.com", "password": "password"})

    assert response.status_code == 401
    assert mock_verify.called
