# backend/tests/test_teams_api.py
"""Integration and unit tests for administrative Teams CRUD endpoints."""

import pytest

from auth.jwt import create_access_token
from db.sqlite import get_connection


def create_test_user(user_id: str, email: str):
    """Insert a test user into the database."""
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                "INSERT INTO users (user_id, email, password_hash, global_role) VALUES (?, ?, 'fake-hash', 'user')",
                (user_id, email),
            )
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def clean_teams():
    """Ensure teams and users tables are clean before and after each test."""
    def clean():
        conn = get_connection()
        try:
            with conn:
                conn.execute("DELETE FROM team_members")
                conn.execute("DELETE FROM teams")
                conn.execute("DELETE FROM users WHERE email != 'admin@example.com'")
        finally:
            conn.close()
    clean()
    yield
    clean()


@pytest.fixture()
def admin_headers():
    create_test_user("admin-user-123", "admin_user@test.com")
    token = create_access_token(user_id="admin-user-123", global_role="admin", team_memberships=[])
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def superadmin_headers():
    create_test_user("super-user-123", "super_user@test.com")
    token = create_access_token(user_id="super-user-123", global_role="superadmin", team_memberships=[])
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def user_headers():
    create_test_user("std-user-123", "std_user@test.com")
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


def test_add_member_and_lead_success(client, admin_headers):
    """Verify successfully adding a user as a member and team lead."""
    # 1. Create team
    team_resp = client.post(
        "/admin/teams",
        json={"name": "Engineering Team"},
        headers=admin_headers,
    )
    assert team_resp.status_code == 201
    team_id = team_resp.json()["team_id"]

    # 2. Create users
    create_test_user("user-id-1", "user1@test.com")
    create_test_user("user-id-2", "user2@test.com")

    # 3. Add user 1 as member (role="user")
    resp1 = client.post(
        f"/admin/teams/{team_id}/members",
        json={"user_id": "user-id-1", "role": "user"},
        headers=admin_headers,
    )
    assert resp1.status_code == 201
    data1 = resp1.json()
    assert data1["user_id"] == "user-id-1"
    assert data1["email"] == "user1@test.com"
    assert data1["role"] == "user"

    # 4. Add user 2 as team lead (role="lead")
    resp2 = client.post(
        f"/admin/teams/{team_id}/members",
        json={"user_id": "user-id-2", "role": "lead"},
        headers=admin_headers,
    )
    assert resp2.status_code == 201
    data2 = resp2.json()
    assert data2["user_id"] == "user-id-2"
    assert data2["email"] == "user2@test.com"
    assert data2["role"] == "lead"


