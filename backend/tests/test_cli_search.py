"""`pkanban search`: what it sends, and what it prints."""

import json
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


def run(args, results=None, error=None):
    client = MagicMock()
    if error is not None:
        client.search.side_effect = error
    else:
        client.search.return_value = results or []
    with patch("pkanban.cli.PkanbanClient", return_value=client):
        outcome = CliRunner().invoke(cli.app, args, catch_exceptions=False)
    return outcome, client


def result(**overrides):
    return {
        "id": 781,
        "title": "Card archiving",
        "snippet": "cards still \x02count\x03 toward the limit",
        "column_id": 4,
        "column_name": "Todo",
        "board_id": 1,
        "board_name": "Dev",
        **overrides,
    }


def test_every_word_is_searched_without_quoting():
    _, client = run(["search", "card", "archiving"])
    client.search.assert_called_once_with("card archiving", None, 20)


def test_board_and_limit_are_passed_through():
    _, client = run(["search", "deploy", "--board", "9", "-n", "5"])
    client.search.assert_called_once_with("deploy", 9, 5)


def test_prints_id_title_location_and_snippet():
    outcome, _ = run(["search", "count"], [result()])
    assert "#781 Card archiving  Dev / Todo" in outcome.output
    assert "cards still count toward the limit" in outcome.output
    assert "\x02" not in outcome.output and "\x03" not in outcome.output


@pytest.mark.parametrize("text", ["[bug] login fails", "[/x] weird", "[red]not red[/red]"])
def test_card_text_prints_as_written(text):
    outcome, _ = run(
        ["search", "x"],
        [result(title=text, snippet=f"\x02{text}\x03 and {text}", board_name=text)],
    )
    assert outcome.exit_code == 0
    assert outcome.output.count(text) == 4


def test_a_card_without_a_snippet_prints_just_its_line():
    outcome, _ = run(["search", "x"], [result(snippet=None)])
    assert outcome.output.strip() == "#781 Card archiving  Dev / Todo"


def test_no_results():
    outcome, _ = run(["search", "nothing"], [])
    assert "No matching cards" in outcome.output


def test_json_is_the_raw_response():
    outcome, _ = run(["--json", "search", "count"], [result()])
    assert json.loads(outcome.output) == [result()]


def test_a_board_you_cannot_open_is_explained():
    response = MagicMock(status_code=403, text="")
    outcome, _ = run(
        ["search", "x", "--board", "9"],
        error=requests.exceptions.HTTPError(response=response),
    )
    assert outcome.exit_code == 1
    assert "You don't have access to board 9." in outcome.output


def test_limit_is_bounded():
    outcome, client = run(["search", "x", "--limit", "500"])
    assert outcome.exit_code != 0
    client.search.assert_not_called()
