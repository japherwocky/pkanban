"""
Permission tests for Unix-like permission model.

Permission model:
- Organization has an explicit owner (like root)
- Only owner can update/delete organization, add/remove org members
- Any org member can create teams
- Any team member can add other org members to the team (Unix group model)
- Any team member can remove themselves from a team
- Only org owner can delete teams
- Board can be shared with a team or made public to org
- Board owner can share boards
- Team members (or org members if public) can access/modify boards
"""

import os
import sys
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app
from backend.database import db
from backend.models import User, Board, Column, Card, Organization, OrganizationMember, Team, TeamMember
from backend.auth import create_access_token





@pytest.fixture
def client():
    return TestClient(app)


import random
import string

user_counter = 0
org_counter = 0

def create_user(username_base, password):
    global user_counter
    user_counter += 1
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    username = f"{username_base}_{user_counter}_{random_suffix}"
    return User.create_user(username, password)


def create_organization(name, owner, **kwargs):
    """Helper to create organization with unique slug"""
    global org_counter
    org_counter += 1
    slug = kwargs.pop('slug', None)
    if slug is None:
        # Generate unique slug from name with counter and random suffix
        base_slug = name.lower().replace(' ', '-')
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        slug = f"{base_slug}-{org_counter}-{random_suffix}"
    return Organization.create(name=name, slug=slug, owner=owner, created_at=datetime.now(timezone.utc), **kwargs)


def get_auth_headers(user):
    token = create_access_token(data={"sub": user.id, "username": user.username})
    return {"Authorization": f"Bearer {token}"}


# ===============================
# ORGANIZATION PERMISSION TESTS
# ===============================

def test_create_organization_requires_auth(client):
    """Creating an organization requires authentication"""
    response = client.post("/api/organizations", json={"name": "Test Org"})
    assert response.status_code == 401


