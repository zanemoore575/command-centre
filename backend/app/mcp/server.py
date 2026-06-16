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
    tool_complete_task,
    tool_update_task,
    tool_create_task,
    tool_merge_tasks,
    tool_save_artifact,
    tool_search_artifacts,
    tool_get_artifact,
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


@mcp.tool()
def complete_task(task_id: str) -> dict:
    """
    Mark a task as completed and stamp completed_at.

    Args:
        task_id: The task's UUID, from get_tasks.
    """
    return tool_complete_task(task_id=task_id)


@mcp.tool()
def update_task(
    task_id: str,
    task: Optional[str] = None,
    urgency: Optional[str] = None,
    priority: Optional[str] = None,
    due_date: Optional[str] = None,
    category: Optional[str] = None,
) -> dict:
    """
    Edit an existing task. Only the fields you pass are changed; everything
    else is left as-is.

    Args:
        task_id: The task's UUID, from get_tasks.
        task: New task text.
        urgency: 'immediate', 'this_week', 'soon', or 'someday'.
        priority: 'high', 'medium', or 'low'.
        due_date: ISO date string (YYYY-MM-DD).
        category: e.g. 'build', 'outreach', 'research', 'content', 'personal', 'follow_up'.
    """
    return tool_update_task(
        task_id=task_id,
        task=task,
        urgency=urgency,
        priority=priority,
        due_date=due_date,
        category=category,
    )


@mcp.tool()
def create_task(
    task: str,
    context: Optional[str] = None,
    urgency: str = "soon",
    category: Optional[str] = None,
    due_date: Optional[str] = None,
    entity_name: Optional[str] = None,
) -> dict:
    """
    Create a new task directly from a Claude.ai chat (not extracted from a memory).

    Args:
        task: Clear, actionable task description.
        context: Why this task matters.
        urgency: 'immediate', 'this_week', 'soon' (default), or 'someday'.
        category: e.g. 'build', 'outreach', 'research', 'content', 'personal', 'follow_up'.
        due_date: ISO date string (YYYY-MM-DD), if known.
        entity_name: Person/company/project this task relates to, e.g. 'Jake'.
    """
    return tool_create_task(
        task=task,
        context=context,
        urgency=urgency,
        category=category,
        due_date=due_date,
        entity_name=entity_name,
    )


@mcp.tool()
def merge_tasks(keep_id: str, merge_ids: list[str]) -> dict:
    """
    Fold near-duplicate tasks into one. The kept task preserves the earliest
    created_at and any due_date across the merged set; the others are marked
    'merged' (no longer open).

    Args:
        keep_id: UUID of the task to keep.
        merge_ids: UUIDs of the duplicate tasks to fold into keep_id.
    """
    return tool_merge_tasks(keep_id=keep_id, merge_ids=merge_ids)


@mcp.tool()
def save_artifact(
    title: str,
    kind: str = "authored",
    format: str = "md",
    content: Optional[str] = None,
    file_base64: Optional[str] = None,
    tags: Optional[list[str]] = None,
    entity_name: Optional[str] = None,
    artifact_id: Optional[str] = None,
) -> dict:
    """
    Save a document Zane and Claude worked on — a proposal, guide, schema, or
    any other deliverable — so it can be found and pulled back up in a later
    session, exactly as it was saved.

    Two kinds of artifact:
    - 'authored' (default): something Claude wrote/edited in this chat. Pass
      the full text as `content`. This is the canonical, editable version —
      recall it, edit it, and call save_artifact again with the same
      artifact_id to update it in place (e.g. after Zane requests changes).
    - 'uploaded': a real file Zane shared (e.g. a client's PDF). Pass the raw
      bytes base64-encoded as `file_base64`.

    To UPDATE an existing artifact (not create a duplicate), pass its
    artifact_id from a prior search_artifacts/get_artifact call. Without an
    artifact_id, this checks for an exact title+entity match first — if one
    exists, it returns that artifact's id instead of silently duplicating it.

    Args:
        title: Human-readable name, used to find this artifact again later.
        kind: 'authored' (Claude-made, default) or 'uploaded' (a real file).
        format: 'md', 'txt', 'pdf', or 'docx'.
        content: The canonical text content, for authored artifacts.
        file_base64: Base64-encoded file bytes, for uploaded/binary artifacts.
        tags: Free-text tags for topical search (e.g. ['proposal', 'pricing']).
        entity_name: Person/company/project this belongs to, e.g. 'Jake'.
        artifact_id: Pass this to overwrite an existing artifact in place.
    """
    return tool_save_artifact(
        title=title,
        kind=kind,
        format=format,
        content=content,
        file_base64=file_base64,
        tags=tags,
        entity_name=entity_name,
        artifact_id=artifact_id,
    )


@mcp.tool()
def search_artifacts(query: Optional[str] = None) -> list[dict]:
    """
    Find saved documents by title, tag, entity, or content. Use this when
    Zane references something he and Claude worked on before — a proposal,
    guide, or any other saved deliverable.

    Args:
        query: Search term (e.g. 'Jake proposal', 'Phase 1'). Omit to list recent artifacts.
    """
    return tool_search_artifacts(query=query)


@mcp.tool()
def get_artifact(artifact_id: str, include_file: bool = False) -> dict:
    """
    Get the full content of a saved artifact — exactly as it was last saved.
    Use this after search_artifacts to pull up the real text to read,
    discuss, or continue editing.

    Args:
        artifact_id: The artifact's UUID, from search_artifacts.
        include_file: Set true to also get the raw file bytes (base64) — only
            needed when Zane wants the literal original file back, not just its content.
    """
    return tool_get_artifact(artifact_id=artifact_id, include_file=include_file)


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
