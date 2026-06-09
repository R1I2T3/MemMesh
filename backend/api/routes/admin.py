import logging
import uuid
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from backend.db.mysql import get_db
from backend.models import User, Team, TeamMember
from backend.auth.middleware import get_current_user, require_global_role
from backend.auth.passwords import hash_password
from backend.db.weaviate import get_weaviate_mgr

logger = logging.getLogger(__name__)

# --- Separate routers for different access levels ---

user_router = APIRouter(prefix="/api", tags=["user"])
admin_router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_global_role("superadmin"))])

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

# --- Teams — any authenticated user ---

@user_router.post("/teams")
def create_team(
    payload: TeamCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = db.query(Team).filter_by(name=payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Team already exists")
    team = Team(team_id=str(uuid.uuid4()), name=payload.name)
    db.add(team)

    # Provision tenant in Weaviate
    try:
        weaviate_mgr = get_weaviate_mgr()
        weaviate_mgr.create_tenant(team.team_id)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create Weaviate tenant for team {team.team_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to provision team workspace: {e}")

    db.flush()

    # Auto-add creator as owner
    creator_member = TeamMember(
        team_id=team.team_id,
        user_id=current_user["sub"],
        role="owner",
    )
    db.add(creator_member)
    db.commit()
    return {"status": "created", "team_id": team.team_id}

@user_router.delete("/teams/{team_id}")
def delete_team(
    team_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    team = db.query(Team).filter_by(team_id=team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    membership = db.query(TeamMember).filter_by(
        team_id=team_id, user_id=current_user["sub"], role="owner"
    ).first()
    if not membership and current_user.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="Only team owners can delete the team")

    db.delete(team)
    db.commit()
    return {"status": "deleted"}

# --- Members — team owners / admins only ---

@user_router.post("/members")
def add_member(
    payload: MemberAdd,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    team = db.query(Team).filter_by(team_id=payload.team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    if current_user.get("role") != "superadmin":
        membership = db.query(TeamMember).filter_by(
            team_id=payload.team_id, user_id=current_user["sub"]
        ).first()
        if not membership or membership.role not in ("owner", "admin"):
            raise HTTPException(status_code=403, detail="Not authorized to manage team members")

    user = db.query(User).filter_by(user_id=payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    existing = db.query(TeamMember).filter_by(team_id=payload.team_id, user_id=payload.user_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="User is already a member of this team")

    member = TeamMember(team_id=payload.team_id, user_id=payload.user_id, role=payload.role)
    db.add(member)
    db.commit()
    return {"status": "added", "team_id": member.team_id, "user_id": member.user_id, "role": member.role}

@user_router.get("/members")
def list_members(
    team_id: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(TeamMember)
    if team_id:
        if current_user.get("role") != "superadmin":
            membership = db.query(TeamMember).filter_by(
                team_id=team_id, user_id=current_user["sub"]
            ).first()
            if not membership:
                raise HTTPException(status_code=403, detail="Not a member of this team")
        query = query.filter_by(team_id=team_id)

    members = query.offset(offset).limit(limit).all()
    total = query.count()
    return {
        "members": [{"team_id": m.team_id, "user_id": m.user_id, "role": m.role} for m in members],
        "total": total,
    }

@user_router.delete("/members")
def remove_member(
    team_id: str,
    user_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    team = db.query(Team).filter_by(team_id=team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    if current_user.get("role") != "superadmin":
        membership = db.query(TeamMember).filter_by(
            team_id=team_id, user_id=current_user["sub"]
        ).first()
        if not membership or membership.role not in ("owner", "admin"):
            raise HTTPException(status_code=403, detail="Not authorized to manage team members")

    member = db.query(TeamMember).filter_by(team_id=team_id, user_id=user_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Membership not found")
    db.delete(member)
    db.commit()
    return {"status": "removed"}

# --- Users CRUD — superadmin only ---

@admin_router.post("/users")
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

@admin_router.get("/users")
def list_users(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    users = db.query(User).offset(offset).limit(limit).all()
    total = db.query(User).count()
    return {
        "users": [{"user_id": u.user_id, "email": u.email, "role": u.global_role} for u in users],
        "total": total
    }

@admin_router.delete("/users/{user_id}")
def delete_user(user_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(user_id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"status": "deleted"}
