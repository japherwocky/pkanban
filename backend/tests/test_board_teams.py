"""Boards shared with many teams, each at read / write / admin (Dev #1037).

A board used to hold one shared_team and grant it everything. Now BoardTeam
is many-to-many with a level, board_permission() takes the highest route in,
and every write endpoint asks for write. These pin each level's edge, the
team check on sharing, and teams that have no organization.
"""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.auth import create_access_token
from backend.main import app
from backend.models import (
    ApiKey,
    Board,
    BoardTeam,
    Card,
    Column,
    Comment,
    Organization,
    OrganizationInvite,
    OrganizationMember,
    Team,
    TeamMember,
    User,
)


@pytest.fixture
def client(db_session):
    return TestClient(app)


def headers(user):
    return {
        "Authorization": "Bearer "
        + create_access_token(data={"sub": user.id, "username": user.username})
    }


def now():
    return datetime.now(timezone.utc)


def team_with(*users, name="Team", organization=None):
    team = Team.create_with_columns(name, organization)
    for user in users:
        TeamMember.create(user=user, team=team, joined_at=now())
    return team


@pytest.fixture
def owner(db_session):
    return User.create_user("bt_owner", "password", email="owner@example.com")


@pytest.fixture
def member(db_session):
    return User.create_user("bt_member", "password", email="member@example.com")


@pytest.fixture
def board(owner, member):
    board = Board.create_with_columns(owner=owner, name="Shared")
    column = board.columns.order_by(Column.position).first()
    card = Card.create(column=column, title="A card", position=0)
    # The member's own comment, so editing it turns on their level alone.
    Comment.create(card=card, user=member, content="hi", created_at=now())
    return board


def grant(board, user, level):
    team = team_with(user, name=f"{level} team")
    BoardTeam.create(board=board, team=team, permission=level)
    return team


def parts(board):
    column = board.columns.order_by(Column.position).first()
    card = column.cards.first()
    comment = Comment.get(Comment.card == card)
    return column, card, comment


def writes(board):
    """Every endpoint that changes a board, as (method, path, json)."""
    column, card, comment = parts(board)
    return [
        ("post", f"/api/boards/{board.id}", {"name": "Renamed"}),
        ("post", "/api/columns", {"board_id": board.id, "name": "New", "position": 9}),
        ("put", f"/api/columns/{column.id}", {"name": "Col", "position": 0}),
        ("post", "/api/columns/reorder", {"columns": [{"id": column.id, "position": 0}]}),
        ("post", "/api/cards", {"column_id": column.id, "title": "New", "position": 0}),
        ("put", f"/api/cards/{card.id}", {"title": "Changed"}),
        ("post", f"/api/cards/{card.id}/archive", None),
        ("post", f"/api/cards/{card.id}/unarchive", None),
        ("post", "/api/cards/reorder", {"cards": [{"id": card.id, "position": 0}]}),
        ("post", "/api/comments", {"card_id": card.id, "content": "more"}),
        ("put", f"/api/comments/{comment.id}", {"content": "edited"}),
        ("delete", f"/api/comments/{comment.id}", None),
        ("delete", f"/api/cards/{card.id}", None),
        ("delete", f"/api/columns/{column.id}", None),
    ]


def send(client, user, method, path, body):
    kwargs = {"headers": headers(user)}
    if body is not None:
        kwargs["json"] = body
    return getattr(client, method)(path, **kwargs)


# --- Levels -----------------------------------------------------------------


