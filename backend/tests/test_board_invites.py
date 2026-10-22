"""Inviting someone to one board by email (Dev #1038).

POST /boards/{id}/invites makes a team of inviter and invitee (no org),
shares the board with it at the level asked for, and sends a team invite.
These follow that through to the invitee landing on the board, and pin
re-sending, revoking, and who may do it.
"""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.api import BOARD_INVITES_PER_HOUR
from backend.auth import create_access_token
from backend.main import app
from backend.models import (
    Board,
    BoardTeam,
    OrganizationInvite,
    Team,
    TeamMember,
    User,
)

CURTIS = "curtis@heckinquest.example"


@pytest.fixture
def client(db_session):
    return TestClient(app)


def headers(user):
    return {
        "Authorization": "Bearer "
        + create_access_token(data={"sub": user.id, "username": user.username})
    }


@pytest.fixture
def owner(db_session):
    return User.create_user("bi_owner", "password", email="owner@example.com")


@pytest.fixture
def board(owner):
    return Board.create_with_columns(owner=owner, name="heckinquest")


def invite(client, user, board, email=CURTIS, permission="write"):
    with patch("backend.api.send_board_invite_email") as sent:
        response = client.post(
            f"/api/boards/{board.id}/invites",
            json={"email": email, "permission": permission},
            headers=headers(user),
        )
    return response, sent


def token_of(response):
    return response.json()["invite"]["url"].rsplit("/", 1)[1]


class TestInviting:
    def test_makes_a_team_of_two_shares_the_board_and_sends_the_mail(self, client, owner, board):
        response, sent = invite(client, owner, board, permission="read")
        assert response.status_code == 200, response.json()
        body = response.json()

        team = Team.get_by_id(body["invite"]["team_id"])
        assert team.organization_id is None
        assert team.name == "heckinquest: curtis"
        assert [m.user_id for m in team.members] == [owner.id]
        assert BoardTeam.get(BoardTeam.team == team).permission == "read"

        # The mail names the board and the level, not the team.
        assert sent.call_args.args[0] == CURTIS
        assert sent.call_args.args[2:] == ("bi_owner", "heckinquest", "read")
        assert body["email_sent"] is False  # no RESEND_API_KEY in tests
        assert body["invite"]["url"].endswith(sent.call_args.args[1])

        assert [i["email"] for i in body["invites"]] == [CURTIS]

    def test_the_invitee_lands_on_the_board_at_that_level_and_nothing_else(
        self, client, owner, board
    ):
        Board.create_with_columns(owner=owner, name="Private")
        response, _ = invite(client, owner, board, permission="read")
        token = token_of(response)

        landing = client.get(f"/api/invites/{token}").json()
        assert landing["board_id"] == board.id
        assert landing["board_name"] == "heckinquest"
        assert landing["permission"] == "read"

        curtis = User.create_user("curtis", "password", email=CURTIS)
        accepted = client.post(f"/api/invites/{token}/accept", headers=headers(curtis))
        assert accepted.status_code == 200, accepted.json()
        assert accepted.json()["board_id"] == board.id

        boards = client.get("/api/boards", headers=headers(curtis)).json()
        assert [(b["id"], b["permission"]) for b in boards] == [(board.id, "read")]

    def test_only_the_invited_address_can_accept(self, client, owner, board):
        response, _ = invite(client, owner, board)
        other = User.create_user("someone", "password", email="someone@example.com")
        refused = client.post(
            f"/api/invites/{token_of(response)}/accept", headers=headers(other)
        )
        assert refused.status_code == 403

    def test_inviting_again_resends_on_the_same_team_at_the_new_level(
        self, client, owner, board
    ):
        first, _ = invite(client, owner, board, permission="read")
        second, sent = invite(client, owner, board, email=CURTIS.upper(), permission="write")
        assert second.status_code == 200, second.json()
        assert second.json()["invite"]["team_id"] == first.json()["invite"]["team_id"]
        assert sent.called

        assert Team.select().count() == 1
        assert BoardTeam.get().permission == "write"
        assert [i["id"] for i in second.json()["invites"]] == [second.json()["invite"]["id"]]
        # The first link is dead.
        assert client.get(f"/api/invites/{token_of(first)}").status_code == 404

    def test_someone_who_can_already_open_it_is_refused(self, client, owner, board):
        member = User.create_user("member", "password", email=CURTIS)
        team = Team.create_with_columns("Core")
        TeamMember.create(user=member, team=team, joined_at=datetime.now(timezone.utc))
        BoardTeam.create(board=board, team=team, permission="read")

        response, sent = invite(client, owner, board)
        assert response.status_code == 400
        assert "already" in response.json()["detail"]
        assert not sent.called

        mine, _ = invite(client, owner, board, email="owner@example.com")
        assert mine.status_code == 400

    @pytest.mark.parametrize("email", ["", "curtis", "curtis@", "a b@c.d"])
    def test_not_an_address_is_refused(self, client, owner, board, email):
        response, sent = invite(client, owner, board, email=email)
        assert response.status_code == 400
        assert not sent.called

    def test_an_unknown_level_is_refused(self, client, owner, board):
        response, _ = invite(client, owner, board, permission="owner")
        assert response.status_code == 422

    def test_there_is_an_hourly_budget(self, client, owner, board):
        for n in range(BOARD_INVITES_PER_HOUR):
            response, _ = invite(client, owner, board, email=f"p{n}@example.com")
            assert response.status_code == 200
        response, sent = invite(client, owner, board, email="one-more@example.com")
        assert response.status_code == 429
        assert not sent.called


