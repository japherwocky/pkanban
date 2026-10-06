"""How the command line reaches the commands, before and after Click.

Everything here is about text arriving intact: a card body with quotes in it,
a title that happens to look like a flag or begin with `~`. Each of these used
to be altered on the way in, silently, and exit 0.
"""

import io
import os
import sys
from unittest.mock import MagicMock, patch

import pytest
import typer

from pkanban import cli


@pytest.fixture(autouse=True)
def sandbox_config(tmp_path, monkeypatch):
    monkeypatch.setenv("PKANBAN_CONFIG_PATH", str(tmp_path / "config.yaml"))
    cli.set_token("test-token")
    yield
    cli.set_runtime_api_key(None)


# --- --api-key ---------------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["pkanban", "--api-key", "KEY", "board", "list"],
        ["pkanban", "board", "list", "-k", "KEY"],
        ["pkanban", "--api-key=KEY", "board", "list"],
    ],
)
def test_api_key_forms(argv):
    assert cli._extract_api_key(argv) == "KEY"
    assert argv == ["pkanban", "board", "list"]


def test_a_dash_k_that_is_another_options_value_is_left_alone():
    """It used to take the first `-k` anywhere, so this consumed "title" as
    the key and sent a card with no title."""
    argv = ["pkanban", "card", "create", "4", "-d", "-k", "title"]
    assert cli._extract_api_key(argv) is None
    assert argv == ["pkanban", "card", "create", "4", "-d", "-k", "title"]


def test_nothing_after_double_dash_is_an_option():
    argv = ["pkanban", "card", "create", "4", "--", "-k", "--json"]
    assert cli._extract_api_key(argv) is None
    assert cli._extract_json_flag(argv) is False
    assert argv == ["pkanban", "card", "create", "4", "--", "-k", "--json"]


def _boolean_flags():
    """Every value-less flag any command declares, read off the command tree."""
    from typer.main import get_command

    found, pending = set(), [get_command(cli.app)]
    while pending:
        command = pending.pop()
        for param in command.params:
            if getattr(param, "is_flag", False):
                found.update(param.opts)
                found.update(param.secondary_opts)
        pending.extend(getattr(command, "commands", {}).values())
    return found - {"--help", "--json"}


@pytest.mark.parametrize("flag", sorted(_boolean_flags()))
def test_json_after_any_boolean_flag_is_still_ours(flag):
    """`pkanban login --no-wait --json` -- the line /agents.md gives agents --
    failed with "No such option: --json": the flag list was kept by hand, and
    --no-wait wasn't on it, so --json was taken for --no-wait's value."""
    argv = ["pkanban", "login", flag, "--json"]
    assert cli._extract_json_flag(argv) is True
    assert argv == ["pkanban", "login", flag]


def test_login_no_wait_json_reaches_the_command(monkeypatch, capsys):
    from pkanban.client import PkanbanClient

    started = {
        "device_code": "d",
        "user_code": "BCDF-GHJK",
        "verification_uri": "http://x/device",
        "verification_uri_complete": "http://x/device?code=BCDF-GHJK",
        "expires_in": 600,
        "interval": 3,
    }
    monkeypatch.setattr(sys, "argv", ["pkanban", "login", "--no-wait", "--no-browser", "--json"])
    with patch.object(PkanbanClient, "device_login_start", return_value=started):
        try:
            cli.main()
        except SystemExit as e:
            assert e.code in (0, None)
        finally:
            cli.set_json_output(None)
    assert '"user_code": "BCDF-GHJK"' in capsys.readouterr().out


def test_api_key_without_a_value_is_an_error():
    with pytest.raises(SystemExit):
        cli._extract_api_key(["pkanban", "board", "list", "--api-key"])


# --- Click's Windows argument expansion ---------------------------------------


def test_click_does_not_expand_arguments():
    """Click expands `~` and globs on Windows, so a title of "~4,100" was
    stored as "C:\\Users\\4,100"."""
    with patch.object(sys, "argv", ["pkanban", "board", "list"]):
        with patch("pkanban.cli.app") as app:
            cli.main()
    app.assert_called_once_with(windows_expand_args=False)


# --- descriptions that never pass through a shell (Dev #474) ------------------

BODY = 'it reports "too big". Then ~4,100 rows, and *.py.\n'


def _update(**kwargs):
    mock_client = MagicMock()
    mock_client.card_update.return_value = {"id": 245}
    args = dict(
        card_id=245,
        title=None,
        description=None,
        description_file=None,
        position=None,
        column=None,
    )
    args.update(kwargs)
    with patch("pkanban.cli.PkanbanClient", return_value=mock_client):
        cli.cmd_card_update(**args)
    return mock_client.card_update.call_args.args


def test_description_file_arrives_intact(tmp_path):
    path = tmp_path / "body.md"
    path.write_text(BODY, encoding="utf-8")

    card_id, title, description, position, column = _update(
        description_file=str(path)
    )
    assert title is None  # nothing got split off into the TITLE slot
    assert description == BODY.rstrip("\n")


def test_description_file_drops_a_byte_order_mark(tmp_path):
    """PowerShell's Out-File writes one, and it would become the card's
    first character."""
    path = tmp_path / "body.md"
    path.write_bytes(b"\xef\xbb\xbf" + BODY.encode("utf-8"))
    assert _update(description_file=str(path))[2] == BODY.rstrip("\n")


def test_description_from_stdin(monkeypatch):
    stdin = MagicMock()
    stdin.buffer = io.BytesIO(BODY.encode("utf-8"))
    monkeypatch.setattr(sys, "stdin", stdin)
    assert _update(description="-")[2] == BODY.rstrip("\n")


def test_description_file_expands_tilde(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    (tmp_path / "body.md").write_text("from home", encoding="utf-8")
    assert _update(description_file="~/body.md")[2] == "from home"


def test_description_and_description_file_together_is_an_error(tmp_path):
    path = tmp_path / "body.md"
    path.write_text("x", encoding="utf-8")
    with pytest.raises(typer.Exit):
        _update(description="y", description_file=str(path))


def test_plain_description_is_untouched():
    assert _update(description="  keep\n")[2] == "  keep\n"


def test_card_create_takes_a_description_file(tmp_path):
    path = tmp_path / "body.md"
    path.write_text(BODY, encoding="utf-8")
    mock_client = MagicMock()
    mock_client.card_create.return_value = {"id": 1}
    with patch("pkanban.cli.PkanbanClient", return_value=mock_client):
        cli.cmd_card_create(
            column_id=4,
            title="Title",
            description=None,
            description_file=str(path),
            position=0,
        )
    mock_client.card_create.assert_called_once_with(
        4, "Title", BODY.rstrip("\n"), 0
    )
