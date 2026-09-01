import os
import sys
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app
from backend.database import db
from backend.models import User, Organization, OrganizationMember, Team, TeamMember, Board, Column
from backend.auth import create_access_token


@pytest.fixture(autouse=True)
def admin_test_db(test_db):
    """Admin tests need their own database isolation"""
    # Clean the database completely
    db.drop_tables([Board, Column, TeamMember, Team, OrganizationMember, Organization, User])
    db.create_tables([User, Organization, OrganizationMember, Team, TeamMember, Board, Column])
    yield test_db


@pytest.fixture
def admin_user(admin_test_db):
    """Create an admin user"""
    import random
    import string
    random_suffix = ''.join(random.choices(string.ascii_lowercase, k=8))
    username = f"admin_{random_suffix}"
    user = User.create_user(username=username, password="admin123", admin=True)
    return user


@pytest.fixture
def regular_user(admin_test_db):
    """Create a regular user"""
    import random
    import string
    random_suffix = ''.join(random.choices(string.ascii_lowercase, k=8))
    username = f"user_{random_suffix}"
    user = User.create_user(username=username, password="user123", admin=False)
    return user


@pytest.fixture
def admin_token(admin_user):
    """Create admin token"""
    return create_access_token(data={"sub": admin_user.id, "username": admin_user.username})


@pytest.fixture
def regular_token(regular_user):
    """Create regular user token"""
    return create_access_token(data={"sub": regular_user.id, "username": regular_user.username})


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


