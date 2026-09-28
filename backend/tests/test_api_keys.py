import pytest
from fastapi.testclient import TestClient

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app
from backend.database import db
from backend.models import User, ApiKey
from backend.auth import create_access_token


@pytest.fixture
def auth_headers(test_user):
    token = create_access_token(
        data={"sub": test_user.id, "username": test_user.username}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(_setup_test_db):
    return TestClient(app)


class TestApiKeyModel:
    """Tests for the ApiKey model"""

    def test_generate_api_key_format(self):
        """Test that generated API keys have the correct format"""
        from backend.models import generate_api_key, API_KEY_PREFIX

        key = generate_api_key()
        assert key.startswith(API_KEY_PREFIX)
        assert len(key) == len(API_KEY_PREFIX) + 32  # prefix + 32 random chars

    def test_api_key_prefix(self):
        """The displayed prefix reaches past "pkanban_" into the random part.

        It used to be the first 8 characters -- "pkanban_" on every key -- so
        a key list showed the same prefix on every row.
        """
        from backend.models import get_api_key_prefix

        key = "pkanban_abc123def456"
        assert get_api_key_prefix(key) == "pkanban_abc123de"

    def test_hash_api_key(self):
        """Keys are stored by SHA-256: deterministic, so they can be looked up."""
        from backend.models import hash_api_key

        key = "pkanban_testkey123"
        hashed = hash_api_key(key)

        assert hashed != key
        assert len(hashed) == 64
        assert hashed == hash_api_key(key)
        assert hashed != hash_api_key(key + "x")

    def test_create_api_key(self, test_user):
        """Test creating an API key"""
        api_key, raw_key = ApiKey.create_key(test_user, "Test Key")

        assert api_key is not None
        assert raw_key is not None
        assert api_key.user == test_user
        assert api_key.name == "Test Key"
        assert api_key.prefix == raw_key[:16]
        assert api_key.is_active is True
        assert api_key.last_used_at is None

    def test_verify_api_key(self, test_user):
        """Test verifying a valid API key"""
        api_key, raw_key = ApiKey.create_key(test_user, "Test Key")

        assert api_key.verify(raw_key) is True
        assert api_key.verify("wrong_key") is False

    def test_deactivate_api_key(self, test_user):
        """Test deactivating an API key"""
        api_key, _ = ApiKey.create_key(test_user, "Test Key")

        assert api_key.is_active is True
        api_key.deactivate()
        assert api_key.is_active is False


class TestApiKeyEndpoints:
    """Tests for the API key endpoints"""

    def test_create_api_key_endpoint(self, client, auth_headers, test_user):
        """Test creating an API key via the API"""
        response = client.post(
            "/api/api-keys",
            json={"name": "CI Agent"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "key" in data  # The raw key (shown only once)
        assert "id" in data
        assert "name" in data
        assert data["name"] == "CI Agent"
        assert data["key"].startswith("pkanban_")

    def test_create_api_key_requires_auth(self, client):
        """Test that creating an API key requires authentication"""
        response = client.post(
            "/api/api-keys",
            json={"name": "CI Agent"},
        )
        assert response.status_code == 401

    def test_list_api_keys_endpoint(self, client, auth_headers, test_user):
        """Test listing API keys"""
        # Create a key first
        client.post(
            "/api/api-keys",
            json={"name": "Test Key"},
            headers=auth_headers,
        )

        # List keys
        response = client.get("/api/api-keys", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        # Keys should NOT include the full key for security
        assert "key" not in data[0]
        assert "prefix" in data[0]
        assert "name" in data[0]
        assert "is_active" in data[0]

    def test_revoke_api_key_endpoint(self, client, auth_headers, test_user):
        """Test revoking (deactivating) an API key"""
        # Create a key
        create_response = client.post(
            "/api/api-keys",
            json={"name": "Revoke Test"},
            headers=auth_headers,
        )
        key_id = create_response.json()["id"]

        # Revoke it
        response = client.delete(f"/api/api-keys/{key_id}", headers=auth_headers)
        assert response.status_code == 200

        # Verify it's inactive
        list_response = client.get("/api/api-keys", headers=auth_headers)
        keys = list_response.json()
        revoked_key = next((k for k in keys if k["id"] == key_id), None)
        assert revoked_key is not None
        assert revoked_key["is_active"] is False

    def test_activate_api_key_endpoint(self, client, auth_headers, test_user):
        """Test activating a deactivated API key"""
        # Create a key
        create_response = client.post(
            "/api/api-keys",
            json={"name": "Activate Test"},
            headers=auth_headers,
        )
        key_id = create_response.json()["id"]

        # Revoke it first
        client.delete(f"/api/api-keys/{key_id}", headers=auth_headers)

        # Activate it again
        response = client.post(f"/api/api-keys/{key_id}/activate", headers=auth_headers)
        assert response.status_code == 200

        # Verify it's active
        list_response = client.get("/api/api-keys", headers=auth_headers)
        keys = list_response.json()
        activated_key = next((k for k in keys if k["id"] == key_id), None)
        assert activated_key is not None
        assert activated_key["is_active"] is True

    def test_revoke_nonexistent_key(self, client, auth_headers):
        """Test that revoking a non-existent key returns 404"""
        response = client.delete("/api/api-keys/99999", headers=auth_headers)
        assert response.status_code == 404


class TestApiKeyAuthentication:
    """Tests for using API keys for authentication"""

    def test_authenticate_with_api_key(self, client, test_user, db_session):
        """Test that API keys can be used for authentication."""
        from backend.models import ApiKey

        # Create API key directly via model (bypasses HTTP)
        api_key, raw_key = ApiKey.create_key(test_user, "Auth Test")

        # Use the API key for authentication
        response = client.get("/api/boards", headers={"X-API-Key": raw_key})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_authenticate_with_invalid_api_key(self, client):
        """Test that invalid API keys are rejected"""
        response = client.get(
            "/api/boards",
            headers={"X-API-Key": "pkanban_invalidkey123456789"},
        )
        assert response.status_code == 401

    def test_authenticate_with_inactive_api_key(self, client, auth_headers):
        """Test that inactive API keys are rejected"""
        # Create an API key via the API
        create_response = client.post(
            "/api/api-keys",
            json={"name": "Inactive Test"},
            headers=auth_headers,
        )
        assert create_response.status_code == 200
        key_id = create_response.json()["id"]
        raw_key = create_response.json()["key"]

        # Deactivate it
        client.delete(f"/api/api-keys/{key_id}", headers=auth_headers)

        # Try to use it
        response = client.get("/api/boards", headers={"X-API-Key": raw_key})
        assert response.status_code == 401

    def test_api_key_updates_last_used(self, client, auth_headers, db_session):
        """Test that using an API key updates last_used_at."""
        # Create an API key via the API
        create_response = client.post(
            "/api/api-keys",
            json={"name": "Last Used Test"},
            headers=auth_headers,
        )
        assert create_response.status_code == 200, (
            f"Failed to create API key: {create_response.text}"
        )
        key_id = create_response.json()["id"]
        raw_key = create_response.json()["key"]

        # First use
        response = client.get("/api/boards", headers={"X-API-Key": raw_key})
        assert response.status_code == 200, f"API key auth failed: {response.text}"

        # Verify last_used_at is updated by checking the API key list
        list_response = client.get("/api/api-keys", headers=auth_headers)
        keys = list_response.json()
        test_key = next((k for k in keys if k["id"] == key_id), None)
        assert test_key is not None
        assert test_key["last_used_at"] is not None

    def test_bearer_token_still_works(self, client, auth_headers):
        """Test that regular Bearer token authentication still works"""
        response = client.get("/api/boards", headers=auth_headers)
        assert response.status_code == 200

    def test_no_auth_returns_401(self, client):
        """Test that requests without auth return 401"""
        response = client.get("/api/boards")
        assert response.status_code == 401


class TestKeysCannotMintKeys:
    """A key that can make keys makes a leak permanent: mint a second key,
    and revoking the first cuts off nothing."""

    def test_a_key_cannot_create_a_key(self, client, test_user):
        _, raw = ApiKey.create_key(test_user, "leaked")
        response = client.post(
            "/api/api-keys", json={"name": "backdoor"}, headers={"X-API-Key": raw}
        )
        assert response.status_code == 403
        assert ApiKey.select().where(ApiKey.name == "backdoor").count() == 0

    def test_a_key_cannot_reactivate_a_key(self, client, test_user):
        revoked, _ = ApiKey.create_key(test_user, "revoked")
        revoked.deactivate()
        _, raw = ApiKey.create_key(test_user, "leaked")
        response = client.post(
            f"/api/api-keys/{revoked.id}/activate", headers={"X-API-Key": raw}
        )
        assert response.status_code == 403
        assert ApiKey.get_by_id(revoked.id).is_active is False

    def test_a_key_can_still_list_and_revoke(self, client, test_user):
        _, raw = ApiKey.create_key(test_user, "agent")
        other, _ = ApiKey.create_key(test_user, "other")
        headers = {"X-API-Key": raw}
        assert client.get("/api/api-keys", headers=headers).status_code == 200
        response = client.delete(f"/api/api-keys/{other.id}", headers=headers)
        assert response.status_code == 200
        assert ApiKey.get_by_id(other.id).is_active is False

    def test_a_session_can_still_create_and_reactivate(self, client, auth_headers):
        created = client.post(
            "/api/api-keys", json={"name": "fine"}, headers=auth_headers
        )
        assert created.status_code == 200
        key_id = created.json()["id"]
        client.delete(f"/api/api-keys/{key_id}", headers=auth_headers)
        response = client.post(
            f"/api/api-keys/{key_id}/activate", headers=auth_headers
        )
        assert response.status_code == 200

def _legacy_key(user, name="Legacy"):
    """A key as it was stored before migration 006: bcrypt only, no SHA-256."""
    import bcrypt
    from backend.models import generate_api_key

    raw = generate_api_key()
    row = ApiKey.create(
        user=user,
        name=name,
        key_hash=bcrypt.hashpw(raw.encode(), bcrypt.gensalt(4)).decode(),
        key_sha256=None,
        prefix="pkanban_",
    )
    return row, raw


@pytest.fixture
def second_user(db_session):
    return User.create_user("second_key_user", "testpassword")


class TestApiKeyLookup:
    """More than one key in the table.

    Every test above creates exactly one key into a freshly cleared database,
    which is the only situation in which looking a key up by its first 8
    characters -- "pkanban_", on every key -- happened to work.
    """

    def test_every_key_authenticates(self, client, test_user, second_user):
        keys = [
            ApiKey.create_key(test_user, "first")[1],
            ApiKey.create_key(test_user, "second")[1],
            ApiKey.create_key(second_user, "third")[1],
        ]
        for raw in keys:
            response = client.get("/api/boards", headers={"X-API-Key": raw})
            assert response.status_code == 200, response.text

    def test_each_key_is_its_owners(self, client, test_user, second_user):
        """The old lookup authenticated whoever owned the first row."""
        from backend.models import Board

        ApiKey.create_key(test_user, "first")
        _, raw = ApiKey.create_key(second_user, "second")
        response = client.post(
            "/api/boards", json={"name": "made by key"}, headers={"X-API-Key": raw}
        )
        assert response.status_code == 200, response.text
        board = Board.get(Board.name == "made by key")
        assert board.owner_id == second_user.id

    def test_revoking_one_key_leaves_the_others(self, client, test_user):
        first, _ = ApiKey.create_key(test_user, "first")
        _, raw = ApiKey.create_key(test_user, "second")
        first.deactivate()
        response = client.get("/api/boards", headers={"X-API-Key": raw})
        assert response.status_code == 200, response.text

    def test_unknown_key_is_refused_even_with_a_valid_token(
        self, client, auth_headers
    ):
        """A key that was sent decides; it does not fall through to the JWT."""
        headers = dict(auth_headers, **{"X-API-Key": "pkanban_" + "x" * 32})
        response = client.get("/api/boards", headers=headers)
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid API key"

    def test_oversized_key_is_a_401_not_a_500(self, client, test_user):
        _legacy_key(test_user)
        response = client.get(
            "/api/boards", headers={"X-API-Key": "pkanban_" + "x" * 200}
        )
        assert response.status_code == 401

    def test_legacy_key_authenticates_and_upgrades(self, client, test_user):
        from backend.models import hash_api_key

        ApiKey.create_key(test_user, "new")
        row, raw = _legacy_key(test_user)

        response = client.get("/api/boards", headers={"X-API-Key": raw})
        assert response.status_code == 200, response.text

        row = ApiKey.get_by_id(row.id)
        assert row.key_sha256 == hash_api_key(raw)
        assert row.key_hash == ""
        assert row.prefix == raw[:16]

        # And from now on it is found by the fast path.
        assert ApiKey.find(raw).id == row.id

    def test_two_legacy_keys_both_work(self, client, test_user, second_user):
        _, first = _legacy_key(test_user, "first")
        _, second = _legacy_key(second_user, "second")
        for raw in (second, first):
            response = client.get("/api/boards", headers={"X-API-Key": raw})
            assert response.status_code == 200, response.text

    def test_inactive_legacy_key_is_refused(self, client, test_user):
        row, raw = _legacy_key(test_user)
        row.deactivate()
        response = client.get("/api/boards", headers={"X-API-Key": raw})
        assert response.status_code == 401

    def test_last_used_is_not_rewritten_on_every_request(self, client, test_user):
        row, raw = ApiKey.create_key(test_user, "busy")
        client.get("/api/boards", headers={"X-API-Key": raw})
        first = ApiKey.get_by_id(row.id).last_used_at
        assert first is not None

        client.get("/api/boards", headers={"X-API-Key": raw})
        assert ApiKey.get_by_id(row.id).last_used_at == first
