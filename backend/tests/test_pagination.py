"""Paged list routes: limit, keyset cursor, headers, and the CLI following them."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.auth import create_access_token
from backend.main import app
from backend.models import Board, User
from pkanban.client import PkanbanClient


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers(test_user):
    token = create_access_token(data={"sub": test_user.id, "username": test_user.username})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def five_boards(test_user):
    return [Board.create_with_columns(owner=test_user, name=f"b{i}") for i in range(5)]


def ids(response):
    return [b["id"] for b in response.json()]


def test_default_page_is_generous_and_complete(client, auth_headers, five_boards):
    response = client.get("/api/boards", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 5
    assert response.headers["X-Total-Count"] == "5"
    assert "X-Next-Cursor" not in response.headers


def test_limit_pages_through_everything_exactly_once(client, auth_headers, five_boards):
    seen, cursor = [], None
    for _ in range(10):
        params = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        response = client.get("/api/boards", params=params, headers=auth_headers)
        seen += ids(response)
        assert response.headers["X-Total-Count"] == "5"
        cursor = response.headers.get("X-Next-Cursor")
        if not cursor:
            break
    assert seen == sorted(b.id for b in five_boards)


def test_cursor_is_stable_when_a_row_is_deleted_between_pages(client, auth_headers, five_boards):
    first = client.get("/api/boards", params={"limit": 2}, headers=auth_headers)
    five_boards[0].delete_instance()  # an offset would now skip a board
    rest = client.get(
        "/api/boards",
        params={"limit": 10, "cursor": first.headers["X-Next-Cursor"]},
        headers=auth_headers,
    )
    assert ids(first)[1:] + ids(rest) == [b.id for b in five_boards[1:]]


def test_limit_is_bounded(client, auth_headers):
    assert client.get("/api/boards", params={"limit": 0}, headers=auth_headers).status_code == 422
    assert client.get("/api/boards", params={"limit": 10**6}, headers=auth_headers).status_code == 422


def test_admin_lists_are_paged_too(client, test_user, five_boards):
    admin = User.create_user(username="pager_admin", password="pw", admin=True)
    headers = {"Authorization": "Bearer " + create_access_token(data={"sub": admin.id, "username": admin.username})}
    for route in ("/api/admin/users", "/api/admin/boards"):
        response = client.get(route, params={"limit": 1}, headers=headers)
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert "X-Next-Cursor" in response.headers


def test_cli_client_follows_cursors_to_the_end():
    pages = [
        ([{"id": 1}, {"id": 2}], {"X-Next-Cursor": "2"}),
        ([{"id": 3}], {}),
    ]
    calls = []

    def send(method, path, **kwargs):
        calls.append(kwargs["params"])
        body, headers = pages[len(calls) - 1]
        response = MagicMock()
        response.json.return_value = body
        response.headers = headers
        return response

    cli_client = PkanbanClient.__new__(PkanbanClient)
    cli_client._send = send
    assert [b["id"] for b in cli_client._request_all("/api/boards")] == [1, 2, 3]
    assert calls == [{}, {"cursor": "2"}]


def test_cli_client_refuses_a_cursor_that_does_not_move():
    """A server that hands back the cursor it was given would page forever."""
    from pkanban.client import PkanbanError

    def send(method, path, **kwargs):
        response = MagicMock()
        response.json.return_value = [{"id": 1}]
        response.headers = {"X-Next-Cursor": "1"}
        return response

    cli_client = PkanbanClient.__new__(PkanbanClient)
    cli_client._send = send
    with pytest.raises(PkanbanError, match="same page cursor"):
        cli_client._request_all("/api/boards")
