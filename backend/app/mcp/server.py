"""
CAiS Command Centre — MCP Server with Google OAuth

Tools query Supabase directly (memories/entities schema written by n8n).
Auth: Google OAuth proxy (RFC 9728 AS + RS combined)
Transport: Streamable HTTP on port 8001

Run:
    cd backend
    python -m app.mcp.server

Dev curl (bypasses OAuth, localhost only):
    curl -s http://127.0.0.1:8001/mcp \\
      -H "Authorization: Bearer $MCP_DEV_TOKEN" \\
      -H "Content-Type: application/json" \\
      -H "Accept: application/json, text/event-stream" \\
      -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
"""

import os
import sys

# ---------------------------------------------------------------------------
# Bootstrap: load .env before any app imports
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(__file__)
_BACKEND_ROOT = os.path.abspath(os.path.join(_HERE, "../../.."))
sys.path.insert(0, _BACKEND_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_BACKEND_ROOT, "backend", ".env"))

_MCP_PUBLIC_URL = os.environ.get("MCP_PUBLIC_URL", "").rstrip("/")
_MCP_PORT = int(os.environ.get("PORT", os.environ.get("MCP_PORT", "8001")))
_MCP_HOST = os.environ.get("MCP_HOST", "0.0.0.0")
_GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
_GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
_ALLOWED_EMAIL = os.environ.get("MCP_ALLOWED_EMAIL", "")
_DEV_TOKEN = os.environ.get("MCP_DEV_TOKEN", "")
_SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
_SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

_missing = [k for k, v in {
    "MCP_PUBLIC_URL": _MCP_PUBLIC_URL,
    "GOOGLE_CLIENT_ID": _GOOGLE_CLIENT_ID,
    "GOOGLE_CLIENT_SECRET": _GOOGLE_CLIENT_SECRET,
    "MCP_ALLOWED_EMAIL": _ALLOWED_EMAIL,
    "SUPABASE_URL": _SUPABASE_URL,
    "SUPABASE_SERVICE_KEY": _SUPABASE_KEY,
}.items() if not v]
if _missing:
    raise RuntimeError(f"Missing required env vars: {', '.join(_missing)}")

# ---------------------------------------------------------------------------
# App imports
# ---------------------------------------------------------------------------

from typing import Optional

import uvicorn
from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import Response

from mcp.server.fastmcp import FastMCP
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
from mcp.server.transport_security import TransportSecuritySettings

from app.mcp.oauth_provider import GoogleOAuthProvider, google_callback as _google_callback
from app.mcp.supabase_tools import (
    tool_get_recent_memories,
    tool_search_memories,
    tool_get_memory,
    tool_search_entities,
    tool_get_decisions,
    tool_get_tasks,
    tool_get_insights,
    tool_get_customer_insights,
    tool_get_reflections,
    tool_discover_database,
    tool_log_memory,
)

# ---------------------------------------------------------------------------
# FastMCP server
# ---------------------------------------------------------------------------

_provider = GoogleOAuthProvider()

from urllib.parse import urlparse as _urlparse
_public_host = _urlparse(_MCP_PUBLIC_URL).netloc

_transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*", _public_host],
    allowed_origins=[
        "http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*",
        f"https://{_public_host}",
    ],
)

mcp = FastMCP(
    "CAiS Command Centre",
    stateless_http=True,
    json_response=True,
    host=_MCP_HOST,
    port=_MCP_PORT,
    streamable_http_path="/mcp",
    transport_security=_transport_security,
    auth_server_provider=_provider,
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(_MCP_PUBLIC_URL + "/"),
        resource_server_url=AnyHttpUrl(_MCP_PUBLIC_URL + "/mcp"),
        required_scopes=["mcp"],
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            valid_scopes=["mcp"],
            default_scopes=["mcp"],
        ),
        revocation_options=RevocationOptions(enabled=True),
    ),
)


# ---------------------------------------------------------------------------
# Google OAuth callback
# ---------------------------------------------------------------------------

@mcp.custom_route("/oauth/google/callback", methods=["GET"])
async def google_oauth_callback(request: Request) -> Response:
    return await _google_callback(request)


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> Response:
    return Response(content="ok", media_type="text/plain")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def discover_database() -> list[dict]:
    """
    Returns an overview of ALL data in the CAiS system: every person, company,
    project, and tool ever mentioned; decision categories; reflection topics;
    customer names; themes; and database statistics.

    Use this FIRST when you're unsure what data exists or when a specific search
    returns empty results — it tells you exactly what names and categories to
    search for.
    """
    return tool_discover_database()


