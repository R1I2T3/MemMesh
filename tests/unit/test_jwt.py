import pytest
import time
from auth.jwt import encode_jwt, decode_jwt, JWTError


SECRET = "test-secret-key"


def test_encode_and_decode_jwt():
    payload = {"sub": "user-1", "email": "a@b.com", "team_id": "team-1", "is_admin": False}
    token = encode_jwt(payload, secret=SECRET, expires_minutes=15)
    decoded = decode_jwt(token, secret=SECRET)
    assert decoded["sub"] == "user-1"
    assert decoded["email"] == "a@b.com"
    assert decoded["team_id"] == "team-1"
    assert decoded["is_admin"] is False


def test_expired_jwt_raises():
    payload = {"sub": "user-1"}
    token = encode_jwt(payload, secret=SECRET, expires_minutes=0)
    time.sleep(1)
    with pytest.raises(JWTError, match="expired"):
        decode_jwt(token, secret=SECRET)


def test_invalid_signature_raises():
    payload = {"sub": "user-1"}
    token = encode_jwt(payload, secret=SECRET, expires_minutes=15)
    with pytest.raises(JWTError, match="invalid"):
        decode_jwt(token, secret="wrong-secret")


def test_malformed_token_raises():
    with pytest.raises(JWTError):
        decode_jwt("not.a.valid.token", secret=SECRET)
