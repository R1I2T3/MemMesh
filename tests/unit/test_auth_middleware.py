import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient

from auth.middleware import require_auth, require_admin
from auth.jwt import JWTError


@pytest.fixture
def app():
    app = FastAPI()

    @app.get("/protected")
    def protected(user: dict = Depends(require_auth)):
        return {"user_id": user["id"]}

    @app.get("/admin-only")
    def admin_endpoint(user: dict = Depends(require_admin)):
        return {"admin": True}

    return app


def test_valid_jwt_returns_user(app):
    with patch.dict(os.environ, {"JWT_SECRET": "test-secret"}):
        with patch("auth.middleware.decode_jwt") as mock_decode:
            mock_decode.return_value = {
                "sub": "user-1",
                "email": "a@b.com",
                "team_id": "team-1",
                "is_admin": False,
            }
            with patch("auth.middleware.get_auth_store") as mock_store:
                mock_store.return_value.get_user_by_id.return_value = {
                    "id": "user-1",
                    "email": "a@b.com",
                    "team_id": "team-1",
                    "is_admin": False,
                }
                client = TestClient(app)
                r = client.get("/protected", headers={"Authorization": "Bearer faketoken"})
                assert r.status_code == 200
                assert r.json()["user_id"] == "user-1"


def test_missing_auth_header_returns_401(app):
    client = TestClient(app)
    r = client.get("/protected")
    assert r.status_code == 401


def test_invalid_jwt_returns_401(app):
    with patch.dict(os.environ, {"JWT_SECRET": "test-secret"}):
        with patch("auth.middleware.decode_jwt", side_effect=JWTError("invalid")):
            client = TestClient(app)
            r = client.get("/protected", headers={"Authorization": "Bearer badtoken"})
            assert r.status_code == 401


def test_non_admin_accessing_admin_endpoint_returns_403(app):
    with patch.dict(os.environ, {"JWT_SECRET": "test-secret"}):
        with patch("auth.middleware.decode_jwt") as mock_decode:
            mock_decode.return_value = {
                "sub": "user-1",
                "email": "a@b.com",
                "team_id": "team-1",
                "is_admin": False,
            }
            with patch("auth.middleware.get_auth_store") as mock_store:
                mock_store.return_value.get_user_by_id.return_value = {
                    "id": "user-1",
                    "is_admin": False,
                }
                client = TestClient(app)
                r = client.get("/admin-only", headers={"Authorization": "Bearer faketoken"})
                assert r.status_code == 403
