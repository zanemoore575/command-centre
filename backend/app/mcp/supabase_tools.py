"""
MCP tool implementations that query Supabase directly.
Uses the REST API via httpx so there's no ORM dependency.
"""

import os
import httpx
from typing import Optional

_SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
_SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")


def _headers() -> dict:
    return {
        "apikey": _SUPABASE_KEY,
        "Authorization": f"Bearer {_SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def _rest(path: str, params: dict = None) -> list:
    """GET from Supabase REST API."""
    url = f"{_SUPABASE_URL}/rest/v1/{path}"
    with httpx.Client(timeout=10) as client:
        r = client.get(url, headers=_headers(), params=params or {})
        r.raise_for_status()
        return r.json()


def _rpc(fn: str, body: dict = None) -> list:
    """Call a Supabase RPC function."""
    url = f"{_SUPABASE_URL}/rest/v1/rpc/{fn}"
    with httpx.Client(timeout=10) as client:
        r = client.post(url, headers=_headers(), json=body or {})
        r.raise_for_status()
        return r.json()


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def tool_get_recent_memories(limit: int = 10, source: Optional[str] = None) -> list[dict]:
    """Get the most recent completed memories."""
    result = _rpc("agent_get_recent_memories", {
        "limit_count": min(limit, 30),
        "filter_source": source,
    })
    return result if isinstance(result, list) else []


def tool_search_memories(query: str, limit: int = 8) -> list[dict]:
    """
    Keyword search across memory titles, summaries, and transcripts.
    Returns memories ranked by relevance.
    """
    result = _rpc("agent_search_by_theme", {
        "theme_keywords": query,
        "limit_count": min(limit, 20),
    })
    return result if isinstance(result, list) else []


def tool_get_memory(memory_id: int) -> dict | None:
    """Get the full content of a specific memory including all extracted entities."""
    result = _rpc("agent_get_memory_context", {"target_memory_id": memory_id})
    if isinstance(result, list) and result:
        return result[0]
    return None


def tool_search_entities(name: str) -> list[dict]:
    """Search for people, companies, projects, or tools by name."""
    result = _rpc("agent_get_entity_details", {"search_name": name})
    return result if isinstance(result, list) else []


def tool_get_decisions(topic: Optional[str] = None, days: int = 365) -> list[dict]:
    """Get past decisions, optionally filtered by topic."""
    result = _rpc("agent_get_decisions", {
        "search_topic": topic,
        "recent_days": days,
    })
    return result if isinstance(result, list) else []


def tool_get_tasks(status: str = "open") -> list[dict]:
    """Get tasks/action items. Status: 'open', 'completed', or 'all'."""
    result = _rpc("agent_get_tasks", {"task_status": status})
    return result if isinstance(result, list) else []


def tool_get_insights(category: Optional[str] = None, days: int = 365) -> list[dict]:
    """Get strategic insights, optionally filtered by category."""
    result = _rpc("agent_get_strategic_insights", {
        "search_category": category,
        "recent_days": days,
    })
    return result if isinstance(result, list) else []


def tool_get_customer_insights(customer: Optional[str] = None) -> list[dict]:
    """Get customer pain points, desires, and quotes."""
    result = _rpc("agent_get_customer_insights", {"search_customer": customer})
    return result if isinstance(result, list) else []


def tool_get_reflections(topic: Optional[str] = None, days: int = 365) -> list[dict]:
    """Get personal reflections and breakthroughs."""
    result = _rpc("agent_get_reflections", {
        "search_topic": topic,
        "recent_days": days,
    })
    return result if isinstance(result, list) else []


def tool_discover_database() -> list[dict]:
    """
    Returns an overview of all data in the system: entity names, decision categories,
    themes, customer names, and stats. Use this first when unsure what data exists.
    """
    result = _rpc("agent_discover_database", {})
    return result if isinstance(result, list) else []


def tool_complete_task(task_id: str) -> dict:
    """Mark a task as completed."""
    result = _rpc("agent_complete_task", {"target_task_id": task_id})
    if isinstance(result, list) and result:
        return result[0]
    return {}


def tool_update_task(
    task_id: str,
    task: Optional[str] = None,
    urgency: Optional[str] = None,
    priority: Optional[str] = None,
    due_date: Optional[str] = None,
    category: Optional[str] = None,
) -> dict:
    """Edit an existing task's text, urgency, priority, due date, or category."""
    result = _rpc("agent_update_task", {
        "target_task_id": task_id,
        "new_task": task,
        "new_urgency": urgency,
        "new_priority": priority,
        "new_due_date": due_date,
        "new_category": category,
    })
    if isinstance(result, list) and result:
        return result[0]
    return {}


def tool_create_task(
    task: str,
    context: Optional[str] = None,
    urgency: str = "soon",
    category: Optional[str] = None,
    due_date: Optional[str] = None,
    entity_name: Optional[str] = None,
) -> dict:
    """Create a new task directly (not extracted from a memory)."""
    result = _rpc("agent_create_task", {
        "new_task": task,
        "new_context": context,
        "new_urgency": urgency,
        "new_category": category,
        "new_due_date": due_date,
        "new_entity_name": entity_name,
    })
    if isinstance(result, list) and result:
        return result[0]
    return {}


def tool_merge_tasks(keep_id: str, merge_ids: list[str]) -> dict:
    """Fold near-duplicate tasks into one, keeping the earliest created_at and any due_date."""
    result = _rpc("agent_merge_tasks", {
        "keep_task_id": keep_id,
        "merge_task_ids": merge_ids,
    })
    if isinstance(result, list) and result:
        return result[0]
    return {}


def tool_log_memory(transcript: str, source: str = "claude_conversation") -> dict:
    """
    Save a new memory (conversation or note) to the database with status 'pending'.
    n8n's ingest pipeline will pick it up and extract entities automatically.
    """
    url = f"{_SUPABASE_URL}/rest/v1/memories"
    body = {
        "transcript": transcript,
        "source": source,
        "status": "pending",
    }
    with httpx.Client(timeout=10) as client:
        r = client.post(
            url,
            headers={**_headers(), "Prefer": "return=representation"},
            json=body,
        )
        r.raise_for_status()
        rows = r.json()
        return rows[0] if rows else {}
