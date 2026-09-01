"""Sharing a board with a whole organization.

can_access_board() used to carry this branch:

    if board.is_public_to_org:
        # For now, skip this - we'll handle it via the shared_team approach
        pass

POST /boards/{id}/share accepted the flag, returned 200 and persisted it, and
nothing ever read it. An org member got a 403 and an empty board list while
every step of the flow reported success.
"""

import os
import sys
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app
from backend.auth import create_access_token
from backend.models import Board, OrganizationMember, User


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


def join(user, org_id):
    OrganizationMember.create(
        user=user, organization=org_id, joined_at=datetime.now(timezone.utc)
    )


class TestOrgPublicSharing:
    def test_org_member_can_open_and_list_an_org_public_board(self, client, db_session):
        owner = User.create_user("op_owner", "password")
        member = User.create_user("op_member", "password")

        org = make_org(client, owner, "OP Org")
        join(member, org["id"])
        board = client.post(
            "/api/boards", json={"name": "OP Board"}, headers=headers(owner)
        ).json()

        assert (
            client.get(
                f"/api/boards/{board['id']}", headers=headers(member)
            ).status_code
            == 403
        )

        shared = client.post(
            f"/api/boards/{board['id']}/share",
            json={"is_public_to_org": True},
            headers=headers(owner),
        )
        assert shared.status_code == 200, shared.json()
        assert shared.json()["organization_id"] == org["id"]

        assert (
            client.get(
                f"/api/boards/{board['id']}", headers=headers(member)
            ).status_code
            == 200
        )
        listed = client.get("/api/boards", headers=headers(member)).json()
        assert board["id"] in [b["id"] for b in listed], (
            "an org-public board must be listed, not merely reachable by URL"
        )

    def test_outsiders_are_still_refused(self, client, db_session):
        owner = User.create_user("ou_owner", "password")
        outsider = User.create_user("ou_outsider", "password")

        make_org(client, owner, "OU Org")
        board = client.post(
            "/api/boards", json={"name": "OU Board"}, headers=headers(owner)
        ).json()
        client.post(
            f"/api/boards/{board['id']}/share",
            json={"is_public_to_org": True},
            headers=headers(owner),
        )

        assert (
            client.get(
                f"/api/boards/{board['id']}", headers=headers(outsider)
            ).status_code
            == 403
        )
        assert client.get("/api/boards", headers=headers(outsider)).json() == []

    def test_members_of_a_different_org_are_refused(self, client, db_session):
        owner_a = User.create_user("do_owner_a", "password")
        owner_b = User.create_user("do_owner_b", "password")

        make_org(client, owner_a, "DO Org A")
        make_org(client, owner_b, "DO Org B")
        board = client.post(
            "/api/boards", json={"name": "DO Board"}, headers=headers(owner_a)
        ).json()
        client.post(
            f"/api/boards/{board['id']}/share",
            json={"is_public_to_org": True},
            headers=headers(owner_a),
        )

        assert (
            client.get(
                f"/api/boards/{board['id']}", headers=headers(owner_b)
            ).status_code
            == 403
        )

    def test_unsharing_revokes_access(self, client, db_session):
        owner = User.create_user("un_owner", "password")
        member = User.create_user("un_member", "password")

        org = make_org(client, owner, "UN Org")
        join(member, org["id"])
        board = client.post(
            "/api/boards", json={"name": "UN Board"}, headers=headers(owner)
        ).json()
        client.post(
            f"/api/boards/{board['id']}/share",
            json={"is_public_to_org": True},
            headers=headers(owner),
        )
        assert (
            client.get(
                f"/api/boards/{board['id']}", headers=headers(member)
            ).status_code
            == 200
        )

        client.post(
            f"/api/boards/{board['id']}/share",
            json={"is_public_to_org": False},
            headers=headers(owner),
        )
        assert (
            client.get(
                f"/api/boards/{board['id']}", headers=headers(member)
            ).status_code
            == 403
        )
        assert client.get("/api/boards", headers=headers(member)).json() == []


class TestResolvingWhichOrg:
    def test_belonging_to_several_orgs_requires_an_explicit_choice(
        self, client, db_session
    ):
        owner = User.create_user("mo_owner", "password")
        org_a = make_org(client, owner, "MO Org A")
        make_org(client, owner, "MO Org B")
        board = client.post(
            "/api/boards", json={"name": "MO Board"}, headers=headers(owner)
        ).json()

        ambiguous = client.post(
            f"/api/boards/{board['id']}/share",
            json={"is_public_to_org": True},
            headers=headers(owner),
        )
        assert ambiguous.status_code == 400
        assert "organization_id" in ambiguous.json()["detail"]
        assert Board.get_by_id(board["id"]).organization_id is None
        assert Board.get_by_id(board["id"]).is_public_to_org is False, (
            "a refused share must not leave the flag set"
        )

        explicit = client.post(
            f"/api/boards/{board['id']}/share",
            json={"is_public_to_org": True, "organization_id": org_a["id"]},
            headers=headers(owner),
        )
        assert explicit.status_code == 200
        assert explicit.json()["organization_id"] == org_a["id"]

    def test_cannot_share_into_an_org_you_are_not_in(self, client, db_session):
        owner = User.create_user("ni_owner", "password")
        stranger = User.create_user("ni_stranger", "password")

        make_org(client, owner, "NI Mine")
        theirs = make_org(client, stranger, "NI Theirs")
        board = client.post(
            "/api/boards", json={"name": "NI Board"}, headers=headers(owner)
        ).json()

        response = client.post(
            f"/api/boards/{board['id']}/share",
            json={"is_public_to_org": True, "organization_id": theirs["id"]},
            headers=headers(owner),
        )
        assert response.status_code == 403

    def test_with_no_org_at_all_the_request_is_refused(self, client, db_session):
        loner = User.create_user("na_loner", "password")
        board = client.post(
            "/api/boards", json={"name": "NA Board"}, headers=headers(loner)
        ).json()

        response = client.post(
            f"/api/boards/{board['id']}/share",
            json={"is_public_to_org": True},
            headers=headers(loner),
        )
        assert response.status_code == 400
        assert "not a member of any organization" in response.json()["detail"].lower()


class TestTeamAndOrgSharingCoexist:
    def test_a_team_member_keeps_access_when_the_board_also_goes_org_public(
        self, client, db_session
    ):
        """share_board does not clear shared_team when the org flag goes on.

        can_access_board used to return from the first matching branch, so
        whichever was checked first decided the answer for both.
        """
        owner = User.create_user("co_owner", "password")
        teammate = User.create_user("co_teammate", "password")

        org = make_org(client, owner, "CO Org")
        join(teammate, org["id"])
        board = client.post(
            "/api/boards", json={"name": "CO Board"}, headers=headers(owner)
        ).json()
        team = client.post(
            f"/api/organizations/{org['id']}/teams",
            json={"name": "CO Team"},
            headers=headers(owner),
        ).json()
        client.post(
            f"/api/teams/{team['id']}/members",
            json={"username": "co_teammate"},
            headers=headers(owner),
        )
        client.post(
            f"/api/boards/{board['id']}/share",
            json={"team_id": team["id"]},
            headers=headers(owner),
        )
        client.post(
            f"/api/boards/{board['id']}/share",
            json={"is_public_to_org": True},
            headers=headers(owner),
        )

        board_row = Board.get_by_id(board["id"])
        assert board_row.shared_team_id == team["id"]
        assert board_row.is_public_to_org is True

        assert (
            client.get(
                f"/api/boards/{board['id']}", headers=headers(teammate)
            ).status_code
            == 200
        )
