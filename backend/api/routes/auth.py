# backend/api/routes/auth.py
"""Authentication routes: login, refresh, and me."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from auth.jwt import create_access_token, verify_token
from auth.middleware import require_auth
from auth.passwords import verify_password
from db.sqlite import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshedTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    user_id: str
    email: str
    global_role: str


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, conn: sqlite3.Connection = Depends(get_db)):
    """Authenticate with email + password and receive JWT tokens."""
    row = conn.execute(
        "SELECT user_id, email, password_hash, global_role FROM users WHERE email = ?",
        (body.email,),
    ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not verify_password(body.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # In Phase 1, no teams exist yet — team_memberships is empty
    team_memberships: list[dict[str, str]] = []

    # Fetch team memberships if any exist (future-proofing)
    try:
        members = conn.execute(
            "SELECT team_id, role FROM team_members WHERE user_id = ?",
            (row["user_id"],),
        ).fetchall()
        team_memberships = [
            {"team_id": m["team_id"], "role": m["role"]} for m in members
        ]
    except sqlite3.OperationalError:
        # team_members table may not exist yet in Phase 1
        pass

    access_token = create_access_token(
        user_id=row["user_id"],
        global_role=row["global_role"],
        team_memberships=team_memberships,
        token_type="access",
    )

    # Refresh token has a longer expiry (7 days)
    refresh_token = create_access_token(
        user_id=row["user_id"],
        global_role=row["global_role"],
        team_memberships=team_memberships,
        expiry_minutes=60 * 24 * 7,
        token_type="refresh",
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=RefreshedTokenResponse)
async def refresh(body: RefreshRequest, conn: sqlite3.Connection = Depends(get_db)):
    """Exchange a valid refresh token for a new access token."""
    payload = verify_token(body.refresh_token)
    if payload is None or payload.get("typ") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Query the database to check if the user is active/exists (prevent blind trust)
    row = conn.execute(
        "SELECT user_id, email, global_role FROM users WHERE user_id = ?",
        (payload["user_id"],),
    ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )

    # Re-evaluate current team memberships
    team_memberships: list[dict[str, str]] = []
    try:
        members = conn.execute(
            "SELECT team_id, role FROM team_members WHERE user_id = ?",
            (row["user_id"],),
        ).fetchall()
        team_memberships = [
            {"team_id": m["team_id"], "role": m["role"]} for m in members
        ]
    except sqlite3.OperationalError:
        pass

    # Issue a fresh access token using current DB values
    access_token = create_access_token(
        user_id=row["user_id"],
        global_role=row["global_role"],
        team_memberships=team_memberships,
        token_type="access",
    )

    return RefreshedTokenResponse(access_token=access_token)


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    current_user: dict = Depends(require_auth),
    conn: sqlite3.Connection = Depends(get_db),
):
    """Return the currently authenticated user's info."""
    row = conn.execute(
        "SELECT user_id, email, global_role FROM users WHERE user_id = ?",
        (current_user["user_id"],),
    ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse(
        user_id=row["user_id"],
        email=row["email"],
        global_role=row["global_role"],
    )
