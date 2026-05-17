from pydantic import BaseModel
from typing import Optional


class RegisterRequest(BaseModel):
    email: str
    password: str
    team_name: Optional[str] = None


class RegisterResponse(BaseModel):
    user_id: str
    email: str
    team_id: Optional[str]


class TokenRequest(BaseModel):
    pass


class TokenResponse(BaseModel):
    token: str
    expires_in: int


class CreateApiKeyRequest(BaseModel):
    label: Optional[str] = None


class CreateApiKeyResponse(BaseModel):
    api_key: str


class RevokeApiKeyRequest(BaseModel):
    key_hash: str


class UserResponse(BaseModel):
    id: str
    email: str
    team_id: Optional[str]
    is_admin: bool
