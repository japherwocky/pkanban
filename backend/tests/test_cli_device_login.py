"""`pkanban login` with no username: approve the login in a browser."""

import json
import os
import tempfile
import time
from unittest.mock import patch

import pytest
import typer

from pkanban.client import PkanbanClient


@pytest.fixture(autouse=True)
def temp_config(monkeypatch):
    path = os.path.join(tempfile.mkdtemp(), ".pkanban.yaml")
    monkeypatch.setenv("PKANBAN_CONFIG_PATH", path)
    from pkanban.config import set_server_url

    set_server_url("http://kanban.test")
    yield path


@pytest.fixture
def json_mode():
    from pkanban.output import set_json_output

    set_json_output(True)
    yield
    set_json_output(None)


@pytest.fixture(autouse=True)
def no_browser_no_sleep():
    with patch("webbrowser.open") as opened, patch("time.sleep"):
        yield opened


STARTED = {
    "device_code": "secret-device-code",
    "user_code": "BCDF-GHJK",
    "verification_uri": "http://kanban.test/device",
    "verification_uri_complete": "http://kanban.test/device?code=BCDF-GHJK",
    "expires_in": 600,
    "interval": 3,
}
APPROVED = {
    "api_key": "pkanban_minted",
    "api_key_id": 42,
    "api_key_name": "pkanban login: laptop",
    "username": "ada",
}
PENDING = (False, {"error": "authorization_pending"})


def login(**kwargs):
    from pkanban.cli import cmd_login

    args = dict(username=None, password=None, server=None, wait=True, browser=True)
    args.update(kwargs)
    cmd_login(**args)


def test_waits_for_approval_then_saves_the_minted_key(no_browser_no_sleep, capsys):
    from pkanban.config import get_api_key, get_api_key_id, get_pending_login, set_token, get_token

    set_token("old-session")
    with patch.object(PkanbanClient, "device_login_start", return_value=STARTED), \
         patch.object(
             PkanbanClient, "device_login_poll", side_effect=[PENDING, PENDING, (True, APPROVED)]
         ) as poll:
        login()

    assert poll.call_count == 3
    assert get_api_key() == "pkanban_minted"
    assert get_api_key_id() == 42
    assert get_pending_login() is None
    assert get_token() is None
    no_browser_no_sleep.assert_called_once_with(STARTED["verification_uri_complete"])
    out = capsys.readouterr().out
    assert STARTED["verification_uri_complete"] in out
    assert "Logged in as ada" in out


def test_no_wait_prints_the_link_and_a_later_login_finishes_it(capsys, json_mode):
    from pkanban.config import get_api_key, get_pending_login

    with patch.object(PkanbanClient, "device_login_start", return_value=STARTED) as start:
        login(wait=False)
    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "pending"
    assert printed["verification_uri_complete"] == STARTED["verification_uri_complete"]
    assert get_pending_login()["device_code"] == "secret-device-code"

    # The second run picks the same login back up: no new code.
    with patch.object(PkanbanClient, "device_login_start") as start_again, \
         patch.object(PkanbanClient, "device_login_poll", return_value=(True, APPROVED)):
        login()
    start_again.assert_not_called()
    assert get_api_key() == "pkanban_minted"
    assert json.loads(capsys.readouterr().out)["username"] == "ada"


def test_json_mode_keeps_the_link_off_stdout_while_waiting(capsys, json_mode):
    with patch.object(PkanbanClient, "device_login_start", return_value=STARTED), \
         patch.object(PkanbanClient, "device_login_poll", side_effect=[PENDING, (True, APPROVED)]):
        login()
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {
        "ok": True,
        "username": "ada",
        "server_url": "http://kanban.test",
        "api_key_name": "pkanban login: laptop",
    }
    assert STARTED["verification_uri_complete"] in captured.err


def test_an_expired_pending_login_is_replaced():
    from pkanban.config import set_pending_login

    set_pending_login({**STARTED, "server_url": "http://kanban.test", "expires_at": time.time() - 1})
    with patch.object(PkanbanClient, "device_login_start", return_value=STARTED) as start, \
         patch.object(PkanbanClient, "device_login_poll", return_value=(True, APPROVED)):
        login()
    start.assert_called_once()


def test_denied_login_fails_and_saves_nothing(capsys):
    from pkanban.config import get_api_key, get_pending_login

    denied = (False, {"error": "access_denied", "detail": "The login was denied."})
    with patch.object(PkanbanClient, "device_login_start", return_value=STARTED), \
         patch.object(PkanbanClient, "device_login_poll", return_value=denied):
        with pytest.raises(typer.Exit) as exc:
            login()
    assert exc.value.exit_code == 1
    assert get_api_key() is None
    assert get_pending_login() is None
    assert "denied" in capsys.readouterr().err


def test_no_browser_does_not_open_one(no_browser_no_sleep):
    with patch.object(PkanbanClient, "device_login_start", return_value=STARTED), \
         patch.object(PkanbanClient, "device_login_poll", return_value=(True, APPROVED)):
        login(browser=False)
    no_browser_no_sleep.assert_not_called()


def test_logout_revokes_a_key_from_a_browser_login():
    from pkanban.cli import cmd_logout
    from pkanban.config import get_api_key, get_api_key_id

    with patch.object(PkanbanClient, "device_login_start", return_value=STARTED), \
         patch.object(PkanbanClient, "device_login_poll", return_value=(True, APPROVED)):
        login()
    with patch.object(PkanbanClient, "api_key_revoke") as revoke:
        cmd_logout()
    revoke.assert_called_once_with(42)
    assert get_api_key() is None
    assert get_api_key_id() is None


def test_logout_forgets_but_does_not_revoke_a_hand_saved_key():
    from pkanban.cli import cmd_logout
    from pkanban.config import get_api_key, set_api_key

    set_api_key("pkanban_by_hand")
    with patch.object(PkanbanClient, "api_key_revoke") as revoke:
        cmd_logout()
    revoke.assert_not_called()
    assert get_api_key() is None


def test_password_login_replaces_an_earlier_browser_login():
    from pkanban.config import get_api_key, get_token

    with patch.object(PkanbanClient, "device_login_start", return_value=STARTED), \
         patch.object(PkanbanClient, "device_login_poll", return_value=(True, APPROVED)):
        login()
    with patch.object(PkanbanClient, "login", return_value="jwt"), \
         patch.object(PkanbanClient, "api_key_revoke") as revoke:
        login(username="ada", password="pw")
    revoke.assert_called_once_with(42)
    assert get_api_key() is None
    assert get_token() == "jwt"
