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
        """Test that API key prefix extraction works"""
        from backend.models import get_api_key_prefix

        key = "pkanban_abc123def456"
        prefix = get_api_key_prefix(key)
        assert prefix == "pkanban_"  # First 8 chars (the prefix itself is 8 chars)

    def test_hash_api_key(self):
        """Test that API keys can be hashed and verified"""
        from backend.models import hash_api_key

        key = "pkanban_testkey123"
        hashed = hash_api_key(key)

        # Hash should be different from original
        assert hashed != key
        # Hash should be a valid bcrypt hash
        assert hashed.startswith("$2b$")

    def test_create_api_key(self, test_user):
        """Test creating an API key"""
        api_key, raw_key = ApiKey.create_key(test_user, "Test Key")

        assert api_key is not None
        assert raw_key is not None
        assert api_key.user == test_user
        assert api_key.name == "Test Key"
        assert api_key.prefix == raw_key[:8]
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
