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
    description: Optional[str] = None

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
    description: Optional[str]
    created_at: str


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
