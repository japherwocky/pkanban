"""Teams as the unit of authorization, independent of organizations.

can_access_board checks team membership, not org membership. Teams are
therefore allowed to span organizations, so a contractor or a partner can be
put on one project's team without being handed the run of the org.

add_team_member used to refuse anyone who was not already an OrganizationMember
("User is not a member of this organization"), which made that impossible.
"""

import os
import sys
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app
from backend.auth import create_access_token
from backend.models import OrganizationMember, Team, TeamMember, User


@pytest.fixture
def client():
    return TestClient(app)


def headers(user):
    return {
        "Authorization": "Bearer "
        + create_access_token(data={"sub": user.id, "username": user.username})
    }


def make_org(client, owner, name):
    return client.post(
        "/api/organizations", json={"name": name}, headers=headers(owner)
    ).json()


class TestOutsidersOnTeams:
    def test_a_contractor_gets_one_board_and_nothing_else(self, client, db_session):
        owner = User.create_user("xo_owner", "password")
        contractor = User.create_user("xo_contractor", "password")

        org = make_org(client, owner, "XO Org")
        shared = client.post(
            "/api/boards", json={"name": "Shared Project"}, headers=headers(owner)
        ).json()
        private = client.post(
            "/api/boards", json={"name": "Internal Only"}, headers=headers(owner)
        ).json()
        team = client.post(
            f"/api/organizations/{org['id']}/teams",
            json={"name": "Contractors"},
            headers=headers(owner),
        ).json()

        added = client.post(
            f"/api/teams/{team['id']}/members",
            json={"username": "xo_contractor"},
            headers=headers(owner),
        )
        assert added.status_code == 200, added.json()

        client.post(
            f"/api/boards/{shared['id']}/share",
            json={"team_id": team["id"]},
            headers=headers(owner),
        )

        assert (
            client.get(
                f"/api/boards/{shared['id']}", headers=headers(contractor)
            ).status_code
            == 200
        )
        assert (
            client.get(
                f"/api/boards/{private['id']}", headers=headers(contractor)
            ).status_code
            == 403
        )
        assert [b["id"] for b in client.get(
            "/api/boards", headers=headers(contractor)
        ).json()] == [shared["id"]]

        # Still not in the organization, and cannot see into it.
        assert OrganizationMember.get_or_none(
            (OrganizationMember.organization == org["id"])
            & (OrganizationMember.user == contractor)
        ) is None
        assert client.get(
            "/api/organizations", headers=headers(contractor)
        ).json() == []

    def test_an_org_public_board_stays_shut_to_a_contractor(self, client, db_session):
        """Team membership must not leak into the org-wide branch."""
        owner = User.create_user("cl_owner", "password")
        contractor = User.create_user("cl_contractor", "password")

        org = make_org(client, owner, "CL Org")
        team = client.post(
            f"/api/organizations/{org['id']}/teams",
            json={"name": "CL Team"},
            headers=headers(owner),
        ).json()
        client.post(
            f"/api/teams/{team['id']}/members",
            json={"username": "cl_contractor"},
            headers=headers(owner),
        )

        org_board = client.post(
            "/api/boards", json={"name": "Org Wide"}, headers=headers(owner)
        ).json()
        client.post(
            f"/api/boards/{org_board['id']}/share",
            json={"is_public_to_org": True},
            headers=headers(owner),
        )

        assert (
            client.get(
                f"/api/boards/{org_board['id']}", headers=headers(contractor)
            ).status_code
            == 403
        )

    def test_a_contractor_can_see_the_team_they_are_on(self, client, db_session):
        owner = User.create_user("vt_owner", "password")
        contractor = User.create_user("vt_contractor", "password")

        org = make_org(client, owner, "VT Org")
        team = client.post(
            f"/api/organizations/{org['id']}/teams",
            json={"name": "VT Team"},
            headers=headers(owner),
        ).json()
        client.post(
            f"/api/teams/{team['id']}/members",
            json={"username": "vt_contractor"},
            headers=headers(owner),
        )

        listed = client.get(
            f"/api/teams/{team['id']}/members", headers=headers(contractor)
        )
        assert listed.status_code == 200
        assert "vt_contractor" in [m["username"] for m in listed.json()]

    def test_someone_on_no_team_still_cannot_list_its_members(
        self, client, db_session
    ):
        owner = User.create_user("nt_owner", "password")
        stranger = User.create_user("nt_stranger", "password")

        org = make_org(client, owner, "NT Org")
        team = client.post(
            f"/api/organizations/{org['id']}/teams",
            json={"name": "NT Team"},
            headers=headers(owner),
        ).json()

        assert (
            client.get(
                f"/api/teams/{team['id']}/members", headers=headers(stranger)
            ).status_code
            == 403
        )


