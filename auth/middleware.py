import os
from fastapi import Header, HTTPException, Request

from auth.jwt import decode_jwt, JWTError
from db.auth_store import AuthStore


def get_auth_store() -> AuthStore:
    db_path = os.getenv("AUTH_DB_PATH", "data/memmesh.db")
    return AuthStore(db_path)


def require_auth(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = authorization.split(" ", 1)[1]
    secret = os.getenv("JWT_SECRET", "")
    if not secret:
        raise HTTPException(status_code=500, detail="JWT_SECRET not configured")

    try:
        payload = decode_jwt(token, secret)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    store = get_auth_store()
    user = store.get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


def require_admin(authorization: str = Header(None)) -> dict:
    user = require_auth(authorization)
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
