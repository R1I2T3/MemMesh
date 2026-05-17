import jwt
from datetime import datetime, timedelta, timezone


class JWTError(Exception):
    pass


def encode_jwt(payload: dict, secret: str, expires_minutes: int = 15) -> str:
    now = datetime.now(timezone.utc)
    to_encode = payload.copy()
    to_encode["exp"] = now + timedelta(minutes=expires_minutes)
    to_encode["iat"] = now
    return jwt.encode(to_encode, secret, algorithm="HS256")


def decode_jwt(token: str, secret: str) -> dict:
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise JWTError("Token has expired")
    except jwt.InvalidTokenError:
        raise JWTError("invalid token")
