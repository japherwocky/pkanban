"""`pkanban card archive|unarchive`, `board get --archived`, and archived markers."""

from unittest.mock import MagicMock, patch

import pytest
import requests
from typer.testing import CliRunner

from pkanban import cli
from pkanban.output import set_json_output


@pytest.fixture(autouse=True)
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setenv("PKANBAN_CONFIG_PATH", str(tmp_path / "config.yaml"))
    monkeypatch.delenv("PKANBAN_OUTPUT", raising=False)
    set_json_output(False)
    cli.set_token("test-token")
    yield
    set_json_output(None)
    cli.set_runtime_api_key(None)


def run(args, **methods):
    client = MagicMock()
    for name, answer in methods.items():
        if isinstance(answer, Exception):
            getattr(client, name).side_effect = answer
        else:
            getattr(client, name).return_value = answer
    with patch("pkanban.cli.PkanbanClient", return_value=client):
        outcome = CliRunner().invoke(cli.app, args, catch_exceptions=False)
    return outcome, client


def http_error(status):
    return requests.exceptions.HTTPError(response=MagicMock(status_code=status, text=""))


ARCHIVED = "2026-10-15T12:00:00Z"

BOARD = {
    "id": 1,
    "name": "Dev",
    "columns": [
        {
            "id": 4,
            "name": "Todo",
            "archived_count": 2,
            "cards": [{"id": 10, "title": "Live card", "archived_at": None}],
        }
    ],
}

BOARD_WITH_ARCHIVED = {
    **BOARD,
    "columns": [
        {
            **BOARD["columns"][0],
            "cards": [
                {"id": 10, "title": "Live card", "archived_at": None},
                {"id": 11, "title": "Old card", "archived_at": ARCHIVED},
            ],
        }
    ],
}


def test_archive_calls_the_server_and_says_where_the_card_went():
    outcome, client = run(["card", "archive", "11"], card_archive={"id": 11})
    client.card_archive.assert_called_once_with(11)
    assert outcome.exit_code == 0
    assert "Card archived" in outcome.output
    assert "Search still finds it" in outcome.output


def test_unarchive_calls_the_server():
    outcome, client = run(["card", "unarchive", "11"], card_unarchive={"id": 11})
    client.card_unarchive.assert_called_once_with(11)
    assert "bottom of its column" in outcome.output


@pytest.mark.parametrize(
    "status, message",
    [(404, "Card 11 not found."), (403, "You don't have permission to change this card.")],
)
@pytest.mark.parametrize("command, method", [("archive", "card_archive"), ("unarchive", "card_unarchive")])
def test_failures_are_explained(command, method, status, message):
    outcome, _ = run(["card", command, "11"], **{method: http_error(status)})
    assert outcome.exit_code == 1
    assert message in outcome.output


def test_board_get_hides_archived_cards_and_says_so():
    outcome, client = run(["board", "get", "1"], board_get=BOARD)
    client.board_get.assert_called_once_with(1, include_archived=False)
    assert "Todo (1 cards, 2 archived)" in outcome.output
    assert "--archived shows them" in outcome.output


def test_board_get_archived_lists_and_marks_them():
    outcome, client = run(["board", "get", "1", "--archived"], board_get=BOARD_WITH_ARCHIVED)
    client.board_get.assert_called_once_with(1, include_archived=True)
    assert "#11 Old card  (archived)" in outcome.output
    assert "#10 Live card" in outcome.output
    assert "#10 Live card  (archived)" not in outcome.output
    assert "--archived shows them" not in outcome.output


def test_board_get_from_an_older_server_without_archive_fields():
    board = {"id": 1, "name": "Dev", "columns": [{"id": 4, "name": "Todo", "cards": [{"id": 1, "title": "x"}]}]}
    outcome, _ = run(["board", "get", "1"], board_get=board)
    assert outcome.exit_code == 0
    assert "Todo (1 cards)" in outcome.output


def test_card_get_says_it_is_archived():
    card = {
        "id": 11,
        "title": "Old card",
        "board_name": "Dev",
        "column_name": "Todo",
        "column_id": 4,
        "description": None,
        "archived_at": ARCHIVED,
        "comments": [],
    }
    outcome, _ = run(["card", "get", "11"], card_get=card)
    assert "archived 2026-10-15" in outcome.output
    assert "pkanban card unarchive 11" in outcome.output


def test_search_marks_archived_results():
    results = [
        {"id": 11, "title": "Old card", "snippet": None, "column_id": 4,
         "column_name": "Todo", "board_id": 1, "board_name": "Dev", "archived_at": ARCHIVED},
        {"id": 10, "title": "Live card", "snippet": None, "column_id": 4,
         "column_name": "Todo", "board_id": 1, "board_name": "Dev", "archived_at": None},
    ]
    outcome, _ = run(["search", "card"], search=results)
    lines = outcome.output.splitlines()
    assert lines[0] == "#11 Old card  Dev / Todo  (archived)"
    assert lines[1] == "#10 Live card  Dev / Todo"
