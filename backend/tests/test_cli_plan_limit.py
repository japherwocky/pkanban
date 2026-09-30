"""The CLI's side of plan limits: a 402 becomes a readable message, or in
--json mode a stderr object an agent can branch on, never a blob of raw JSON.
"""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest
import requests

from pkanban.client import PkanbanClient, PlanLimitError
from pkanban.output import set_json_output

BODY = {
    "error": "plan_limit",
    "limit": "cards_per_board",
    "max": 100,
    "current": 100,
    "detail": "This board is on the free plan, which allows 100 cards per board.",
}


@pytest.fixture(autouse=True)
def _reset_output_mode():
    set_json_output(None)
    yield
    set_json_output(None)


def _client_returning(status, body):
    client = PkanbanClient(server_url="https://pkanban.example.com/", token="t")
    response = MagicMock()
    response.status_code = status
    response.json.return_value = body
    response.headers = {}
    if status >= 400:
        response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=response
        )
    client.session = MagicMock()
    client.session.request.return_value = response
    return client


def test_a_402_plan_limit_raises_a_typed_error_not_an_http_error():
    client = _client_returning(402, BODY)
    with pytest.raises(PlanLimitError) as raised:
        client.card_create(1, "title")
    e = raised.value
    assert (e.limit, e.maximum, e.current) == ("cards_per_board", 100, 100)
    assert e.upgrade_url == "https://pkanban.example.com/settings/plan"
    assert "100 cards per board" in str(e)
    assert "https://pkanban.example.com/settings/plan" in str(e)


def test_plan_limit_error_is_not_swallowed_by_a_commands_http_error_handler():
    """Commands catch HTTPError and print `Error: <raw text>`. A PlanLimitError
    must sail past that to main()."""
    assert not issubclass(PlanLimitError, requests.exceptions.HTTPError)


def test_a_402_that_is_not_a_plan_limit_is_still_an_http_error():
    client = _client_returning(402, {"detail": "Payment Required"})
    with pytest.raises(requests.exceptions.HTTPError):
        client.boards()


def _run_main(error):
    from pkanban import cli

    with patch.object(sys, "argv", ["pkanban", "card", "create", "1", "x"]):
        with patch("pkanban.cli.app", side_effect=error):
            with pytest.raises(SystemExit) as exit_info:
                cli.main()
    return exit_info.value.code


def _error():
    return PlanLimitError(
        BODY["detail"], "cards_per_board", 100, 100, "https://h/settings/plan"
    )


def test_main_reports_a_plan_limit_as_json_on_stderr(capsys):
    set_json_output(True)
    assert _run_main(_error()) == 1
    captured = capsys.readouterr()
    assert captured.out == ""  # stdout stays parseable
    payload = json.loads(captured.err)
    assert payload["status"] == 402
    assert payload["code"] == "plan_limit"
    assert payload["limit"] == "cards_per_board"
    assert payload["max"] == 100
    assert payload["current"] == 100
    assert payload["upgrade_url"] == "https://h/settings/plan"
    assert "100 cards per board" in payload["error"]


def test_main_reports_a_plan_limit_readably_for_a_human(capsys):
    assert _run_main(_error()) == 1
    out = capsys.readouterr().out
    assert "100 cards per board" in out
    assert "https://h/settings/plan" in out
    assert "{" not in out  # not a dump of the response body


# === pkanban account ===


def _account(usage, capsys):
    from pkanban.cli import cmd_account

    mock_client = MagicMock()
    mock_client.usage.return_value = usage
    mock_client.server_url = "https://h"
    with patch("pkanban.cli.make_client", return_value=mock_client):
        cmd_account()
    return capsys.readouterr().out


FREE = {
    "plan": "free",
    "billing_enabled": True,
    "max_boards": 5,
    "max_cards_per_board": 100,
    "boards_owned": 3,
    "boards": [
        {"id": 1, "name": "Dev", "cards": 97},
        {"id": 2, "name": "Side [project]", "cards": 12},
    ],
}


def test_account_shows_usage_and_only_boards_near_the_cap(capsys):
    out = _account(FREE, capsys)
    assert "free" in out
    assert "3 / 5" in out
    assert "97 / 100" in out
    assert "Dev" in out
    assert "Side" not in out  # 12 cards is nowhere near the cap
    assert "https://h/settings/plan" in out


def test_account_escapes_board_names_that_look_like_markup(capsys):
    usage = dict(FREE, boards=[{"id": 2, "name": "Side [project]", "cards": 99}])
    assert "Side [project]" in _account(usage, capsys)


def test_account_for_a_pro_user_shows_no_limits(capsys):
    usage = dict(FREE, plan="pro", max_boards=None, max_cards_per_board=None)
    out = _account(usage, capsys)
    assert "pro" in out
    assert "no limit" in out
    assert "Upgrade" not in out


def test_account_when_billing_is_off_says_nothing_is_enforced(capsys):
    usage = dict(FREE, billing_enabled=False, max_boards=None, max_cards_per_board=None)
    assert "No plan limits" in _account(usage, capsys)


def test_account_json_passes_the_usage_through(capsys):
    set_json_output(True)
    assert json.loads(_account(FREE, capsys)) == FREE
