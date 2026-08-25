"""KANBAN_CONFIG_PATH must be honoured whenever it is set.

pkanban.config used to bind its path at import time, so the variable only took
effect if it was set before the first import. A test module importing the CLI
at collection time -- earlier than any fixture -- silently bound the real
~/.pkanban.yaml, and every subsequent test wrote to the developer's own
credentials: server URL overwritten, token replaced, API key cleared.
"""

import os
from pathlib import Path

# Imported at module scope on purpose: this is the collection-time import that
# used to freeze the path to the developer's home directory.
from pkanban import config


def test_config_path_follows_the_env_var_set_after_import(tmp_path, monkeypatch):
    target = tmp_path / "late.yaml"
    monkeypatch.setenv("KANBAN_CONFIG_PATH", str(target))

    config.set_server_url("http://late.example.com")

    assert target.exists()
    assert config.get_server_url() == "http://late.example.com"


def test_writes_never_reach_the_real_home_config(tmp_path, monkeypatch):
    """The failure this guards against is destructive, so assert the negative
    directly: nothing may touch ~/.pkanban.yaml."""
    real = config.DEFAULT_CONFIG_FILE
    before = real.read_bytes() if real.exists() else None

    monkeypatch.setenv("KANBAN_CONFIG_PATH", str(tmp_path / "sandbox.yaml"))
    config.set_server_url("http://sandbox.example.com")
    config.set_token("sandbox-token")
    config.set_api_key("sandbox-key")
    config.clear_api_key()
    config.clear_token()

    after = real.read_bytes() if real.exists() else None
    assert after == before, f"{real} was modified by the test suite"


def test_switching_the_env_var_switches_files(tmp_path, monkeypatch):
    first, second = tmp_path / "a.yaml", tmp_path / "b.yaml"

    monkeypatch.setenv("KANBAN_CONFIG_PATH", str(first))
    config.set_server_url("http://first.example.com")

    monkeypatch.setenv("KANBAN_CONFIG_PATH", str(second))
    config.set_server_url("http://second.example.com")

    assert config.get_server_url() == "http://second.example.com"
    monkeypatch.setenv("KANBAN_CONFIG_PATH", str(first))
    assert config.get_server_url() == "http://first.example.com"


def test_falls_back_to_home_when_unset(monkeypatch):
    monkeypatch.delenv("KANBAN_CONFIG_PATH", raising=False)
    assert config.config_file() == Path.home() / ".pkanban.yaml"


def test_login_does_not_wipe_a_saved_api_key(tmp_path, monkeypatch):
    """set_token used to replace the whole auth dict, so 'pkanban login'
    silently deleted a saved API key (card #113)."""
    monkeypatch.setenv("KANBAN_CONFIG_PATH", str(tmp_path / "sandbox.yaml"))

    config.set_api_key("existing-api-key")
    config.set_token("new-login-token")

    assert config.get_api_key() == "existing-api-key"
    assert config.get_token() == "new-login-token"


def test_logout_does_not_wipe_a_saved_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("KANBAN_CONFIG_PATH", str(tmp_path / "sandbox.yaml"))

    config.set_api_key("existing-api-key")
    config.set_token("session-token")
    config.clear_token()

    assert config.get_api_key() == "existing-api-key"
    assert config.get_token() is None