def test_admin_status_admin(client, admin_token):
    """Admin user can check admin status"""
    response = client.get("/api/admin/status", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    assert response.json()["is_admin"] is True


def test_admin_status_regular_user(client, regular_token):
    """Regular user can check admin status"""
    response = client.get("/api/admin/status", headers={"Authorization": f"Bearer {regular_token}"})
    assert response.status_code == 200
    assert response.json()["is_admin"] is False


def test_list_users_requires_admin(client, regular_token):
    """Regular users cannot list all users"""
    response = client.get("/api/admin/users", headers={"Authorization": f"Bearer {regular_token}"})
    assert response.status_code == 403


def test_list_users_admin(client, admin_token, admin_user, regular_user):
    """Admin can list all users"""
    response = client.get("/api/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    users = response.json()
    assert len(users) == 2
    usernames = [u["username"] for u in users]
    assert admin_user.username in usernames
    assert regular_user.username in usernames


def test_create_user_requires_admin(client, regular_token):
    """Regular users cannot create users"""
    response = client.post(
        "/api/admin/users",
        json={"username": "newuser", "password": "password123"},
        headers={"Authorization": f"Bearer {regular_token}"}
    )
    assert response.status_code == 403


def test_create_user_admin(client, admin_token):
    """Admin can create a new user"""
    response = client.post(
        "/api/admin/users",
        json={"username": "newuser", "password": "password123", "email": "new@test.com"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert response.json()["username"] == "newuser"
    assert response.json()["email"] == "new@test.com"
    assert response.json()["admin"] is False

    # Verify user exists in database
    user = User.get_or_none(User.username == "newuser")
    assert user is not None


def test_create_admin_user(client, admin_token):
    """Admin can create another admin user"""
    response = client.post(
        "/api/admin/users",
        json={"username": "admin2", "password": "password123", "admin": True},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert response.json()["admin"] is True


def test_update_user_requires_admin(client, regular_token, admin_user):
    """Regular users cannot update users"""
    response = client.put(
        f"/api/admin/users/{admin_user.id}",
        json={"username": "hacked"},
        headers={"Authorization": f"Bearer {regular_token}"}
    )
    assert response.status_code == 403


def test_update_user_admin(client, admin_token, regular_user):
    """Admin can update users"""
    response = client.put(
        f"/api/admin/users/{regular_user.id}",
        json={"username": "updated", "email": "updated@test.com", "admin": True},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert response.json()["username"] == "updated"
    assert response.json()["email"] == "updated@test.com"
    assert response.json()["admin"] is True


def test_update_user_cannot_remove_own_admin(client, admin_token, admin_user):
    """Admin cannot remove their own admin access"""
    response = client.put(
        f"/api/admin/users/{admin_user.id}",
        json={"username": admin_user.username, "admin": False},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 400


def test_delete_user_requires_admin(client, regular_token, admin_user):
    """Regular users cannot delete users"""
    response = client.delete(
        f"/api/admin/users/{admin_user.id}",
        headers={"Authorization": f"Bearer {regular_token}"}
    )
    assert response.status_code == 403


def test_delete_user_admin(client, admin_token, regular_user):
    """Admin can delete users"""
    user_id = regular_user.id
    response = client.delete(
        f"/api/admin/users/{user_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200

    # Verify user is deleted
    assert User.get_or_none(User.id == user_id) is None


def test_delete_user_cannot_delete_self(client, admin_token, admin_user):
    """Admin cannot delete themselves"""
    response = client.delete(
        f"/api/admin/users/{admin_user.id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 400


def test_reset_password_requires_admin(client, regular_token, admin_user):
    """Regular users cannot reset passwords"""
    response = client.post(
        f"/api/admin/users/{admin_user.id}/reset-password",
        json={"password": "newpassword"},
        headers={"Authorization": f"Bearer {regular_token}"}
    )
    assert response.status_code == 403


def test_reset_password_admin(client, admin_token, regular_user):
    """Admin can reset user passwords"""
    response = client.post(
        f"/api/admin/users/{regular_user.id}/reset-password",
        json={"password": "newpassword123"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200

    # Re-fetch user from database to verify password was changed
    user = User.get_by_id(regular_user.id)
    assert user.verify_password("newpassword123")


def test_reset_password_too_long(client, admin_token, regular_user):
    """Password reset fails if password is too long"""
    response = client.post(
        f"/api/admin/users/{regular_user.id}/reset-password",
        json={"password": "x" * 100},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 400


# Admin organization management tests
def test_list_organizations_requires_admin(client, regular_token):
    """Regular users cannot list all organizations"""
    response = client.get("/api/admin/organizations", headers={"Authorization": f"Bearer {regular_token}"})
    assert response.status_code == 403


def test_list_organizations_admin(client, admin_token, regular_token):
    """Admin can list all organizations"""
    # Create some test organizations
    response = client.post(
        "/api/organizations",
        json={"name": "Test Org 1"},
        headers={"Authorization": f"Bearer {regular_token}"}
    )
    org1_id = response.json()["id"]

    response = client.get("/api/admin/organizations", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    orgs = response.json()
    assert len(orgs) >= 1
    assert any(o["name"] == "Test Org 1" for o in orgs)


def test_create_organization_requires_admin(client, regular_token, admin_user):
    """Regular users cannot create organizations for others via admin API"""
    response = client.post(
        "/api/admin/organizations",
        json={"name": "Admin Org", "owner_id": admin_user.id},
        headers={"Authorization": f"Bearer {regular_token}"}
    )
    assert response.status_code == 403


def test_create_organization_admin(client, admin_token, regular_user):
    """Admin can create organization for any user"""
    response = client.post(
        "/api/admin/organizations",
        json={"name": "Admin Created Org", "owner_id": regular_user.id},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    org = response.json()
    assert org["name"] == "Admin Created Org"
    assert org["owner_id"] == regular_user.id
    assert org["owner_username"] == regular_user.username


def test_create_organization_invalid_owner(client, admin_token):
    """Organization creation fails with invalid owner"""
    response = client.post(
        "/api/admin/organizations",
        json={"name": "Bad Org", "owner_id": 99999},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 404


def test_update_organization_requires_admin(client, regular_token, admin_user):
    """Regular users cannot update organizations via admin API"""
    response = client.put(
        f"/api/admin/organizations/{admin_user.id}",
        json={"name": "Hacked", "owner_id": admin_user.id},
        headers={"Authorization": f"Bearer {regular_token}"}
    )
    assert response.status_code == 403


def test_update_organization_admin(client, admin_token, regular_user, admin_user):
    """Admin can update organization"""
    # Create organization
    response = client.post(
        "/api/admin/organizations",
        json={"name": "Original Name", "owner_id": admin_user.id},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    org_id = response.json()["id"]

    # Update it
    response = client.put(
        f"/api/admin/organizations/{org_id}",
        json={"name": "Updated Name", "owner_id": regular_user.id},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    org = response.json()
    assert org["name"] == "Updated Name"
    assert org["owner_id"] == regular_user.id


def test_update_organization_invalid_owner(client, admin_token, admin_user):
    """Organization update fails with invalid owner"""
    response = client.put(
        f"/api/admin/organizations/{admin_user.id}",
        json={"name": "Test", "owner_id": 99999},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 404


def test_delete_organization_requires_admin(client, regular_token, admin_user):
    """Regular users cannot delete organizations via admin API"""
    response = client.delete(
        f"/api/admin/organizations/{admin_user.id}",
        headers={"Authorization": f"Bearer {regular_token}"}
    )
    assert response.status_code == 403


def test_delete_organization_admin(client, admin_token, regular_user):
    """Admin can delete organization"""
    # Create organization
    response = client.post(
        "/api/admin/organizations",
        json={"name": "To Delete", "owner_id": regular_user.id},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    org_id = response.json()["id"]

    # Delete it
    response = client.delete(
        f"/api/admin/organizations/{org_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200

    # Verify it's deleted
    from backend.models import Organization
    assert Organization.get_or_none(Organization.id == org_id) is None


# Admin team management tests
def test_list_teams_requires_admin(client, regular_token):
    """Regular users cannot list all teams"""
    response = client.get("/api/admin/teams", headers={"Authorization": f"Bearer {regular_token}"})
    assert response.status_code == 403


def test_list_teams_admin(client, admin_token, admin_user):
    """Admin can list all teams"""
    # Create organization and team
    response = client.post(
        "/api/admin/organizations",
        json={"name": "Test Org", "owner_id": admin_user.id},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    org_id = response.json()["id"]

    response = client.get("/api/admin/teams", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    teams = response.json()
    assert len(teams) >= 1
    assert any(t["name"] == "Administrators" for t in teams)


def test_create_team_requires_admin(client, regular_token, admin_user):
    """Regular users cannot create teams via admin API"""
    response = client.post(
        "/api/admin/teams",
        json={"name": "Admin Team", "organization_id": admin_user.id},
        headers={"Authorization": f"Bearer {regular_token}"}
    )
    assert response.status_code == 403


def test_create_team_admin(client, admin_token, admin_user):
    """Admin can create team for any organization"""
    # Create organization
    response = client.post(
        "/api/admin/organizations",
        json={"name": "Test Org", "owner_id": admin_user.id},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    org_id = response.json()["id"]

    # Create team
    response = client.post(
        "/api/admin/teams",
        json={"name": "Admin Created Team", "organization_id": org_id},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    team = response.json()
    assert team["name"] == "Admin Created Team"
    assert team["organization_id"] == org_id


def test_create_team_invalid_organization(client, admin_token):
    """Team creation fails with invalid organization"""
    response = client.post(
        "/api/admin/teams",
        json={"name": "Bad Team", "organization_id": 99999},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 404


def test_update_team_requires_admin(client, regular_token):
    """Regular users cannot update teams via admin API"""
    response = client.put(
        "/api/admin/teams/1",
        json={"name": "Hacked", "organization_id": 1},
        headers={"Authorization": f"Bearer {regular_token}"}
    )
    assert response.status_code == 403


def test_update_team_admin(client, admin_token, admin_user, regular_user):
    """Admin can update team and transfer organization"""
    # Create two orgs
    response = client.post(
        "/api/admin/organizations",
        json={"name": "Org 1", "owner_id": admin_user.id},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    org1_id = response.json()["id"]

    response = client.post(
        "/api/admin/organizations",
        json={"name": "Org 2", "owner_id": regular_user.id},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    org2_id = response.json()["id"]

    # Create team in first org
    response = client.post(
        "/api/admin/teams",
        json={"name": "Original Team", "organization_id": org1_id},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    team_id = response.json()["id"]

    # Update to second org
    response = client.put(
        f"/api/admin/teams/{team_id}",
        json={"name": "Updated Team", "organization_id": org2_id},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    team = response.json()
    assert team["name"] == "Updated Team"
    assert team["organization_id"] == org2_id


def test_update_team_invalid_organization(client, admin_token):
    """Team update fails with invalid organization"""
    response = client.put(
        "/api/admin/teams/1",
        json={"name": "Test", "organization_id": 99999},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 404


def test_delete_team_requires_admin(client, regular_token):
    """Regular users cannot delete teams via admin API"""
    response = client.delete(
        "/api/admin/teams/1",
        headers={"Authorization": f"Bearer {regular_token}"}
    )
    assert response.status_code == 403


def test_delete_team_admin(client, admin_token, admin_user):
    """Admin can delete team"""
    # Create organization first
    response = client.post(
        "/api/admin/organizations",
        json={"name": "Test Org for Delete", "owner_id": admin_user.id},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    org_id = response.json()["id"]

    # Create team
    response = client.post(
        "/api/admin/teams",
        json={"name": "To Delete", "organization_id": org_id},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    team_id = response.json()["id"]

    # Delete it
    response = client.delete(
        f"/api/admin/teams/{team_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200

    # Verify it's deleted
    from backend.models import Team
    assert Team.get_or_none(Team.id == team_id) is None


# Admin board management tests
def test_list_boards_requires_admin(client, regular_token):
    """Regular users cannot list all boards"""
    response = client.get("/api/admin/boards", headers={"Authorization": f"Bearer {regular_token}"})
    assert response.status_code == 403


def test_list_boards_admin(client, admin_token, admin_user):
    """Admin can list all boards"""
    # Create a board
    response = client.post(
        "/api/admin/boards",
        json={"name": "Admin Board", "owner_id": admin_user.id},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    board1_id = response.json()["id"]

    response = client.get("/api/admin/boards", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    boards = response.json()
    assert len(boards) >= 1
    assert any(b["name"] == "Admin Board" for b in boards)
    # Note: API no longer creates default columns, so column_count is 0


def test_create_board_requires_admin(client, regular_token, admin_user):
    """Regular users cannot create boards via admin API"""
    response = client.post(
        "/api/admin/boards",
        json={"name": "Admin Board", "owner_id": admin_user.id},
        headers={"Authorization": f"Bearer {regular_token}"}
    )
    assert response.status_code == 403


def test_create_board_admin(client, admin_token, regular_user):
    """Admin can create board for any user"""
    response = client.post(
        "/api/admin/boards",
        json={"name": "Admin Created Board", "owner_id": regular_user.id},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    board = response.json()
    assert board["name"] == "Admin Created Board"
    assert board["owner_id"] == regular_user.id
    assert board["owner_username"] == regular_user.username
    # Note: API no longer creates default columns, so column_count is 0


def test_create_board_invalid_owner(client, admin_token):
    """Board creation fails with invalid owner"""
    response = client.post(
        "/api/admin/boards",
        json={"name": "Bad Board", "owner_id": 99999},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 404


def test_update_board_requires_admin(client, regular_token):
    """Regular users cannot update boards via admin API"""
    response = client.put(
        "/api/admin/boards/1",
        json={"name": "Hacked"},
        headers={"Authorization": f"Bearer {regular_token}"}
    )
    assert response.status_code == 403


def test_update_board_admin(client, admin_token, admin_user):
    """Admin can update board name"""
    # Create board
    response = client.post(
        "/api/admin/boards",
        json={"name": "Original Name", "owner_id": admin_user.id},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    board_id = response.json()["id"]

    # Update it
    response = client.put(
        f"/api/admin/boards/{board_id}",
        json={"name": "Updated Name"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    board = response.json()
    assert board["name"] == "Updated Name"


def test_delete_board_requires_admin(client, regular_token, admin_user):
    """Regular users cannot delete boards via admin API"""
    response = client.delete(
        "/api/admin/boards/1",
        headers={"Authorization": f"Bearer {regular_token}"}
    )
    assert response.status_code == 403


def test_delete_board_admin(client, admin_token, admin_user):
    """Admin can delete board"""
    # Create board
    response = client.post(
        "/api/admin/boards",
        json={"name": "To Delete", "owner_id": admin_user.id},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    board_id = response.json()["id"]

    # Delete it
    response = client.delete(
        f"/api/admin/boards/{board_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200

    # Verify it's deleted
    from backend.models import Board
    assert Board.get_or_none(Board.id == board_id) is None


# Admin team member management tests

def test_list_team_members_requires_admin(client, regular_token, admin_token, admin_user):
    """Regular users cannot list team members via admin API"""
    # Create organization and team
    org = Organization.create_with_columns(name="Test Org", slug="test-org", owner=admin_user)
    team = Team.create_with_columns(name="Test Team", organization=org)
    OrganizationMember.create(user=admin_user, organization=org, joined_at=datetime.now())

    response = client.get(
        f"/api/admin/teams/{team.id}/members",
        headers={"Authorization": f"Bearer {regular_token}"}
    )
    assert response.status_code == 403


def test_list_team_members_admin(client, admin_token, admin_user, regular_user):
    """Admin can list team members"""
    # Create organization and team
    org = Organization.create_with_columns(name="Test Org", slug="test-org", owner=admin_user)
    team = Team.create_with_columns(name="Test Team", organization=org)
    OrganizationMember.create(user=admin_user, organization=org, joined_at=datetime.now())
    OrganizationMember.create(user=regular_user, organization=org, joined_at=datetime.now())
    TeamMember.create(user=admin_user, team=team, joined_at=datetime.now())
    TeamMember.create(user=regular_user, team=team, joined_at=datetime.now())

    response = client.get(
        f"/api/admin/teams/{team.id}/members",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    members = response.json()
    assert len(members) == 2
    usernames = {m["username"] for m in members}
    assert usernames == {admin_user.username, regular_user.username}


def test_list_available_team_members_requires_admin(client, regular_token):
    """Regular users cannot list available team members via admin API"""
    response = client.get(
        "/api/admin/teams/1/available-members",
        headers={"Authorization": f"Bearer {regular_token}"}
    )
    assert response.status_code == 403


def test_list_available_team_members_admin(client, admin_token, admin_user, regular_user):
    """Admin can list available team members"""
    # Create organization and team
    org = Organization.create_with_columns(name="Test Org", slug="test-org", owner=admin_user)
    team = Team.create_with_columns(name="Test Team", organization=org)
    OrganizationMember.create(user=admin_user, organization=org, joined_at=datetime.now())
    OrganizationMember.create(user=regular_user, organization=org, joined_at=datetime.now())
    TeamMember.create(user=admin_user, team=team, joined_at=datetime.now())  # admin is already on the team

    response = client.get(
        f"/api/admin/teams/{team.id}/available-members",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    available = response.json()
    assert len(available) == 1
    assert available[0]["username"] == regular_user.username


def test_add_team_member_requires_admin(client, regular_token):
    """Regular users cannot add team members via admin API"""
    response = client.post(
        "/api/admin/teams/1/members",
        json={"username": "user"},
        headers={"Authorization": f"Bearer {regular_token}"}
    )
    assert response.status_code == 403


def test_add_team_member_admin(client, admin_token, admin_user, regular_user):
    """Admin can add a member to a team"""
    # Create organization and team
    org = Organization.create_with_columns(name="Test Org", slug="test-org", owner=admin_user)
    team = Team.create_with_columns(name="Test Team", organization=org)
    OrganizationMember.create(user=admin_user, organization=org, joined_at=datetime.now())
    OrganizationMember.create(user=regular_user, organization=org, joined_at=datetime.now())
    TeamMember.create(user=admin_user, team=team, joined_at=datetime.now())

    # Add regular user to team
    response = client.post(
        f"/api/admin/teams/{team.id}/members",
        json={"username": regular_user.username},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    member = response.json()
    assert member["username"] == regular_user.username


def test_add_team_member_not_in_org(client, admin_token, admin_user, regular_user):
    """A user outside the organization can still be put on its team.

    This asserted a 400 until teams became the unit of authorization. Teams
    may span organizations, so there is nothing to reject here.
    """
    org = Organization.create_with_columns(name="Test Org", slug="test-org", owner=admin_user)
    team = Team.create_with_columns(name="Test Team", organization=org)
    OrganizationMember.create(user=admin_user, organization=org, joined_at=datetime.now())
    TeamMember.create(user=admin_user, team=team, joined_at=datetime.now())

    response = client.post(
        f"/api/admin/teams/{team.id}/members",
        json={"username": regular_user.username},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert TeamMember.get_or_none(
        (TeamMember.team == team) & (TeamMember.user == regular_user)
    ) is not None


def test_add_team_member_already_in_team(client, admin_token, admin_user, regular_user):
    """Cannot add a user who is already on the team"""
    org = Organization.create_with_columns(name="Test Org", slug="test-org", owner=admin_user)
    team = Team.create_with_columns(name="Test Team", organization=org)
    OrganizationMember.create(user=admin_user, organization=org, joined_at=datetime.now())
    OrganizationMember.create(user=regular_user, organization=org, joined_at=datetime.now())
    TeamMember.create(user=admin_user, team=team, joined_at=datetime.now())
    TeamMember.create(user=regular_user, team=team, joined_at=datetime.now())

    # Try to add regular user again
    response = client.post(
        f"/api/admin/teams/{team.id}/members",
        json={"username": regular_user.username},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "User is already in this team"


def test_remove_team_member_requires_admin(client, regular_token):
    """Regular users cannot remove team members via admin API"""
    response = client.delete(
        "/api/admin/teams/1/members/1",
        headers={"Authorization": f"Bearer {regular_token}"}
    )
    assert response.status_code == 403


def test_remove_team_member_admin(client, admin_token, admin_user, regular_user):
    """Admin can remove a member from a team"""
    org = Organization.create_with_columns(name="Test Org", slug="test-org", owner=admin_user)
    team = Team.create_with_columns(name="Test Team", organization=org)
    OrganizationMember.create(user=admin_user, organization=org, joined_at=datetime.now())
    OrganizationMember.create(user=regular_user, organization=org, joined_at=datetime.now())
    TeamMember.create(user=admin_user, team=team, joined_at=datetime.now())
    TeamMember.create(user=regular_user, team=team, joined_at=datetime.now())

    # Remove regular user from team
    response = client.delete(
        f"/api/admin/teams/{team.id}/members/{regular_user.id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200

    # Verify they're removed
    remaining = TeamMember.select().where(TeamMember.team == team)
    assert remaining.count() == 1
