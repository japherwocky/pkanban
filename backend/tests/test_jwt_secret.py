"""Tests for JWT signing key resolution.

The bug these cover: backend/auth.py used to fall back to the literal string
"change-this-in-production" when JWT_SECRET_KEY was unset. This repo is public,
so any deployment running on that default could have tokens forged for any
account, and nothing anywhere said so.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.auth import (
    PLACEHOLDER_SECRETS,
    _load_secret_key,
    _secret_file_path,
    create_access_token,
    decode_token,
)


@pytest.fixture
def secret_file(tmp_path, monkeypatch):
    """Keep key generation inside tmp_path instead of the working directory."""
    path = tmp_path / ".jwt_secret"
    monkeypatch.setenv("JWT_SECRET_FILE", str(path))
    return path


class TestExplicitSecret:
    def test_configured_secret_is_used(self, secret_file, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "a-real-secret")
        assert _load_secret_key() == "a-real-secret"

    def test_configured_secret_wins_over_generated_file(self, secret_file, monkeypatch):
        secret_file.write_text("previously-generated")
        monkeypatch.setenv("JWT_SECRET_KEY", "a-real-secret")
        assert _load_secret_key() == "a-real-secret"

    def test_whitespace_only_secret_counts_as_unset(self, secret_file, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "   ")
        assert _load_secret_key() != "   "
        assert secret_file.exists()


class TestPlaceholderRejection:
    @pytest.mark.parametrize("placeholder", sorted(PLACEHOLDER_SECRETS))
    def test_placeholder_refuses_to_start(self, placeholder, secret_file, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", placeholder)
        with pytest.raises(RuntimeError) as exc:
            _load_secret_key()
        assert "public" in str(exc.value)

    def test_old_default_is_covered(self):
        """The value auth.py silently fell back to before this was fixed."""
        assert "change-this-in-production" in PLACEHOLDER_SECRETS

    def test_shipped_example_env_value_is_covered(self):
        """sys/config/production.env ships a key; copying it verbatim must fail."""
        assert (
            "your-super-secret-jwt-key-here-change-this-in-production"
            in PLACEHOLDER_SECRETS
        )


class TestGeneratedSecret:
    def test_generates_and_persists_when_unset(self, secret_file, monkeypatch):
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

        generated = _load_secret_key()

        assert generated
        assert generated not in PLACEHOLDER_SECRETS
        assert len(generated) >= 32
        assert secret_file.read_text().strip() == generated

    def test_reuses_the_same_secret_across_restarts(self, secret_file, monkeypatch):
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

        first = _load_secret_key()
        second = _load_secret_key()

        # Regenerating per process would log every user out on each restart,
        # and would break outright under multiple workers.
        assert first == second

    def test_two_deployments_get_different_secrets(self, tmp_path, monkeypatch):
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

        monkeypatch.setenv("JWT_SECRET_FILE", str(tmp_path / "one"))
        first = _load_secret_key()
        monkeypatch.setenv("JWT_SECRET_FILE", str(tmp_path / "two"))
        second = _load_secret_key()

        assert first != second

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes only")
    def test_generated_file_is_not_world_readable(self, secret_file, monkeypatch):
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

        _load_secret_key()

        assert secret_file.stat().st_mode & 0o077 == 0

    def test_unwritable_location_explains_itself(self, tmp_path, monkeypatch):
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        # A directory component that is not a directory: open() fails on every
        # platform, unlike permission tricks which root ignores.
        blocker = tmp_path / "not-a-dir"
        blocker.write_text("")
        monkeypatch.setenv("JWT_SECRET_FILE", str(blocker / ".jwt_secret"))

        with pytest.raises(RuntimeError) as exc:
            _load_secret_key()
        assert "JWT_SECRET_KEY" in str(exc.value)


class TestSecretFileLocation:
    def test_defaults_to_beside_the_database(self, tmp_path, monkeypatch):
        monkeypatch.delenv("JWT_SECRET_FILE", raising=False)
        monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "pkanban.db"))

        assert _secret_file_path() == str(tmp_path / ".jwt_secret")

    def test_in_memory_database_falls_back_to_cwd(self, monkeypatch):
        monkeypatch.delenv("JWT_SECRET_FILE", raising=False)
        monkeypatch.setenv("DATABASE_PATH", "file:kanban_test?mode=memory")

        # A URI has no directory to sit beside; it must not be treated as one.
        assert _secret_file_path() == os.path.join(os.getcwd(), ".jwt_secret")


class TestTokensStillWork:
    def test_round_trip_with_the_configured_secret(self, test_user):
        token = create_access_token(
            data={"sub": test_user.id, "username": test_user.username}
        )
        decoded = decode_token(token)

        assert decoded.user_id == test_user.id
        assert decoded.username == test_user.username
