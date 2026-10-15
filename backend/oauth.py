"""OAuth sign-in for /mcp, so the chat apps can connect (Dev #969; plan in #900).

claude.ai, Claude Desktop and mobile, and ChatGPT connect to a remote MCP
server only through OAuth, per the MCP authorization spec. The flow:

1. /mcp answers 401, pointing at /.well-known/oauth-protected-resource/mcp,
   which names this server as the authorization server.
2. The app reads /.well-known/oauth-authorization-server and registers itself
   at /oauth/register (dynamic client registration, RFC 7591).
3. It sends the person's browser to /oauth/authorize, which lands them on the
   consent page in the web app (/oauth/consent).
4. Approving there issues a code and sends the browser back to the app, which
   trades the code and its PKCE verifier for a token at /oauth/token.

The token is a new API key, minted the way device login mints one. A connected
app therefore shows up in Settings > API keys and is disconnected by revoking
its key there, and /mcp needs nothing new to accept it.

The protocol work -- validating requests, redirect URIs, PKCE, client
authentication -- is the MCP SDK's handlers. This module is their storage, the
consent page's API, and the discovery documents. Those are built per request,
from the URL the request came in on, rather than with the SDK's metadata
routes, which bake in one issuer URL: a self-hosted server has to describe
itself, and needs nothing registered with Anthropic or OpenAI to be used.
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from mcp.server.auth.handlers.authorize import AuthorizationHandler
from mcp.server.auth.handlers.register import RegistrationHandler
from mcp.server.auth.handlers.token import TokenHandler
from mcp.server.auth.middleware.client_auth import ClientAuthenticator
from mcp.server.auth.provider import (
    AuthorizationCode,
    AuthorizationParams,
    RegistrationError,
    TokenError,
    construct_redirect_uri,
)
from mcp.server.auth.settings import ClientRegistrationOptions
from mcp.server.transport_security import RequestBodyLimitMiddleware
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import request_response

from backend.auth import get_current_user_by_session
from backend.database import db
from backend.models import (
    OAUTH_CODE_EXPIRY_MINUTES,
    OAUTH_REQUEST_EXPIRY_MINUTES,
    ApiKey,
    OAuthClient,
    OAuthGrant,
    User,
    _as_datetime,
    hash_api_key,
)

CONSENT_PATH = "/oauth/consent"
MCP_PATH = "/mcp"

# Registration and token requests are a few hundred bytes. The SDK's own routes
# allow 4 MiB; an unauthenticated endpoint has no reason to.
MAX_BODY_BYTES = 64 * 1024

# Schemes a browser runs or reads locally instead of leaving the page for. The
# consent page sends the browser to the app's redirect URI, so one of these
# would run as script on this site. Anything else is allowed: native apps
# register their own schemes (cursor://, vscode://), as RFC 8252 provides.
UNSAFE_SCHEMES = {"javascript", "data", "vbscript", "file", "blob", "about"}
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


def redirect_uri_problem(uri: str) -> Optional[str]:
    """Why `uri` cannot be a redirect URI, or None if it can."""
    parsed = urlparse(uri)
    scheme = parsed.scheme.lower()
    if not scheme or scheme in UNSAFE_SCHEMES:
        return f"{scheme or 'A scheme-less'}: URIs cannot be redirect URIs."
    if scheme == "http" and parsed.hostname not in LOOPBACK_HOSTS:
        return "A plain http redirect URI must point at this computer (localhost); use https."
    if parsed.fragment:
        return "A redirect URI cannot have a fragment."  # RFC 6749 3.1.2
    return None


def base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def resource_metadata_url(request: Request) -> str:
    """Where /mcp's 401 points: its protected-resource metadata (RFC 9728)."""
    return f"{base_url(request)}/.well-known/oauth-protected-resource{MCP_PATH}"


