import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from auth.routes import router


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def test_register_creates_user(client):
    with patch("auth.routes.get_auth_store") as mock_store:
        store = MagicMock()
        store.get_user_by_email.return_value = None
        store.create_team.return_value = "team-1"
        store.create_user.return_value = "user-1"
        mock_store.return_value = store

        with patch("auth.routes.validate_admin_api_key", return_value=True):
            r = client.post(
                "/auth/register",
                json={"email": "new@test.com", "password": "secret", "team_name": "Team X"},
            )
            assert r.status_code == 201
            assert "user_id" in r.json()


def test_register_missing_admin_key_returns_401(client):
    r = client.post("/auth/register", json={"email": "a@b.com", "password": "x"})
    assert r.status_code == 401


def test_token_exchange_returns_jwt(client):
    with patch("auth.routes.get_auth_store") as mock_store:
        store = MagicMock()
        store.validate_api_key.return_value = {
            "id": "user-1",
            "email": "a@b.com",
            "team_id": "team-1",
            "is_admin": False,
        }
        mock_store.return_value = store

        with patch("auth.routes.encode_jwt", return_value="faketoken"):
            r = client.post("/auth/token", headers={"X-API-Key": "some-api-key"})
            assert r.status_code == 200
            assert "token" in r.json()


def test_token_invalid_api_key_returns_401(client):
    with patch("auth.routes.get_auth_store") as mock_store:
        mock_store.return_value.validate_api_key.return_value = None
        r = client.post("/auth/token", headers={"X-API-Key": "bad-key"})
        assert r.status_code == 401


def test_create_api_key_returns_plaintext(client):
    with patch("auth.middleware.require_auth") as mock_auth:
        mock_auth.return_value = {"id": "user-1", "team_id": "team-1"}

        with patch("auth.routes.get_auth_store") as mock_store:
            store = MagicMock()
            store.create_api_key.return_value = ("raw-key-123", "hash-456")
            mock_store.return_value = store

            r = client.post("/auth/api-keys", json={"label": "my-key"})
            assert r.status_code == 201
            assert "api_key" in r.json()


def test_me_returns_current_user(client):
    with patch("auth.middleware.require_auth") as mock_auth:
        mock_auth.return_value = {
            "id": "user-1",
            "email": "a@b.com",
            "team_id": "team-1",
            "is_admin": False,
        }

        r = client.get("/auth/me")
        assert r.status_code == 200
        assert r.json()["email"] == "a@b.com"
