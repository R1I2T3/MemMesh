import pytest
import os
import tempfile
import sqlite3

from db.auth_store import AuthStore


@pytest.fixture
def auth_store():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    store = AuthStore(path)
    yield store
    store.close()
    os.unlink(path)


def test_create_team(auth_store):
    team_id = auth_store.create_team("Team Alpha")
    assert team_id is not None
    team = auth_store.get_team(team_id)
    assert team["name"] == "Team Alpha"


def test_create_user(auth_store):
    team_id = auth_store.create_team("Team Alpha")
    user_id = auth_store.create_user("alice@test.com", "password123", team_id)
    assert user_id is not None
    user = auth_store.get_user_by_email("alice@test.com")
    assert user["email"] == "alice@test.com"
    assert user["team_id"] == team_id
    assert user["is_admin"] is False


def test_create_admin_user(auth_store):
    user_id = auth_store.create_user("admin@test.com", "adminpass", is_admin=True)
    user = auth_store.get_user_by_email("admin@test.com")
    assert user["is_admin"] is True
    assert user["team_id"] is None


def test_verify_password_correct(auth_store):
    user_id = auth_store.create_user("bob@test.com", "secret")
    assert auth_store.verify_password(user_id, "secret") is True


def test_verify_password_incorrect(auth_store):
    user_id = auth_store.create_user("bob@test.com", "secret")
    assert auth_store.verify_password(user_id, "wrong") is False


def test_create_api_key(auth_store):
    user_id = auth_store.create_user("carol@test.com", "pass")
    raw_key, key_hash = auth_store.create_api_key(user_id, "my-key")
    assert raw_key is not None
    assert key_hash is not None
    assert auth_store.validate_api_key(raw_key) is not None


def test_validate_api_key_returns_user(auth_store):
    user_id = auth_store.create_user("dave@test.com", "pass")
    raw_key, _ = auth_store.create_api_key(user_id, "key")
    user = auth_store.validate_api_key(raw_key)
    assert user["id"] == user_id


def test_revoke_api_key(auth_store):
    user_id = auth_store.create_user("eve@test.com", "pass")
    raw_key, key_hash = auth_store.create_api_key(user_id, "key")
    auth_store.revoke_api_key(key_hash)
    assert auth_store.validate_api_key(raw_key) is None


def test_duplicate_email_raises(auth_store):
    auth_store.create_user("dup@test.com", "pass")
    with pytest.raises(Exception):
        auth_store.create_user("dup@test.com", "pass2")
