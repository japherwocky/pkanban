"""The one-line installers served at /install.sh and /install.ps1."""

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.mark.parametrize("path", ["/install.sh", "/install.ps1", "/install.cmd"])
def test_installer_is_served_as_text(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    # Not the SPA fallback, which would hand `sh` a page of HTML.
    assert "<html" not in response.text.lower()


@pytest.mark.parametrize("path", ["/install.sh", "/install.ps1", "/install.cmd"])
def test_installer_points_at_the_server_that_served_it(client, path):
    response = client.get(path, headers={"Host": "kanban.example.test"})
    assert "__PKANBAN_SERVER__" not in response.text
    assert "http://kanban.example.test" in response.text


def test_shell_installer_has_unix_line_endings(client):
    assert "\r" not in client.get("/install.sh").text


def test_cmd_installer_has_windows_line_endings(client):
    text = client.get("/install.cmd").text
    assert "\r\n" in text
    assert "\n" not in text.replace("\r\n", "")


def test_cmd_installer_hands_over_to_the_powershell_one_on_this_server(client):
    text = client.get("/install.cmd", headers={"Host": "kanban.example.test"}).text
    assert "irm 'http://kanban.example.test/install.ps1' | iex" in text


def test_powershell_installer_never_exits(client):
    # It runs under `irm | iex`, in the caller's own session: `exit` would
    # close their terminal window.
    script = client.get("/install.ps1").text
    code = [line for line in script.splitlines() if not line.lstrip().startswith("#")]
    assert not any(line.strip().startswith("exit") for line in code)


def test_agents_md_is_markdown_filled_in_with_this_server(client):
    response = client.get("/agents.md", headers={"Host": "kanban.example.test"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "__PKANBAN_SERVER__" not in response.text
    assert "http://kanban.example.test/install.sh" in response.text


def test_agents_md_only_names_commands_the_cli_has(client):
    # The page is instructions an agent follows literally: a command that
    # doesn't exist sends it off course with nobody watching.
    import re

    from typer.main import get_command

    from pkanban.cli import app as cli_app

    cli = get_command(cli_app)
    text = client.get("/agents.md").text
    named = re.findall(r"(?:^|`)pkanban ([a-z]+(?: [a-z]+)?)", text, re.MULTILINE)
    assert "login" in named and "init" in named
    for line in named:
        words = line.split()
        command = cli.commands.get(words[0])
        assert command is not None, f"agents.md names 'pkanban {words[0]}'"
        if len(words) > 1 and hasattr(command, "commands"):
            assert words[1] in command.commands, f"agents.md names 'pkanban {line}'"
