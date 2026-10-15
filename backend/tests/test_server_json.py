"""server.json: the MCP registry listing (Dev #965).

The publish workflow (.github/workflows/publish-mcp-registry.yml) checks it
against the registry's schema when it runs, which is long after a careless
edit. These are the parts that would otherwise fail there, or list the wrong
thing.
"""

import json
import os

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")

with open(os.path.join(ROOT, "server.json"), encoding="utf-8") as f:
    SERVER = json.load(f)


def test_name_is_the_namespace_github_oidc_proves():
    # The workflow signs in as this repository's owner, which grants only
    # io.github.japherwocky/*.
    assert SERVER["name"] == "io.github.japherwocky/pkanban"


def test_lists_the_hosted_mcp_endpoint():
    assert SERVER["remotes"] == [
        {"type": "streamable-http", "url": "https://pkanban.pearachute.com/mcp"}
    ]


def test_fits_the_registrys_limits():
    # From the registry's server.schema.json (2025-12-11).
    assert 1 <= len(SERVER["description"]) <= 100
    assert 1 <= len(SERVER["title"]) <= 100


def test_mcp_endpoint_route_exists():
    # The listing points at /mcp; this is the route that serves it.
    from backend.mcp_server import McpEndpoint  # noqa: F401
    from backend.main import app

    assert any(getattr(route, "path", None) == "/mcp" for route in app.routes)