class TestWhoMayInvite:
    def test_an_admin_may(self, client, owner, board):
        admin = User.create_user("admin_member", "password")
        team = Team.create_with_columns("Admins")
        TeamMember.create(user=admin, team=team, joined_at=datetime.now(timezone.utc))
        BoardTeam.create(board=board, team=team, permission="admin")
        response, _ = invite(client, admin, board)
        assert response.status_code == 200, response.json()

    def test_a_writer_may_not_and_sees_no_invites(self, client, owner, board):
        invite(client, owner, board)
        writer = User.create_user("writer", "password")
        team = Team.create_with_columns("Writers")
        TeamMember.create(user=writer, team=team, joined_at=datetime.now(timezone.utc))
        BoardTeam.create(board=board, team=team, permission="write")

        response, sent = invite(client, writer, board, email="x@example.com")
        assert response.status_code == 403
        assert not sent.called
        assert client.get(
            f"/api/boards/{board.id}", headers=headers(writer)
        ).json()["invites"] is None


def test_the_board_itself_lists_pending_invites_for_its_admin(client, owner, board):
    """GET /boards/{id} is what the share dialog reloads; its response model
    must carry the invites through, not drop them as an unknown field."""
    invite(client, owner, board)
    got = client.get(f"/api/boards/{board.id}", headers=headers(owner)).json()
    assert [i["email"] for i in got["invites"]] == [CURTIS]


class TestRevoking:
    def test_revoking_kills_the_link_and_clears_away_the_empty_team(self, client, owner, board):
        response, _ = invite(client, owner, board)
        invite_id = response.json()["invite"]["id"]

        revoked = client.delete(
            f"/api/boards/{board.id}/invites/{invite_id}", headers=headers(owner)
        )
        assert revoked.status_code == 200
        assert revoked.json()["invites"] == []
        assert revoked.json()["teams"] == []
        assert not Team.select().exists()
        assert client.get(f"/api/invites/{token_of(response)}").status_code == 404

    def test_revoking_on_a_team_with_people_on_it_keeps_the_team(self, client, owner, board):
        response, _ = invite(client, owner, board)
        team = Team.get_by_id(response.json()["invite"]["team_id"])
        friend = User.create_user("friend", "password")
        TeamMember.create(user=friend, team=team, joined_at=datetime.now(timezone.utc))

        client.delete(
            f"/api/boards/{board.id}/invites/{response.json()['invite']['id']}",
            headers=headers(owner),
        )
        assert Team.select().count() == 1
        assert BoardTeam.select().count() == 1

    def test_removing_the_team_from_the_board_revokes_its_invite(self, client, owner, board):
        response, _ = invite(client, owner, board)
        team_id = response.json()["invite"]["team_id"]
        client.delete(f"/api/boards/{board.id}/teams/{team_id}", headers=headers(owner))

        assert OrganizationInvite.get_by_id(response.json()["invite"]["id"]).status == "revoked"

    def test_an_invite_on_another_board_is_not_reachable(self, client, owner, board):
        response, _ = invite(client, owner, board)
        other = Board.create_with_columns(owner=owner, name="Other")
        assert client.delete(
            f"/api/boards/{other.id}/invites/{response.json()['invite']['id']}",
            headers=headers(owner),
        ).status_code == 404


def test_a_general_teams_invite_still_names_the_team(client, owner, board):
    """A team holding several boards is not "for" one of them, so its invite
    page describes the team, as before."""
    team = Team.create_with_columns("Core")
    TeamMember.create(user=owner, team=team, joined_at=datetime.now(timezone.utc))
    for b in (board, Board.create_with_columns(owner=owner, name="Second")):
        BoardTeam.create(board=b, team=team, permission="write")
    with patch("backend.api.send_invite_email"):
        made = client.post(
            f"/api/teams/{team.id}/invites", json={"email": CURTIS}, headers=headers(owner)
        )
    landing = client.get(f"/api/invites/{made.json()['token']}").json()
    assert landing["team_name"] == "Core"
    assert "board_id" not in landing


def test_the_mail_escapes_the_board_name_and_says_what_the_level_allows():
    from backend import mailer

    with patch.object(mailer, "send_email", return_value=True) as send:
        mailer.send_board_invite_email(
            CURTIS, "tok", "japhy", "<script>x</script>", "read"
        )
    to, subject, html = send.call_args.args
    assert to == CURTIS
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "you can read it." in html
    assert "/invite/tok" in html
    assert subject == "japhy invited you to <script>x</script> on pkanban"
