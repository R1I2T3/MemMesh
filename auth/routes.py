import os
from fastapi import APIRouter, Depends, Header, HTTPException

from auth.jwt import encode_jwt
from auth.models import (
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    CreateApiKeyRequest,
    CreateApiKeyResponse,
    UserResponse,
)
from db.auth_store import AuthStore

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_store() -> AuthStore:
    db_path = os.getenv("AUTH_DB_PATH", "data/memmesh.db")
    return AuthStore(db_path)


def validate_admin_api_key(x_api_key: str = Header(None)) -> bool:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Admin API key required")
    admin_key = os.getenv("ADMIN_API_KEY", "")
    if not admin_key or x_api_key != admin_key:
        raise HTTPException(status_code=401, detail="Invalid admin API key")
    return True


def _admin_auth_dep(x_api_key: str = Header(None)) -> bool:
    return validate_admin_api_key(x_api_key)


def _require_auth_dep(authorization: str = Header(None)) -> dict:
    from auth.middleware import require_auth
    return require_auth(authorization)


@router.post("/register", status_code=201, response_model=RegisterResponse)
def register(req: RegisterRequest, _: bool = Depends(_admin_auth_dep)):
    store = get_auth_store()

    if store.get_user_by_email(req.email):
        raise HTTPException(status_code=409, detail="Email already registered")

    team_id = None
    if req.team_name:
        team_id = store.create_team(req.team_name)

    user_id = store.create_user(req.email, req.password, team_id)
    return RegisterResponse(user_id=user_id, email=req.email, team_id=team_id)


@router.post("/token", response_model=TokenResponse)
def token_exchange(x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")

    store = get_auth_store()
    user = store.validate_api_key(x_api_key)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")

    expires_minutes = int(os.getenv("JWT_EXPIRY_MINUTES", "15"))
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "team_id": user["team_id"],
        "is_admin": bool(user["is_admin"]),
    }
    jwt_token = encode_jwt(payload, secret=os.getenv("JWT_SECRET", ""), expires_minutes=expires_minutes)
    return TokenResponse(token=jwt_token, expires_in=expires_minutes * 60)


@router.post("/api-keys", status_code=201, response_model=CreateApiKeyResponse)
def create_api_key(req: CreateApiKeyRequest, user: dict = Depends(_require_auth_dep)):
    store = get_auth_store()
    raw_key, _ = store.create_api_key(user["id"], req.label)
    return CreateApiKeyResponse(api_key=raw_key)


@router.post("/revoke-key")
def revoke_api_key(req: dict, user: dict = Depends(_require_auth_dep)):
    key_hash = req.get("key_hash")
    if not key_hash:
        raise HTTPException(status_code=400, detail="key_hash required")
    store = get_auth_store()
    store.revoke_api_key(key_hash)
    return {"status": "revoked"}


@router.get("/me", response_model=UserResponse)
def get_me(user: dict = Depends(_require_auth_dep)):
    return UserResponse(
        id=user["id"],
        email=user["email"],
        team_id=user.get("team_id"),
        is_admin=bool(user.get("is_admin", False)),
    )
