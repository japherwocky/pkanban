"""`pkanban card comment`: posting a comment from the command line.

Agents kept concluding pkanban had no comments, because the CLI could only
read them. The body arrives the same ways a card description does -- inline,
'-' for stdin, or a file -- and for the same reason (Dev #474): a quoted
phrase that a shell splits must fail loudly, not arrive altered.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
import requests
from typer.testing import CliRunner

from pkanban import cli
from pkanban.client import PkanbanClient
from pkanban.output import set_json_output

BODY = 'Fixed in #101 -- it reports "too big" past ~4,100 rows. [/x] stays.\n'

POSTED = {
    "id": 7,
    "card_id": 92,
    "user_id": 1,
    "username": "agent",
    "content": "LGTM",
    "created_at": "2026-10-09T12:00:00",
    "updated_at": "2026-10-09T12:00:00",
}


@pytest.fixture(autouse=True)
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setenv("PKANBAN_CONFIG_PATH", str(tmp_path / "config.yaml"))
    monkeypatch.delenv("PKANBAN_OUTPUT", raising=False)
    set_json_output(False)
    cli.set_token("test-token")
    yield
    set_json_output(None)
    cli.set_runtime_api_key(None)


def run(args, input=None, **create):
    """Run `pkanban card comment ...` against a mocked server.

    Returns the Click result and the mocked client, so a test can check what
    was sent -- or that nothing was.
    """
    client = MagicMock()
    client.comment_create.configure_mock(**({"return_value": POSTED} | create))
    with patch("pkanban.cli.PkanbanClient", return_value=client):
        result = CliRunner().invoke(
            cli.app, ["card", "comment", *args], input=input, catch_exceptions=False
        )
    return result, client


def test_an_inline_comment_is_posted():
    result, client = run(["92", "LGTM"])
    assert result.exit_code == 0
    client.comment_create.assert_called_once_with(92, "LGTM")
    assert "id=7" in result.output


def test_a_comment_file_arrives_intact(tmp_path):
    path = tmp_path / "note.md"
    path.write_text(BODY, encoding="utf-8")
    result, client = run(["92", "--file", str(path)])
    assert result.exit_code == 0
    # Quotes, brackets and all; only the file's trailing newline is dropped.
    client.comment_create.assert_called_once_with(92, BODY.rstrip("\n"))


def test_a_comment_file_drops_a_byte_order_mark(tmp_path):
    """PowerShell's Out-File writes one, and it would open the comment."""
    path = tmp_path / "note.md"
    path.write_bytes(b"\xef\xbb\xbf" + BODY.encode("utf-8"))
    result, client = run(["92", "-f", str(path)])
    assert client.comment_create.call_args.args == (92, BODY.rstrip("\n"))


def test_a_comment_from_stdin():
    result, client = run(["92", "-"], input=BODY)
    assert result.exit_code == 0
    client.comment_create.assert_called_once_with(92, BODY.rstrip("\n"))


def test_a_comment_split_by_the_shell_is_refused_not_mangled():
    """What PowerShell 5.1 makes of `"he said \\"hi there\\""`: two pieces.
    The second must be an error, not dropped or sent somewhere else."""
    result, client = run(["92", "he said hi", "there"])
    assert result.exit_code == 2
    assert "unexpected extra argument" in result.output.lower()
    client.comment_create.assert_not_called()


def test_text_and_file_together_is_an_error(tmp_path):
    path = tmp_path / "note.md"
    path.write_text("x", encoding="utf-8")
    result, client = run(["92", "y", "--file", str(path)])
    assert result.exit_code == 1
    client.comment_create.assert_not_called()


@pytest.mark.parametrize("args", [["92"], ["92", "   "]])
def test_an_empty_comment_is_not_sent(args):
    result, client = run(args)
    assert result.exit_code == 1
    assert "Nothing to say" in result.output
    client.comment_create.assert_not_called()


def test_an_empty_file_is_not_sent(tmp_path):
    path = tmp_path / "note.md"
    path.write_text("\n", encoding="utf-8")
    result, client = run(["92", "--file", str(path)])
    assert result.exit_code == 1
    client.comment_create.assert_not_called()


def test_json_mode_prints_only_the_new_comment():
    set_json_output(True)
    result, _ = run(["92", "LGTM"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == POSTED


@pytest.mark.parametrize(
    "status,expected",
    [
        (404, "Card 92 not found"),
        (403, "permission to comment"),
    ],
)
def test_a_refused_comment_is_explained(status, expected):
    error = requests.exceptions.HTTPError(response=MagicMock(status_code=status))
    result, _ = run(["92", "LGTM"], side_effect=error)
    assert result.exit_code == 1
    assert expected in result.output


def test_card_help_lists_the_comment_command():
    """The whole point: an agent reading `card --help` finds it."""
    result = CliRunner().invoke(cli.app, ["card", "--help"])
    assert "comment" in result.output


def test_the_client_posts_to_the_comments_route():
    pkanban_client = PkanbanClient(server_url="http://localhost:9999", token="t")
    pkanban_client.session = MagicMock()
    pkanban_client.session.request.return_value.json.return_value = POSTED

    assert pkanban_client.comment_create(92, "LGTM") == POSTED

    call = pkanban_client.session.request.call_args
    assert call.args == ("POST", "http://localhost:9999/api/comments")
    assert call.kwargs["json"] == {"card_id": 92, "content": "LGTM"}
