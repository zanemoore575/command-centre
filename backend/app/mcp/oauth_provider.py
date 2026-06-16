"""
Google OAuth proxy provider for the CAiS MCP server.

Flow:
  1. Claude → /authorize (with PKCE, client_id, redirect_uri=claude.ai/…/auth_callback)
  2. We → redirect to Google OAuth
  3. Google → /oauth/google/callback (with code)
  4. We → exchange Google code for Google token, extract user email
  5. Single-user check: reject if not ALLOWED_EMAIL
  6. We → generate our own auth code, redirect to Claude's redirect_uri
  7. Claude → POST /token (with PKCE verifier, our auth code)
  8. We → issue our own access token + refresh token
  9. Claude → calls MCP tools with Bearer token
 10. We → validate token, check subject == ALLOWED_EMAIL, serve tool
"""

import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.parse
from typing import Any
from dataclasses import dataclass, field

import httpx
from pydantic import AnyUrl
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    TokenError,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

# ---------------------------------------------------------------------------
# Config (all read from env; loaded by server.py before this module imports)
# ---------------------------------------------------------------------------

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
ALLOWED_EMAIL = os.environ.get("MCP_ALLOWED_EMAIL", "")
PUBLIC_URL = os.environ.get("MCP_PUBLIC_URL", "")  # e.g. https://abc.ngrok-free.app
DEV_TOKEN = os.environ.get("MCP_DEV_TOKEN", "")    # local testing only

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

# Our tokens expire in 1 hour; refresh tokens in 30 days
ACCESS_TOKEN_TTL = 3600
REFRESH_TOKEN_TTL = 30 * 24 * 3600


# ---------------------------------------------------------------------------
# In-memory stores (single-user — process-local is fine)
# ---------------------------------------------------------------------------

@dataclass
class _PendingAuth:
    """State kept between /authorize and Google's callback."""
    client_id: str
    auth_params: AuthorizationParams  # original params from Claude
    google_state: str               # opaque value we sent to Google


# { our_state_token: _PendingAuth }
_pending: dict[str, _PendingAuth] = {}

# { code: AuthorizationCode }
_auth_codes: dict[str, AuthorizationCode] = {}

# { token_string: AccessToken }
_access_tokens: dict[str, AccessToken] = {}

# { token_string: RefreshToken }
_refresh_tokens: dict[str, RefreshToken] = {}

# { client_id: OAuthClientInformationFull }
_clients: dict[str, OAuthClientInformationFull] = {}


# ---------------------------------------------------------------------------
# Provider implementation
# ---------------------------------------------------------------------------

class GoogleOAuthProvider(
    OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]
):
    """
    MCP OAuthAuthorizationServerProvider that proxies user identity to Google.
    Maintains its own auth-code and token stores.
    """

    # -- Client registration -------------------------------------------------

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return _clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        if client_info.client_id is None:
            client_info = client_info.model_copy(
                update={"client_id": secrets.token_urlsafe(24)}
            )
        _clients[client_info.client_id] = client_info

    # -- Authorization -------------------------------------------------------

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        """Return Google's auth URL; stash state so we can complete the flow on callback."""
        our_state = secrets.token_urlsafe(32)
        google_state = secrets.token_urlsafe(32)

        _pending[our_state] = _PendingAuth(
            client_id=client.client_id,
            auth_params=params,
            google_state=google_state,
        )

        google_callback = f"{PUBLIC_URL}/oauth/google/callback"

        qs = urllib.parse.urlencode({
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": google_callback,
            "response_type": "code",
            "scope": "openid email",
            "state": f"{our_state}:{google_state}",
            "access_type": "online",
            "prompt": "select_account",
        })
        return f"{GOOGLE_AUTH_URL}?{qs}"

    # -- Auth code -----------------------------------------------------------

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        return _auth_codes.get(authorization_code)

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        if authorization_code.expires_at < time.time():
            raise TokenError("invalid_grant", "authorization code has expired")

        del _auth_codes[authorization_code.code]

        access_token_str = secrets.token_urlsafe(40)
        refresh_token_str = secrets.token_urlsafe(40)
        now = int(time.time())

        _access_tokens[access_token_str] = AccessToken(
            token=access_token_str,
            client_id=client.client_id,
            scopes=authorization_code.scopes or [],
            expires_at=now + ACCESS_TOKEN_TTL,
            subject=authorization_code.subject,
            claims={"iss": PUBLIC_URL},
        )
        _refresh_tokens[refresh_token_str] = RefreshToken(
            token=refresh_token_str,
            client_id=client.client_id,
            scopes=authorization_code.scopes or [],
            expires_at=now + REFRESH_TOKEN_TTL,
            subject=authorization_code.subject,
        )

        return OAuthToken(
            access_token=access_token_str,
            token_type="Bearer",
            expires_in=ACCESS_TOKEN_TTL,
            refresh_token=refresh_token_str,
            scope=" ".join(authorization_code.scopes or []),
        )

    # -- Refresh token -------------------------------------------------------

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        rt = _refresh_tokens.get(refresh_token)
        if rt and rt.client_id == client.client_id:
            return rt
        return None

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        # rotate both tokens
        del _refresh_tokens[refresh_token.token]
        # revoke all existing access tokens for this subject
        subject = refresh_token.subject
        for tok_str, tok in list(_access_tokens.items()):
            if tok.subject == subject:
                del _access_tokens[tok_str]

        access_token_str = secrets.token_urlsafe(40)
        refresh_token_str = secrets.token_urlsafe(40)
        now = int(time.time())
        use_scopes = scopes or refresh_token.scopes

        _access_tokens[access_token_str] = AccessToken(
            token=access_token_str,
            client_id=client.client_id,
            scopes=use_scopes,
            expires_at=now + ACCESS_TOKEN_TTL,
            subject=subject,
            claims={"iss": PUBLIC_URL},
        )
        _refresh_tokens[refresh_token_str] = RefreshToken(
            token=refresh_token_str,
            client_id=client.client_id,
            scopes=use_scopes,
            expires_at=now + REFRESH_TOKEN_TTL,
            subject=subject,
        )

        return OAuthToken(
            access_token=access_token_str,
            token_type="Bearer",
            expires_in=ACCESS_TOKEN_TTL,
            refresh_token=refresh_token_str,
            scope=" ".join(use_scopes),
        )

    # -- Access token (validation) ------------------------------------------

    async def load_access_token(self, token: str) -> AccessToken | None:
        # Dev token shortcut — localhost smoke-testing only, never expose publicly
        if DEV_TOKEN and token == DEV_TOKEN:
            return AccessToken(
                token=token,
                client_id="dev",
                scopes=["mcp"],
                expires_at=int(time.time()) + 3600,
                subject=ALLOWED_EMAIL,
                claims={"iss": PUBLIC_URL},
            )

        at = _access_tokens.get(token)
        if at is None:
            return None
        if at.expires_at and at.expires_at < int(time.time()):
            del _access_tokens[token]
            return None
        # Single-user allowlist: reject any token not belonging to the allowed identity
        if at.subject != ALLOWED_EMAIL:
            return None
        return at

    # -- Revocation ----------------------------------------------------------

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        if isinstance(token, AccessToken):
            _access_tokens.pop(token.token, None)
        else:
            _refresh_tokens.pop(token.token, None)


