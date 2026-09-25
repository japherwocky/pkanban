"""Tests for inviting someone to a team by email.

Board sharing runs through teams, and the only way onto a team was
POST /teams/{id}/members, which takes a username and so requires the person
to have signed up already. These cover the email path: who may open one, what
accepting grants, and -- the point of the whole feature -- that it grants the
team without quietly handing out organization membership as well.
"""

import os
import random
import string
import sys
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.auth import create_access_token
from backend.main import app
from backend.models import (
    Organization,
    OrganizationInvite,
    OrganizationMember,
    Team,
    TeamMember,
    User,
)


@pytest.fixture
def client():
    return TestClient(app)


def unique(base):
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{base}-{suffix}"


def headers_for(user):
    token = create_access_token(data={"sub": user.id, "username": user.username})
    return {"Authorization": f"Bearer {token}"}


def make_user(email=None):
    name = unique("u").replace("-", "_")
    return User.create_user(name, "testpassword", email=email or f"{name}@example.com")


@pytest.fixture
def org_owner_team(db_session):
    """An owner, their org, and a team in it that the owner is a member of."""
    owner = make_user()
    org = Organization.create_with_columns("Acme", unique("acme"), owner)
    OrganizationMember.create(
        user=owner, organization=org, joined_at=datetime.now(timezone.utc)
    )
    team = Team.create_with_columns("Collaborators", org)
    TeamMember.create(user=owner, team=team, joined_at=datetime.now(timezone.utc))
    return owner, org, team


class TestCreateTeamInvite:
    def test_team_member_can_invite(self, client, org_owner_team):
        owner, org, team = org_owner_team
        member = make_user()
        TeamMember.create(user=member, team=team, joined_at=datetime.now(timezone.utc))

        response = client.post(
            f"/api/teams/{team.id}/invites",
            json={"email": "outsider@example.com"},
            headers=headers_for(member),
        )

        # Being in the group is what lets you add to the group -- the member
        # is not an org member and still may invite.
        assert response.status_code == 200
        assert response.json()["email"] == "outsider@example.com"

    def test_org_owner_can_invite_to_a_team_they_are_not_on(
        self, client, org_owner_team
    ):
        owner, org, team = org_owner_team
        TeamMember.delete().where(TeamMember.team == team).execute()

        response = client.post(
            f"/api/teams/{team.id}/invites",
            json={"email": "outsider@example.com"},
            headers=headers_for(owner),
        )
        assert response.status_code == 200

    def test_outsider_cannot_invite(self, client, org_owner_team):
        owner, org, team = org_owner_team
        stranger = make_user()

        response = client.post(
            f"/api/teams/{team.id}/invites",
            json={"email": "outsider@example.com"},
            headers=headers_for(stranger),
        )
        assert response.status_code == 403

    def test_inviting_an_existing_team_member_is_refused(self, client, org_owner_team):
        owner, org, team = org_owner_team

        response = client.post(
            f"/api/teams/{team.id}/invites",
            json={"email": owner.email},
            headers=headers_for(owner),
        )
        assert response.status_code == 400
        assert "already in this team" in response.json()["detail"]

    def test_reinviting_revokes_the_previous_token(self, client, org_owner_team):
        owner, org, team = org_owner_team

        first = client.post(
            f"/api/teams/{team.id}/invites",
            json={"email": "outsider@example.com"},
            headers=headers_for(owner),
        ).json()
        client.post(
            f"/api/teams/{team.id}/invites",
            json={"email": "outsider@example.com"},
            headers=headers_for(owner),
        )

        # Otherwise revoking the invite the UI shows leaves the older token
        # working, and revocation does not revoke.
        assert client.get(f"/api/invites/{first['token']}").status_code == 404


