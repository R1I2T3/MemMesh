import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from backend.db.mysql import get_db
from backend.models import User
from backend.auth.passwords import verify_password
from backend.auth.jwt import create_access_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])
DUMMY_PASSWORD_HASH = "$2b$12$jxrolaQomPjC981oKukEYeYjOlt5pe0WyeMrDbS3QqAkCaVgZ.oN6"

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=payload.email).first()
    password_hash = user.password_hash if user else DUMMY_PASSWORD_HASH
    password_correct = verify_password(payload.password, password_hash)
    if not user or not password_correct:
        logger.warning(f"Failed login attempt for {payload.email}")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.user_id, "role": user.global_role})
    return {"token": token, "role": user.global_role}
