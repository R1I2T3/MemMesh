import logging
from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session
from backend.db.mysql import get_db
from backend.models import TeamMember
from backend.auth.jwt import decode_access_token

logger = logging.getLogger(__name__)

def get_current_user(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    try:
        token = authorization.split(" ", 1)[1]
        return decode_access_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

def require_global_role(role: str):
    def dep(payload: dict = Depends(get_current_user)):
        if payload.get("role") != role:
            logger.warning(f"Forbidden: user {payload.get('sub')} tried role={role}")
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return payload
    return dep

def require_team_membership():
    async def dep(
        x_active_team_id: str | None = Header(default=None, alias="X-Active-Team-ID"),
        current_user: dict = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        if not x_active_team_id:
            raise HTTPException(status_code=400, detail="Missing X-Active-Team-ID header")
        if current_user.get("role") == "superadmin":
            return x_active_team_id
        membership = db.query(TeamMember).filter_by(
            team_id=x_active_team_id,
            user_id=current_user.get("sub")
        ).first()
        if not membership:
            raise HTTPException(status_code=403, detail="Not a member of this team")
        return x_active_team_id
    return dep

_ROLE_HIERARCHY = {"user": 0, "team_lead": 1}

def require_team_role(min_role: str):
    if min_role not in _ROLE_HIERARCHY:
        raise ValueError(f"Unknown role: {min_role}")
    async def dep(
        x_active_team_id: str = Depends(require_team_membership()),
        current_user: dict = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        if current_user.get("role") == "superadmin":
            return x_active_team_id
        membership = db.query(TeamMember).filter_by(
            team_id=x_active_team_id,
            user_id=current_user.get("sub")
        ).first()
        if membership.role not in _ROLE_HIERARCHY:
            raise HTTPException(status_code=403, detail=f"Unknown membership role: {membership.role}")
        if _ROLE_HIERARCHY[membership.role] < _ROLE_HIERARCHY[min_role]:
            raise HTTPException(status_code=403, detail=f"Requires role: {min_role}")
        return x_active_team_id
    return dep
