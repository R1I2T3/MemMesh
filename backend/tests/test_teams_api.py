# backend/tests/test_teams_api.py
"""Integration and unit tests for administrative Teams CRUD endpoints."""

import pytest

from auth.jwt import create_access_token
from db.sqlite import get_connection


@pytest.fixture(autouse=True)
def clean_teams():
    """Ensure teams table is empty before and after each test for isolation."""
    conn = get_connection()
    try:
        with conn:
            conn.execute("DELETE FROM teams")
    finally:
        conn.close()
    yield
    conn = get_connection()
    try:
        with conn:
            conn.execute("DELETE FROM teams")
    finally:
        conn.close()


@pytest.fixture()
def admin_headers():
    token = create_access_token(user_id="admin-user-123", global_role="admin", team_memberships=[])
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def superadmin_headers():
    token = create_access_token(user_id="super-user-123", global_role="superadmin", team_memberships=[])
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def user_headers():
    token = create_access_token(user_id="std-user-123", global_role="user", team_memberships=[])
    return {"Authorization": f"Bearer {token}"}


def test_create_team_success(client, admin_headers):
    """Verify that an admin can successfully create a new team."""
    response = client.post(
        "/admin/teams",
        json={"name": "Alpha Team", "description": "The elite alpha squad"},
        headers=admin_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert "team_id" in data
    assert data["name"] == "Alpha Team"
    assert data["description"] == "The elite alpha squad"
    assert "created_at" in data

    # Verify db entry
    conn = get_connection()
    row = conn.execute("SELECT * FROM teams WHERE name = 'Alpha Team'").fetchone()
    conn.close()
    assert row is not None
    assert row["team_id"] == data["team_id"]


def test_create_team_superadmin_success(client, superadmin_headers):
    """Verify that a superadmin can successfully create a new team."""
    response = client.post(
        "/admin/teams",
        json={"name": "Beta Team", "description": "Beta testing team"},
        headers=superadmin_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Beta Team"


def test_create_team_duplicate_name_fails(client, admin_headers):
    """Verify that creating a team with a duplicate name is rejected with 400."""
    # Create first team
    response = client.post(
        "/admin/teams",
        json={"name": "Duplicate Team", "description": "First version"},
        headers=admin_headers,
    )
    assert response.status_code == 201

    # Attempt to create duplicate team
    response = client.post(
        "/admin/teams",
        json={"name": "Duplicate Team", "description": "Second version"},
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Team name already exists"


def test_get_all_teams(client, admin_headers):
    """Verify that listing teams retrieves all stored teams correctly."""
    # Create multiple teams
    client.post("/admin/teams", json={"name": "Team One"}, headers=admin_headers)
    client.post("/admin/teams", json={"name": "Team Two"}, headers=admin_headers)

    response = client.get("/admin/teams", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    names = {team["name"] for team in data}
    assert names == {"Team One", "Team Two"}


def test_delete_team_success(client, admin_headers):
    """Verify that a team can be deleted by its ID."""
    # Create a team first
    create_resp = client.post(
        "/admin/teams",
        json={"name": "To Be Deleted"},
        headers=admin_headers,
    )
    team_id = create_resp.json()["team_id"]

    # Delete team
    delete_resp = client.delete(f"/admin/teams/{team_id}", headers=admin_headers)
    assert delete_resp.status_code == 204

    # Verify team is no longer in the list
    list_resp = client.get("/admin/teams", headers=admin_headers)
    assert len(list_resp.json()) == 0

    # Verify db is empty
    conn = get_connection()
    row = conn.execute("SELECT * FROM teams WHERE team_id = ?", (team_id,)).fetchone()
    conn.close()
    assert row is None


def test_delete_team_nonexistent_returns_404(client, admin_headers):
    """Verify that deleting a non-existent team returns 404."""
    response = client.delete("/admin/teams/non-existent-uuid-123", headers=admin_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Team not found"


def test_endpoints_reject_unauthenticated(client):
    """Verify that all admin teams endpoints reject unauthenticated requests with 401."""
    # POST
    resp_post = client.post("/admin/teams", json={"name": "Unauth Team"})
    assert resp_post.status_code == 401

    # GET
    resp_get = client.get("/admin/teams")
    assert resp_get.status_code == 401

    # DELETE
    resp_delete = client.delete("/admin/teams/some-uuid")
    assert resp_delete.status_code == 401


def test_endpoints_reject_non_admin(client, user_headers):
    """Verify that non-admin (standard) users are rejected with 403."""
    # POST
    resp_post = client.post(
        "/admin/teams",
        json={"name": "User Created Team"},
        headers=user_headers,
    )
    assert resp_post.status_code == 403
    assert resp_post.json()["detail"] == "Insufficient permissions"

    # GET
    resp_get = client.get("/admin/teams", headers=user_headers)
    assert resp_get.status_code == 403
    assert resp_get.json()["detail"] == "Insufficient permissions"

    # DELETE
    resp_delete = client.delete("/admin/teams/some-uuid", headers=user_headers)
    assert resp_delete.status_code == 403
    assert resp_delete.json()["detail"] == "Insufficient permissions"
