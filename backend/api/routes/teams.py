# backend/api/routes/teams.py
"""Administrative Teams CRUD endpoints."""

import sqlite3
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from auth.middleware import require_global_role
from db.sqlite import get_db

router = APIRouter(
    prefix="/admin/teams",
    tags=["admin-teams"],
    dependencies=[Depends(require_global_role(["superadmin", "admin"]))],
)


class TeamCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Team name must not be empty or whitespace only")
        return stripped


class TeamResponse(BaseModel):
    team_id: str
    name: str
    description: str | None
    created_at: str


class MemberAddRequest(BaseModel):
    user_id: str
    role: str = Field("user", pattern="^(user|lead)$")


class MemberResponse(BaseModel):
    user_id: str
    email: str
    role: str


@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(body: TeamCreate, conn: sqlite3.Connection = Depends(get_db)):
    """Create a new team (Admin/Superadmin only)."""
    # Check if team name already exists
    existing = conn.execute(
        "SELECT team_id FROM teams WHERE name = ?", (body.name,)
    ).fetchone()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team name already exists",
        )

    team_id = str(uuid.uuid4())
    try:
        with conn:
            conn.execute(
                "INSERT INTO teams (team_id, name, description) VALUES (?, ?, ?)",
                (team_id, body.name, body.description),
            )
    except sqlite3.IntegrityError:
        # Just in case of concurrent requests or race conditions
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team name already exists",
        )

    row = conn.execute(
        "SELECT team_id, name, description, created_at FROM teams WHERE team_id = ?",
        (team_id,),
    ).fetchone()

    return TeamResponse(
        team_id=row["team_id"],
        name=row["name"],
        description=row["description"],
        created_at=row["created_at"],
    )


@router.get("", response_model=list[TeamResponse])
async def list_teams(conn: sqlite3.Connection = Depends(get_db)):
    """List all teams (Admin/Superadmin only)."""
    rows = conn.execute(
        "SELECT team_id, name, description, created_at FROM teams ORDER BY created_at DESC"
    ).fetchall()

    return [
        TeamResponse(
            team_id=row["team_id"],
            name=row["name"],
            description=row["description"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(team_id: str, conn: sqlite3.Connection = Depends(get_db)):
    """Delete a team by ID (Admin/Superadmin only)."""
    with conn:
        cursor = conn.execute("DELETE FROM teams WHERE team_id = ?", (team_id,))
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found",
            )
    return


@router.post("/{team_id}/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def add_team_member(
    team_id: str,
    body: MemberAddRequest,
    current_user: dict = Depends(require_global_role(["superadmin", "admin"])),
    conn: sqlite3.Connection = Depends(get_db),
):
    """Add a user to a team (Admin/Superadmin only)."""
    # Verify that team_id exists in teams
    team = conn.execute("SELECT team_id FROM teams WHERE team_id = ?", (team_id,)).fetchone()
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    # Verify that user_id exists in users
    user = conn.execute("SELECT email FROM users WHERE user_id = ?", (body.user_id,)).fetchone()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    membership_id = str(uuid.uuid4())
    try:
        with conn:
            conn.execute(
                "INSERT INTO team_members (membership_id, user_id, team_id, role, added_by) VALUES (?, ?, ?, ?, ?)",
                (membership_id, body.user_id, team_id, body.role, current_user["user_id"]),
            )
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already in team",
        )

    return MemberResponse(
        user_id=body.user_id,
        email=user["email"],
        role=body.role,
    )


@router.get("/{team_id}/members", response_model=list[MemberResponse])
async def list_team_members(
    team_id: str,
    conn: sqlite3.Connection = Depends(get_db),
):
    """Retrieve all members of a team (Admin/Superadmin only)."""
    # Verify that team_id exists in teams
    team = conn.execute("SELECT team_id FROM teams WHERE team_id = ?", (team_id,)).fetchone()
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    rows = conn.execute(
        """
        SELECT tm.user_id, u.email, tm.role
        FROM team_members tm
        JOIN users u ON tm.user_id = u.user_id
        WHERE tm.team_id = ?
        ORDER BY tm.added_at ASC
        """,
        (team_id,),
    ).fetchall()

    return [
        MemberResponse(
            user_id=row["user_id"],
            email=row["email"],
            role=row["role"],
        )
        for row in rows
    ]


@router.delete("/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_team_member(
    team_id: str,
    user_id: str,
    conn: sqlite3.Connection = Depends(get_db),
):
    """Remove a member from a team (Admin/Superadmin only)."""
    with conn:
        cursor = conn.execute(
            "DELETE FROM team_members WHERE team_id = ? AND user_id = ?",
            (team_id, user_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found",
            )
    return
