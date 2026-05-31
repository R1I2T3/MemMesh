# backend/auth/middleware.py
"""FastAPI dependency for JWT authentication on protected routes."""

from typing import Any, Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth.jwt import verify_token

_bearer_scheme = HTTPBearer(auto_error=False)


async def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict:
    """FastAPI dependency that extracts and verifies the JWT from the Authorization header.

    Returns:
        Decoded JWT payload dict containing user_id, role, team_memberships.

    Raises:
        HTTPException 401 if token is missing, invalid, or expired.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    payload = verify_token(token)
    if payload is None or payload.get("typ") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


def require_global_role(required_roles: list[str]) -> Callable[..., Any]:
    """FastAPI dependency that restricts route access based on global roles.

    Raises:
        HTTPException 403 if the user's global role is not in required_roles.
    """
    async def dependency(payload: dict = Depends(require_auth)) -> dict:
        global_role = payload.get("role")
        if global_role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return payload

    return dependency


def require_team_role(min_role: str) -> Callable[..., Any]:
    """FastAPI dependency that restricts route access based on team roles.

    Asserts that the user is either a global admin/superadmin (who bypass all team checks)
    or has a membership in team_id with a role satisfying min_role.

    IMPORTANT: This dependency binds to the route path parameter named exactly `team_id`.
    Ensure your path signature defines `{team_id}` so FastAPI can resolve it correctly.

    Raises:
        ValueError if the defined min_role is invalid.
        HTTPException 403 if not in the team or role requirements are not met.
    """
    if min_role not in ("user", "lead"):
        raise ValueError(f"Invalid min_role: '{min_role}'. Must be 'user' or 'lead'.")

    async def dependency(
        team_id: str,
        payload: dict = Depends(require_auth),
    ) -> dict:
        global_role = payload.get("role")
        if global_role in ("admin", "superadmin"):
            return payload

        memberships = payload.get("team_memberships") or []
        user_team_role = None
        for membership in memberships:
            if membership.get("team_id") == team_id:
                user_team_role = membership.get("role")
                break

        if user_team_role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this team",
            )

        if min_role == "lead" and user_team_role != "lead":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Team lead permission required",
            )

        return payload

    return dependency

