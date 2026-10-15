"""OAuth sign-in for /mcp (Dev #969).

The whole flow a chat app drives -- discovery, registration, authorize, the
consent page's approve, the token exchange, then /mcp with the token -- plus
the places it must refuse. The protocol checks are the MCP SDK's handlers;
these tests pin what this server adds: the storage, the consent API, the
redirect URI rule, and that the token is a revocable API key.
"""

import base64
import hashlib
import random
import secrets
import string
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from backend.auth import create_access_token
from backend.main import app
from backend.models import ApiKey, OAuthClient, OAuthGrant, User

BASE = "http://testserver"
CALLBACK = "https://claude.ai/api/mcp/auth_callback"
ACCEPT = {"Accept": "application/json, text/event-stream"}


@pytest.fixture
def client(db_session):
    # With the lifespan, so /mcp can be called with the token at the end.
    with TestClient(app) as c:
        yield c


@pytest.fixture
def user(db_session):
    suffix = "".join(random.choices(string.ascii_lowercase, k=8))
    return User.create_user(f"oauth_{suffix}", "testpassword")


def session(user):
    token = create_access_token(data={"sub": user.id, "username": user.username})
    return {"Authorization": f"Bearer {token}"}


def pkce():
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    return verifier, base64.urlsafe_b64encode(digest).decode().rstrip("=")


def register(client, redirect_uris=(CALLBACK,), **extra):
    return client.post(
        "/oauth/register",
        json={"client_name": "Claude", "redirect_uris": list(redirect_uris), **extra},
    )


@pytest.fixture
def app_client(client):
    """A registered app: the registration response, secret included."""
    response = register(client)
    assert response.status_code == 201, response.text
    return response.json()


def authorize(client, app_client, challenge, state="xyz", redirect_uri=CALLBACK):
    response = client.get(
        "/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": app_client["client_id"],
            "redirect_uri": redirect_uri,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
            "resource": f"{BASE}/mcp",
        },
        follow_redirects=False,
    )
    return response


def request_id_from(response):
    assert response.status_code == 302, response.text
    location = urlparse(response.headers["location"])
    assert location.path == "/oauth/consent"
    return parse_qs(location.query)["request"][0]


def exchange(client, app_client, code, verifier, redirect_uri=CALLBACK):
    return client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
            "client_id": app_client["client_id"],
            "client_secret": app_client["client_secret"],
        },
    )


def sign_in(client, app_client, user):
    """The whole flow, approved; (token response, redirect query)."""
    verifier, challenge = pkce()
    request_id = request_id_from(authorize(client, app_client, challenge))
    approved = client.post(f"/api/oauth/requests/{request_id}/approve", headers=session(user))
    assert approved.status_code == 200, approved.text
    query = parse_qs(urlparse(approved.json()["redirect_to"]).query)
    token = exchange(client, app_client, query["code"][0], verifier)
    return token, query


def mcp_status(client, token):
    response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        headers={**ACCEPT, "Authorization": f"Bearer {token}"},
    )
    return response.status_code


# --- Discovery -------------------------------------------------------------


def test_mcp_401_points_at_the_resource_metadata(client):
    response = client.post("/mcp", json={}, headers=ACCEPT)
    assert response.status_code == 401
    challenge = response.headers["www-authenticate"]
    assert f'resource_metadata="{BASE}/.well-known/oauth-protected-resource/mcp"' in challenge
    # Nothing was presented, so nothing is called invalid (RFC 6750 3.1).
    assert "error=" not in challenge


def test_a_refused_key_is_called_invalid(client):
    response = client.post("/mcp", json={}, headers={**ACCEPT, "X-API-Key": "pkanban_nope"})
    assert 'error="invalid_token"' in response.headers["www-authenticate"]


@pytest.mark.parametrize(
    "path",
    ["/.well-known/oauth-protected-resource/mcp", "/.well-known/oauth-protected-resource"],
)
def test_protected_resource_metadata(client, path):
    body = client.get(path).json()
    assert body["resource"] == f"{BASE}/mcp"
    assert body["authorization_servers"] == [BASE]