class TestReadOnly:
    def test_a_reader_sees_the_board_its_cards_and_search(self, client, board, member):
        grant(board, member, "read")
        _, card, _ = parts(board)

        got = client.get(f"/api/boards/{board.id}", headers=headers(member))
        assert got.status_code == 200
        assert got.json()["permission"] == "read"
        assert client.get(f"/api/cards/{card.id}", headers=headers(member)).status_code == 200
        assert client.get(
            f"/api/cards/{card.id}/comments", headers=headers(member)
        ).status_code == 200
        assert [b["id"] for b in client.get("/api/boards", headers=headers(member)).json()] == [
            board.id
        ]
        found = client.get("/api/search", params={"q": "card"}, headers=headers(member))
        assert [r["id"] for r in found.json()] == [card.id]

    def test_a_reader_is_refused_every_write(self, client, board, member):
        grant(board, member, "read")
        for method, path, body in writes(board):
            response = send(client, member, method, path, body)
            assert response.status_code == 403, (method, path, response.json())

        # And nothing changed underneath.
        column, card, comment = parts(board)
        assert Board.get_by_id(board.id).name == "Shared"
        assert card.title == "A card" and card.archived_at is None
        assert comment.content == "hi"

    def test_a_reader_cannot_move_a_card_onto_the_board(self, client, board, owner, member):
        grant(board, member, "read")
        mine = Board.create_with_columns(owner=member, name="Mine")
        my_column = mine.columns.first()
        card = Card.create(column=my_column, title="Mine", position=0)
        target = parts(board)[0]

        moved = client.put(
            f"/api/cards/{card.id}",
            json={"column_id": target.id},
            headers=headers(member),
        )
        assert moved.status_code == 403


class TestWrite:
    def test_a_writer_can_make_every_change(self, client, board, member):
        grant(board, member, "write")
        for method, path, body in writes(board):
            response = send(client, member, method, path, body)
            assert response.status_code == 200, (method, path, response.json())

    def test_a_writer_cannot_share(self, client, board, member):
        grant(board, member, "write")
        other = team_with(member, name="Elsewhere")
        assert client.put(
            f"/api/boards/{board.id}/teams/{other.id}",
            json={"permission": "read"},
            headers=headers(member),
        ).status_code == 403
        assert client.post(
            f"/api/boards/{board.id}/share",
            json={"team_id": None, "is_public_to_org": False},
            headers=headers(member),
        ).status_code == 403


class TestAdmin:
    def test_an_admin_can_share_and_unshare(self, client, board, member):
        grant(board, member, "admin")
        friend = User.create_user("bt_friend", "password")
        theirs = team_with(member, friend, name="Friends")

        shared = client.put(
            f"/api/boards/{board.id}/teams/{theirs.id}",
            json={"permission": "read"},
            headers=headers(member),
        )
        assert shared.status_code == 200, shared.json()
        assert client.get(f"/api/boards/{board.id}", headers=headers(friend)).json()[
            "permission"
        ] == "read"

        removed = client.delete(
            f"/api/boards/{board.id}/teams/{theirs.id}", headers=headers(member)
        )
        assert removed.status_code == 200
        assert client.get(
            f"/api/boards/{board.id}", headers=headers(friend)
        ).status_code == 403

    def test_only_the_owner_deletes_the_board(self, client, board, owner, member):
        grant(board, member, "admin")
        assert client.delete(
            f"/api/boards/{board.id}", headers=headers(member)
        ).status_code == 403
        assert client.delete(f"/api/boards/{board.id}", headers=headers(owner)).status_code == 200
        assert not BoardTeam.select().where(BoardTeam.board == board.id).exists()

    def test_the_owner_is_always_admin(self, client, board, owner):
        assert client.get(f"/api/boards/{board.id}", headers=headers(owner)).json()[
            "permission"
        ] == "admin"


class TestLevelsCombine:
    def test_the_highest_route_in_wins(self, client, board, member):
        grant(board, member, "read")
        grant(board, member, "write")
        got = client.get(f"/api/boards/{board.id}", headers=headers(member)).json()
        assert got["permission"] == "write"
        assert {t["permission"] for t in got["teams"]} == {"read", "write"}

    def test_two_teams_both_keep_access(self, client, board, owner, member):
        """The bug that made this card: sharing with a second team took the
        first one's access away."""
        other = User.create_user("bt_other", "password")
        first = team_with(owner, member, name="First")
        second = team_with(owner, other, name="Second")
        for team in (first, second):
            assert client.put(
                f"/api/boards/{board.id}/teams/{team.id}",
                json={"permission": "write"},
                headers=headers(owner),
            ).status_code == 200
        for user in (member, other):
            assert client.get(
                f"/api/boards/{board.id}", headers=headers(user)
            ).status_code == 200

    def test_changing_a_level_updates_the_grant(self, client, board, owner, member):
        team = team_with(owner, member)
        url = f"/api/boards/{board.id}/teams/{team.id}"
        client.put(url, json={"permission": "write"}, headers=headers(owner))
        client.put(url, json={"permission": "read"}, headers=headers(owner))
        assert BoardTeam.select().where(BoardTeam.board == board.id).count() == 1
        assert client.get(f"/api/boards/{board.id}", headers=headers(member)).json()[
            "permission"
        ] == "read"

    def test_an_unknown_level_is_rejected(self, client, board, owner, member):
        team = team_with(owner, member)
        response = client.put(
            f"/api/boards/{board.id}/teams/{team.id}",
            json={"permission": "root"},
            headers=headers(owner),
        )
        assert response.status_code == 422