class TestRevokingAContractor:
    def test_the_org_owner_can_take_them_off_the_team(self, client, db_session):
        owner = User.create_user("rv_owner", "password")
        contractor = User.create_user("rv_contractor", "password")

        org = make_org(client, owner, "RV Org")
        board = client.post(
            "/api/boards", json={"name": "RV Board"}, headers=headers(owner)
        ).json()
        team = client.post(
            f"/api/organizations/{org['id']}/teams",
            json={"name": "RV Team"},
            headers=headers(owner),
        ).json()
        client.post(
            f"/api/teams/{team['id']}/members",
            json={"username": "rv_contractor"},
            headers=headers(owner),
        )
        client.post(
            f"/api/boards/{board['id']}/share",
            json={"team_id": team["id"]},
            headers=headers(owner),
        )
        assert (
            client.get(
                f"/api/boards/{board['id']}", headers=headers(contractor)
            ).status_code
            == 200
        )

        removed = client.delete(
            f"/api/teams/{team['id']}/members/{contractor.id}", headers=headers(owner)
        )
        assert removed.status_code == 200
        assert (
            client.get(
                f"/api/boards/{board['id']}", headers=headers(contractor)
            ).status_code
            == 403
        )

    def test_removing_an_org_member_also_takes_them_off_its_teams(
        self, client, db_session
    ):
        """Otherwise the removal revokes nothing they could actually reach."""
        owner = User.create_user("om_owner", "password")
        staff = User.create_user("om_staff", "password")

        org = make_org(client, owner, "OM Org")
        OrganizationMember.create(
            user=staff, organization=org["id"], joined_at=datetime.now(timezone.utc)
        )
        board = client.post(
            "/api/boards", json={"name": "OM Board"}, headers=headers(owner)
        ).json()
        team = client.post(
            f"/api/organizations/{org['id']}/teams",
            json={"name": "OM Team"},
            headers=headers(owner),
        ).json()
        client.post(
            f"/api/teams/{team['id']}/members",
            json={"username": "om_staff"},
            headers=headers(owner),
        )
        client.post(
            f"/api/boards/{board['id']}/share",
            json={"team_id": team["id"]},
            headers=headers(owner),
        )

        client.delete(
            f"/api/organizations/{org['id']}/members/{staff.id}", headers=headers(owner)
        )

        assert TeamMember.get_or_none(
            (TeamMember.team == team["id"]) & (TeamMember.user == staff)
        ) is None
        assert (
            client.get(
                f"/api/boards/{board['id']}", headers=headers(staff)
            ).status_code
            == 403
        )

    def test_a_genuine_outsider_is_untouched_by_org_member_removal(
        self, client, db_session
    ):
        """They have no OrganizationMember row, so nothing removes them."""
        owner = User.create_user("un_owner", "password")
        staff = User.create_user("un_staff", "password")
        contractor = User.create_user("un_contractor", "password")

        org = make_org(client, owner, "UN Org")
        OrganizationMember.create(
            user=staff, organization=org["id"], joined_at=datetime.now(timezone.utc)
        )
        team = client.post(
            f"/api/organizations/{org['id']}/teams",
            json={"name": "UN Team"},
            headers=headers(owner),
        ).json()
        for name in ("un_staff", "un_contractor"):
            client.post(
                f"/api/teams/{team['id']}/members",
                json={"username": name},
                headers=headers(owner),
            )

        client.delete(
            f"/api/organizations/{org['id']}/members/{staff.id}", headers=headers(owner)
        )

        assert TeamMember.get_or_none(
            (TeamMember.team == team["id"]) & (TeamMember.user == contractor)
        ) is not None