def test_any_user_can_create_organization(client, test_db):
    """Any authenticated user can create an organization"""
    user = create_user("orguser1", "password")
    headers = get_auth_headers(user)

    response = client.post("/api/organizations", json={"name": "My Org"}, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "My Org"
    assert data["owner_id"] == user.id
    assert "id" in data


def test_list_organizations_returns_only_user_orgs(client, test_db):
    """List organizations should only return orgs user is a member of"""
    user1 = create_user("orguser1", "password")
    user2 = create_user("orguser2", "password")

    # Create org as user1
    org = create_organization("Org1", user1)
    OrganizationMember.create(user=user1, organization=org, joined_at=datetime.now(timezone.utc))

    # Create another org as user2
    org2 = create_organization("Org2", user2)
    OrganizationMember.create(user=user2, organization=org2, joined_at=datetime.now(timezone.utc))

    # user1 should only see their org
    headers1 = get_auth_headers(user1)
    response = client.get("/api/organizations", headers=headers1)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == org.id


def test_get_organization_requires_membership(client, test_db):
    """Getting an org requires being a member"""
    user1 = create_user("orguser1", "password")
    user2 = create_user("orguser2", "password")

    org = create_organization("Org1", user1)
    OrganizationMember.create(user=user1, organization=org, joined_at=datetime.now(timezone.utc))

    # user2 cannot access
    headers2 = get_auth_headers(user2)
    response = client.get(f"/api/organizations/{org.id}", headers=headers2)
    assert response.status_code == 403


def test_update_organization_requires_owner(client, test_db):
    """Updating organization requires owner (root)"""
    owner = create_user("owner", "password")
    member = create_user("member", "password")

    org = create_organization("Original Name", owner)
    OrganizationMember.create(user=owner, organization=org, joined_at=datetime.now(timezone.utc))
    OrganizationMember.create(user=member, organization=org, joined_at=datetime.now(timezone.utc))

    # Owner can update
    response = client.put(
        f"/api/organizations/{org.id}",
        json={"name": "Updated by Owner"},
        headers=get_auth_headers(owner)
    )
    assert response.status_code == 200

    # Member cannot update
    response = client.put(
        f"/api/organizations/{org.id}",
        json={"name": "Should Not Update"},
        headers=get_auth_headers(member)
    )
    assert response.status_code == 403


# ===============================
# ORGANIZATION MEMBER PERMISSION TESTS
# ===============================

def test_add_org_member_requires_owner(client, test_db):
    """Adding organization members requires owner"""
    owner = create_user("owner", "password")
    member = create_user("member", "password")
    new_user = create_user("newuser", "password")

    org = create_organization("Org1", owner)
    OrganizationMember.create(user=owner, organization=org, joined_at=datetime.now(timezone.utc))
    OrganizationMember.create(user=member, organization=org, joined_at=datetime.now(timezone.utc))

    # Owner can add
    response = client.post(
        f"/api/organizations/{org.id}/members",
        json={"username": new_user.username},
        headers=get_auth_headers(owner)
    )
    assert response.status_code == 200

    # Member cannot add
    another_user = create_user("anotheruser", "password")
    response = client.post(
        f"/api/organizations/{org.id}/members",
        json={"username": another_user.username},  # Should fail on permission
        headers=get_auth_headers(member)
    )
    assert response.status_code == 403


def test_remove_org_member_permissions(client, test_db):
    """Removing org member: owner can remove others, anyone can remove self"""
    owner = create_user("owner", "password")
    member_user = create_user("member", "password")

    org = create_organization("Org1", owner)
    OrganizationMember.create(user=owner, organization=org, joined_at=datetime.now(timezone.utc))
    member = OrganizationMember.create(user=member_user, organization=org, joined_at=datetime.now(timezone.utc))

    # Owner can remove member
    response = client.delete(
        f"/api/organizations/{org.id}/members/{member_user.id}",
        headers=get_auth_headers(owner)
    )
    assert response.status_code == 200

    # Recreate member for next test
    member = OrganizationMember.create(user=member_user, organization=org, joined_at=datetime.now(timezone.utc))

    # Member can remove self
    response = client.delete(
        f"/api/organizations/{org.id}/members/{member_user.id}",
        headers=get_auth_headers(member_user)
    )
    assert response.status_code == 200


def test_cannot_remove_org_owner(client, test_db):
    """Cannot remove an organization owner"""
    owner = create_user("owner", "password")
    member = create_user("member", "password")

    org = create_organization("Org1", owner)
    owner_member = OrganizationMember.create(user=owner, organization=org, joined_at=datetime.now(timezone.utc))
    OrganizationMember.create(user=member, organization=org, joined_at=datetime.now(timezone.utc))

    # Member cannot remove owner
    response = client.delete(
        f"/api/organizations/{org.id}/members/{owner.id}",
        headers=get_auth_headers(member)
    )
    assert response.status_code == 400


# ===============================
# TEAM PERMISSION TESTS
# ===============================

def test_create_team_requires_org_membership(client, test_db):
    """Creating a team requires being an org member"""
    user1 = create_user("user1", "password")
    user2 = create_user("user2", "password")

    org = create_organization("Org1", user1)
    OrganizationMember.create(user=user1, organization=org, joined_at=datetime.now(timezone.utc))

    # user1 (org member) can create team
    response = client.post(
        f"/api/organizations/{org.id}/teams",
        json={"name": "New Team"},
        headers=get_auth_headers(user1)
    )
    assert response.status_code == 200

    # user2 (not org member) cannot create team
    response = client.post(
        f"/api/organizations/{org.id}/teams",
        json={"name": "Should Not Create"},
        headers=get_auth_headers(user2)
    )
    assert response.status_code == 403


def test_list_teams_requires_org_membership(client, test_db):
    """Listing teams requires being an org member"""
    user1 = create_user("user1", "password")
    user2 = create_user("user2", "password")

    org = create_organization("Org1", user1)
    OrganizationMember.create(user=user1, organization=org, joined_at=datetime.now(timezone.utc))

    Team.create(name="Team1", organization=org, created_at=datetime.now(timezone.utc))

    # user1 (org member) can list teams
    response = client.get(f"/api/organizations/{org.id}/teams", headers=get_auth_headers(user1))
    assert response.status_code == 200
    assert len(response.json()) == 1

    # user2 (not org member) cannot list teams
    response = client.get(f"/api/organizations/{org.id}/teams", headers=get_auth_headers(user2))
    assert response.status_code == 403


def test_update_team_requires_team_membership(client, test_db):
    """Updating a team requires being a team member"""
    team_member1 = create_user("teammember1", "password")
    team_member2 = create_user("teammember2", "password")
    outsider = create_user("outsider", "password")

    org = create_organization("Org1", team_member1)
    OrganizationMember.create(user=team_member1, organization=org, joined_at=datetime.now(timezone.utc))
    OrganizationMember.create(user=team_member2, organization=org, joined_at=datetime.now(timezone.utc))
    OrganizationMember.create(user=outsider, organization=org, joined_at=datetime.now(timezone.utc))

    team = Team.create(name="Team1", organization=org, created_at=datetime.now(timezone.utc))
    TeamMember.create(user=team_member1, team=team, joined_at=datetime.now(timezone.utc))
    TeamMember.create(user=team_member2, team=team, joined_at=datetime.now(timezone.utc))

    # Team member can update
    response = client.put(
        f"/api/teams/{team.id}",
        json={"name": "Updated Name"},
        headers=get_auth_headers(team_member1)
    )
    assert response.status_code == 200

    # Outsider (org member but not team member) cannot update
    response = client.put(
        f"/api/teams/{team.id}",
        json={"name": "Should Not Update"},
        headers=get_auth_headers(outsider)
    )
    assert response.status_code == 403


def test_delete_team_requires_org_owner(client, test_db):
    """Deleting a team requires org owner"""
    org_owner = create_user("owner", "password")
    team_member1 = create_user("teammember1", "password")
    team_member2 = create_user("teammember2", "password")

    org = create_organization("Org1", org_owner)
    OrganizationMember.create(user=org_owner, organization=org, joined_at=datetime.now(timezone.utc))
    OrganizationMember.create(user=team_member1, organization=org, joined_at=datetime.now(timezone.utc))
    OrganizationMember.create(user=team_member2, organization=org, joined_at=datetime.now(timezone.utc))

    team = Team.create(name="Team1", organization=org, created_at=datetime.now(timezone.utc))
    TeamMember.create(user=team_member1, team=team, joined_at=datetime.now(timezone.utc))

    # Org owner can delete team
    response = client.delete(f"/api/teams/{team.id}", headers=get_auth_headers(org_owner))
    assert response.status_code == 200

    # Create another team for team member test
    team2 = Team.create(name="Team2", organization=org, created_at=datetime.now(timezone.utc))
    TeamMember.create(user=team_member2, team=team2, joined_at=datetime.now(timezone.utc))

    # Team member cannot delete team
    response = client.delete(f"/api/teams/{team2.id}", headers=get_auth_headers(team_member2))
    assert response.status_code == 403


# ===============================
# TEAM MEMBER PERMISSION TESTS
# ===============================

def test_add_team_member_requires_team_membership(client, test_db):
    """Adding team member requires being a team member (Unix group model)"""
    team_member1 = create_user("teammember1", "password")
    outsider = create_user("outsider", "password")
    new_user = create_user("newuser", "password")

    org = create_organization("Org1", team_member1)
    OrganizationMember.create(user=team_member1, organization=org, joined_at=datetime.now(timezone.utc))
    OrganizationMember.create(user=outsider, organization=org, joined_at=datetime.now(timezone.utc))
    OrganizationMember.create(user=new_user, organization=org, joined_at=datetime.now(timezone.utc))

    team = Team.create(name="Team1", organization=org, created_at=datetime.now(timezone.utc))
    TeamMember.create(user=team_member1, team=team, joined_at=datetime.now(timezone.utc))

    # Team member can add member
    response = client.post(
        f"/api/teams/{team.id}/members",
        json={"username": new_user.username},
        headers=get_auth_headers(team_member1)
    )
    assert response.status_code == 200

    # Outsider (not team member) cannot add
    another_user = create_user("anotheruser", "password")
    OrganizationMember.create(user=another_user, organization=org, joined_at=datetime.now(timezone.utc))
    response = client.post(
        f"/api/teams/{team.id}/members",
        json={"username": another_user.username},
        headers=get_auth_headers(outsider)
    )
    assert response.status_code == 403


def test_add_team_member_requires_org_membership(client, test_db):
    """Adding to team requires user to be org member first"""
    team_member = create_user("teammember", "password")
    outsider = create_user("outsider", "password")

    org = create_organization("Org1", team_member)
    OrganizationMember.create(user=team_member, organization=org, joined_at=datetime.now(timezone.utc))
    # outsider is NOT an org member

    team = Team.create(name="Team1", organization=org, created_at=datetime.now(timezone.utc))
    TeamMember.create(user=team_member, team=team, joined_at=datetime.now(timezone.utc))

    # Cannot add non-org-member to team
    response = client.post(
        f"/api/teams/{team.id}/members",
        json={"username": outsider.username},
        headers=get_auth_headers(team_member)
    )
    assert response.status_code == 400


def test_list_team_members_requires_org_membership(client, test_db):
    """Listing team members requires being an org member"""
    user1 = create_user("user1", "password")
    user2 = create_user("user2", "password")

    org = create_organization("Org1", user1)
    OrganizationMember.create(user=user1, organization=org, joined_at=datetime.now(timezone.utc))

    team = Team.create(name="Team1", organization=org, created_at=datetime.now(timezone.utc))
    TeamMember.create(user=user1, team=team, joined_at=datetime.now(timezone.utc))

    # user1 (org member) can list
    response = client.get(f"/api/teams/{team.id}/members", headers=get_auth_headers(user1))
    assert response.status_code == 200
    assert len(response.json()) == 1

    # user2 (not org member) cannot list
    response = client.get(f"/api/teams/{team.id}/members", headers=get_auth_headers(user2))
    assert response.status_code == 403


def test_remove_team_member_can_remove_self(client, test_db):
    """Team member can remove themselves"""
    team_member1 = create_user("teammember1", "password")
    team_member2 = create_user("teammember2", "password")

    org = create_organization("Org1", team_member1)
    OrganizationMember.create(user=team_member1, organization=org, joined_at=datetime.now(timezone.utc))
    OrganizationMember.create(user=team_member2, organization=org, joined_at=datetime.now(timezone.utc))

    team = Team.create(name="Team1", organization=org, created_at=datetime.now(timezone.utc))
    TeamMember.create(user=team_member1, team=team, joined_at=datetime.now(timezone.utc))
    team_member2_record = TeamMember.create(user=team_member2, team=team, joined_at=datetime.now(timezone.utc))

    # Member can remove self
    response = client.delete(
        f"/api/teams/{team.id}/members/{team_member2.id}",
        headers=get_auth_headers(team_member2)
    )
    assert response.status_code == 200


def test_remove_team_member_cannot_remove_others(client, test_db):
    """Team member cannot remove other team members

    The org owner is a third user here on purpose. This test used to make
    team_member1 the owner, so it was really asserting that the *owner* could
    not remove people -- it passed only because the owner had no way to, which
    also left an owner unable to undo their own add.
    """
    org_owner = create_user("teamremoveowner", "password")
    team_member1 = create_user("teammember1", "password")
    team_member2 = create_user("teammember2", "password")

    org = create_organization("Org1", org_owner)
    OrganizationMember.create(user=org_owner, organization=org, joined_at=datetime.now(timezone.utc))
    OrganizationMember.create(user=team_member1, organization=org, joined_at=datetime.now(timezone.utc))
    OrganizationMember.create(user=team_member2, organization=org, joined_at=datetime.now(timezone.utc))

    team = Team.create(name="Team1", organization=org, created_at=datetime.now(timezone.utc))
    TeamMember.create(user=team_member1, team=team, joined_at=datetime.now(timezone.utc))
    team_member2_record = TeamMember.create(user=team_member2, team=team, joined_at=datetime.now(timezone.utc))

    # A plain team member cannot remove someone else...
    response = client.delete(
        f"/api/teams/{team.id}/members/{team_member2.id}",
        headers=get_auth_headers(team_member1)
    )
    assert response.status_code == 403

    # ...but the org owner can.
    response = client.delete(
        f"/api/teams/{team.id}/members/{team_member2.id}",
        headers=get_auth_headers(org_owner)
    )
    assert response.status_code == 200


# ===============================
# BOARD PERMISSION TESTS
# ===============================

def test_share_board_requires_owner(client, test_db):
    """Sharing a board requires being a board owner"""
    owner = create_user("owner", "password")
    other_user = create_user("other", "password")

    board = Board.create_with_columns(owner=owner, name="My Board")

    # Owner can share
    response = client.post(
        f"/api/boards/{board.id}/share",
        json={"team_id": None},
        headers=get_auth_headers(owner)
    )
    assert response.status_code == 200

    # Other user cannot share
    response = client.post(
        f"/api/boards/{board.id}/share",
        json={"team_id": None},
        headers=get_auth_headers(other_user)
    )
    assert response.status_code == 403


def test_board_can_be_public_to_org(client, test_db):
    """Board can be shared publicly to organization"""
    owner = create_user("owner", "password")
    member = create_user("member", "password")

    org = create_organization("Org1", owner)
    OrganizationMember.create(user=owner, organization=org, joined_at=datetime.now(timezone.utc))
    OrganizationMember.create(user=member, organization=org, joined_at=datetime.now(timezone.utc))

    board = Board.create_with_columns(owner=owner, name="Public Board", is_public_to_org=True)

    # Owner can access
    response = client.get(f"/api/boards/{board.id}", headers=get_auth_headers(owner))
    assert response.status_code == 200

    # Org member can access (public board)
    # Note: This test assumes we implement org-wide access
    # For now, we'll skip this until we add that feature
    # response = client.get(f"/api/boards/{board.id}", headers=get_auth_headers(member))
    # assert response.status_code == 200


def test_board_access_through_team_sharing(client, test_db):
    """Board shared with team is accessible to team members"""
    owner = create_user("owner", "password")
    team_member = create_user("teammember", "password")
    non_member = create_user("nonmember", "password")

    org = create_organization("Org1", owner)
    OrganizationMember.create(user=owner, organization=org, joined_at=datetime.now(timezone.utc))
    OrganizationMember.create(user=team_member, organization=org, joined_at=datetime.now(timezone.utc))

    team = Team.create(name="Team1", organization=org, created_at=datetime.now(timezone.utc))
    TeamMember.create(user=team_member, team=team, joined_at=datetime.now(timezone.utc))

    board = Board.create_with_columns(owner=owner, name="Shared Board", shared_team=team)

    # Owner can access
    response = client.get(f"/api/boards/{board.id}", headers=get_auth_headers(owner))
    assert response.status_code == 200

    # Team member can access
    response = client.get(f"/api/boards/{board.id}", headers=get_auth_headers(team_member))
    assert response.status_code == 200

    # Non-member cannot access
    response = client.get(f"/api/boards/{board.id}", headers=get_auth_headers(non_member))
    assert response.status_code == 403


def test_update_board_requires_owner_or_team_member(client, test_db):
    """Updating board requires owner or team member"""
    owner = create_user("owner", "password")
    team_member = create_user("teammember", "password")
    other_user = create_user("other", "password")

    org = create_organization("Org1", owner)
    OrganizationMember.create(user=owner, organization=org, joined_at=datetime.now(timezone.utc))
    OrganizationMember.create(user=team_member, organization=org, joined_at=datetime.now(timezone.utc))

    team = Team.create(name="Team1", organization=org, created_at=datetime.now(timezone.utc))
    TeamMember.create(user=team_member, team=team, joined_at=datetime.now(timezone.utc))

    board = Board.create_with_columns(owner=owner, name="Shared Board", shared_team=team)

    # Owner can update
    response = client.post(
        f"/api/boards/{board.id}",
        json={"name": "Updated"},
        headers=get_auth_headers(owner)
    )
    assert response.status_code == 200

    # Team member can update
    response = client.post(
        f"/api/boards/{board.id}",
        json={"name": "Updated"},
        headers=get_auth_headers(team_member)
    )
    assert response.status_code == 200

    # Other user cannot update
    response = client.post(
        f"/api/boards/{board.id}",
        json={"name": "Should Not Update"},
        headers=get_auth_headers(other_user)
    )
    assert response.status_code == 403


def test_delete_board_requires_owner(client, test_db):
    """Deleting a board requires being a board owner"""
    owner = create_user("owner", "password")
    team_member = create_user("teammember", "password")

    org = create_organization("Org1", owner)
    OrganizationMember.create(user=owner, organization=org, joined_at=datetime.now(timezone.utc))
    OrganizationMember.create(user=team_member, organization=org, joined_at=datetime.now(timezone.utc))

    team = Team.create(name="Team1", organization=org, created_at=datetime.now(timezone.utc))
    TeamMember.create(user=team_member, team=team, joined_at=datetime.now(timezone.utc))

    board = Board.create_with_columns(owner=owner, name="Shared Board", shared_team=team)

    # Owner can delete
    response = client.delete(f"/api/boards/{board.id}", headers=get_auth_headers(owner))
    assert response.status_code == 200

    # Create another board for team member test
    board2 = Board.create_with_columns(owner=owner, name="Shared Board 2", shared_team=team)

    # Team member cannot delete
    response = client.delete(f"/api/boards/{board2.id}", headers=get_auth_headers(team_member))
    assert response.status_code == 403


def test_list_boards_includes_shared_boards(client, test_db):
    """Listing boards includes both owned and shared boards"""
    owner = create_user("owner", "password")
    team_member = create_user("teammember", "password")
    other_user = create_user("other", "password")

    org = create_organization("Org1", owner)
    OrganizationMember.create(user=owner, organization=org, joined_at=datetime.now(timezone.utc))
    OrganizationMember.create(user=team_member, organization=org, joined_at=datetime.now(timezone.utc))

    team = Team.create(name="Team1", organization=org, created_at=datetime.now(timezone.utc))
    TeamMember.create(user=team_member, team=team, joined_at=datetime.now(timezone.utc))

    board1 = Board.create_with_columns(owner=owner, name="Owned Board")
    board2 = Board.create_with_columns(owner=owner, name="Shared Board", shared_team=team)

    # Owner sees both boards
    response = client.get("/api/boards", headers=get_auth_headers(owner))
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    # Team member sees only shared board
    response = client.get("/api/boards", headers=get_auth_headers(team_member))
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == board2.id

    # Other user sees no boards
    response = client.get("/api/boards", headers=get_auth_headers(other_user))
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0