class TestOrgPermission:
    @pytest.fixture
    def org(self, owner, member):
        org = Organization.create_with_columns("Acme", "acme", owner)
        for user in (owner, member):
            OrganizationMember.create(user=user, organization=org, joined_at=now())
        return org

    def test_public_to_org_defaults_to_write(self, client, board, owner, member, org):
        client.post(
            f"/api/boards/{board.id}/share",
            json={"is_public_to_org": True},
            headers=headers(owner),
        )
        assert client.get(f"/api/boards/{board.id}", headers=headers(member)).json()[
            "permission"
        ] == "write"

    def test_the_org_can_be_given_read(self, client, board, owner, member, org):
        client.post(
            f"/api/boards/{board.id}/share",
            json={"is_public_to_org": True, "org_permission": "read"},
            headers=headers(owner),
        )
        assert client.get(f"/api/boards/{board.id}", headers=headers(member)).json()[
            "permission"
        ] == "read"
        column = parts(board)[0]
        assert client.post(
            "/api/cards",
            json={"column_id": column.id, "title": "x", "position": 0},
            headers=headers(member),
        ).status_code == 403


# --- Who you may share with -------------------------------------------------


class TestShareTargets:
    def test_a_strangers_team_is_refused(self, client, board, owner):
        stranger = User.create_user("bt_stranger", "password")
        theirs = team_with(stranger, name="Theirs")
        response = client.put(
            f"/api/boards/{board.id}/teams/{theirs.id}",
            json={"permission": "write"},
            headers=headers(owner),
        )
        assert response.status_code == 403
        assert not BoardTeam.select().exists()
        # The legacy endpoint has the same check.
        assert client.post(
            f"/api/boards/{board.id}/share",
            json={"team_id": theirs.id},
            headers=headers(owner),
        ).status_code == 403

    def test_a_team_in_your_org_is_allowed_without_being_on_it(self, client, board, owner):
        org = Organization.create_with_columns("Acme", "acme", owner)
        team = team_with(name="Design", organization=org)
        assert client.put(
            f"/api/boards/{board.id}/teams/{team.id}",
            json={"permission": "write"},
            headers=headers(owner),
        ).status_code == 200

    def test_my_teams_lists_what_i_can_share_with(self, client, owner):
        stranger = User.create_user("bt_stranger", "password")
        org = Organization.create_with_columns("Acme", "acme", owner)
        mine = team_with(owner, name="Mine")
        in_org = team_with(name="In org", organization=org)
        team_with(stranger, name="Theirs")

        listed = client.get("/api/me/teams", headers=headers(owner)).json()
        assert {(t["id"], t["is_member"]) for t in listed} == {
            (mine.id, True),
            (in_org.id, False),
        }

    def test_removing_a_team_that_has_no_grant_is_404(self, client, board, owner):
        team = team_with(owner)
        assert client.delete(
            f"/api/boards/{board.id}/teams/{team.id}", headers=headers(owner)
        ).status_code == 404


class TestLegacyShare:
    """POST /share as older clients use it: a team_id adds at write, and no
    team with the org flag off makes the board private."""

    def test_team_id_adds_alongside_existing_teams(self, client, board, owner, member):
        first = grant(board, member, "read")
        TeamMember.create(user=owner, team=first, joined_at=now())
        second = team_with(owner, name="Second")
        client.post(
            f"/api/boards/{board.id}/share",
            json={"team_id": second.id},
            headers=headers(owner),
        )
        levels = {g.team_id: g.permission for g in BoardTeam.select()}
        assert levels == {first.id: "read", second.id: "write"}

    def test_private_removes_every_team(self, client, board, owner, member):
        grant(board, member, "write")
        grant(board, member, "read")
        response = client.post(
            f"/api/boards/{board.id}/share",
            json={"team_id": None, "is_public_to_org": False},
            headers=headers(owner),
        )
        assert response.status_code == 200
        assert response.json()["teams"] == []
        assert client.get(
            f"/api/boards/{board.id}", headers=headers(member)
        ).status_code == 403


