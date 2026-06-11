import pytest
from backend.auth.passwords import hash_password, verify_password
from backend.auth.jwt import create_access_token, decode_access_token

def test_password_hash_and_verify():
    hashed = hash_password("my_secret_123")
    assert hashed != "my_secret_123"
    assert verify_password("my_secret_123", hashed) is True
    assert verify_password("wrong_password", hashed) is False

def test_jwt_create_and_decode():
    token = create_access_token({"sub": "user-123", "role": "superadmin"})
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"
    assert payload["role"] == "superadmin"
    assert "exp" in payload

def test_jwt_invalid_token_raises():
    with pytest.raises(ValueError):
        decode_access_token("invalid.token.here")