def test_add_member_nonexistent_team_fails(client, admin_headers):
    """Verify adding a user to a nonexistent team returns 404 'Team not found'."""
    create_test_user("user-id-1", "user1@test.com")

    resp = client.post(
        "/admin/teams/nonexistent-team-uuid/members",
        json={"user_id": "user-id-1", "role": "user"},
        headers=admin_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Team not found"


def test_add_member_nonexistent_user_fails(client, admin_headers):
    """Verify adding a nonexistent user to a team returns 404 'User not found'."""
    team_resp = client.post(
        "/admin/teams",
        json={"name": "Engineering Team"},
        headers=admin_headers,
    )
    team_id = team_resp.json()["team_id"]

    resp = client.post(
        f"/admin/teams/{team_id}/members",
        json={"user_id": "nonexistent-user-uuid", "role": "user"},
        headers=admin_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "User not found"


def test_add_member_duplicate_ok(client, admin_headers):
    """Verify adding a duplicate member returns 201 (upsert is supported)."""
    team_resp = client.post(
        "/admin/teams",
        json={"name": "Engineering Team"},
        headers=admin_headers,
    )
    team_id = team_resp.json()["team_id"]
    create_test_user("user-id-1", "user1@test.com")

    # Add first time
    resp1 = client.post(
        f"/admin/teams/{team_id}/members",
        json={"user_id": "user-id-1", "role": "user"},
        headers=admin_headers,
    )
    assert resp1.status_code == 201

    # Add second time (same role)
    resp2 = client.post(
        f"/admin/teams/{team_id}/members",
        json={"user_id": "user-id-1", "role": "user"},
        headers=admin_headers,
    )
    assert resp2.status_code == 201
    assert resp2.json()["role"] == "user"


def test_add_member_invalid_role_fails(client, admin_headers):
    """Verify adding a member with an invalid role returns 422."""
    team_resp = client.post(
        "/admin/teams",
        json={"name": "Engineering Team"},
        headers=admin_headers,
    )
    team_id = team_resp.json()["team_id"]
    create_test_user("user-id-1", "user1@test.com")

    # Invalid roles
    for role in ["admin", "superadmin", "lead-user", ""]:
        resp = client.post(
            f"/admin/teams/{team_id}/members",
            json={"user_id": "user-id-1", "role": role},
            headers=admin_headers,
        )
        assert resp.status_code == 422


def test_list_team_members_success(client, admin_headers):
    """Verify successfully listing all members of a team (returns correct list with emails)."""
    team_resp = client.post(
        "/admin/teams",
        json={"name": "Engineering Team"},
        headers=admin_headers,
    )
    team_id = team_resp.json()["team_id"]

    create_test_user("user-id-1", "user1@test.com")
    create_test_user("user-id-2", "user2@test.com")

    # Add both to team
    client.post(
        f"/admin/teams/{team_id}/members",
        json={"user_id": "user-id-1", "role": "user"},
        headers=admin_headers,
    )
    client.post(
        f"/admin/teams/{team_id}/members",
        json={"user_id": "user-id-2", "role": "lead"},
        headers=admin_headers,
    )

    # Get members
    resp = client.get(f"/admin/teams/{team_id}/members", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    
    # Check details
    m1 = next(x for x in data if x["user_id"] == "user-id-1")
    assert m1["email"] == "user1@test.com"
    assert m1["role"] == "user"

    m2 = next(x for x in data if x["user_id"] == "user-id-2")
    assert m2["email"] == "user2@test.com"
    assert m2["role"] == "lead"


def test_list_team_members_nonexistent_team_fails(client, admin_headers):
    """Verify listing members of a nonexistent team returns 404."""
    resp = client.get("/admin/teams/nonexistent-team-uuid/members", headers=admin_headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Team not found"


def test_remove_team_member_success(client, admin_headers):
    """Verify successfully removing a member from a team."""
    team_resp = client.post(
        "/admin/teams",
        json={"name": "Engineering Team"},
        headers=admin_headers,
    )
    team_id = team_resp.json()["team_id"]
    create_test_user("user-id-1", "user1@test.com")

    # Add user
    client.post(
        f"/admin/teams/{team_id}/members",
        json={"user_id": "user-id-1", "role": "user"},
        headers=admin_headers,
    )

    # Delete user
    del_resp = client.delete(
        f"/admin/teams/{team_id}/members/user-id-1",
        headers=admin_headers,
    )
    assert del_resp.status_code == 204

    # Verify empty
    get_resp = client.get(f"/admin/teams/{team_id}/members", headers=admin_headers)
    assert len(get_resp.json()) == 0


def test_remove_team_member_nonexistent_fails(client, admin_headers):
    """Verify removing a nonexistent member from a team returns 404 'Member not found'."""
    team_resp = client.post(
        "/admin/teams",
        json={"name": "Engineering Team"},
        headers=admin_headers,
    )
    team_id = team_resp.json()["team_id"]

    # Delete nonexistent user ID
    del_resp1 = client.delete(
        f"/admin/teams/{team_id}/members/nonexistent-user-uuid",
        headers=admin_headers,
    )
    assert del_resp1.status_code == 404
    assert del_resp1.json()["detail"] == "Member not found"

    # Delete existing user who is not in the team
    create_test_user("user-id-2", "user2@test.com")
    del_resp2 = client.delete(
        f"/admin/teams/{team_id}/members/user-id-2",
        headers=admin_headers,
    )
    assert del_resp2.status_code == 404
    assert del_resp2.json()["detail"] == "Member not found"


def test_member_endpoints_reject_unauthorized(client, user_headers):
    """Verify that unauthorized (non-admin) requests to all these member routes are rejected."""
    # POST
    resp_post_unauth = client.post("/admin/teams/some-team/members", json={"user_id": "user-id", "role": "user"})
    assert resp_post_unauth.status_code == 401
    
    resp_post_user = client.post("/admin/teams/some-team/members", json={"user_id": "user-id", "role": "user"}, headers=user_headers)
    assert resp_post_user.status_code == 403

    # GET
    resp_get_unauth = client.get("/admin/teams/some-team/members")
    assert resp_get_unauth.status_code == 401
    
    resp_get_user = client.get("/admin/teams/some-team/members", headers=user_headers)
    assert resp_get_user.status_code == 403

    # DELETE
    resp_del_unauth = client.delete("/admin/teams/some-team/members/user-id")
    assert resp_del_unauth.status_code == 401
    
    resp_del_user = client.delete("/admin/teams/some-team/members/user-id", headers=user_headers)
    assert resp_del_user.status_code == 403


def test_list_users_success(client, admin_headers):
    """Verify that an admin can successfully list all users in the system."""
    create_test_user("user-id-1", "user1@test.com")
    create_test_user("user-id-2", "user2@test.com")

    response = client.get("/admin/users", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    
    # We should have admin, user1, user2, plus the admin-user-123 created in fixture
    assert len(data) >= 3
    emails = {user["email"] for user in data}
    assert "user1@test.com" in emails
    assert "user2@test.com" in emails
    
    # Verify field structure
    user1 = next(u for u in data if u["user_id"] == "user-id-1")
    assert user1["email"] == "user1@test.com"
    assert user1["global_role"] == "user"
    assert "created_at" in user1


def test_list_users_superadmin_success(client, superadmin_headers):
    """Verify that a superadmin can successfully list all users in the system."""
    response = client.get("/admin/users", headers=superadmin_headers)
    assert response.status_code == 200


def test_list_users_reject_unauthenticated(client):
    """Verify that listing users rejects unauthenticated requests with 401."""
    response = client.get("/admin/users")
    assert response.status_code == 401


def test_list_users_reject_non_admin(client, user_headers):
    """Verify that listing users rejects non-admin users with 403."""
    response = client.get("/admin/users", headers=user_headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_add_member_upsert_role(client, admin_headers):
    """Verify that adding an existing member again with a different role updates their role (upsert)."""
    # 1. Create team
    team_resp = client.post(
        "/admin/teams",
        json={"name": "Engineering Team"},
        headers=admin_headers,
    )
    assert team_resp.status_code == 201
    team_id = team_resp.json()["team_id"]

    # 2. Create user
    create_test_user("user-id-upsert", "upsert@test.com")

    # 3. Add as user
    resp1 = client.post(
        f"/admin/teams/{team_id}/members",
        json={"user_id": "user-id-upsert", "role": "user"},
        headers=admin_headers,
    )
    assert resp1.status_code == 201
    assert resp1.json()["role"] == "user"

    # 4. Upsert/Promote to lead
    resp2 = client.post(
        f"/admin/teams/{team_id}/members",
        json={"user_id": "user-id-upsert", "role": "lead"},
        headers=admin_headers,
    )
    assert resp2.status_code == 201
    assert resp2.json()["role"] == "lead"

    # 5. Check in list
    list_resp = client.get(f"/admin/teams/{team_id}/members", headers=admin_headers)
    assert list_resp.status_code == 200
    members = list_resp.json()
    assert len(members) == 1
    assert members[0]["user_id"] == "user-id-upsert"
    assert members[0]["role"] == "lead"

