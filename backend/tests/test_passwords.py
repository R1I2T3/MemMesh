# backend/tests/test_passwords.py
"""Unit tests for bcrypt password hashing."""

from auth.passwords import hash_password, verify_password


def test_hash_returns_string():
    hashed = hash_password("mypassword")
    assert isinstance(hashed, str)
    assert len(hashed) > 0


def test_hash_is_not_plaintext():
    password = "mypassword"
    hashed = hash_password(password)
    assert hashed != password


def test_verify_correct_password():
    password = "testpass123"
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True


def test_verify_wrong_password():
    hashed = hash_password("correctpassword")
    assert verify_password("wrongpassword", hashed) is False


def test_different_hashes_for_same_password():
    """bcrypt generates unique salts, so same password produces different hashes."""
    h1 = hash_password("samepassword")
    h2 = hash_password("samepassword")
    assert h1 != h2


def test_verify_empty_password():
    password = ""
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True


def test_verify_malformed_hash_returns_false():
    assert verify_password("password", "invalid-hash-string") is False
    assert verify_password("password", "") is False
