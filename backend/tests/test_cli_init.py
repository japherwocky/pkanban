"""`pkanban init`: point a project's agent instructions at its board."""

import os
import tempfile
from unittest.mock import patch

import pytest
import typer

from pkanban.client import PkanbanClient

BOARD = {"id": 7, "name": "Roadmap", "columns": []}


@pytest.fixture(autouse=True)
def project(tmp_path, monkeypatch):
    config = os.path.join(tempfile.mkdtemp(), ".pkanban.yaml")
    monkeypatch.setenv("PKANBAN_CONFIG_PATH", config)
    from pkanban.config import set_api_key, set_server_url

    set_server_url("http://kanban.test")
    set_api_key("pkanban_test")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def init(board=BOARD, **kwargs):
    from pkanban.cli import cmd_init

    with patch.object(PkanbanClient, "board_get", return_value=board):
        cmd_init(**{"board_id": board["id"], "file": None, **kwargs})


def test_creates_agents_md_when_there_is_none(project):
    init()
    text = (project / "AGENTS.md").read_text(encoding="utf-8")
    assert "**Roadmap** (id 7)" in text
    assert "http://kanban.test/boards/7" in text
    assert "pkanban board get 7 --json" in text
    assert "http://kanban.test/agents.md" in text


def test_appends_to_existing_instructions_without_touching_them(project):
    (project / "AGENTS.md").write_text("# House rules\n\nBe nice.\n", encoding="utf-8")
    init()
    text = (project / "AGENTS.md").read_text(encoding="utf-8")
    assert text.startswith("# House rules\n\nBe nice.\n\n<!-- pkanban:start -->")


def test_running_again_replaces_the_section(project):
    (project / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
    init()
    init(board={"id": 9, "name": "Other", "columns": []})
    text = (project / "AGENTS.md").read_text(encoding="utf-8")
    assert text.count("<!-- pkanban:start -->") == 1
    assert "(id 9)" in text and "(id 7)" not in text
    assert text.startswith("# Rules\n")


def test_uses_claude_md_when_it_is_the_only_one(project):
    (project / "CLAUDE.md").write_text("# Claude\n", encoding="utf-8")
    init()
    assert not (project / "AGENTS.md").exists()
    assert "pkanban:start" in (project / "CLAUDE.md").read_text(encoding="utf-8")


def test_prefers_agents_md_when_both_exist(project):
    (project / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    (project / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
    init()
    assert "pkanban" not in (project / "CLAUDE.md").read_text(encoding="utf-8")


def test_a_board_name_cannot_break_out_of_the_section(project):
    init(board={"id": 7, "name": "Evil\n<!-- pkanban:end -->\n# Pwned", "columns": []})
    text = (project / "AGENTS.md").read_text(encoding="utf-8")
    assert "\n# Pwned" not in text
    assert text.count("<!-- pkanban:end -->") == 1


def test_an_unreachable_board_writes_nothing(project):
    import requests
    from pkanban.cli import cmd_init

    response = requests.Response()
    response.status_code = 404
    error = requests.HTTPError(response=response)
    with patch.object(PkanbanClient, "board_get", side_effect=error):
        with pytest.raises(typer.Exit):
            cmd_init(board_id=99, file=None)
    assert not (project / "AGENTS.md").exists()