class Provider:
    """Storage for the SDK's OAuth handlers: clients, grants, and tokens.

    Refresh tokens are not issued. The access token is an API key, which does
    not expire; it lasts until it is revoked in Settings > API keys.
    """

    async def get_client(self, client_id: str) -> Optional[OAuthClientInformationFull]:
        row = OAuthClient.get_or_none(OAuthClient.client_id == client_id)
        if row is None:
            return None
        return OAuthClientInformationFull.model_validate_json(row.info)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        for uri in client_info.redirect_uris or []:
            problem = redirect_uri_problem(str(uri))
            if problem:
                raise RegistrationError("invalid_redirect_uri", problem)
        OAuthClient.prune_unused()
        OAuthClient.create(
            client_id=client_info.client_id,
            client_name=(client_info.client_name or "").strip()[:100] or "An MCP app",
            info=client_info.model_dump_json(),
            created_at=datetime.now(timezone.utc),
        )

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        """Hold the request and send the browser to the consent page.

        The page gets only the request id: everything it could otherwise
        tamper with -- the redirect URI, the PKCE challenge -- stays here.
        """
        now = datetime.now(timezone.utc)
        # Requests nobody finished are only clutter after a day; clearing them
        # here keeps the table bounded without a scheduled job. Used grants
        # stay, to recognize a code presented twice.
        OAuthGrant.delete().where(
            (OAuthGrant.status != "used") & (OAuthGrant.expires_at < now - timedelta(days=1))
        ).execute()
        grant = OAuthGrant.create(
            request_id=secrets.token_urlsafe(24),
            client=OAuthClient.get(OAuthClient.client_id == client.client_id),
            redirect_uri=str(params.redirect_uri),
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            code_challenge=params.code_challenge,
            state=params.state,
            scopes=" ".join(params.scopes or []),
            resource=params.resource,
            created_at=now,
            expires_at=now + timedelta(minutes=OAUTH_REQUEST_EXPIRY_MINUTES),
        )
        # Relative: Location may be, and the provider is never told the host.
        return f"{CONSENT_PATH}?request={grant.request_id}"

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> Optional[AuthorizationCode]:
        grant = OAuthGrant.get_or_none(
            OAuthGrant.code_sha256 == hash_api_key(authorization_code)
        )
        if grant is None or grant.client.client_id != client.client_id:
            return None
        if grant.status == "used":
            # A code presented twice has probably been stolen, and the token it
            # already bought may be in the wrong hands (RFC 6749 4.1.2).
            if grant.api_key_id:
                ApiKey.update(is_active=False).where(
                    ApiKey.id == grant.api_key_id
                ).execute()
            return None
        if grant.status != "approved":
            return None
        return AuthorizationCode(
            code=authorization_code,
            scopes=grant.scopes.split(),
            expires_at=_as_datetime(grant.expires_at).timestamp(),
            client_id=client.client_id,
            code_challenge=grant.code_challenge,
            redirect_uri=grant.redirect_uri,
            redirect_uri_provided_explicitly=grant.redirect_uri_provided_explicitly,
            resource=grant.resource,
            subject=str(grant.user_id),
        )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        digest = hash_api_key(authorization_code.code)
        with db.atomic():
            # Claimed by conditional update, so two exchanges racing on the same
            # code cannot both mint a key.
            claimed = (
                OAuthGrant.update(status="used")
                .where((OAuthGrant.code_sha256 == digest) & (OAuthGrant.status == "approved"))
                .execute()
            )
            if not claimed:
                raise TokenError("invalid_grant", "This code was already used.")
            grant = OAuthGrant.get(OAuthGrant.code_sha256 == digest)
            api_key, raw_key = ApiKey.create_key(
                user=grant.user, name=f"{grant.client.client_name} (connected app)"[:100]
            )
            OAuthGrant.update(api_key=api_key).where(OAuthGrant.id == grant.id).execute()
        return OAuthToken(
            access_token=raw_key,
            scope=" ".join(authorization_code.scopes) or None,
        )

    async def load_refresh_token(self, client, refresh_token):
        return None

    async def exchange_refresh_token(self, client, refresh_token, scopes):
        raise TokenError("invalid_grant", "This server does not issue refresh tokens.")

    async def load_access_token(self, token):
        # Unused: /mcp checks its key itself (mcp_server.McpEndpoint).
        return None

    async def revoke_token(self, token):
        # No revocation endpoint; keys are revoked in Settings > API keys.
        return None


provider = Provider()


async def protected_resource_metadata(request: Request) -> JSONResponse:
    """RFC 9728: what /mcp is, and who issues tokens for it (this server)."""
    base = base_url(request)
    return JSONResponse(
        {
            "resource": f"{base}{MCP_PATH}",
            "authorization_servers": [base],
            "bearer_methods_supported": ["header"],
            "resource_name": "pkanban",
        }
    )


async def authorization_server_metadata(request: Request) -> JSONResponse:
    """RFC 8414: where to register, send the person, and fetch the token."""
    base = base_url(request)
    return JSONResponse(
        {
            "issuer": base,
            "authorization_endpoint": f"{base}/oauth/authorize",
            "token_endpoint": f"{base}/oauth/token",
            "registration_endpoint": f"{base}/oauth/register",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": [
                "client_secret_post",
                "client_secret_basic",
                "none",
            ],
            "service_documentation": f"{base}/docs",
        }
    )


def _limited(handler):
    return RequestBodyLimitMiddleware(request_response(handler), MAX_BODY_BYTES)


