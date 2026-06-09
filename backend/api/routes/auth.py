import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from backend.db.mysql import get_db
from backend.models import User
from backend.auth.passwords import verify_password, hash_password
from backend.auth.jwt import create_access_token, decode_access_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])
DUMMY_PASSWORD_HASH = "$2b$12$jxrolaQomPjC981oKukEYeYjOlt5pe0WyeMrDbS3QqAkCaVgZ.oN6"

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=payload.email).first()
    password_hash = user.password_hash if user else DUMMY_PASSWORD_HASH
    password_correct = verify_password(payload.password, password_hash)
    if not user or not password_correct:
        logger.warning(f"Failed login attempt for {payload.email}")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.user_id, "email": user.email, "role": user.global_role})
    return {"token": token, "role": user.global_role}

@router.post("/register", status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter_by(email=payload.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        user_id=str(uuid.uuid4()),
        email=payload.email,
        password_hash=hash_password(payload.password),
        global_role="user"
    )
    db.add(user)
    db.commit()
    return {"user_id": user.user_id, "email": user.email}

@router.post("/refresh")
def refresh(payload: RefreshRequest):
    try:
        decoded = decode_access_token(payload.refresh_token)
        new_token = create_access_token({
            "sub": decoded["sub"],
            "email": decoded.get("email"),
            "role": decoded.get("role")
        })
        return {"token": new_token}
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
