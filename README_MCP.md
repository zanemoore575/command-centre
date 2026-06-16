# CAiS Command Centre — MCP Server

Remote MCP server exposing CAiS journal data to Claude (web, mobile, Projects, Desktop, Code).

**Auth:** Google OAuth 2.0 (PKCE, S256) — single-user allowlist  
**Transport:** Streamable HTTP (MCP spec 2025-03-26)  
**Phase 1 tool:** `search_journal_entries`

---

## Architecture

```
Claude app
    │  1. POST /mcp  (no token) → 401 + WWW-Authenticate: Bearer resource_metadata=…
    │  2. GET /.well-known/oauth-protected-resource/mcp  → AS URL
    │  3. GET /.well-known/oauth-authorization-server    → /authorize, /token, /register
    │  4. POST /register  → get client_id / client_secret
    │  5. GET /authorize  → redirect to Google
    │         └─ Google consent screen
    │  6. GET /oauth/google/callback  → single-user check → issue auth code
    │  7. POST /token  (PKCE exchange) → access token + refresh token
    │  8. POST /mcp  (Bearer token) → tool result
    └──────────────────────────────────────────────────────────────┘
                    CAiS MCP server (port 8001)
                    ngrok stable tunnel (HTTPS)
```

---

## Step 1 — Get a stable ngrok domain

You need a hostname that doesn't change on every restart. ngrok free plans give one reserved domain.

1. Go to **ngrok Dashboard → Cloud Edge → Domains**
2. Claim your free static domain (e.g. `your-name.ngrok-free.app`)
3. Note it — you'll use it everywhere below

---

## Step 2 — Register a Google OAuth app

1. Go to [Google Cloud Console → APIs & Services → Credentials](https://console.cloud.google.com/apis/credentials)
2. **Create credentials → OAuth 2.0 Client ID**
   - Application type: **Web application**
   - Name: `CAiS MCP Server` (or anything)
3. Add **Authorised redirect URIs** — add ALL of these:
   ```
   https://<your-ngrok-domain>/oauth/google/callback
   https://claude.ai/api/mcp/auth_callback
   https://claude.com/api/mcp/auth_callback
   ```
   > The first URI is where Google sends the code back to our server.
   > The claude.ai/claude.com URIs are where Claude's browser is redirected after our server
   > issues the MCP auth code — Claude's connector UI handles those.
   > Add both claude.ai and claude.com; the active one varies by client.
4. Copy the **Client ID** and **Client Secret**

> **OAuth consent screen:** Set to "External", add your own email as a test user.
> You do NOT need to publish the app — test mode is fine for personal use.

---

## Step 3 — Configure `.env`

Edit `backend/.env`:

```env
DATABASE_URL=sqlite:///./cais_command_center.db
ANTHROPIC_API_KEY=sk-ant-…

# MCP OAuth — fill these in
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
MCP_ALLOWED_EMAIL=zane.moore575@gmail.com
MCP_PUBLIC_URL=https://your-ngrok-domain.ngrok-free.app

# Optional: dev token for local curl testing (never expose via tunnel)
MCP_DEV_TOKEN=pick-any-random-string
```

> `MCP_PUBLIC_URL` must match your stable ngrok domain exactly, no trailing slash.

---

## Step 4 — Install dependencies

```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
```

---

## Step 5 — Start the MCP server

```bash
cd backend
source venv/bin/activate
python -m app.mcp.server
```

You should see:
```
CAiS MCP server
  Local:   http://127.0.0.1:8001/mcp
  Public:  https://your-ngrok-domain.ngrok-free.app/mcp
  AS meta: https://…/.well-known/oauth-authorization-server
  RS meta: https://…/.well-known/oauth-protected-resource/mcp
  Google callback: https://…/oauth/google/callback
```

---

## Step 6 — Start the tunnel

In a second terminal:

```bash
ngrok http --domain=your-ngrok-domain.ngrok-free.app 8001
```

> Keep this running while using the connector. Stop it when done — do not leave it up unattended.

---

## Step 7 — Verify locally (before touching Claude)

```bash
# AC1: unauthenticated → 401 with correct WWW-Authenticate header
curl -si https://your-ngrok-domain.ngrok-free.app/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | head -5

# Expected:
# HTTP/2 401
# www-authenticate: Bearer error="invalid_token", ..., resource_metadata="https://…"

# AC2: protected resource metadata
curl -s https://your-ngrok-domain.ngrok-free.app/.well-known/oauth-protected-resource/mcp

# AC2: AS discovery
curl -s https://your-ngrok-domain.ngrok-free.app/.well-known/oauth-authorization-server
```

---

## Step 8 — Add connector on claude.ai

1. Go to **claude.ai → Settings → Connectors → Add custom connector**
2. Enter your MCP URL: `https://your-ngrok-domain.ngrok-free.app/mcp`
3. Click **Advanced settings** — leave Client ID / Secret blank (the server supports dynamic registration, so Claude will register itself automatically)
4. Save → Claude will redirect to Google login
5. Sign in with **zane.moore575@gmail.com** (any other account gets a 403)
6. After consent, the connector shows as connected with `search_journal_entries` available

> If you see "Couldn't reach the MCP server": check the `www-authenticate` header is present (Step 7 above). That header is what Claude uses to discover the auth server — if it's missing, Claude can't proceed.

---

## Local dev testing (no OAuth dance)

While `MCP_DEV_TOKEN` is set in `.env`, you can curl the local server directly:

```bash
curl -s http://127.0.0.1:8001/mcp \
  -H "Authorization: Bearer local-dev-only-token" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

curl -s http://127.0.0.1:8001/mcp \
  -H "Authorization: Bearer local-dev-only-token" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"search_journal_entries","arguments":{"query":"meeting","limit":3}}}'
```

> The dev token is only accepted by `127.0.0.1:8001`, not through the tunnel (ngrok terminates TLS but the local server binds to 127.0.0.1 only, so external requests never reach the local port directly).

---

## Security notes

| Layer | Status |
|---|---|
| OAuth 2.0 + PKCE (S256) | Implemented |
| Single-user allowlist (email check) | Implemented — only `MCP_ALLOWED_EMAIL` is admitted |
| Tokens scoped to this server | Implemented via `mcp` scope |
| HTTPS via tunnel | Required — ngrok provides TLS termination |
| Tunnel not permanently running | Your responsibility — stop ngrok when not in use |

> **Before always-on hosting:** replace ngrok with a proper deployment (Fly.io, Railway, VPS) and front it with Cloudflare Access or a similar zero-trust gateway. The current setup is for development and personal use only.

---

## File layout

```
backend/
  app/
    mcp/
      __init__.py
      server.py          ← FastMCP server + Google OAuth integration
      oauth_provider.py  ← OAuthAuthorizationServerProvider implementation
  .env                   ← secrets (never commit)
  requirements.txt
README_MCP.md            ← this file
```