# ---------------------------------------------------------------------------
# Google callback handler (Starlette route handler)
# ---------------------------------------------------------------------------

async def google_callback(request: Request) -> Response:
    """
    Starlette handler for GET /oauth/google/callback.
    Exchanges the Google code for a Google token, verifies the user's email,
    enforces the single-user allowlist, then completes the MCP auth flow.
    """
    error = request.query_params.get("error")
    if error:
        return HTMLResponse(
            f"<h1>Authentication failed</h1><p>Google returned: {error}</p>",
            status_code=400,
        )

    raw_state = request.query_params.get("state", "")
    google_code = request.query_params.get("code", "")

    # Unpack our compound state
    if ":" not in raw_state:
        return HTMLResponse("<h1>Invalid state</h1>", status_code=400)
    our_state, google_state_received = raw_state.split(":", 1)

    pending = _pending.pop(our_state, None)
    if pending is None:
        return HTMLResponse("<h1>Unknown or expired state</h1>", status_code=400)
    if pending.google_state != google_state_received:
        return HTMLResponse("<h1>State mismatch — possible CSRF</h1>", status_code=400)

    google_callback_url = f"{PUBLIC_URL}/oauth/google/callback"

    # Exchange code with Google
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": google_code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": google_callback_url,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            return HTMLResponse(
                f"<h1>Token exchange failed</h1><pre>{token_resp.text}</pre>",
                status_code=502,
            )
        google_tokens = token_resp.json()

        # Get user email from Google
        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {google_tokens['access_token']}"},
        )
        if userinfo_resp.status_code != 200:
            return HTMLResponse("<h1>Could not fetch user info from Google</h1>", status_code=502)
        userinfo = userinfo_resp.json()

    email = userinfo.get("email", "")

    # Single-user allowlist
    if email.lower() != ALLOWED_EMAIL.lower():
        return HTMLResponse(
            "<h1>Access denied</h1>"
            "<p>This MCP server is private. Your Google account is not authorised.</p>",
            status_code=403,
        )

    # Issue our own auth code
    auth_code_str = secrets.token_urlsafe(32)
    params = pending.auth_params

    _auth_codes[auth_code_str] = AuthorizationCode(
        code=auth_code_str,
        scopes=params.scopes or ["mcp"],
        expires_at=time.time() + 300,  # 5 minutes
        client_id=pending.client_id,
        code_challenge=params.code_challenge,
        redirect_uri=params.redirect_uri,
        redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
        resource=params.resource,
        subject=email,
    )

    # Redirect back to Claude with our auth code
    redirect_params = {"code": auth_code_str}
    if params.state:
        redirect_params["state"] = params.state

    redirect_url = str(params.redirect_uri) + "?" + urllib.parse.urlencode(redirect_params)
    return RedirectResponse(url=redirect_url, status_code=302)
