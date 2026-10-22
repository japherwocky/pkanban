"""Card archiving (#781): archive/unarchive, board views, search and limits."""

import os
import sys
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.auth import create_access_token  # noqa: E402
from backend.billing import FREE_MAX_CARDS_PER_BOARD  # noqa: E402
from backend.main import app  # noqa: E402
from backend.models import (  # noqa: E402
    Board,
    Card,
    CardSearch,
    Column,
    Organization,
    BoardTeam,
    Team,
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


def first_column(board):
    return board.columns.order_by(Column.position).first()


def add_card(client, user, column, title, position=0):
    response = client.post(
        "/api/cards",
        json={"column_id": column.id, "title": title, "position": position},
        headers=headers(user),
    )
    assert response.status_code == 200, response.json()
    return response.json()


def archive(client, user, card_id):
    return client.post(f"/api/cards/{card_id}/archive", headers=headers(user))


def unarchive(client, user, card_id):
    return client.post(f"/api/cards/{card_id}/unarchive", headers=headers(user))


def board_cards(client, user, board, **params):
    response = client.get(f"/api/boards/{board.id}", params=params, headers=headers(user))
    assert response.status_code == 200, response.json()
    return response.json()


def titles(board_json):
    return [c["title"] for col in board_json["columns"] for c in col["cards"]]


@pytest.fixture
def owner(db_session):
    return User.create_user("arch_owner", "password")


@pytest.fixture
def board(owner):
    return Board.create_with_columns(owner=owner, name="Archive board")


class TestArchiving:
    def test_an_archived_card_leaves_the_board_view(self, client, owner, board):
        column = first_column(board)
        keep = add_card(client, owner, column, "Keep", 0)
        gone = add_card(client, owner, column, "Gone", 1)

        response = archive(client, owner, gone["id"])
        assert response.status_code == 200
        assert response.json()["archived_at"] is not None

        view = board_cards(client, owner, board)
        assert titles(view) == ["Keep"]
        assert view["columns"][0]["archived_count"] == 1
        assert view["columns"][0]["cards"][0]["id"] == keep["id"]
        assert view["columns"][0]["cards"][0]["archived_at"] is None

    def test_include_archived_shows_them_flagged(self, client, owner, board):
        column = first_column(board)
        add_card(client, owner, column, "Live", 0)
        gone = add_card(client, owner, column, "Gone", 1)
        archive(client, owner, gone["id"])

        view = board_cards(client, owner, board, include_archived=True)
        cards = {c["title"]: c for c in view["columns"][0]["cards"]}
        assert set(cards) == {"Live", "Gone"}
        assert cards["Gone"]["archived_at"] is not None
        assert cards["Live"]["archived_at"] is None

    def test_archiving_twice_keeps_the_first_timestamp(self, client, owner, board):
        card = add_card(client, owner, first_column(board), "Twice")
        first = archive(client, owner, card["id"]).json()["archived_at"]
        second = archive(client, owner, card["id"]).json()["archived_at"]
        assert first == second

    def test_the_card_itself_still_reads_and_says_it_is_archived(
        self, client, owner, board
    ):
        card = add_card(client, owner, first_column(board), "Readable")
        archive(client, owner, card["id"])

        response = client.get(f"/api/cards/{card['id']}", headers=headers(owner))
        assert response.status_code == 200
        assert response.json()["archived_at"] is not None
        assert response.json()["column_id"] == first_column(board).id

    def test_editing_an_archived_card_keeps_it_archived(self, client, owner, board):
        card = add_card(client, owner, first_column(board), "Before")
        archive(client, owner, card["id"])

        response = client.put(
            f"/api/cards/{card['id']}", json={"title": "After"}, headers=headers(owner)
        )
        assert response.json()["archived_at"] is not None
        assert titles(board_cards(client, owner, board)) == []


class TestUnarchiving:
    def test_comes_back_at_the_bottom_of_its_column(self, client, owner, board):
        column = first_column(board)
        old = add_card(client, owner, column, "Old", 0)
        archive(client, owner, old["id"])
        add_card(client, owner, column, "A", 0)
        add_card(client, owner, column, "B", 1)

        response = unarchive(client, owner, old["id"])
        assert response.status_code == 200
        assert response.json()["archived_at"] is None
        assert titles(board_cards(client, owner, board)) == ["A", "B", "Old"]
        assert board_cards(client, owner, board)["columns"][0]["archived_count"] == 0

    def test_into_an_otherwise_empty_column(self, client, owner, board):
        card = add_card(client, owner, first_column(board), "Alone", 7)
        archive(client, owner, card["id"])

        assert unarchive(client, owner, card["id"]).json()["position"] == 0

    def test_a_live_card_is_left_alone(self, client, owner, board):
        card = add_card(client, owner, first_column(board), "Live", 3)
        response = unarchive(client, owner, card["id"])
        assert response.json()["position"] == 3
        assert response.json()["archived_at"] is None


class TestAccess:
    def test_strangers_cannot_archive_or_unarchive(self, client, owner, board):
        stranger = User.create_user("arch_stranger", "password")
        card = add_card(client, owner, first_column(board), "Mine")

        assert archive(client, stranger, card["id"]).status_code == 403
        archive(client, owner, card["id"])
        assert unarchive(client, stranger, card["id"]).status_code == 403
        assert Card.get_by_id(card["id"]).archived_at is not None

    def test_a_missing_card_is_404(self, client, owner):
        assert archive(client, owner, 999999).status_code == 404
        assert unarchive(client, owner, 999999).status_code == 404

    def test_a_teammate_can_archive(self, client, owner, board):
        teammate = User.create_user("arch_team", "password")
        org = Organization.create_with_columns("Arch Org", "arch-org", owner)
        team = Team.create_with_columns("Arch Team", org)
        TeamMember.create(user=teammate, team=team, joined_at=datetime.now(timezone.utc))
        BoardTeam.create(board=board, team=team, permission="write")
        card = add_card(client, owner, first_column(board), "Shared")

        assert archive(client, teammate, card["id"]).status_code == 200

    def test_requires_auth(self, client, owner, board):
        card = add_card(client, owner, first_column(board), "Auth")
        assert client.post(f"/api/cards/{card['id']}/archive").status_code == 401


class TestSearchFindsArchivedCards:
    def test_archived_cards_are_found_and_flagged(self, client, owner, board):
        column = first_column(board)
        live = add_card(client, owner, column, "Rocket live")
        gone = add_card(client, owner, column, "Rocket archived")
        archive(client, owner, gone["id"])

        results = client.get(
            "/api/search", params={"q": "rocket"}, headers=headers(owner)
        ).json()
        flags = {r["id"]: r["archived_at"] for r in results}
        assert set(flags) == {live["id"], gone["id"]}
        assert flags[live["id"]] is None
        assert flags[gone["id"]] is not None

    def test_a_card_id_lookup_flags_it_too(self, client, owner, board):
        card = add_card(client, owner, first_column(board), "By id")
        archive(client, owner, card["id"])

        (result,) = client.get(
            "/api/search", params={"q": f"#{card['id']}"}, headers=headers(owner)
        ).json()
        assert result["archived_at"] is not None

    def test_archiving_leaves_the_index_consistent(self, client, owner, board):
        card = add_card(client, owner, first_column(board), "Indexed")
        archive(client, owner, card["id"])
        unarchive(client, owner, card["id"])
        CardSearch.integrity_check(rank=1)


class TestPlanLimit:
    def test_archived_cards_still_count(self, client, owner, board, monkeypatch):
        """By decision (#781): archiving is not a way under the free plan's
        per-board cap, so a board full of archived cards is still full."""
        monkeypatch.setenv("BILLING_ENABLED", "true")
        column = first_column(board)
        for n in range(FREE_MAX_CARDS_PER_BOARD):
            Card.create(
                column=column,
                title=f"c{n}",
                position=n,
                archived_at=datetime.now(timezone.utc),
            )

        response = client.post(
            "/api/cards",
            json={"column_id": column.id, "title": "one more", "position": 0},
            headers=headers(owner),
        )
        assert response.status_code == 402
        assert "archived cards included" in response.json()["detail"]


def test_deleting_a_column_takes_its_archived_cards_with_it(client, owner, board):
    """Documented rather than prevented: the board view reports archived_count
    per column so the UI can say so before the delete."""
    column = first_column(board)
    card = add_card(client, owner, column, "Hidden")
    archive(client, owner, card["id"])

    client.delete(f"/api/columns/{column.id}", headers=headers(owner))
    assert Card.get_or_none(Card.id == card["id"]) is None
