import requests

from pkanban.config import get_server_url, get_token, get_api_key, set_token

# Seconds before giving up on the server. Without this a hung or black-holed
# host makes the CLI wait forever with no output.
DEFAULT_TIMEOUT = 30

# Matches backend.auth.RENEWED_TOKEN_HEADER. Not imported from there: the CLI
# is published as a standalone package and does not ship the server.
RENEWED_TOKEN_HEADER = "X-Renewed-Token"


class PkanbanError(Exception):
    """A problem the user can act on, reported without a traceback."""


class PkanbanClient:
    def __init__(self, server_url=None, token=None, api_key=None):
        self.server_url = server_url or get_server_url()
        self.token = token or get_token()
        self.api_key = api_key or get_api_key()
        # A renewed token is written back to the config only if what we are
        # using is what the config holds. Compared by value rather than by
        # "was it passed in", because make_client() reads the config itself and
        # passes the token explicitly -- a token from somewhere else belongs to
        # its caller, and silently rewriting the user's config with it is the
        # bug --api-key already had.
        self._token_from_config = self.token is not None and self.token == get_token()
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({"X-API-Key": self.api_key})
        elif self.token:
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})

    def _request(self, method, path, **kwargs):
        url = f"{self.server_url.rstrip('/')}{path}"
        kwargs.setdefault("timeout", DEFAULT_TIMEOUT)

        try:
            response = self.session.request(method, url, **kwargs)
        except requests.exceptions.Timeout:
            raise PkanbanError(
                f"The server at {self.server_url} took too long to respond "
                f"(waited {DEFAULT_TIMEOUT}s). Try again shortly."
            )
        except requests.exceptions.SSLError as e:
            raise PkanbanError(f"Could not verify the TLS certificate for {self.server_url}: {e}")
        except (
            requests.exceptions.MissingSchema,
            requests.exceptions.InvalidSchema,
            requests.exceptions.InvalidURL,
        ):
            # e.g. "localhost:8000", which requests reads as scheme "localhost".
            raise PkanbanError(
                f"'{self.server_url}' is not a valid server URL - it needs an "
                f"http:// or https:// prefix.\n"
                f"Set one with: pkanban config --url https://pkanban.pearachute.com"
            )
        except requests.exceptions.ConnectionError:
            raise PkanbanError(
                f"Could not reach the pkanban server at {self.server_url}.\n"
                f"Check that the server is running and the URL is right "
                f"(see: pkanban config)."
            )

        self._store_renewed_token(response)

        # HTTPError is left alone: individual commands catch it to explain
        # domain-specific failures, and main() handles whatever they don't.
        response.raise_for_status()
        return response.json()

    def _store_renewed_token(self, response):
        """Save a replacement token the server offered.

        JWTs expire; the server hands back a fresh one on this header when the
        current one is close to its expiry, which is what keeps a CLI that gets
        used regularly from having to `pkanban login` every day. API-key auth
        never sees the header and is left alone.
        """
        if self.api_key or not self._token_from_config:
            return

        renewed = response.headers.get(RENEWED_TOKEN_HEADER)
        if not renewed or renewed == self.token:
            return

        self.token = renewed
        self.session.headers.update({"Authorization": f"Bearer {renewed}"})
        set_token(renewed)

    def login(self, username, password):
        data = self._request(
            "POST", "/api/token", json={"username": username, "password": password}
        )
        return data["access_token"]

    def boards(self):
        return self._request("GET", "/api/boards")

    def board_create(self, name):
        return self._request("POST", "/api/boards", json={"name": name})

    def board_get(self, board_id):
        return self._request("GET", f"/api/boards/{board_id}")

    def board_update(self, board_id, name):
        return self._request("POST", f"/api/boards/{board_id}", json={"name": name})

    def board_delete(self, board_id):
        return self._request("DELETE", f"/api/boards/{board_id}")

    def column_create(self, board_id, name, position=None):
        # position is left out entirely when omitted, so the server appends.
        data = {"board_id": board_id, "name": name}
        if position is not None:
            data["position"] = position
        return self._request("POST", "/api/columns", json=data)

    def column_update(self, column_id, name, position):
        return self._request(
            "PUT",
            f"/api/columns/{column_id}",
            json={"name": name, "position": position},
        )

    def column_delete(self, column_id):
        return self._request("DELETE", f"/api/columns/{column_id}")

    def card_get(self, card_id):
        return self._request("GET", f"/api/cards/{card_id}")

    def card_create(self, column_id, title, description=None, position=0):
        return self._request(
            "POST",
            "/api/cards",
            json={
                "column_id": column_id,
                "title": title,
                "description": description,
                "position": position,
            },
        )

    def card_update(
        self, card_id, title=None, description=None, position=None, column_id=None
    ):
        # Every field is omitted unless given: the endpoint leaves out what it
        # is not sent, so a move must not carry a title along with it.
        data = {}
        if title is not None:
            data["title"] = title
        if description is not None:
            data["description"] = description
        if position is not None:
            data["position"] = position
        if column_id is not None:
            data["column_id"] = column_id
        return self._request("PUT", f"/api/cards/{card_id}", json=data)

    def card_delete(self, card_id):
        return self._request("DELETE", f"/api/cards/{card_id}")

    # Organization methods
    def organizations(self):
        return self._request("GET", "/api/organizations")

    def organization_create(self, name):
        return self._request("POST", "/api/organizations", json={"name": name})

    def organization_get(self, org_id):
        return self._request("GET", f"/api/organizations/{org_id}")

    def organization_update(self, org_id, name):
        return self._request("PUT", f"/api/organizations/{org_id}", json={"name": name})

    def organization_members(self, org_id):
        return self._request("GET", f"/api/organizations/{org_id}/members")

    def organization_member_add(self, org_id, username):
        return self._request(
            "POST", f"/api/organizations/{org_id}/members", json={"username": username}
        )

    def organization_member_update(self, org_id, user_id, role):
        return self._request(
            "PUT", f"/api/organizations/{org_id}/members/{user_id}", json={"role": role}
        )

    def organization_member_remove(self, org_id, user_id):
        return self._request(
            "DELETE", f"/api/organizations/{org_id}/members/{user_id}"
        )

    # Invite methods
    def organization_invite_create(self, org_id, email=None):
        """Create an invite for an organization."""
        data = {}
        if email:
            data["email"] = email
        return self._request("POST", f"/api/organizations/{org_id}/invites", json=data)

    def organization_invites(self, org_id):
        """List pending invites for an organization."""
        return self._request("GET", f"/api/organizations/{org_id}/invites")

    def organization_invite_revoke(self, org_id, invite_id):
        """Revoke an invite."""
        return self._request(
            "DELETE", f"/api/organizations/{org_id}/invites/{invite_id}"
        )

    def invite_get(self, token):
        """Get invite details."""
        return self._request("GET", f"/api/invites/{token}")

    def invite_accept(self, token):
        """Accept an invite."""
        return self._request("POST", f"/api/invites/{token}/accept")

    # Team methods
    def organization_teams(self, org_id):
        return self._request("GET", f"/api/organizations/{org_id}/teams")

    def team_create(self, org_id, name):
        return self._request(
            "POST", f"/api/organizations/{org_id}/teams", json={"name": name}
        )

    def team_get(self, team_id):
        return self._request("GET", f"/api/teams/{team_id}")

    def team_update(self, team_id, name):
        return self._request("PUT", f"/api/teams/{team_id}", json={"name": name})

    def team_delete(self, team_id):
        return self._request("DELETE", f"/api/teams/{team_id}")

    def team_members(self, team_id):
        return self._request("GET", f"/api/teams/{team_id}/members")

    def team_member_add(self, team_id, username):
        return self._request(
            "POST", f"/api/teams/{team_id}/members", json={"username": username}
        )

    def team_member_remove(self, team_id, user_id):
        return self._request("DELETE", f"/api/teams/{team_id}/members/{user_id}")

    # Board sharing
    def board_share(
        self, board_id, team_id=None, is_public_to_org=False, organization_id=None
    ):
        data = {
            "team_id": team_id,
            "is_public_to_org": is_public_to_org,
            "organization_id": organization_id,
        }
        return self._request("POST", f"/api/boards/{board_id}/share", json=data)

    # API Key methods
    def api_keys(self):
        """List all API keys for the current user."""
        return self._request("GET", "/api/api-keys")

    def api_key_create(self, name, expires_at=None):
        """Create a new API key. Returns the key only once!"""
        data = {"name": name}
        if expires_at:
            data["expires_at"] = expires_at.isoformat()
        return self._request("POST", "/api/api-keys", json=data)

    def api_key_revoke(self, key_id):
        """Deactivate an API key."""
        return self._request("DELETE", f"/api/api-keys/{key_id}")

    def api_key_activate(self, key_id):
        """Reactivate a deactivated API key."""
        return self._request("POST", f"/api/api-keys/{key_id}/activate")
