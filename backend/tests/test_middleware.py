# backend/tests/test_middleware.py
"""Unit tests for the authentication middleware FastAPI dependency."""

import asyncio

import pytest
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from auth.jwt import create_access_token
from auth.middleware import require_auth, require_global_role, require_team_role


def test_require_auth_valid_token():
    token = create_access_token(
        user_id="user-123",
        global_role="admin",
        team_memberships=[{"team_id": "team-A", "role": "user"}],
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    # Run async function using asyncio.run
    payload = asyncio.run(require_auth(credentials))

    assert payload is not None
    assert payload["user_id"] == "user-123"
    assert payload["role"] == "admin"
    assert payload["team_memberships"] == [{"team_id": "team-A", "role": "user"}]


def test_require_auth_invalid_token():
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials="invalid.token.here"
    )

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
    from fastapi import Depends, FastAPI
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
    response = client.get(
        "/protected", headers={"Authorization": "Bearer invalid.token.here"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"

    # 3. Valid Token -> should return 200 (Success)
    token = create_access_token(
        user_id="user-456", global_role="user", team_memberships=[]
    )
    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {"user_id": "user-456"}


def test_require_global_role_authorized():
    dep = require_global_role(["admin", "superadmin"])
    payload = {"user_id": "u1", "role": "admin"}
    result = asyncio.run(dep(payload=payload))
    assert result == payload


def test_require_global_role_unauthorized():
    dep = require_global_role(["admin", "superadmin"])
    payload = {"user_id": "u1", "role": "user"}
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(dep(payload=payload))
    
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc_info.value.detail == "Insufficient permissions"


def test_require_team_role_global_admin():
    dep = require_team_role("user")
    
    # admin bypass
    payload_admin = {"user_id": "u1", "role": "admin", "team_memberships": []}
    result = asyncio.run(dep(team_id="team-X", payload=payload_admin))
    assert result == payload_admin
    
    # superadmin bypass
    payload_super = {"user_id": "u1", "role": "superadmin", "team_memberships": []}
    result = asyncio.run(dep(team_id="team-X", payload=payload_super))
    assert result == payload_super


def test_require_team_role_member_as_user():
    dep = require_team_role("user")
    
    # Standard team member with role: "user" accessing their own team as user
    payload = {
        "user_id": "u1",
        "role": "user",
        "team_memberships": [{"team_id": "team-A", "role": "user"}]
    }
    result = asyncio.run(dep(team_id="team-A", payload=payload))
    assert result == payload


def test_require_team_role_member_not_in_team():
    dep = require_team_role("user")
    
    # Standard team member accessing a team they are not in
    payload = {
        "user_id": "u1",
        "role": "user",
        "team_memberships": [{"team_id": "team-A", "role": "user"}]
    }
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(dep(team_id="team-B", payload=payload))
    
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc_info.value.detail == "Not a member of this team"


def test_require_team_role_lead_as_lead():
    dep = require_team_role("lead")
    
    # Team lead with role: "lead" accessing their own team as lead
    payload = {
        "user_id": "u1",
        "role": "user",
        "team_memberships": [{"team_id": "team-A", "role": "lead"}]
    }
    result = asyncio.run(dep(team_id="team-A", payload=payload))
    assert result == payload


def test_require_team_role_lead_as_user():
    dep = require_team_role("user")
    
    # Team lead accessing their own team as user (should be permitted since lead is >= user)
    payload = {
        "user_id": "u1",
        "role": "user",
        "team_memberships": [{"team_id": "team-A", "role": "lead"}]
    }
    result = asyncio.run(dep(team_id="team-A", payload=payload))
    assert result == payload


def test_require_team_role_member_as_lead():
    dep = require_team_role("lead")
    
    # Standard team member (role: "user") accessing their own team with min_role="lead"
    payload = {
        "user_id": "u1",
        "role": "user",
        "team_memberships": [{"team_id": "team-A", "role": "user"}]
    }
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(dep(team_id="team-A", payload=payload))
    
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc_info.value.detail == "Team lead permission required"


def test_rbac_integration():
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()

    @app.get("/global")
    def global_route(payload: dict = Depends(require_global_role(["admin"]))):
        return {"ok": True}

    @app.get("/teams/{team_id}/lead-only")
    def team_lead_route(team_id: str, payload: dict = Depends(require_team_role("lead"))):
        return {"team_id": team_id, "user_id": payload["user_id"]}

    client = TestClient(app)

    # 1. Global role: authorized
    token_admin = create_access_token(user_id="u1", global_role="admin", team_memberships=[])
    res = client.get("/global", headers={"Authorization": f"Bearer {token_admin}"})
    assert res.status_code == 200

    # 2. Global role: unauthorized
    token_user = create_access_token(user_id="u2", global_role="user", team_memberships=[])
    res = client.get("/global", headers={"Authorization": f"Bearer {token_user}"})
    assert res.status_code == 403
    assert res.json()["detail"] == "Insufficient permissions"

    # 3. Team role: lead accessing team_lead_route (permitted)
    token_lead = create_access_token(
        user_id="u3",
        global_role="user",
        team_memberships=[{"team_id": "team-123", "role": "lead"}]
    )
    res = client.get("/teams/team-123/lead-only", headers={"Authorization": f"Bearer {token_lead}"})
    assert res.status_code == 200
    assert res.json() == {"team_id": "team-123", "user_id": "u3"}

    # 4. Team role: standard member accessing team_lead_route (raises 403)
    token_member = create_access_token(
        user_id="u4",
        global_role="user",
        team_memberships=[{"team_id": "team-123", "role": "user"}]
    )
    res = client.get("/teams/team-123/lead-only", headers={"Authorization": f"Bearer {token_member}"})
    assert res.status_code == 403
    assert res.json()["detail"] == "Team lead permission required"

    # 5. Team role: non-member accessing team_lead_route (raises 403)
    token_non_member = create_access_token(
        user_id="u5",
        global_role="user",
        team_memberships=[{"team_id": "team-456", "role": "lead"}]
    )
    res = client.get("/teams/team-123/lead-only", headers={"Authorization": f"Bearer {token_non_member}"})
    assert res.status_code == 403
    assert res.json()["detail"] == "Not a member of this team"


def test_require_team_role_invalid_min_role():
    with pytest.raises(ValueError) as exc_info:
        require_team_role("invalid-role-name")
    
    assert "Invalid min_role: 'invalid-role-name'" in str(exc_info.value)