def mount(app):
    """Serve discovery and the OAuth endpoints. Before the SPA catch-all."""
    registration = RegistrationHandler(provider, ClientRegistrationOptions(enabled=True))
    token = TokenHandler(provider, ClientAuthenticator(provider))
    for path in (
        # RFC 9728 puts the resource's path after the well-known name; some
        # clients look at the bare name first, so it answers too.
        f"/.well-known/oauth-protected-resource{MCP_PATH}",
        "/.well-known/oauth-protected-resource",
    ):
        app.add_route(path, protected_resource_metadata, methods=["GET"], include_in_schema=False)
    app.add_route(
        "/.well-known/oauth-authorization-server",
        authorization_server_metadata,
        methods=["GET"],
        include_in_schema=False,
    )
    app.add_route(
        "/oauth/authorize",
        AuthorizationHandler(provider).handle,
        methods=["GET", "POST"],
        include_in_schema=False,
    )
    app.add_route("/oauth/token", _limited(token.handle), methods=["POST"], include_in_schema=False)
    app.add_route(
        "/oauth/register", _limited(registration.handle), methods=["POST"], include_in_schema=False
    )


# --- The consent page's API ------------------------------------------------
#
# Session only, like device login's approval: an API key must not be able to
# approve a request for a new one.

router = APIRouter()


def _grant(request_id: str) -> OAuthGrant:
    grant = OAuthGrant.get_or_none(OAuthGrant.request_id == request_id)
    if grant is None:
        raise HTTPException(status_code=404, detail="No sign-in request with that id.")
    return grant


def _grant_view(grant: OAuthGrant) -> dict:
    redirect = urlparse(grant.redirect_uri)
    return {
        # Chosen by the app when it registered, so it is a claim, not a fact.
        "client_name": grant.client.client_name,
        # Where approving sends the browser, which is where the code goes.
        "redirect_host": redirect.netloc or f"{redirect.scheme}:",
        "status": "expired"
        if grant.status == "pending" and grant.is_expired()
        else grant.status,
        "created_at": grant.created_at,
        "expires_at": grant.expires_at,
    }


@router.get("/oauth/requests/{request_id}")
async def oauth_request_get(
    request_id: str, current_user: User = Depends(get_current_user_by_session)
):
    """What the consent page shows before the person decides."""
    return _grant_view(_grant(request_id))


def _decide(request_id: str, user: User, approve: bool) -> dict:
    grant = _grant(request_id)
    if grant.status == "pending" and grant.is_expired():
        raise HTTPException(
            status_code=410,
            detail="This sign-in request has expired. Start connecting again from the app.",
        )
    if grant.status != "pending":
        raise HTTPException(status_code=409, detail="This sign-in request was already decided.")
    # Checked at registration too; checked again here because this is the one
    # place the URI is handed to a browser.
    problem = redirect_uri_problem(grant.redirect_uri)
    if problem:
        raise HTTPException(status_code=400, detail=problem)

    now = datetime.now(timezone.utc)
    code = secrets.token_urlsafe(32) if approve else None
    changes = (
        {
            "status": "approved",
            "user": user,
            "code_sha256": hash_api_key(code),
            "expires_at": now + timedelta(minutes=OAUTH_CODE_EXPIRY_MINUTES),
        }
        if approve
        else {"status": "denied"}
    )
    with db.atomic():
        updated = (
            OAuthGrant.update(**changes)
            .where((OAuthGrant.id == grant.id) & (OAuthGrant.status == "pending"))
            .execute()
        )
        if not updated:
            raise HTTPException(status_code=409, detail="This sign-in request was already decided.")
        if approve:
            OAuthClient.update(authorized_at=now).where(
                (OAuthClient.id == grant.client_id) & OAuthClient.authorized_at.is_null()
            ).execute()

    if approve:
        redirect_to = construct_redirect_uri(grant.redirect_uri, code=code, state=grant.state)
    else:
        redirect_to = construct_redirect_uri(
            grant.redirect_uri,
            error="access_denied",
            error_description="The person declined to connect.",
            state=grant.state,
        )
    return {**_grant_view(OAuthGrant.get_by_id(grant.id)), "redirect_to": redirect_to}


@router.post("/oauth/requests/{request_id}/approve")
async def oauth_request_approve(
    request_id: str, current_user: User = Depends(get_current_user_by_session)
):
    """Approve: issue a code and say where to send the browser with it."""
    return _decide(request_id, current_user, approve=True)


@router.post("/oauth/requests/{request_id}/deny")
async def oauth_request_deny(
    request_id: str, current_user: User = Depends(get_current_user_by_session)
):
    return _decide(request_id, current_user, approve=False)
