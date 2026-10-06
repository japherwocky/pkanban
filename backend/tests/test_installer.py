"""The one-line installers served at /install.sh and /install.ps1."""

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.mark.parametrize("path", ["/install.sh", "/install.ps1"])
def test_installer_is_served_as_text(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    # Not the SPA fallback, which would hand `sh` a page of HTML.
    assert "<html" not in response.text.lower()


@pytest.mark.parametrize("path", ["/install.sh", "/install.ps1"])
def test_installer_points_at_the_server_that_served_it(client, path):
    response = client.get(path, headers={"Host": "kanban.example.test"})
    assert "__PKANBAN_SERVER__" not in response.text
    assert "http://kanban.example.test" in response.text


def test_shell_installer_has_unix_line_endings(client):
    assert "\r" not in client.get("/install.sh").text


def test_powershell_installer_never_exits(client):
    # It runs under `irm | iex`, in the caller's own session: `exit` would
    # close their terminal window.
    script = client.get("/install.ps1").text
    code = [line for line in script.splitlines() if not line.lstrip().startswith("#")]
    assert not any(line.strip().startswith("exit") for line in code)
