import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.main import app
from backend.auth.jwt import create_access_token
from backend.db.mysql import get_db, Base
from backend.models import User, Team, TeamMember
from sqlalchemy.pool import StaticPool

# Setup in-memory SQLite database for admin tests
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(autouse=True)
def setup_db_and_dependencies():
    # Recreate tables cleanly for every single test
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)

client = TestClient(app)

def get_superadmin_headers():
    token = create_access_token({"sub": "test-admin", "role": "superadmin"})
    return {"Authorization": f"Bearer {token}"}

def get_user_headers():
    token = create_access_token({"sub": "test-user", "role": "user"})
    return {"Authorization": f"Bearer {token}"}

# --- Teams Tests ---

def test_create_team_as_superadmin():
    res = client.post("/api/admin/teams", json={"name": "TestTeam"}, headers=get_superadmin_headers())
    assert res.status_code == 200
    assert "team_id" in res.json()

def test_create_team_duplicate():
    # First creation
    res1 = client.post("/api/admin/teams", json={"name": "TestTeam"}, headers=get_superadmin_headers())
    assert res1.status_code == 200
    
    # Duplicate creation
    res2 = client.post("/api/admin/teams", json={"name": "TestTeam"}, headers=get_superadmin_headers())
    assert res2.status_code == 409

def test_create_team_as_user_forbidden():
    res = client.post("/api/admin/teams", json={"name": "TestTeam2"}, headers=get_user_headers())
    assert res.status_code == 403

def test_list_teams():
    # Insert a team first
    client.post("/api/admin/teams", json={"name": "TestTeam"}, headers=get_superadmin_headers())
    
    res = client.get("/api/admin/teams", headers=get_superadmin_headers())
    assert res.status_code == 200
    data = res.json()
    assert "teams" in data
    assert isinstance(data["teams"], list)
    assert len(data["teams"]) >= 1
    assert any(t["name"] == "TestTeam" for t in data["teams"])

def test_delete_team():
    # First create a temporary team
    create_res = client.post("/api/admin/teams", json={"name": "TempTeam"}, headers=get_superadmin_headers())
    team_id = create_res.json()["team_id"]
    
    # Delete it
    del_res = client.delete(f"/api/admin/teams/{team_id}", headers=get_superadmin_headers())
    assert del_res.status_code == 200
    
    # Verify 404
    del_res2 = client.delete(f"/api/admin/teams/{team_id}", headers=get_superadmin_headers())
    assert del_res2.status_code == 404

# --- Users Tests ---

def test_create_user_as_superadmin():
    res = client.post(
        "/api/admin/users",
        json={"email": "newuser@memmesh.com", "password": "securepassword", "global_role": "user"},
        headers=get_superadmin_headers()
    )
    assert res.status_code == 200
    assert "user_id" in res.json()

def test_create_user_duplicate():
    # First creation
    res1 = client.post(
        "/api/admin/users",
        json={"email": "newuser@memmesh.com", "password": "securepassword", "global_role": "user"},
        headers=get_superadmin_headers()
    )
    assert res1.status_code == 200

    # Duplicate creation
    res2 = client.post(
        "/api/admin/users",
        json={"email": "newuser@memmesh.com", "password": "anotherpassword"},
        headers=get_superadmin_headers()
    )
    assert res2.status_code == 409

def test_list_users():
    # Create user first
    client.post(
        "/api/admin/users",
        json={"email": "newuser@memmesh.com", "password": "securepassword", "global_role": "user"},
        headers=get_superadmin_headers()
    )
    
    res = client.get("/api/admin/users", headers=get_superadmin_headers())
    assert res.status_code == 200
    data = res.json()
    assert "users" in data
    assert len(data["users"]) >= 1
    assert any(u["email"] == "newuser@memmesh.com" for u in data["users"])

def test_delete_user():
    # Create temp user
    create_res = client.post(
        "/api/admin/users",
        json={"email": "tempuser@memmesh.com", "password": "password"},
        headers=get_superadmin_headers()
    )
    user_id = create_res.json()["user_id"]
    
    # Delete
    del_res = client.delete(f"/api/admin/users/{user_id}", headers=get_superadmin_headers())
    assert del_res.status_code == 200
    
    # Verify 404
    del_res2 = client.delete(f"/api/admin/users/{user_id}", headers=get_superadmin_headers())
    assert del_res2.status_code == 404

# --- Members Tests ---

def test_member_crud_flow():
    # Create team
    t_res = client.post("/api/admin/teams", json={"name": "MemberTestTeam"}, headers=get_superadmin_headers())
    team_id = t_res.json()["team_id"]

    # Create user
    u_res = client.post(
        "/api/admin/users",
        json={"email": "memberuser@memmesh.com", "password": "password"},
        headers=get_superadmin_headers()
    )
    user_id = u_res.json()["user_id"]

    # Add member
    add_res = client.post(
        "/api/admin/members",
        json={"team_id": team_id, "user_id": user_id, "role": "admin"},
        headers=get_superadmin_headers()
    )
    assert add_res.status_code == 200
    member_data = add_res.json()
    assert member_data["status"] == "added"
    assert member_data["team_id"] == team_id
    assert member_data["user_id"] == user_id
    assert member_data["role"] == "admin"

    # Add duplicate
    add_dup = client.post(
        "/api/admin/members",
        json={"team_id": team_id, "user_id": user_id, "role": "admin"},
        headers=get_superadmin_headers()
    )
    assert add_dup.status_code == 409

    # List members
    list_res = client.get(f"/api/admin/members?team_id={team_id}", headers=get_superadmin_headers())
    assert list_res.status_code == 200
    data = list_res.json()
    assert len(data["members"]) == 1
    assert data["members"][0]["user_id"] == user_id
    assert data["members"][0]["role"] == "admin"

    # Remove member
    rem_res = client.delete(f"/api/admin/members?team_id={team_id}&user_id={user_id}", headers=get_superadmin_headers())
    assert rem_res.status_code == 200

    # Remove member 404
    rem_res2 = client.delete(f"/api/admin/members?team_id={team_id}&user_id={user_id}", headers=get_superadmin_headers())
    assert rem_res2.status_code == 404