class TestAcceptTeamInvite:
    def test_accepting_grants_the_team_and_not_the_org(self, client, org_owner_team):
        owner, org, team = org_owner_team
        invitee = make_user()

        created = client.post(
            f"/api/teams/{team.id}/invites",
            json={"email": invitee.email},
            headers=headers_for(owner),
        ).json()
        response = client.post(
            f"/api/invites/{created['token']}/accept", headers=headers_for(invitee)
        )

        assert response.status_code == 200
        assert response.json()["team_name"] == "Collaborators"
        assert TeamMember.get_or_none(
            (TeamMember.team == team) & (TeamMember.user == invitee)
        )
        # Teams span organizations on purpose: the narrow grant is the point.
        assert (
            OrganizationMember.get_or_none(
                (OrganizationMember.organization == org)
                & (OrganizationMember.user == invitee)
            )
            is None
        )

    def test_an_org_member_can_still_accept_a_team_invite(self, client, org_owner_team):
        owner, org, team = org_owner_team
        colleague = make_user()
        OrganizationMember.create(
            user=colleague, organization=org, joined_at=datetime.now(timezone.utc)
        )

        created = client.post(
            f"/api/teams/{team.id}/invites",
            json={"email": colleague.email},
            headers=headers_for(owner),
        ).json()
        response = client.post(
            f"/api/invites/{created['token']}/accept", headers=headers_for(colleague)
        )

        # Checking org membership here would refuse every colleague.
        assert response.status_code == 200
        assert TeamMember.get_or_none(
            (TeamMember.team == team) & (TeamMember.user == colleague)
        )

    def test_a_team_invite_is_not_bearer(self, client, org_owner_team):
        owner, org, team = org_owner_team
        created = client.post(
            f"/api/teams/{team.id}/invites",
            json={"email": "intended@example.com"},
            headers=headers_for(owner),
        ).json()
        someone_else = make_user()

        response = client.post(
            f"/api/invites/{created['token']}/accept",
            headers=headers_for(someone_else),
        )
        assert response.status_code == 403

    def test_the_landing_page_names_the_team(self, client, org_owner_team):
        owner, org, team = org_owner_team
        created = client.post(
            f"/api/teams/{team.id}/invites",
            json={"email": "outsider@example.com"},
            headers=headers_for(owner),
        ).json()

        data = client.get(f"/api/invites/{created['token']}").json()
        assert data["team_name"] == "Collaborators"
        assert data["organization_name"] == "Acme"

    def test_an_org_invite_still_grants_the_org(self, client, org_owner_team):
        owner, org, team = org_owner_team
        invitee = make_user()

        created = client.post(
            f"/api/organizations/{org.id}/invites",
            json={"email": invitee.email},
            headers=headers_for(owner),
        ).json()
        response = client.post(
            f"/api/invites/{created['token']}/accept", headers=headers_for(invitee)
        )

        assert response.status_code == 200
        assert response.json()["team_name"] is None
        assert OrganizationMember.get_or_none(
            (OrganizationMember.organization == org)
            & (OrganizationMember.user == invitee)
        )


class TestListAndRevoke:
    def test_team_invites_are_not_listed_as_org_invites(self, client, org_owner_team):
        owner, org, team = org_owner_team
        client.post(
            f"/api/teams/{team.id}/invites",
            json={"email": "outsider@example.com"},
            headers=headers_for(owner),
        )

        # The org page's owner cannot revoke these and accepting one grants no
        # org membership, so showing them there describes something untrue.
        org_invites = client.get(
            f"/api/organizations/{org.id}/invites", headers=headers_for(owner)
        ).json()
        assert org_invites == []

        team_invites = client.get(
            f"/api/teams/{team.id}/invites", headers=headers_for(owner)
        ).json()
        assert [i["email"] for i in team_invites] == ["outsider@example.com"]

    def test_a_team_member_can_revoke(self, client, org_owner_team):
        owner, org, team = org_owner_team
        member = make_user()
        TeamMember.create(user=member, team=team, joined_at=datetime.now(timezone.utc))
        created = client.post(
            f"/api/teams/{team.id}/invites",
            json={"email": "outsider@example.com"},
            headers=headers_for(owner),
        ).json()

        response = client.delete(
            f"/api/teams/{team.id}/invites/{created['id']}",
            headers=headers_for(member),
        )
        assert response.status_code == 200
        assert client.get(f"/api/invites/{created['token']}").status_code == 404

    def test_an_outsider_cannot_list(self, client, org_owner_team):
        owner, org, team = org_owner_team
        response = client.get(
            f"/api/teams/{team.id}/invites", headers=headers_for(make_user())
        )
        assert response.status_code == 403

    def test_expired_invites_are_not_listed(self, client, org_owner_team):
        owner, org, team = org_owner_team
        created = client.post(
            f"/api/teams/{team.id}/invites",
            json={"email": "outsider@example.com"},
            headers=headers_for(owner),
        ).json()
        invite = OrganizationInvite.get_by_id(created["id"])
        invite.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        invite.save()

        listed = client.get(
            f"/api/teams/{team.id}/invites", headers=headers_for(owner)
        ).json()
        assert listed == []
