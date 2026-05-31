# backend/tests/test_jwt.py
"""Unit tests for JWT token creation and verification."""

from auth.jwt import create_access_token, verify_token


def test_create_token_returns_string():
    token = create_access_token(
        user_id="user-1",
        global_role="user",
        team_memberships=[],
    )
    assert isinstance(token, str)
    assert len(token) > 0


def test_verify_valid_token():
    token = create_access_token(
        user_id="user-1",
        global_role="admin",
        team_memberships=[{"team_id": "t1", "role": "team_lead"}],
    )
    payload = verify_token(token)
    assert payload is not None
    assert payload["user_id"] == "user-1"
    assert payload["role"] == "admin"
    assert payload["team_memberships"] == [{"team_id": "t1", "role": "team_lead"}]


def test_verify_invalid_token_returns_none():
    payload = verify_token("this.is.not.a.valid.jwt")
    assert payload is None


def test_verify_tampered_token_returns_none():
    token = create_access_token(
        user_id="user-1",
        global_role="user",
        team_memberships=[],
    )
    # Tamper with the token by changing a character
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
    payload = verify_token(tampered)
    assert payload is None


def test_token_contains_expiry():
    token = create_access_token(
        user_id="user-1",
        global_role="user",
        team_memberships=[],
    )
    payload = verify_token(token)
    assert "exp" in payload


def test_expired_token_returns_none():
    token = create_access_token(
        user_id="user-1",
        global_role="user",
        team_memberships=[],
        expiry_minutes=-1,  # Already expired
    )
    payload = verify_token(token)
    assert payload is None
