"""Pages served with their own <head> (backend/pages.py).

Run against the real frontend/index.html, so a change to how it writes its
<meta> tags that the rewriting no longer matches fails here, rather than
quietly shipping the generic title on every page again.
"""

import os
import shutil

import pytest
from fastapi.testclient import TestClient

from backend import main, pages
from backend.main import app

INDEX_HTML = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "index.html")
CLAUDE = pages.PAGES["/connect/claude"]


@pytest.fixture
def client(tmp_path, monkeypatch, db_session):
    shutil.copy(INDEX_HTML, tmp_path / "index.html")
    monkeypatch.setattr(main, "STATIC_PATH", str(tmp_path))
    return TestClient(app)


def meta(html, attr, name):
    import re

    match = re.search(rf'<meta\s+{attr}="{re.escape(name)}"\s+content="([^"]*)"', html)
    return match.group(1) if match else None


def test_connect_claude_has_its_own_head(client):
    html = client.get("/connect/claude").text
    assert f"<title>{CLAUDE['title']}</title>" in html
    assert meta(html, "name", "description") == CLAUDE["description"]
    assert meta(html, "property", "og:title") == CLAUDE["title"]
    assert meta(html, "property", "og:description") == CLAUDE["description"]
    assert meta(html, "property", "og:url") == "http://testserver/connect/claude"
    assert meta(html, "name", "twitter:title") == CLAUDE["title"]
    assert '<link rel="canonical" href="http://testserver/connect/claude" />' in html
    # Still the app: the script that renders the page is untouched.
    assert '<div id="app"></div>' in html


def test_a_trailing_slash_gets_the_same_head(client):
    assert f"<title>{CLAUDE['title']}</title>" in client.get("/connect/claude/").text


def test_other_pages_keep_the_default_head(client):
    html = client.get("/pricing").text
    assert "<title>pkanban — A CLI-first Kanban board" in html
    assert 'rel="canonical"' not in html


def test_values_are_escaped():
    html = pages.page_html(
        "<head><title>x</title></head>", "/connect/claude", 'http://h"ost'
    )
    assert 'href="http://h&quot;ost/connect/claude"' in html


def test_every_listed_page_has_a_route_in_the_app():
    # A path here with no route in App.svelte would serve a custom title over
    # the app's not-found page.
    with open(
        os.path.join(os.path.dirname(INDEX_HTML), "src", "App.svelte"), encoding="utf-8"
    ) as f:
        app_svelte = f.read()
    for path in pages.PAGES:
        assert f'<Route path="{path}"' in app_svelte, path
