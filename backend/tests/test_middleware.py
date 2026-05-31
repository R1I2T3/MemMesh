# backend/tests/test_middleware.py
"""Unit tests for the authentication middleware FastAPI dependency."""

import asyncio
import pytest
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from auth.jwt import create_access_token
from auth.middleware import require_auth


def test_require_auth_valid_token():
    token = create_access_token(
        user_id="user-123",
        global_role="admin",
        team_memberships=[{"team_id": "team-A", "role": "member"}],
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    
    # Run async function using asyncio.run
    payload = asyncio.run(require_auth(credentials))
    
    assert payload is not None
    assert payload["user_id"] == "user-123"
    assert payload["role"] == "admin"
    assert payload["team_memberships"] == [{"team_id": "team-A", "role": "member"}]


def test_require_auth_invalid_token():
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid.token.here")
    
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(require_auth(credentials))
        
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "Invalid or expired token"
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


def test_require_auth_expired_token():
    # Token with negative expiry so it's already expired
    token = create_access_token(
        user_id="user-123",
        global_role="user",
        team_memberships=[],
        expiry_minutes=-5,
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(require_auth(credentials))
        
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "Invalid or expired token"
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


def test_require_auth_missing_credentials():
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(require_auth(None))
        
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "Not authenticated"
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


def test_require_auth_integration():
    from fastapi import FastAPI, Depends
    from fastapi.testclient import TestClient
    
    app = FastAPI()
    
    @app.get("/protected")
    def protected_route(payload: dict = Depends(require_auth)):
        return {"user_id": payload["user_id"]}
        
    client = TestClient(app)
    
    # 1. No Authorization header -> should return 401 (Not authenticated)
    response = client.get("/protected")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"
    
    # 2. Invalid Token -> should return 401 (Invalid or expired token)
    response = client.get("/protected", headers={"Authorization": "Bearer invalid.token.here"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"
    
    # 3. Valid Token -> should return 200 (Success)
    token = create_access_token(user_id="user-456", global_role="user", team_memberships=[])
    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {"user_id": "user-456"}

