# CAiS Command Centre — MCP Server

Remote MCP server exposing CAiS data to Claude (web, mobile, Projects, Desktop, Code).

**Auth:** Google OAuth 2.0 (PKCE, S256) — single-user allowlist  
**Transport:** Streamable HTTP (MCP spec 2025-03-26)  
**Hosting:** Render Web Service (always-on) — `https://cais-mcp-server.onrender.com`

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
                    CAiS MCP server, hosted on Render
                    https://cais-mcp-server.onrender.com
```

The server used to run on this Mac and was exposed via an ngrok tunnel. As of 2026-06-17 it's
deployed on Render as an always-on Web Service, so it runs independently of the Mac and works
from every Claude client, including mobile, with the Mac off. See "Production deployment (Render)"
below. The ngrok/local-tunnel workflow further down is kept only for local development.

---

## Production deployment (Render)

- **Repo:** `zanemoore575/cais-command-centre` (private, GitHub) — Render deploys from this.
- **Service type:** Web Service, Starter instance (not Free — avoids cold-start spin-down that
  would make the connector intermittently fail to load tools).
- **Root Directory:** `backend`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `python -m app.mcp.server`
- **Health check path:** `/health`
- **Python version:** pinned to 3.12 via `backend/runtime.txt` and the `PYTHON_VERSION` env var —
  newer Python defaults on Render didn't have a prebuilt wheel for `pydantic-core`.
- **Single instance only** — no autoscaling. OAuth/session state (`oauth_provider.py`) is kept
  in-memory per-process; multiple instances would fragment sessions.
- **Env vars** (set in Render dashboard → Environment, never committed):
  `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_CLIENT_ID`,
  `GOOGLE_CLIENT_SECRET`, `MCP_ALLOWED_EMAIL`, `MCP_PUBLIC_URL=https://cais-mcp-server.onrender.com`.
  Render injects `PORT` automatically — do not set `MCP_PORT` or `MCP_HOST`.
- **Google OAuth redirect URI:** `https://cais-mcp-server.onrender.com/oauth/google/callback` must
  be added to the OAuth client's Authorized redirect URIs in Google Cloud Console (in addition to
  the claude.ai/claude.com callback URIs in Step 2 below).
- **claude.ai connector:** points at `https://cais-mcp-server.onrender.com/mcp`.
- Auto-deploy is enabled — pushes to `main` redeploy automatically.

To verify the deployment is healthy:

```bash
curl -s https://cais-mcp-server.onrender.com/health                       # expect: ok
curl -s https://cais-mcp-server.onrender.com/.well-known/oauth-authorization-server
```

---

## Local development setup

The steps below (ngrok + `.env`) are for running the server locally during development. They are
not how the production connector is hosted anymore — see "Production deployment" above for that.

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
| HTTPS | Provided by Render in production; ngrok provides TLS termination for local dev |
| Always-on hosting | Render Web Service (Starter instance), independent of the Mac |
| Secrets | Set in Render's Environment tab only; `backend/.env` stays gitignored and is never committed |

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
