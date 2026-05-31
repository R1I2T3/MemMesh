# backend/auth/jwt.py
"""JWT token creation and verification using python-jose."""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from config import settings

ALGORITHM = "HS256"


def create_access_token(
    user_id: str,
    global_role: str,
    team_memberships: list[dict[str, str]],
    expiry_minutes: int | None = None,
    token_type: str = "access",
) -> str:
    """Create a signed JWT access token.

    Args:
        user_id: The user's unique identifier.
        global_role: The user's global role ('user', 'admin', 'superadmin').
        team_memberships: List of dicts with 'team_id' and 'role' keys.
        expiry_minutes: Override expiry. Defaults to settings.jwt_expiry_minutes.
        token_type: The type of token ('access' or 'refresh').

    Returns:
        Encoded JWT string.
    """
    if expiry_minutes is None:
        expiry_minutes = settings.jwt_expiry_minutes

    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expiry_minutes)

    payload: dict[str, Any] = {
        "user_id": user_id,
        "role": global_role,
        "team_memberships": team_memberships,
        "exp": expire,
        "iat": now,
        "typ": token_type,
    }

    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def verify_token(token: str) -> dict[str, Any] | None:
    """Verify and decode a JWT token.

    Returns:
        Decoded payload dict if valid, None if invalid or expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[ALGORITHM],
            options={"require_exp": True},
        )
        return payload
    except JWTError:
        return None
