"""The MCP server at /mcp (Dev #970).

Driven over HTTP the way a real client drives it, through the app's lifespan,
since that is what starts the MCP request handler. The tools are thin calls to
the REST API, so these tests pin the seams rather than re-testing the API:
the key check at the door, what each tool sends and returns, and that the
API's own refusals (access, plan limits) reach the model as tool errors.
"""

import random
import string

import pytest
from fastapi.testclient import TestClient

from backend.auth import create_access_token
from backend.billing import FREE_MAX_BOARDS
from backend.main import app
from backend.models import ApiKey, Board, Column, User

ACCEPT = {"Accept": "application/json, text/event-stream"}

READ_ONLY = {"list_boards", "get_board", "get_card", "search_cards"}
WRITES = {
    "create_board",
    "create_column",
    "create_card",
    "update_card",
    "move_card",
    "add_comment",
    "archive_card",
    "unarchive_card",
}


@pytest.fixture
def client(db_session):
    # Entered with `with`, unlike the other suites' clients: the lifespan is
    # what starts the MCP request handler.
    with TestClient(app) as c:
        yield c


def make_user():
    suffix = "".join(random.choices(string.ascii_lowercase, k=8))
    return User.create_user(f"mcp_{suffix}", "testpassword")


@pytest.fixture
def user(db_session):
    return make_user()


@pytest.fixture
def key(user):
    return ApiKey.create_key(user, "mcp test")[1]


@pytest.fixture
def board(user):
    return Board.create_with_columns(owner=user, name="MCP board")


def columns(board):
    return list(board.columns.order_by(Column.position))


def rpc(client, method, params=None, headers=None):
    body = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        body["params"] = params
    return client.post("/mcp", json=body, headers={**ACCEPT, **(headers or {})})


def call(client, key, tool, /, **arguments):
    """Call a tool; the raw MCP result, error or not."""
    response = rpc(
        client,
        "tools/call",
        {"name": tool, "arguments": arguments},
        {"X-API-Key": key},
    )
    assert response.status_code == 200, response.text
    return response.json()["result"]


def ok(client, key, tool, /, **arguments):
    """Call a tool that should succeed; its structured result."""
    result = call(client, key, tool, **arguments)
    assert not result["isError"], result["content"]
    structured = result["structuredContent"]
    # A list comes back wrapped, since structured content is always an object.
    return structured["result"] if set(structured) == {"result"} else structured


def refusal(client, key, tool, /, **arguments):
    """Call a tool that should fail; the error text the model sees."""
    result = call(client, key, tool, **arguments)
    assert result["isError"], result
    return result["content"][0]["text"]


# --- The door --------------------------------------------------------------


def test_no_key_is_401_with_a_bearer_challenge(client):
    response = rpc(client, "tools/list")
    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Bearer")
    assert "API key" in response.json()["error_description"]


def test_unknown_key_is_401(client, db_session):
    response = rpc(client, "tools/list", headers={"X-API-Key": "pkanban_nope"})
    assert response.status_code == 401


def test_revoked_key_is_401(client, user, key):
    row = ApiKey.find(key)
    row.is_active = False
    row.save()
    response = rpc(client, "tools/list", headers={"X-API-Key": key})
    assert response.status_code == 401


