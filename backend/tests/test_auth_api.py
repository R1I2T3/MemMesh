# backend/tests/test_auth_api.py
"""API tests for authentication endpoints."""


def test_login_success(client):
    response = client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "changeme"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client):
    response = client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_nonexistent_user(client):
    response = client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "whatever"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_missing_fields(client):
    response = client.post("/auth/login", json={"email": "admin@example.com"})
    assert response.status_code == 422  # Validation error


def test_refresh_token_success(client):
    # First login to get a refresh token
    login_resp = client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "changeme"},
    )
    refresh_token = login_resp.json()["refresh_token"]

    # Use the refresh token
    response = client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_refresh_token_invalid(client):
    response = client.post(
        "/auth/refresh",
        json={"refresh_token": "invalid.token.here"},
    )
    assert response.status_code == 401


def test_protected_endpoint_without_token(client):
    """Verify that accessing a protected endpoint without a token returns 401 (since we set auto_error=False)."""
    response = client.get("/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_protected_endpoint_with_valid_token(client):
    # Login first
    login_resp = client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "changeme"},
    )
    token = login_resp.json()["access_token"]

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "admin@example.com"
    assert data["global_role"] == "superadmin"


def test_protected_endpoint_with_expired_token(client):
    from auth.jwt import create_access_token

    expired_token = create_access_token(
        user_id="user-1",
        global_role="user",
        team_memberships=[],
        expiry_minutes=-1,
    )
    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401


def test_refresh_token_used_as_access_token_fails(client):
    # Login to get tokens
    login_resp = client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "changeme"},
    )
    refresh_token = login_resp.json()["refresh_token"]

    # Try to access a protected endpoint using the refresh token as an Authorization header
    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {refresh_token}"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


def test_access_token_used_as_refresh_token_fails(client):
    # Login to get tokens
    login_resp = client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "changeme"},
    )
    access_token = login_resp.json()["access_token"]

    # Try to refresh using the access token as the refresh token
    response = client.post(
        "/auth/refresh",
        json={"refresh_token": access_token},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired refresh token"


def test_refresh_token_fails_after_user_deletion(client):
    # Login to get tokens
    login_resp = client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "changeme"},
    )
    refresh_token = login_resp.json()["refresh_token"]

    # Delete the user from the database
    from db.sqlite import get_connection

    conn = get_connection()
    try:
        with conn:
            conn.execute("DELETE FROM users WHERE email = ?", ("admin@example.com",))
    finally:
        conn.close()

    # Try to refresh the token — should now fail because the user does not exist in the DB
    response = client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "User not found or deactivated"

    # Re-run seeder to restore database clean state for downstream tests
    from db.sqlite import seed_admin

    seed_admin()