def test_authorization_server_metadata_names_this_server(client):
    # Built from the request, so a self-hosted server describes itself.
    body = client.get("/.well-known/oauth-authorization-server").json()
    assert body["issuer"] == BASE
    assert body["authorization_endpoint"] == f"{BASE}/oauth/authorize"
    assert body["token_endpoint"] == f"{BASE}/oauth/token"
    assert body["registration_endpoint"] == f"{BASE}/oauth/register"
    assert body["code_challenge_methods_supported"] == ["S256"]


def test_metadata_follows_the_host(db_session):
    with TestClient(app, base_url="https://kanban.example.org") as c:
        body = c.get("/.well-known/oauth-authorization-server").json()
    assert body["issuer"] == "https://kanban.example.org"


# --- Registration ----------------------------------------------------------


def test_registration_returns_credentials(client, app_client):
    assert app_client["client_id"]
    assert app_client["client_secret"]
    row = OAuthClient.get(OAuthClient.client_id == app_client["client_id"])
    assert row.client_name == "Claude"


@pytest.mark.parametrize(
    "uri",
    [
        "javascript:alert(1)",
        "data:text/html,hi",
        "http://evil.example.com/callback",
        "https://example.com/callback#frag",
    ],
)
def test_registration_refuses_unsafe_redirect_uris(client, uri):
    response = register(client, redirect_uris=[uri])
    assert response.status_code == 400
    assert response.json()["error"] in ("invalid_redirect_uri", "invalid_client_metadata")


@pytest.mark.parametrize(
    "uri",
    [
        "http://localhost:33418/callback",
        "http://127.0.0.1:8765/cb",
        "cursor://anysphere.cursor-mcp/oauth/callback",
    ],
)
def test_registration_allows_loopback_and_native_app_uris(client, uri):
    assert register(client, redirect_uris=[uri]).status_code == 201


def test_registrations_never_approved_are_pruned(client):
    stale = register(client).json()["client_id"]
    OAuthClient.update(created_at=datetime.now(timezone.utc) - timedelta(days=2)).where(
        OAuthClient.client_id == stale
    ).execute()
    register(client)
    assert OAuthClient.get_or_none(OAuthClient.client_id == stale) is None


# --- The flow --------------------------------------------------------------


def test_sign_in_end_to_end(client, app_client, user):
    token, query = sign_in(client, app_client, user)
    assert token.status_code == 200, token.text
    body = token.json()
    assert body["token_type"] == "Bearer"
    assert query["state"] == ["xyz"]

    # The token is an API key belonging to the person who approved.
    key = ApiKey.find(body["access_token"])
    assert key.user_id == user.id
    assert key.name == "Claude (connected app)"
    assert mcp_status(client, body["access_token"]) == 200

    # Revoking it in Settings disconnects the app.
    key.is_active = False
    key.save()
    assert mcp_status(client, body["access_token"]) == 401


def test_consent_page_sees_who_is_asking_and_where_the_code_goes(client, app_client, user):
    _, challenge = pkce()
    request_id = request_id_from(authorize(client, app_client, challenge))
    view = client.get(f"/api/oauth/requests/{request_id}", headers=session(user)).json()
    assert view["client_name"] == "Claude"
    assert view["redirect_host"] == "claude.ai"
    assert view["status"] == "pending"


def test_deny_sends_access_denied_with_the_state(client, app_client, user):
    _, challenge = pkce()
    request_id = request_id_from(authorize(client, app_client, challenge, state="s1"))
    denied = client.post(f"/api/oauth/requests/{request_id}/deny", headers=session(user))
    query = parse_qs(urlparse(denied.json()["redirect_to"]).query)
    assert query["error"] == ["access_denied"]
    assert query["state"] == ["s1"]
    assert "code" not in query


