"""The public pages' <head>, robots.txt and sitemap.xml (backend/pages.py).

Run against the real frontend/index.html and the real docs/, so a change to
how either is written that the rewriting no longer matches fails here, rather
than quietly shipping the generic title on every page again.
"""

import html as html_lib
import json
import os
import re
import shutil
import xml.etree.ElementTree as ET

import pytest
from fastapi.testclient import TestClient

from backend import main, pages
from backend.main import app

FRONTEND = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
INDEX_HTML = os.path.join(FRONTEND, "index.html")
BASE = "http://testserver"

# The same cases are in frontend/src/lib/pageTitle.test.js: the browser and the
# server title a docs page by one rule.
DOC_TITLE_CASES = [
    ("# Quick Start\n\nGet going.", "Quick Start — pkanban docs"),
    ("# pkanban Documentation\n", "pkanban Documentation"),
    ("intro\n# `pkanban card` *commands*\n", "pkanban card commands"),
    ("# See [the reference](/docs/reference)\n", "See the reference — pkanban docs"),
    ("no heading here\n## only a subheading\n", None),
]


@pytest.fixture
def client(tmp_path, monkeypatch, db_session):
    shutil.copy(INDEX_HTML, tmp_path / "index.html")
    monkeypatch.setattr(main, "STATIC_PATH", str(tmp_path))
    return TestClient(app)


def meta(html, attr, name):
    match = re.search(rf'<meta\s+{attr}="{re.escape(name)}"\s+content="([^"]*)"', html)
    return html_lib.unescape(match.group(1)) if match else None


def title(html):
    return html_lib.unescape(re.search(r"<title>(.*?)</title>", html, re.S).group(1))


def embedded_titles(html):
    match = re.search(r'<script type="application/json" id="page-titles">(.*?)</script>', html)
    return json.loads(match.group(1))


# --- Listed pages ----------------------------------------------------------


@pytest.mark.parametrize("path", list(pages.PAGES))
def test_every_listed_page_has_its_own_head(client, path):
    page = pages.PAGES[path]
    html = client.get(path).text
    assert title(html) == page["title"]
    assert meta(html, "name", "description") == page["description"]
    assert meta(html, "property", "og:title") == page["title"]
    assert meta(html, "property", "og:description") == page["description"]
    assert meta(html, "property", "og:url") == f"{BASE}{path}"
    assert meta(html, "name", "twitter:title") == page["title"]
    assert meta(html, "name", "twitter:description") == page["description"]
    assert f'<link rel="canonical" href="{BASE}{path}" />' in html
    # Still the app: the element it renders into is untouched.
    assert '<div id="app"></div>' in html


def test_a_trailing_slash_gets_the_same_head(client):
    html = client.get("/connect/claude/").text
    assert title(html) == pages.PAGES["/connect/claude"]["title"]
    assert f'href="{BASE}/connect/claude"' in html


def test_other_pages_keep_the_default_head(client):
    html = client.get("/boards").text
    assert title(html).startswith("pkanban — A CLI-first Kanban board")
    assert 'rel="canonical"' not in html


def test_every_page_carries_the_titles_for_in_app_navigation(client):
    titles = embedded_titles(client.get("/boards").text)
    assert titles["pages"] == {path: page["title"] for path, page in pages.PAGES.items()}
    assert titles["default"].startswith("pkanban — A CLI-first Kanban board")


def test_values_are_escaped():
    html = pages.page_html(
        "<head><title>x</title></head>", "/connect/claude", 'http://h"ost'
    )
    assert 'href="http://h&quot;ost/connect/claude"' in html


def test_embedded_titles_cannot_close_the_script(monkeypatch):
    monkeypatch.setitem(pages.PAGES, "/x", {"title": "</script><b>", "description": "d"})
    html = pages.page_html("<head><title>t</title></head>", "/boards", BASE)
    assert "</script><b>" not in html
    assert embedded_titles(html)["pages"]["/x"] == "</script><b>"


def test_every_listed_page_has_a_route_in_the_app():
    # A path here with no route in App.svelte would serve a custom title over
    # the app's not-found page.
    with open(os.path.join(FRONTEND, "src", "App.svelte"), encoding="utf-8") as f:
        app_svelte = f.read()
    for path in pages.PAGES:
        assert f'<Route path="{path}"' in app_svelte, path


# --- Docs pages ------------------------------------------------------------


@pytest.mark.parametrize("markdown,expected", DOC_TITLE_CASES)
def test_doc_title(markdown, expected):
    assert pages.doc_title(markdown) == expected


@pytest.mark.parametrize(
    "path,file",
    [
        ("/docs", "docs.md"),
        ("/docs/quickstart", "quickstart.md"),
        ("/docs/commands/card", os.path.join("commands", "card.md")),
    ],
)
def test_docs_pages_are_titled_by_their_markdown(client, path, file):
    with open(os.path.join(pages.DOCS_PATH, file), encoding="utf-8") as f:
        expected = pages.doc_title(f.read())
    html = client.get(path).text
    assert title(html) == expected
    description = meta(html, "name", "description")
    assert description and len(description) <= pages.DESCRIPTION_LIMIT
    assert "](" not in description and "`" not in description


@pytest.mark.parametrize("path", ["/docs/nope", "/docs/..%2f..%2fREADME", "/docs/a/b"])
def test_unknown_docs_paths_keep_the_default_head(client, path):
    html = client.get(path).text
    assert title(html).startswith("pkanban — A CLI-first Kanban board")


# --- robots.txt and sitemap.xml --------------------------------------------


def test_robots_txt(client):
    body = client.get("/robots.txt").text
    assert "User-agent: *" in body
    assert "Disallow: /api/" in body
    assert f"Sitemap: {BASE}/sitemap.xml" in body


def test_sitemap_lists_the_public_pages(client):
    response = client.get("/sitemap.xml")
    assert response.headers["content-type"].startswith("application/xml")
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [e.text for e in ET.fromstring(response.content).findall("s:url/s:loc", ns)]
    for path in pages.PAGES:
        assert f"{BASE}{path}" in locs
    assert f"{BASE}/docs/quickstart" in locs
    assert f"{BASE}/docs/commands/card" in locs
    assert not any("/boards" in loc or "/api/" in loc for loc in locs)


def test_sitemap_names_this_server(db_session):
    with TestClient(app, base_url="https://kanban.example.org") as c:
        assert "<loc>https://kanban.example.org/pricing</loc>" in c.get("/sitemap.xml").text