# --- Teams with no organization -----------------------------------------------


class TestOrglessTeams:
    def test_create_one_and_share_a_board_with_it(self, client, board, owner, member):
        made = client.post("/api/teams", json={"name": "Curtis"}, headers=headers(owner))
        assert made.status_code == 200, made.json()
        team = made.json()
        assert team["organization_id"] is None

        added = client.post(
            f"/api/teams/{team['id']}/members",
            json={"username": member.username},
            headers=headers(owner),
        )
        assert added.status_code == 200
        client.put(
            f"/api/boards/{board.id}/teams/{team['id']}",
            json={"permission": "write"},
            headers=headers(owner),
        )
        got = client.get(f"/api/boards/{board.id}", headers=headers(member)).json()
        assert got["permission"] == "write"
        assert got["teams"][0]["organization_name"] is None

    def test_invite_by_email_with_no_org_to_name(self, client, owner):
        team = team_with(owner, name="Curtis")
        with patch("backend.api.send_invite_email") as sent:
            response = client.post(
                f"/api/teams/{team.id}/invites",
                json={"email": "curtis@example.com"},
                headers=headers(owner),
            )
        assert response.status_code == 200, response.json()
        invite = OrganizationInvite.get_by_id(response.json()["id"])
        assert invite.organization_id is None
        assert sent.call_args.args[2] is None  # org_name

        landing = client.get(f"/api/invites/{response.json()['token']}").json()
        assert landing["organization_name"] is None
        assert landing["team_name"] == "Curtis"

        curtis = User.create_user("curtis", "password", email="curtis@example.com")
        accepted = client.post(
            f"/api/invites/{response.json()['token']}/accept", headers=headers(curtis)
        )
        assert accepted.status_code == 200, accepted.json()
        assert accepted.json()["team_id"] == team.id
        assert accepted.json()["organization_id"] is None

    def test_any_member_may_delete_it_and_a_stranger_may_not(self, client, board, owner, member):
        team = team_with(owner, member)
        BoardTeam.create(board=board, team=team, permission="write")
        stranger = User.create_user("bt_stranger", "password")

        assert client.delete(f"/api/teams/{team.id}", headers=headers(stranger)).status_code == 403
        assert client.delete(f"/api/teams/{team.id}", headers=headers(member)).status_code == 200
        assert not BoardTeam.select().exists()

    def test_members_can_remove_only_themselves(self, client, owner, member):
        team = team_with(owner, member)
        assert client.delete(
            f"/api/teams/{team.id}/members/{member.id}", headers=headers(owner)
        ).status_code == 403
        assert client.delete(
            f"/api/teams/{team.id}/members/{member.id}", headers=headers(member)
        ).status_code == 200

    def test_admin_listing_survives_a_team_with_no_org(self, client, owner):
        admin = User.create_user("bt_admin", "password", admin=True)
        team_with(owner, name="Loose")
        listed = client.get("/api/admin/teams", headers=headers(admin))
        assert listed.status_code == 200, listed.json()
        assert listed.json()[0]["organization_name"] is None


# --- MCP ------------------------------------------------------------------------


def test_mcp_write_tools_are_refused_for_a_reader(db_session, board, member):
    grant(board, member, "read")
    key = ApiKey.create_key(member, "reader")[1]
    column = parts(board)[0]
    with TestClient(app) as client:
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "create_card",
                "arguments": {"column_id": column.id, "title": "nope"},
            },
        }
        response = client.post(
            "/mcp",
            json=body,
            headers={"Accept": "application/json, text/event-stream", "X-API-Key": key},
        )
    result = response.json()["result"]
    assert result["isError"], result
    assert Card.select().where(Card.title == "nope").count() == 0