def test_a_request_is_decided_once(client, app_client, user):
    _, challenge = pkce()
    request_id = request_id_from(authorize(client, app_client, challenge))
    url = f"/api/oauth/requests/{request_id}"
    assert client.post(f"{url}/approve", headers=session(user)).status_code == 200
    assert client.post(f"{url}/approve", headers=session(user)).status_code == 409
    assert client.post(f"{url}/deny", headers=session(user)).status_code == 409


def test_an_api_key_cannot_approve(client, app_client, user):
    # Otherwise a leaked key could mint itself a successor.
    _, challenge = pkce()
    request_id = request_id_from(authorize(client, app_client, challenge))
    raw = ApiKey.create_key(user, "cli")[1]
    response = client.post(f"/api/oauth/requests/{request_id}/approve", headers={"X-API-Key": raw})
    assert response.status_code == 403


def test_expired_request_cannot_be_approved(client, app_client, user):
    _, challenge = pkce()
    request_id = request_id_from(authorize(client, app_client, challenge))
    OAuthGrant.update(expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)).where(
        OAuthGrant.request_id == request_id
    ).execute()
    response = client.post(f"/api/oauth/requests/{request_id}/approve", headers=session(user))
    assert response.status_code == 410


def test_unknown_request_is_404(client, user):
    assert client.get("/api/oauth/requests/nope", headers=session(user)).status_code == 404


def test_wrong_verifier_gets_no_token(client, app_client, user):
    _, challenge = pkce()
    request_id = request_id_from(authorize(client, app_client, challenge))
    approved = client.post(f"/api/oauth/requests/{request_id}/approve", headers=session(user))
    code = parse_qs(urlparse(approved.json()["redirect_to"]).query)["code"][0]
    response = exchange(client, app_client, code, verifier="not-the-verifier-" + "x" * 40)
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_grant"


def test_a_code_used_twice_revokes_the_token_it_bought(client, app_client, user):
    verifier, challenge = pkce()
    request_id = request_id_from(authorize(client, app_client, challenge))
    approved = client.post(f"/api/oauth/requests/{request_id}/approve", headers=session(user))
    code = parse_qs(urlparse(approved.json()["redirect_to"]).query)["code"][0]

    first = exchange(client, app_client, code, verifier)
    assert first.status_code == 200
    second = exchange(client, app_client, code, verifier)
    assert second.status_code == 400
    assert mcp_status(client, first.json()["access_token"]) == 401


def test_expired_code_gets_no_token(client, app_client, user):
    verifier, challenge = pkce()
    request_id = request_id_from(authorize(client, app_client, challenge))
    approved = client.post(f"/api/oauth/requests/{request_id}/approve", headers=session(user))
    code = parse_qs(urlparse(approved.json()["redirect_to"]).query)["code"][0]
    OAuthGrant.update(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)).where(
        OAuthGrant.request_id == request_id
    ).execute()
    assert exchange(client, app_client, code, verifier).status_code == 400


def test_another_apps_code_is_refused(client, app_client, user):
    verifier, challenge = pkce()
    request_id = request_id_from(authorize(client, app_client, challenge))
    approved = client.post(f"/api/oauth/requests/{request_id}/approve", headers=session(user))
    code = parse_qs(urlparse(approved.json()["redirect_to"]).query)["code"][0]
    other = register(client).json()
    assert exchange(client, other, code, verifier).status_code == 400


def test_unknown_client_at_the_token_endpoint_is_401_invalid_client(client):
    # How Claude learns to register again.
    response = exchange(
        client, {"client_id": "gone", "client_secret": "x"}, "code", "verifier"
    )
    assert response.status_code == 401
    assert response.json()["error"] == "invalid_client"


def test_unregistered_redirect_uri_is_refused_without_redirecting(client, app_client):
    _, challenge = pkce()
    response = authorize(client, app_client, challenge, redirect_uri="https://evil.example.com/cb")
    assert response.status_code == 400


def test_refresh_tokens_are_not_issued(client, app_client, user):
    token, _ = sign_in(client, app_client, user)
    assert "refresh_token" not in token.json() or token.json()["refresh_token"] is None
