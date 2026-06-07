import logging
import uuid
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from backend.db.mysql import get_db
from backend.models import User, Team, TeamMember
from backend.auth.middleware import require_global_role
from backend.auth.passwords import hash_password

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_global_role("superadmin"))])

# --- Pydantic Models ---

class TeamCreate(BaseModel):
    name: str

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    global_role: Literal["user", "admin", "superadmin"] = "user"

class MemberAdd(BaseModel):
    team_id: str
    user_id: str
    role: Literal["member", "admin", "owner"] = "member"

# --- Teams CRUD ---

@router.post("/teams")
def create_team(payload: TeamCreate, db: Session = Depends(get_db)):
    existing = db.query(Team).filter_by(name=payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Team already exists")
    team = Team(team_id=str(uuid.uuid4()), name=payload.name)
    db.add(team)
    db.commit()

    # Provision tenant in Weaviate
    try:
        from backend.db.weaviate import get_weaviate_mgr
        weaviate_mgr = get_weaviate_mgr()
        weaviate_mgr.create_tenant(team.team_id)
    except Exception as e:
        logger.error(f"Failed to create Weaviate tenant for team {team.team_id}: {e}")

    return {"status": "created", "team_id": team.team_id}

@router.get("/teams")
def list_teams(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    teams = db.query(Team).offset(offset).limit(limit).all()
    total = db.query(Team).count()
    return {"teams": [{"team_id": t.team_id, "name": t.name} for t in teams], "total": total}

@router.delete("/teams/{team_id}")
def delete_team(team_id: str, db: Session = Depends(get_db)):
    team = db.query(Team).filter_by(team_id=team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    db.delete(team)
    db.commit()
    return {"status": "deleted"}

# --- Users CRUD ---

@router.post("/users")
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter_by(email=payload.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="User email already exists")
    user = User(
        user_id=str(uuid.uuid4()),
        email=payload.email,
        password_hash=hash_password(payload.password),
        global_role=payload.global_role
    )
    db.add(user)
    db.commit()
    return {"status": "created", "user_id": user.user_id}

@router.get("/users")
def list_users(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    users = db.query(User).offset(offset).limit(limit).all()
    total = db.query(User).count()
    return {
        "users": [{"user_id": u.user_id, "email": u.email, "role": u.global_role} for u in users],
        "total": total
    }

@router.delete("/users/{user_id}")
def delete_user(user_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(user_id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"status": "deleted"}

# --- Members CRUD ---

@router.post("/members")
def add_member(payload: MemberAdd, db: Session = Depends(get_db)):
    # Check if team exists
    team = db.query(Team).filter_by(team_id=payload.team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Check if user exists
    user = db.query(User).filter_by(user_id=payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if membership already exists
    existing = db.query(TeamMember).filter_by(team_id=payload.team_id, user_id=payload.user_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="User is already a member of this team")

    member = TeamMember(team_id=payload.team_id, user_id=payload.user_id, role=payload.role)
    db.add(member)
    db.commit()
    return {
        "status": "added",
        "team_id": member.team_id,
        "user_id": member.user_id,
        "role": member.role
    }

@router.get("/members")
def list_members(
    team_id: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    query = db.query(TeamMember)
    if team_id:
        query = query.filter_by(team_id=team_id)
    
    members = query.offset(offset).limit(limit).all()
    total = query.count()
    return {
        "members": [{"team_id": m.team_id, "user_id": m.user_id, "role": m.role} for m in members],
        "total": total
    }

@router.delete("/members")
def remove_member(team_id: str, user_id: str, db: Session = Depends(get_db)):
    member = db.query(TeamMember).filter_by(team_id=team_id, user_id=user_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Membership not found")
    db.delete(member)
    db.commit()
    return {"status": "removed"}