@mcp.tool()
def get_recent_memories(limit: int = 10, source: Optional[str] = None) -> list[dict]:
    """
    Get the most recent completed memories (voice notes, conversations, imports).

    Args:
        limit: Number of memories to return (default 10, max 30).
        source: Optional filter — e.g. 'telegram_conversation', 'claude_conversation'.
    """
    return tool_get_recent_memories(limit=limit, source=source)


@mcp.tool()
def search_memories(query: str, limit: int = 8) -> list[dict]:
    """
    Search memories by keyword across titles, summaries, and themes.
    Returns memories ranked by relevance.

    Args:
        query: Search term (e.g. 'Jake', 'real estate', 'quoting').
        limit: Max results (default 8, max 20).
    """
    return tool_search_memories(query=query, limit=limit)


@mcp.tool()
def get_memory(memory_id: int) -> dict | None:
    """
    Get the full transcript and all extracted entities for a specific memory.
    Use this after search_memories or get_recent_memories to read the full content.

    Args:
        memory_id: The memory ID (integer) from a previous search result.
    """
    return tool_get_memory(memory_id=memory_id)


@mcp.tool()
def search_entities(name: str) -> list[dict]:
    """
    Find people, companies, projects, or tools by name. Returns all mentions
    with context and which memories they appear in.

    Args:
        name: Name to search for (partial match, e.g. 'Jake', 'Core Finance').
    """
    return tool_search_entities(name=name)


@mcp.tool()
def get_decisions(topic: Optional[str] = None, days: int = 365) -> list[dict]:
    """
    Get past decisions, optionally filtered by topic or recency.

    Args:
        topic: Keyword to filter decisions (e.g. 'pricing', 'tech stack').
        days: How far back to look (default 365).
    """
    return tool_get_decisions(topic=topic, days=days)


@mcp.tool()
def get_tasks(status: str = "open") -> list[dict]:
    """
    Get action items/tasks. Ordered by urgency (immediate → this_week → soon).

    Args:
        status: 'open' (default), 'completed', or 'all'.
    """
    return tool_get_tasks(status=status)


@mcp.tool()
def get_strategic_insights(category: Optional[str] = None, days: int = 365) -> list[dict]:
    """
    Get strategic business insights extracted from past conversations.

    Args:
        category: Filter by category (e.g. 'business_model', 'positioning', 'market_fit').
        days: How far back to look (default 365).
    """
    return tool_get_insights(category=category, days=days)


@mcp.tool()
def get_customer_insights(customer: Optional[str] = None) -> list[dict]:
    """
    Get customer pain points, desires, objections, and quotes.

    Args:
        customer: Filter by customer name (partial match, e.g. 'Aaron', 'Jake').
    """
    return tool_get_customer_insights(customer=customer)


@mcp.tool()
def get_reflections(topic: Optional[str] = None, days: int = 365) -> list[dict]:
    """
    Get personal reflections and breakthroughs from past conversations.

    Args:
        topic: Keyword to filter reflections (e.g. 'pricing', 'focus').
        days: How far back to look (default 365).
    """
    return tool_get_reflections(topic=topic, days=days)


@mcp.tool()
def log_memory(content: str) -> dict:
    """
    Save a new note or conversation to the CAiS database. The n8n ingest pipeline
    will automatically extract entities, decisions, tasks, and insights from it.

    Use this when Zane wants to log something directly from Claude — an idea,
    a meeting recap, a decision, or anything worth remembering.

    Args:
        content: The full text to save. Write it as a clear transcript or note.
    """
    return tool_log_memory(transcript=content, source="claude_conversation")


# ---------------------------------------------------------------------------
# Build final ASGI app
# ---------------------------------------------------------------------------

app = mcp.streamable_http_app()

if _DEV_TOKEN:
    print("[DEV] MCP_DEV_TOKEN active — local curl testing enabled (localhost only)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"CAiS MCP server")
    print(f"  Local:   http://{_MCP_HOST}:{_MCP_PORT}/mcp")
    print(f"  Public:  {_MCP_PUBLIC_URL}/mcp")
    print(f"  Supabase: {_SUPABASE_URL}")
    uvicorn.run(app, host=_MCP_HOST, port=_MCP_PORT, log_level="info")
