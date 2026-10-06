"""Device login: `pkanban login` approved in a browser instead of a password."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.auth import create_access_token
from backend.main import app
from backend.models import ApiKey, DeviceLogin, User


@pytest.fixture
def client(_setup_test_db):
    return TestClient(app)


@pytest.fixture
def auth_headers(test_user):
    token = create_access_token(
        data={"sub": test_user.id, "username": test_user.username}
    )
    return {"Authorization": f"Bearer {token}"}


def start(client, name="laptop"):
    response = client.post("/api/auth/device", json={"client_name": name})
    assert response.status_code == 200
    return response.json()


def poll(client, device_code):
    return client.post("/api/auth/device/token", json={"device_code": device_code})


def test_start_returns_codes_and_a_link_on_this_server(client, db_session):
    body = start(client)
    assert len(body["user_code"]) == 9 and body["user_code"][4] == "-"
    assert body["verification_uri"] == "http://testserver/device"
    assert body["verification_uri_complete"] == (
        f"http://testserver/device?code={body['user_code']}"
    )
    assert body["interval"] > 0 and body["expires_in"] > 0


def test_device_code_is_stored_only_as_a_hash(client, db_session):
    body = start(client)
    login = DeviceLogin.get()
    assert body["device_code"] not in login.device_code_sha256


def test_poll_is_pending_until_approved(client, db_session):
    body = start(client)
    response = poll(client, body["device_code"])
    assert response.status_code == 400
    assert response.json()["error"] == "authorization_pending"


def test_approve_then_poll_mints_a_working_api_key(
    client, test_user, auth_headers
):
    body = start(client, name="Ada's laptop")
    approved = client.post(
        f"/api/auth/device/{body['user_code']}/approve", headers=auth_headers
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    response = poll(client, body["device_code"])
    assert response.status_code == 200
    result = response.json()
    assert result["username"] == test_user.username
    assert result["api_key_name"] == "pkanban login: Ada's laptop"

    boards = client.get("/api/boards", headers={"X-API-Key": result["api_key"]})
    assert boards.status_code == 200
    key = ApiKey.get_by_id(result["api_key_id"])
    assert key.user.id == test_user.id


def test_an_approved_login_is_claimed_only_once(client, test_user, auth_headers):
    body = start(client)
    client.post(f"/api/auth/device/{body['user_code']}/approve", headers=auth_headers)
    assert poll(client, body["device_code"]).status_code == 200

    again = poll(client, body["device_code"])
    assert again.status_code == 400
    assert again.json()["error"] == "invalid_grant"
    assert ApiKey.select().count() == 1


def test_denied_login_says_so_and_mints_nothing(client, test_user, auth_headers):
    body = start(client)
    denied = client.post(
        f"/api/auth/device/{body['user_code']}/deny", headers=auth_headers
    )
    assert denied.json()["status"] == "denied"
    assert poll(client, body["device_code"]).json()["error"] == "access_denied"
    assert ApiKey.select().count() == 0


def test_expired_login_cannot_be_approved_or_claimed(client, test_user, auth_headers):
    body = start(client)
    DeviceLogin.update(
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
    ).execute()

    assert poll(client, body["device_code"]).json()["error"] == "expired_token"
    approve = client.post(
        f"/api/auth/device/{body['user_code']}/approve", headers=auth_headers
    )
    assert approve.status_code == 410
    view = client.get(f"/api/auth/device/{body['user_code']}", headers=auth_headers)
    assert view.json()["status"] == "expired"


def test_user_code_is_forgiving_about_case_and_dash(client, test_user, auth_headers):
    body = start(client)
    sloppy = body["user_code"].replace("-", "").lower()
    view = client.get(f"/api/auth/device/{sloppy}", headers=auth_headers)
    assert view.status_code == 200
    assert view.json()["client_name"] == "laptop"


def test_approving_needs_a_signed_in_person(client, test_user, auth_headers):
    body = start(client)
    code = body["user_code"]
    assert client.post(f"/api/auth/device/{code}/approve").status_code in (401, 403)

    # An API key must not be able to approve a login: that would let a leaked
    # key mint itself a fresh one, the same rule as POST /api-keys.
    _, raw_key = ApiKey.create_key(user=test_user, name="agent")
    refused = client.post(
        f"/api/auth/device/{code}/approve", headers={"X-API-Key": raw_key}
    )
    assert refused.status_code == 403
    assert DeviceLogin.get().status == "pending"


def test_a_decided_code_cannot_be_decided_again(client, test_user, auth_headers):
    body = start(client)
    code = body["user_code"]
    client.post(f"/api/auth/device/{code}/deny", headers=auth_headers)
    again = client.post(f"/api/auth/device/{code}/approve", headers=auth_headers)
    assert again.status_code == 409


def test_unknown_codes(client, test_user, auth_headers):
    assert poll(client, "nope").json()["error"] == "invalid_grant"
    view = client.get("/api/auth/device/BBBB-BBBB", headers=auth_headers)
    assert view.status_code == 404


def test_start_clears_logins_long_expired(client, db_session):
    start(client)
    DeviceLogin.update(
        expires_at=datetime.now(timezone.utc) - timedelta(days=2)
    ).execute()
    start(client)
    assert DeviceLogin.select().count() == 1
