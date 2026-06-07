import logging
from fastapi import Header, HTTPException, Depends
from backend.auth.jwt import decode_access_token

logger = logging.getLogger(__name__)

def get_current_user(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
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
