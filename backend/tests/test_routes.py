"""
Test to verify that FastAPI docs are at /api/docs and /docs is free for frontend
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_api_docs_route_exists(client):
    """Verify that FastAPI docs are available at /api/docs"""
    response = client.get("/api/docs")
    # Should return HTML for Swagger UI
    assert response.status_code == 200
    assert (
        "swagger" in response.text.lower()
        or "api documentation" in response.text.lower()
    )


def test_api_redoc_route_exists(client):
    """Verify that ReDoc is available at /api/redoc"""
    response = client.get("/api/redoc")
    # Should return HTML for ReDoc
    assert response.status_code == 200
    assert "redoc" in response.text.lower()


def test_api_openapi_json_exists(client):
    """Verify that OpenAPI schema is available at /api/openapi.json"""
    response = client.get("/api/openapi.json")
    # Should return JSON schema
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    data = response.json()
    assert "openapi" in data
    assert "paths" in data


def test_docs_route_falls_through_to_spa(client):
    """Verify that /docs falls through to SPA (not handled by FastAPI docs)"""
    response = client.get("/docs")
    # Should fall through to catch-all which returns index.html or API message
    # Importantly, it should NOT be the FastAPI Swagger UI
    assert response.status_code == 200
    # If static files exist, we get HTML; otherwise we get the API message
    # Either way, it's NOT the Swagger UI
    assert "swagger" not in response.text.lower()
    # If we have the built frontend, it should contain the app
    if "<!DOCTYPE html" in response.text or "<html" in response.text:
        # It's serving index.html - good!
        assert True
    else:
        # It's the API message - also fine for testing
        assert (
            "pkanban API is running" in response.text or "docs" in response.text.lower()
        )


def test_api_routes_still_work(client, test_user):
    """Verify that regular API routes still work after the change"""
    from backend.auth import create_access_token

    token = create_access_token(
        data={"sub": test_user.id, "username": test_user.username}
    )
    headers = {"Authorization": f"Bearer {token}"}

    # Test getting boards
    response = client.get("/api/boards", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_health_endpoint_reports_ok(client, db_session):
    """The deploy pipeline gates on this response body."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_endpoint_is_public(client, db_session):
    """No auth: the deploy check has no credentials."""
    response = client.get("/api/health", headers={})
    assert response.status_code == 200


def test_health_is_a_real_route(client, db_session):
    """Regression guard for the check that could never fail.

    The deploy curled /api/health for a long time before the route existed.
    Unmatched /api/ paths answered 200 with the SPA's index.html back then, so
    the check passed on nothing at all; main.py 404s them now, but the deploy
    also accepted 404, so it still passed on nothing. Either way a missing
    route read as healthy. If this one is ever removed, fail here rather than
    let a deploy go green over it.
    """
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"status": "ok"}


def test_health_reports_503_when_the_database_is_broken(client, db_session, monkeypatch):
    """A schema or connection failure must surface, not be swallowed.

    This is the case the old check missed entirely: an unmigrated database
    500s every real request while static files keep serving fine.
    """
    from backend.models import User

    def boom(*args, **kwargs):
        raise Exception("no such column: t1.email_verified")

    monkeypatch.setattr(User, "select", boom)

    response = client.get("/api/health")
    assert response.status_code == 503
    assert "Database unavailable" in response.json()["detail"]


def test_health_query_names_every_user_column(client, db_session, monkeypatch):
    """The health query must select real columns, not just count rows.

    Regression guard with history: this endpoint originally used
    User.select().limit(1).count(), which peewee compiles to
    SELECT COUNT(1) FROM (SELECT 1 FROM user LIMIT 1). That names no model
    columns, so it returned 200 against an unmigrated copy of production
    while /api/token was dying on "no such column: t1.email_verified" --
    the endpoint reproduced the exact blind spot it exists to close.

    Simulated by failing any statement that mentions the newest column. A
    query that does not reference it never trips this and the assertion below
    fails, which is the point.
    """
    from backend.database import db

    original = db.execute_sql

    def fail_on_new_column(sql, *args, **kwargs):
        if "email_verified" in str(sql):
            raise Exception("no such column: t1.email_verified")
        return original(sql, *args, **kwargs)

    monkeypatch.setattr(db, "execute_sql", fail_on_new_column)

    response = client.get("/api/health")
    assert response.status_code == 503, (
        "health passed without ever selecting email_verified -- it would not "
        "notice an unmigrated database"
    )
