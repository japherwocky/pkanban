"""Deleting a team, and the wreckage the unexecuted queries used to leave.

DELETE /teams/{id} built three statements and executed one:

    Board.update(shared_team=None).where(Board.shared_team == team)
    TeamMember.delete().where(TeamMember.team == team)
    team.delete_instance()

peewee's update()/delete() only build a query, so the team vanished while
boards kept pointing at it. can_access_board() resolved the FK, got
Team.DoesNotExist, and returned a 500 to every non-owner -- on a board the
owner could still open fine, with no UI anywhere to repair it.
"""

import os
import sys
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app
from backend.auth import create_access_token
from backend.models import (
    Board,
    Card,
    Column,
    OrganizationMember,
    TeamMember,
    User,
)


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


def make_team(client, owner, org_id, name):
    return client.post(
        f"/api/organizations/{org_id}/teams",
        json={"name": name},
        headers=headers(owner),
    ).json()


class TestTeamDeletionCleansUp:
    def test_deleting_a_team_unshares_boards_and_drops_memberships(
        self, client, db_session
    ):
        owner = User.create_user("td_owner", "password")
        member = User.create_user("td_member", "password")

        org = make_org(client, owner, "TD Org")
        join(member, org["id"])
        board = client.post(
            "/api/boards", json={"name": "TD Board"}, headers=headers(owner)
        ).json()
        team = make_team(client, owner, org["id"], "TD Team")
        client.post(
            f"/api/teams/{team['id']}/members",
            json={"username": "td_member"},
            headers=headers(owner),
        )
        client.post(
            f"/api/boards/{board['id']}/share",
            json={"team_id": team["id"]},
            headers=headers(owner),
        )
        before = client.get(f"/api/boards/{board['id']}", headers=headers(member))
        assert before.status_code == 200

        deleted = client.delete(f"/api/teams/{team['id']}", headers=headers(owner))
        assert deleted.status_code == 200

        assert Board.get_by_id(board["id"]).shared_team_id is None
        assert TeamMember.select().where(TeamMember.team == team["id"]).count() == 0

    def test_non_owner_gets_403_not_500_after_the_team_is_deleted(
        self, client, db_session
    ):
        owner = User.create_user("d5_owner", "password")
        member = User.create_user("d5_member", "password")

        org = make_org(client, owner, "D5 Org")
        join(member, org["id"])
        board = client.post(
            "/api/boards", json={"name": "D5 Board"}, headers=headers(owner)
        ).json()
        team = make_team(client, owner, org["id"], "D5 Team")
        client.post(
            f"/api/teams/{team['id']}/members",
            json={"username": "d5_member"},
            headers=headers(owner),
        )
        client.post(
            f"/api/boards/{board['id']}/share",
            json={"team_id": team["id"]},
            headers=headers(owner),
        )
        client.delete(f"/api/teams/{team['id']}", headers=headers(owner))

        assert (
            client.get(
                f"/api/boards/{board['id']}", headers=headers(member)
            ).status_code
            == 403
        )
        assert (
            client.get(
                f"/api/boards/{board['id']}", headers=headers(owner)
            ).status_code
            == 200
        )

    def test_a_board_pointing_at_a_missing_team_does_not_explode(
        self, client, db_session
    ):
        """Databases already corrupted by the old code still have to load.

        Migration 003 clears these, but can_access_board must not depend on
        having been migrated -- it reads shared_team_id rather than resolving
        the FK for exactly this reason.
        """
        owner = User.create_user("dg_owner", "password")
        other = User.create_user("dg_other", "password")
        board = Board.create_with_columns(owner=owner, name="Dangling")
        Board.update(shared_team=99999).where(Board.id == board.id).execute()

        assert (
            client.get(f"/api/boards/{board.id}", headers=headers(other)).status_code
            == 403
        )
        assert (
            client.get(f"/api/boards/{board.id}", headers=headers(owner)).status_code
            == 200
        )
        assert client.get("/api/boards", headers=headers(other)).status_code == 200


class TestOrgMemberRemovalIsScopedToOneOrg:
    def test_removing_a_member_leaves_their_other_orgs_alone(self, client, db_session):
        """The delete predicate was TeamMember.user alone, with no org filter.

        It never ran, so it never did damage -- but adding .execute() to it
        as written would have dropped the user out of every team everywhere.
        """
        owner_a = User.create_user("sc_owner_a", "password")
        owner_b = User.create_user("sc_owner_b", "password")
        member = User.create_user("sc_member", "password")

        org_a = make_org(client, owner_a, "Scope A")
        org_b = make_org(client, owner_b, "Scope B")
        join(member, org_a["id"])
        join(member, org_b["id"])

        team_a = make_team(client, owner_a, org_a["id"], "A Team")
        team_b = make_team(client, owner_b, org_b["id"], "B Team")
        client.post(
            f"/api/teams/{team_a['id']}/members",
            json={"username": "sc_member"},
            headers=headers(owner_a),
        )
        client.post(
            f"/api/teams/{team_b['id']}/members",
            json={"username": "sc_member"},
            headers=headers(owner_b),
        )

        response = client.delete(
            f"/api/organizations/{org_a['id']}/members/{member.id}",
            headers=headers(owner_a),
        )
        assert response.status_code == 200

        assert (
            TeamMember.get_or_none(
                (TeamMember.user == member) & (TeamMember.team == team_a["id"])
            )
            is None
        ), "should leave the team of the org they were removed from"
        assert (
            TeamMember.get_or_none(
                (TeamMember.user == member) & (TeamMember.team == team_b["id"])
            )
            is not None
        ), "must stay in the unrelated org's team"


class TestAdminBoardDeleteRemovesCards:
    def test_cards_do_not_survive_their_board(self, client, db_session):
        admin = User.create_user("cd_admin", "password", admin=True)
        board = Board.create_with_columns(owner=admin, name="CD Board")
        column = list(board.columns)[0]
        Card.create(column=column, title="orphan", position=0)

        response = client.delete(
            f"/api/admin/boards/{board.id}", headers=headers(admin)
        )
        assert response.status_code == 200
        assert Card.select().where(Card.column == column.id).count() == 0
        assert Column.select().where(Column.board == board.id).count() == 0
