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


@patch("backend.api.routes.auth.hash_password")
def test_register_success(mock_hash):
    from backend.api.routes.auth import router
    from backend.db.mysql import get_db

    class FakeQuery:
        def filter_by(self, **kwargs):
            return self
        def first(self):
            return None

    added_users = []

    class FakeDb:
        def query(self, model):
            return FakeQuery()
        def add(self, obj):
            added_users.append(obj)
        def commit(self):
            pass

    def override_get_db():
        yield FakeDb()

    mock_hash.return_value = "$2b$12$hashedpassword"

    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[get_db] = override_get_db
    t_client = TestClient(test_app)

    response = t_client.post("/api/auth/register", json={"email": "newuser@memmesh.com", "password": "password123"})
    assert response.status_code == 201
    data = response.json()
    assert "user_id" in data
    assert data["email"] == "newuser@memmesh.com"


def test_register_duplicate_email():
    from backend.api.routes.auth import router
    from backend.db.mysql import get_db
    from backend.models import User

    existing_user = User(
        user_id="existing-id",
        email="existing@memmesh.com",
        password_hash="$2b$12$hash",
        global_role="user"
    )

    class FakeQuery:
        def filter_by(self, **kwargs):
            return self
        def first(self):
            return existing_user

    class FakeDb:
        def query(self, model):
            return FakeQuery()
        def add(self, obj):
            pass
        def commit(self):
            pass

    def override_get_db():
        yield FakeDb()

    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[get_db] = override_get_db
    t_client = TestClient(test_app)

    response = t_client.post("/api/auth/register", json={"email": "existing@memmesh.com", "password": "password123"})
    assert response.status_code == 409
    assert response.json()["detail"] == "Email already registered"


@patch("backend.api.routes.auth.decode_access_token")
@patch("backend.api.routes.auth.create_access_token")
def test_refresh_success(mock_create_token, mock_decode):
    from backend.api.routes.auth import router
    from backend.db.mysql import get_db

    mock_decode.return_value = {"sub": "user-id", "email": "user@memmesh.com", "role": "user"}
    mock_create_token.return_value = "new-access-token"

    def override_get_db():
        yield None

    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[get_db] = override_get_db
    t_client = TestClient(test_app)

    response = t_client.post("/api/auth/refresh", json={"refresh_token": "valid-refresh-token"})
    assert response.status_code == 200
    data = response.json()
    assert data["token"] == "new-access-token"
    mock_decode.assert_called_once_with("valid-refresh-token")
    mock_create_token.assert_called_once_with({"sub": "user-id", "email": "user@memmesh.com", "role": "user"})


@patch("backend.api.routes.auth.decode_access_token")
def test_refresh_invalid_token(mock_decode):
    from backend.api.routes.auth import router
    from backend.db.mysql import get_db

    mock_decode.side_effect = ValueError("Invalid or expired token")

    def override_get_db():
        yield None

    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[get_db] = override_get_db
    t_client = TestClient(test_app)

    response = t_client.post("/api/auth/refresh", json={"refresh_token": "garbage-token"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid refresh token"