def test_web_session_token_is_refused(client, user):
    # Session JWTs expire within a day and MCP clients never see the renewal
    # header, so /mcp takes API keys only.
    token = create_access_token(data={"sub": user.id, "username": user.username})
    response = rpc(client, "tools/list", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_key_as_bearer_token_works(client, key):
    response = rpc(client, "tools/list", headers={"Authorization": f"Bearer {key}"})
    assert response.status_code == 200


def test_get_is_405_rather_than_a_stream_that_never_ends(client, key):
    response = client.get("/mcp", headers={"X-API-Key": key, **ACCEPT})
    assert response.status_code == 405
    assert response.headers["allow"] == "POST"


def test_get_without_a_key_is_still_401(client):
    # Not the SPA: /mcp is registered ahead of the catch-all.
    response = client.get("/mcp")
    assert response.status_code == 401


def test_app_can_start_twice(db_session, key):
    # A session manager runs only once, so each startup must build its own.
    for _ in range(2):
        with TestClient(app) as c:
            assert rpc(c, "tools/list", headers={"X-API-Key": key}).status_code == 200


# --- The tool list ---------------------------------------------------------


def test_tool_list(client, key):
    tools = rpc(client, "tools/list", headers={"X-API-Key": key}).json()["result"]["tools"]
    by_name = {t["name"]: t for t in tools}
    assert set(by_name) == READ_ONLY | WRITES
    for name in READ_ONLY:
        assert by_name[name]["annotations"]["readOnlyHint"] is True
    for name in WRITES:
        assert by_name[name]["annotations"]["readOnlyHint"] is False
    assert by_name["update_card"]["annotations"]["destructiveHint"] is True


def test_every_tool_has_a_title(client, key):
    # What an app shows a person, and what connector directories ask for.
    tools = rpc(client, "tools/list", headers={"X-API-Key": key}).json()["result"]["tools"]
    for t in tools:
        assert t.get("title"), t["name"]
        assert t["annotations"].get("title") == t["title"], t["name"]


def test_descriptions_are_dedented(client, key):
    tools = rpc(client, "tools/list", headers={"X-API-Key": key}).json()["result"]["tools"]
    for t in tools:
        assert "\n    " not in t["description"], t["name"]


# --- Reading and writing ---------------------------------------------------


def test_list_boards_shows_only_what_the_caller_can_see(client, key, board):
    Board.create_with_columns(owner=make_user(), name="Someone else's")
    assert ok(client, key, "list_boards") == [
        {"id": board.id, "name": "MCP board", "permission": "admin"}
    ]


def test_another_users_board_is_refused(client, key):
    theirs = Board.create_with_columns(owner=make_user(), name="Private")
    assert "Not authorized" in refusal(client, key, "get_board", board_id=theirs.id)


def test_card_round_trip(client, key, board):
    todo, doing = columns(board)[:2]

    card = ok(
        client, key, "create_card",
        column_id=todo.id, title="Write the docs", description="All of them.",
    )
    assert card["title"] == "Write the docs"

    # get_board carries titles only; get_card has the text.
    layout = ok(client, key, "get_board", board_id=board.id)
    assert [c["name"] for c in layout["columns"]] == [c.name for c in columns(board)]
    assert layout["columns"][0]["cards"] == [{"id": card["id"], "title": "Write the docs"}]
    assert ok(client, key, "get_card", card_id=card["id"])["description"] == "All of them."

    ok(client, key, "update_card", card_id=card["id"], title="Write some docs")
    ok(client, key, "move_card", card_id=card["id"], column_id=doing.id)
    ok(client, key, "add_comment", card_id=card["id"], content="Started.")

    full = ok(client, key, "get_card", card_id=card["id"])
    assert full["title"] == "Write some docs"
    assert full["description"] == "All of them."  # a title edit leaves it alone
    assert full["column_id"] == doing.id
    assert [c["content"] for c in full["comments"]] == ["Started."]


def test_archive_hides_and_unarchive_restores(client, key, board):
    todo = columns(board)[0]
    card = ok(client, key, "create_card", column_id=todo.id, title="Old news")

    ok(client, key, "archive_card", card_id=card["id"])
    layout = ok(client, key, "get_board", board_id=board.id)
    assert layout["columns"][0]["cards"] == []
    assert layout["columns"][0]["archived_count"] == 1

    with_archived = ok(client, key, "get_board", board_id=board.id, include_archived=True)
    assert with_archived["columns"][0]["cards"][0]["archived_at"]

    ok(client, key, "unarchive_card", card_id=card["id"])
    layout = ok(client, key, "get_board", board_id=board.id)
    assert [c["id"] for c in layout["columns"][0]["cards"]] == [card["id"]]


def test_card_writes_answer_with_the_card_as_it_is(client, key, board):
    # The API's write responses carry "comments": [] whatever the card has,
    # and no column (Dev #982). A model took that to mean no comments.
    todo = columns(board)[0]
    card = ok(client, key, "create_card", column_id=todo.id, title="Busy card")
    assert "comments" not in card
    assert card["comment_count"] == 0
    assert (card["column_name"], card["board_name"]) == (todo.name, "MCP board")

    ok(client, key, "add_comment", card_id=card["id"], content="One.")
    ok(client, key, "add_comment", card_id=card["id"], content="Two.")

    for tool in ("update_card", "archive_card", "unarchive_card"):
        extra = {"title": "Still busy"} if tool == "update_card" else {}
        result = ok(client, key, tool, card_id=card["id"], **extra)
        assert "comments" not in result, tool
        assert result["comment_count"] == 2, tool
        assert result["column_id"] == todo.id, tool

    assert result["title"] == "Still busy"
    assert result["archived_at"] is None


def test_move_card_says_where_the_card_went(client, key, board, user):
    elsewhere = Board.create_with_columns(owner=user, name="Elsewhere")
    target = columns(elsewhere)[-1]
    card = ok(client, key, "create_card", column_id=columns(board)[0].id, title="Traveller")

    moved = ok(client, key, "move_card", card_id=card["id"], column_id=target.id)

    assert moved["column_id"] == target.id
    assert moved["column_name"] == target.name
    assert (moved["board_id"], moved["board_name"]) == (elsewhere.id, "Elsewhere")


def test_search_cards(client, key, board):
    todo = columns(board)[0]
    ok(client, key, "create_card", column_id=todo.id, title="Pelican migration")
    results = ok(client, key, "search_cards", query="pelican")
    assert [r["title"] for r in results] == ["Pelican migration"]
    assert results[0]["board_name"] == "MCP board"


def test_search_snippets_mark_matches_in_bold(client, key, board):
    # The API's STX/ETX highlight markers mean nothing to a model (Dev #978).
    todo = columns(board)[0]
    ok(client, key, "create_card", column_id=todo.id, title="Birds",
       description="The pelican flies south for the winter.")
    ok(client, key, "create_card", column_id=todo.id, title="Pelican, no description")
    results = {r["title"]: r for r in ok(client, key, "search_cards", query="pelican")}
    assert results["Birds"]["snippet"] == "The **pelican** flies south for the winter."
    assert results["Pelican, no description"]["snippet"] is None


def test_create_board_and_column(client, key):
    board = ok(client, key, "create_board", name="Fresh")
    column = ok(client, key, "create_column", board_id=board["id"], name="Blocked")
    layout = ok(client, key, "get_board", board_id=board["id"])
    assert layout["columns"][-1] == {
        "id": column["id"], "name": "Blocked", "cards": [], "archived_count": 0,
    }


def test_update_and_move_need_something_to_change(client, key, board):
    card = ok(client, key, "create_card", column_id=columns(board)[0].id, title="x")
    assert "Nothing to change" in refusal(client, key, "update_card", card_id=card["id"])
    assert "Nothing to change" in refusal(client, key, "move_card", card_id=card["id"])


def test_missing_card_is_a_tool_error(client, key):
    assert "not found" in refusal(client, key, "get_card", card_id=999999).lower()


def test_plan_limit_is_a_tool_error_with_the_upgrade_link(client, key, user, monkeypatch):
    monkeypatch.setenv("BILLING_ENABLED", "true")
    for i in range(FREE_MAX_BOARDS):
        Board.create_with_columns(owner=user, name=f"b{i}")
    text = refusal(client, key, "create_board", name="One too many")
    # The link names the server the request came in on: TestClient's host.
    assert "http://testserver/settings/plan" in text
