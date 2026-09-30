"""Plan limits: the free plan's board and card caps, behind BILLING_ENABLED.

The billing unit is the board owner. These tests pin the parts that are easy to
get wrong: the cap follows the OWNER's plan (not the caller's), a card moved to
another board counts there, and being over a limit never blocks anything but
creating more.
"""

import random
import string
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.auth import create_access_token
from backend.billing import FREE_MAX_BOARDS, FREE_MAX_CARDS_PER_BOARD
from backend.main import app
from backend.models import (
    Board,
    Card,
    Column,
    Organization,
    Team,
    TeamMember,
    User,
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def billing_on(monkeypatch):
    monkeypatch.setenv("BILLING_ENABLED", "true")


def make_user(plan="free"):
    suffix = "".join(random.choices(string.ascii_lowercase, k=8))
    user = User.create_user(f"limit_{suffix}", "testpassword")
    if plan != "free":
        user.plan = plan
        user.save()
    return user


def auth(user):
    token = create_access_token(data={"sub": user.id, "username": user.username})
    return {"Authorization": f"Bearer {token}"}


def fill_boards(user, n):
    return [Board.create_with_columns(owner=user, name=f"b{i}") for i in range(n)]


def first_column(board):
    return board.columns.order_by(Column.position).first()


def fill_cards(board, n):
    """Put n cards in the board's first column; returns that column."""
    column = first_column(board)
    Card.insert_many(
        [{"column": column, "title": f"c{i}", "position": i} for i in range(n)]
    ).execute()
    return column


def team_board(owner, member):
    """A board owned by `owner` and shared with a team that `member` is on."""
    slug = "o-" + "".join(random.choices(string.ascii_lowercase, k=10))
    org = Organization.create_with_columns("o", slug, owner)
    team = Team.create_with_columns("t", org)
    TeamMember.create(user=member, team=team, joined_at=datetime.now(timezone.utc))
    return Board.create_with_columns(owner=owner, name="shared", shared_team=team)


def add_card(client, user, column, title="x"):
    return client.post(
        "/api/cards",
        json={"column_id": column.id, "title": title, "position": 0},
        headers=auth(user),
    )


# --- the switch ------------------------------------------------------------


def test_no_limits_while_billing_is_off(client, db_session, monkeypatch):
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    user = make_user()
    fill_boards(user, FREE_MAX_BOARDS)
    r = client.post("/api/boards", json={"name": "one more"}, headers=auth(user))
    assert r.status_code == 200

    board = Board.create_with_columns(owner=user, name="full")
    column = fill_cards(board, FREE_MAX_CARDS_PER_BOARD)
    assert add_card(client, user, column).status_code == 200


# --- boards ----------------------------------------------------------------


def test_free_user_can_own_up_to_the_limit(client, db_session, billing_on):
    user = make_user()
    fill_boards(user, FREE_MAX_BOARDS - 1)
    r = client.post("/api/boards", json={"name": "fifth"}, headers=auth(user))
    assert r.status_code == 200


def test_free_user_over_the_board_limit_gets_a_readable_402(
    client, db_session, billing_on
):
    user = make_user()
    fill_boards(user, FREE_MAX_BOARDS)
    r = client.post("/api/boards", json={"name": "sixth"}, headers=auth(user))
    assert r.status_code == 402
    body = r.json()
    assert body["error"] == "plan_limit"
    assert body["limit"] == "boards"
    assert body["max"] == FREE_MAX_BOARDS
    assert body["current"] == FREE_MAX_BOARDS
    assert body["detail"]  # the key existing clients already print
    assert Board.select().where(Board.owner == user).count() == FREE_MAX_BOARDS


def test_pro_user_has_no_board_limit(client, db_session, billing_on):
    user = make_user(plan="pro")
    fill_boards(user, FREE_MAX_BOARDS)
    r = client.post("/api/boards", json={"name": "sixth"}, headers=auth(user))
    assert r.status_code == 200


def test_boards_shared_with_you_do_not_count_toward_your_limit(
    client, db_session, billing_on
):
    owner = make_user(plan="pro")
    user = make_user()
    for _ in range(FREE_MAX_BOARDS + 2):
        team_board(owner, user)
    r = client.post("/api/boards", json={"name": "mine"}, headers=auth(user))
    assert r.status_code == 200


# --- cards -----------------------------------------------------------------


def test_free_board_holds_exactly_the_card_limit(client, db_session, billing_on):
    user = make_user()
    board = Board.create_with_columns(owner=user, name="b")
    column = fill_cards(board, FREE_MAX_CARDS_PER_BOARD - 1)
    assert add_card(client, user, column).status_code == 200
    r = add_card(client, user, column)
    assert r.status_code == 402
    assert r.json()["limit"] == "cards_per_board"
    assert r.json()["max"] == FREE_MAX_CARDS_PER_BOARD
    assert r.json()["current"] == FREE_MAX_CARDS_PER_BOARD


def test_card_limit_counts_every_column_done_included(
    client, db_session, billing_on
):
    user = make_user()
    board = Board.create_with_columns(owner=user, name="b")
    done = Column.create(board=board, name="Done", position=9)
    Card.insert_many(
        [
            {"column": done, "title": f"d{i}", "position": i}
            for i in range(FREE_MAX_CARDS_PER_BOARD)
        ]
    ).execute()
    assert add_card(client, user, first_column(board)).status_code == 402


def test_card_cap_is_per_board(client, db_session, billing_on):
    user = make_user()
    full = Board.create_with_columns(owner=user, name="full")
    fill_cards(full, FREE_MAX_CARDS_PER_BOARD)
    other = Board.create_with_columns(owner=user, name="other")
    assert add_card(client, user, first_column(other)).status_code == 200


def test_a_free_member_on_a_pro_owners_board_is_unlimited(
    client, db_session, billing_on
):
    owner = make_user(plan="pro")
    member = make_user()
    board = team_board(owner, member)
    column = fill_cards(board, FREE_MAX_CARDS_PER_BOARD)
    assert add_card(client, member, column).status_code == 200


def test_a_pro_member_on_a_free_owners_full_board_is_still_capped(
    client, db_session, billing_on
):
    owner = make_user()
    member = make_user(plan="pro")
    board = team_board(owner, member)
    column = fill_cards(board, FREE_MAX_CARDS_PER_BOARD)
    assert add_card(client, member, column).status_code == 402


# --- moving a card ---------------------------------------------------------


def test_moving_a_card_to_a_full_board_is_refused(client, db_session, billing_on):
    user = make_user()
    full = Board.create_with_columns(owner=user, name="full")
    fill_cards(full, FREE_MAX_CARDS_PER_BOARD)
    src = Board.create_with_columns(owner=user, name="src")
    card = Card.create(column=first_column(src), title="mover", position=0)
    r = client.put(
        f"/api/cards/{card.id}",
        json={"column_id": first_column(full).id},
        headers=auth(user),
    )
    assert r.status_code == 402
    assert r.json()["limit"] == "cards_per_board"
    assert Card.get_by_id(card.id).column_id == first_column(src).id


def test_moving_a_card_to_a_board_with_room_is_allowed(
    client, db_session, billing_on
):
    user = make_user()
    src = Board.create_with_columns(owner=user, name="src")
    dst = Board.create_with_columns(owner=user, name="dst")
    card = Card.create(column=first_column(src), title="mover", position=0)
    r = client.put(
        f"/api/cards/{card.id}",
        json={"column_id": first_column(dst).id},
        headers=auth(user),
    )
    assert r.status_code == 200
    assert Card.get_by_id(card.id).column_id == first_column(dst).id


def test_moving_a_card_within_a_full_board_is_allowed(
    client, db_session, billing_on
):
    user = make_user()
    board = Board.create_with_columns(owner=user, name="full")
    column = fill_cards(board, FREE_MAX_CARDS_PER_BOARD)
    card = column.cards.first()
    target = board.columns.order_by(Column.position).offset(1).first()
    r = client.put(
        f"/api/cards/{card.id}", json={"column_id": target.id}, headers=auth(user)
    )
    # The board still holds 100 cards: a move inside it changes nothing.
    assert r.status_code == 200
    assert Card.get_by_id(card.id).column_id == target.id


# --- over the limit is not locked out --------------------------------------


def test_a_user_over_the_limit_can_still_edit_and_delete(
    client, db_session, billing_on
):
    user = make_user()
    board = Board.create_with_columns(owner=user, name="b")
    column = fill_cards(board, FREE_MAX_CARDS_PER_BOARD + 5)
    card = column.cards.first()
    h = auth(user)

    assert (
        client.put(
            f"/api/cards/{card.id}", json={"title": "renamed"}, headers=h
        ).status_code
        == 200
    )
    assert client.get(f"/api/boards/{board.id}", headers=h).status_code == 200
    assert client.delete(f"/api/cards/{card.id}", headers=h).status_code == 200
    # Still over the cap after the delete, so still no new cards.
    assert add_card(client, user, column).status_code == 402


# --- usage -----------------------------------------------------------------


def get_usage(client, user):
    r = client.get("/api/me/usage", headers=auth(user))
    assert r.status_code == 200
    return r.json()


def test_usage_for_a_free_user_reports_limits_and_busiest_boards_first(
    client, db_session, billing_on
):
    user = make_user()
    quiet, busy = fill_boards(user, 2)
    fill_cards(busy, 7)
    usage = get_usage(client, user)
    assert usage["plan"] == "free"
    assert usage["billing_enabled"] is True
    assert usage["max_boards"] == FREE_MAX_BOARDS
    assert usage["max_cards_per_board"] == FREE_MAX_CARDS_PER_BOARD
    assert usage["boards_owned"] == 2
    assert [(b["id"], b["cards"]) for b in usage["boards"]] == [
        (busy.id, 7),
        (quiet.id, 0),
    ]


def test_usage_counts_owned_boards_not_shared_ones(client, db_session, billing_on):
    owner = make_user(plan="pro")
    user = make_user()
    team_board(owner, user)
    usage = get_usage(client, user)
    assert usage["boards_owned"] == 0
    assert usage["boards"] == []


def test_usage_for_a_user_with_no_boards(client, db_session, billing_on):
    usage = get_usage(client, make_user())
    assert usage["boards_owned"] == 0
    assert usage["boards"] == []


def test_usage_for_a_pro_user_has_no_maximums(client, db_session, billing_on):
    usage = get_usage(client, make_user(plan="pro"))
    assert usage["plan"] == "pro"
    assert usage["max_boards"] is None
    assert usage["max_cards_per_board"] is None


def test_usage_has_no_maximums_while_billing_is_off(
    client, db_session, monkeypatch
):
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    usage = get_usage(client, make_user())
    assert usage["billing_enabled"] is False
    assert usage["max_boards"] is None
    assert usage["max_cards_per_board"] is None


def test_usage_requires_authentication(client, db_session):
    assert client.get("/api/me/usage").status_code == 401
