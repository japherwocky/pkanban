"""What the CLI prints when the text it prints is not tidy, and when nobody is listening.

Three failures, each found by running the CLI the way a script does:

* **Brackets.** Output goes through rich, which reads `[bug]` as a style tag.
  A card titled "[bug] login fails" printed as " login fails", "Q3 [draft] plan"
  as "Q3  plan", and a title containing "[/x]" raised MarkupError and aborted
  the command with a traceback.
* **Errors on stdout.** `pkanban card get 9 > card.txt` wrote "Card not found"
  into card.txt. The JSON form already went to stderr; the human form did not.
* **A reader that leaves.** `pkanban card get 9 | head -1` ended in 105 lines of
  "Exception ignored ... OSError: [Errno 22]" and exit status 120, because the
  error is raised in a final flush that no handler was around to meet.
"""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from pkanban import cli
from pkanban.output import emit_error, reader_left, run_quietly, set_json_output

REPO = Path(__file__).resolve().parents[2]

# Text a user can really type into a title: a lowercase tag rich would swallow,
# a closing tag that matches nothing, and markup that must stay markup-looking.
HOSTILE = [
    "[bug] login fails",
    "Q3 [draft] plan",
    "[/x] weird",
    "[red]not red[/red]",
]


@pytest.fixture(autouse=True)
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setenv("PKANBAN_CONFIG_PATH", str(tmp_path / "config.yaml"))
    monkeypatch.delenv("PKANBAN_OUTPUT", raising=False)
    set_json_output(False)
    cli.set_token("test-token")
    yield
    set_json_output(None)
    cli.set_runtime_api_key(None)


def run(args, **client_methods):
    """Invoke a command with the server replaced by canned answers."""
    client = MagicMock()
    for name, answer in client_methods.items():
        getattr(client, name).return_value = answer
    with patch("pkanban.cli.PkanbanClient", return_value=client):
        return CliRunner().invoke(cli.app, args, catch_exceptions=False)


# --- brackets ----------------------------------------------------------------


@pytest.mark.parametrize("title", HOSTILE)
def test_a_card_title_prints_as_written(title):
    result = run(
        ["card", "get", "7"],
        card_get={
            "id": 7,
            "title": title,
            "board_name": title,
            "column_name": title,
            "column_id": 3,
            "description": "",
            "comments": [{"username": title, "content": "hi"}],
        },
    )
    assert result.exit_code == 0
    assert result.output.count(title) == 4  # title, board, column, commenter


@pytest.mark.parametrize("name", HOSTILE)
@pytest.mark.parametrize(
    "args, method, answer",
    [
        (["board", "list"], "boards", lambda n: [{"id": 1, "name": n}]),
        (
            ["board", "get", "1"],
            "board_get",
            lambda n: {"id": 1, "name": n, "columns": []},
        ),
        (
            ["org", "list"],
            "organizations",
            lambda n: [{"id": 1, "name": n, "owner_username": n}],
        ),
        (
            ["org", "get", "1"],
            "organization_get",
            lambda n: {
                "id": 1,
                "name": n,
                "owner_username": n,
                "members": [{"username": n, "role": n}],
            },
        ),
        (
            ["team", "get", "1"],
            "team_get",
            lambda n: {
                "id": 1,
                "name": n,
                "organization_name": n,
                "members": [{"username": n}],
            },
        ),
    ],
)
def test_names_print_as_written_in_every_listing(name, args, method, answer):
    result = run(args, **{method: answer(name)})
    assert result.exit_code == 0
    assert name in result.output


# --- errors ------------------------------------------------------------------


def test_a_human_error_goes_to_stderr_and_leaves_stdout_clean(capsys):
    emit_error("Card not found")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Card not found" in captured.err


@pytest.mark.parametrize("message", HOSTILE + ["limit: expected a number, got '[/oops]'"])
def test_an_error_message_is_not_markup(message, capsys):
    emit_error(message)
    assert message in capsys.readouterr().err


def test_an_error_is_not_reflowed_to_the_terminal_width(capsys, monkeypatch):
    monkeypatch.setenv("COLUMNS", "40")
    message = "Not authenticated. Run 'pkanban login' first or use --api-key."
    emit_error(message)
    assert capsys.readouterr().err.strip() == message


def test_a_json_error_is_unchanged(capsys):
    set_json_output(True)
    emit_error("Card not found", status=404)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert '"status": 404' in captured.err


# --- a reader that leaves ----------------------------------------------------


def dead_pipe():
    """A pipe's write end with nobody holding the read end: every write fails."""
    read_end, write_end = os.pipe()
    os.close(read_end)
    return write_end


def pkanban(*args, stdout, stderr):
    env = dict(os.environ, PYTHONPATH=str(REPO), PKANBAN_CONFIG_PATH=os.devnull)
    return subprocess.run(
        [sys.executable, "-m", "pkanban", *args],
        stdout=stdout,
        stderr=stderr,
        env=env,
        timeout=60,
    )


def test_a_reader_that_left_stdout_is_not_an_error():
    """`pkanban --help | head -0`: ends quietly, status 0, nothing on stderr."""
    stdout = dead_pipe()
    try:
        done = pkanban("--help", stdout=stdout, stderr=subprocess.PIPE)
    finally:
        os.close(stdout)
    assert done.returncode == 0, done.stderr.decode(errors="replace")
    assert done.stderr == b""


def test_a_short_output_that_fails_in_the_final_flush_is_quiet_too():
    """--version is one line: it sits in the buffer until the interpreter exits."""
    stdout = dead_pipe()
    try:
        done = pkanban("--version", stdout=stdout, stderr=subprocess.PIPE)
    finally:
        os.close(stdout)
    assert done.returncode == 0, done.stderr.decode(errors="replace")
    assert done.stderr == b""


def test_a_reader_that_left_stderr_keeps_the_commands_own_status():
    """A usage error is status 2; a closed stderr must not turn it into 120."""
    stderr = dead_pipe()
    try:
        done = pkanban("--no-such-option", stdout=subprocess.PIPE, stderr=stderr)
    finally:
        os.close(stderr)
    assert done.returncode == 2
    assert done.stdout == b""


def test_run_quietly_returns_the_status_the_command_exits_with():
    def fails():
        raise SystemExit(3)

    assert run_quietly(fails) == 3
    assert run_quietly(lambda: None) == 0


def test_run_quietly_still_raises_an_error_that_is_not_a_reader_leaving():
    def broken():
        raise PermissionError("not a pipe")

    with pytest.raises(PermissionError):
        run_quietly(broken)


def test_reader_left_means_a_closed_pipe_and_nothing_else():
    assert reader_left(BrokenPipeError())
    assert not reader_left(PermissionError())
    assert not reader_left(FileNotFoundError())
