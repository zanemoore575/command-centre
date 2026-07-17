"""
MCP tool implementations that query Supabase directly.
Uses the REST API via httpx so there's no ORM dependency.
"""

from __future__ import annotations

import base64
import os
import uuid
import httpx
from typing import Optional

_SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
_SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
_OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
_ARTIFACTS_BUCKET = "artifacts"


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


def _patch(path: str, body: dict, params: dict = None) -> list:
    """PATCH rows via the Supabase REST API; returns the updated rows."""
    url = f"{_SUPABASE_URL}/rest/v1/{path}"
    with httpx.Client(timeout=10) as client:
        r = client.patch(url, headers={**_headers(), "Prefer": "return=representation"},
                          params=params or {}, json=body)
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
    Hybrid recall: semantic (embedding) + keyword, unioned and re-ranked.

    Semantic (agent_search_memories_by_embedding) catches memories with no
    keyword overlap — the whole point of paying to embed every memory. Keyword
    (agent_search_by_theme) keeps exact-term precision. If embedding is
    unavailable (no OpenAI key, API error), degrades gracefully to keyword-only,
    i.e. the previous behaviour — so search never hard-fails.
    """
    cap = min(limit, 20)
    pool = max(cap * 2, 12)  # over-fetch each leg so the union has room to rank

    keyword = _rpc("agent_search_by_theme", {
        "theme_keywords": query,
        "limit_count": pool,
    })
    keyword = keyword if isinstance(keyword, list) else []

    # Semantic leg is best-effort — one embedding call, one RPC, both guarded.
    semantic: list[dict] = []
    try:
        embedding = _embed_text(query)
        if embedding is not None:
            semantic = _rpc("agent_search_memories_by_embedding", {
                "query_embedding": embedding,
                "match_threshold": 0.35,
                "match_count": pool,
            })
            semantic = semantic if isinstance(semantic, list) else []
    except Exception:
        semantic = []

    # Merge by memory_id, keeping whichever leg has the richer fields.
    merged: dict[int, dict] = {}
    for r in keyword:
        mid = r.get("memory_id")
        if mid is None:
            continue
        merged[mid] = {
            "memory_id": mid,
            "title": r.get("title"),
            "summary": r.get("summary"),
            "main_theme": r.get("main_theme"),
            "created_at": r.get("created_at"),
            "keyword_score": r.get("relevance_score") or 0,
            "similarity": None,
            "match_type": "keyword",
        }
    for r in semantic:
        mid = r.get("memory_id")
        if mid is None:
            continue
        row = merged.get(mid)
        if row is None:
            merged[mid] = {
                "memory_id": mid,
                "title": r.get("title"),
                "summary": r.get("summary"),
                "main_theme": r.get("main_theme"),
                "created_at": r.get("created_at"),
                "keyword_score": 0,
                "similarity": r.get("similarity"),
                "match_type": "semantic",
            }
        else:
            row["similarity"] = r.get("similarity")
            row["match_type"] = "both"
            row["summary"] = row.get("summary") or r.get("summary")
            row["main_theme"] = row.get("main_theme") or r.get("main_theme")

    # relevance_score maxes at 9 (3+2+2+1+1); normalise both legs to 0..1.
    def _rank(row: dict) -> float:
        sem = row.get("similarity") or 0.0
        kw = (row.get("keyword_score") or 0) / 9.0
        return 0.6 * sem + 0.4 * kw

    ranked = sorted(merged.values(), key=_rank, reverse=True)
    return ranked[:cap]


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


def _safe_list(fn) -> list:
    """Run a read that returns a list; swallow any error into []."""
    try:
        out = fn()
        return out if isinstance(out, list) else []
    except Exception:
        return []


def tool_get_context_brief(name: str) -> dict:
    """
    One-call pre-contact brief for a person/company/project. Resolves the entity
    (through canonical aliases) and composes everything you'd otherwise pull in
    five separate calls: current-truth topics, last-contact date, open tasks,
    recent memories, decisions, and customer insights touching them.
    """
    entity_rows = _safe_list(lambda: tool_search_entities(name))

    # Distinct canonicals this name resolved to (e.g. "Jake" -> "Jake Shirley").
    canonicals = sorted({r.get("canonical_name") for r in entity_rows if r.get("canonical_name")})

    # Memories where this entity appears — dedupe, newest first, last_contact = latest.
    seen: dict[int, dict] = {}
    for r in entity_rows:
        mid = r.get("memory_id")
        if mid is None or mid in seen:
            continue
        seen[mid] = {
            "memory_id": mid,
            "title": r.get("memory_title"),
            "date": r.get("memory_date"),
            "context": r.get("context"),
        }
    recent_memories = sorted(seen.values(), key=lambda m: m.get("date") or "", reverse=True)
    last_contact = recent_memories[0]["date"] if recent_memories else None

    # Open tasks touching this entity. No entity filter on agent_get_tasks, so
    # pull the open list and match client-side against name/text/context.
    nl = name.lower()
    all_open = _safe_list(lambda: tool_get_tasks(status="open", limit=200))
    open_tasks = [
        {
            "task_id": t.get("task_id"),
            "task": t.get("task_text"),
            "urgency": t.get("urgency"),
            "due_date": t.get("due_date"),
            "category": t.get("category"),
            "who": t.get("entity_name"),
        }
        for t in all_open
        if any(nl in (t.get(f) or "").lower() for f in ("entity_name", "task_text", "context"))
    ]

    current_state = _safe_list(lambda: tool_get_current_state(topic=name))
    decisions = _safe_list(lambda: tool_get_decisions(topic=name))
    customer_insights = _safe_list(lambda: tool_get_customer_insights(customer=name))

    return {
        "name": name,
        "canonical_names": canonicals,
        "last_contact": last_contact,
        "mention_count": len(entity_rows),
        "current_state": current_state,
        "open_tasks": open_tasks,
        "recent_memories": recent_memories[:5],
        "recent_decisions": decisions[:5],
        "customer_insights": customer_insights[:5],
    }


def tool_get_decisions(topic: Optional[str] = None, days: int = 365) -> list[dict]:
    """Get past decisions, optionally filtered by topic."""
    result = _rpc("agent_get_decisions", {
        "search_topic": topic,
        "recent_days": days,
    })
    return result if isinstance(result, list) else []


def tool_get_tasks(status: str = "open", limit: int = 50) -> list[dict]:
    """Get tasks. Status: 'open', 'suggested', 'snoozed', 'completed', 'archived', or 'all'."""
    try:
        result = _rpc("agent_get_tasks", {"task_status": status, "limit_count": min(limit, 200)})
    except httpx.HTTPStatusError:
        # pre-triage-migration signature (no limit_count)
        result = _rpc("agent_get_tasks", {"task_status": status})
    return result if isinstance(result, list) else []


def tool_archive_task(task_id: str) -> dict:
    """Dismiss a task — archived (preserved), out of every active view."""
    result = _rpc("agent_archive_task", {"target_task_id": task_id})
    if isinstance(result, list) and result:
        return result[0]
    return {}


def tool_promote_task(task_id: str) -> dict:
    """Promote a 'suggested' task to 'open' (or resurrect an archived one)."""
    result = _rpc("agent_promote_task", {"target_task_id": task_id})
    if isinstance(result, list) and result:
        return result[0]
    return {}


def tool_snooze_task(task_id: str, until: str) -> dict:
    """Hide an open task until a date (YYYY-MM-DD). It stays open, just out of view."""
    result = _rpc("agent_snooze_task", {"target_task_id": task_id, "until_date": until})
    if isinstance(result, list) and result:
        return result[0]
    return {}


def tool_get_current_state(topic: Optional[str] = None) -> list[dict]:
    """Get the current-truth layer: one canonical row per topic, most recently updated first."""
    result = _rpc("agent_get_current_state", {"search_topic": topic})
    return result if isinstance(result, list) else []


def tool_update_current_state(
    topic: str,
    statement: str,
    detail: Optional[str] = None,
    status: str = "active",
    source_memory_id: Optional[int] = None,
) -> dict:
    """
    Upsert the canonical answer for a topic. If the topic already exists and the
    statement/detail changed, the prior value is pushed into history before
    being overwritten — the topic always reflects the latest known truth.
    """
    result = _rpc("agent_update_current_state", {
        "p_topic": topic,
        "p_statement": statement,
        "p_detail": detail,
        "p_status": status,
        "p_source_memory_id": source_memory_id,
    })
    if isinstance(result, list) and result:
        return result[0]
    return {}


def tool_record_decision_outcome(decision_id: str, status: str, outcome_text: Optional[str] = None) -> dict:
    """Record what actually happened after a past decision — closes the outcome loop."""
    result = _rpc("agent_record_decision_outcome", {
        "target_decision_id": decision_id,
        "new_outcome_status": status,
        "new_outcome_text": outcome_text,
    })
    if isinstance(result, list) and result:
        return result[0]
    return {}


def tool_get_decisions_due_for_review(limit: int = 2) -> list[dict]:
    """Get pending decisions old enough (or explicitly scheduled) to review for outcome."""
    result = _rpc("agent_get_decisions_due_for_review", {"limit_count": min(limit, 10)})
    return result if isinstance(result, list) else []


def tool_get_entity_matches_due_for_review(limit: int = 3) -> list[dict]:
    """Get pending ambiguous entity matches awaiting confirm/reject."""
    result = _rpc("agent_get_entity_matches_due_for_review", {"limit_count": min(limit, 20)})
    return result if isinstance(result, list) else []


def tool_resolve_entity_match(match_id: str, action: str, note: Optional[str] = None) -> dict:
    """Confirm or reject an ambiguous entity match ('Jake' -> 'Jake Shirley'?)."""
    result = _rpc("agent_resolve_entity_match", {
        "match_id": match_id,
        "action": action,
        "new_note": note,
    })
    if isinstance(result, list) and result:
        return result[0]
    return {}


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


_FORMAT_MIME = {
    "md": "text/markdown",
    "txt": "text/plain",
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _embed_text(text: str) -> Optional[list[float]]:
    """Generate an embedding via OpenAI directly (same model n8n's pipeline uses)."""
    if not _OPENAI_API_KEY or not text:
        return None
    with httpx.Client(timeout=20) as client:
        r = client.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {_OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"model": "text-embedding-3-small", "input": text[:8000]},
        )
        r.raise_for_status()
        data = r.json()
        return data["data"][0]["embedding"]


def _upload_artifact_file(storage_path: str, file_bytes: bytes, format: str) -> None:
    """Upload (or overwrite) a binary file in the artifacts Storage bucket."""
    mime = _FORMAT_MIME.get(format, "application/octet-stream")
    url = f"{_SUPABASE_URL}/storage/v1/object/{_ARTIFACTS_BUCKET}/{storage_path}"
    with httpx.Client(timeout=30) as client:
        r = client.put(
            url,
            headers={
                "apikey": _SUPABASE_KEY,
                "Authorization": f"Bearer {_SUPABASE_KEY}",
                "Content-Type": mime,
            },
            content=file_bytes,
        )
        r.raise_for_status()


def _create_artifact_companion_memory(title: str, text: str, source: str = "artifact") -> Optional[int]:
    """
    Insert a 'completed' memory row with a direct embedding (no n8n extraction —
    artifacts skip the 7-way LLM extraction pipeline and only need to be searchable).
    """
    if not text:
        return None
    embedding = _embed_text(text)
    url = f"{_SUPABASE_URL}/rest/v1/memories"
    body = {
        "title": title,
        "transcript": text,
        "summary": text[:500],
        "source": source,
        "status": "completed",
    }
    if embedding is not None:
        body["embeddings"] = embedding
    with httpx.Client(timeout=15) as client:
        r = client.post(
            url,
            headers={**_headers(), "Prefer": "return=representation"},
            json=body,
        )
        r.raise_for_status()
        rows = r.json()
        return rows[0]["id"] if rows else None


def tool_save_artifact(
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
    Save or overwrite an artifact. `content` is the canonical editable text
    (authored docs); `file_base64` is binary file bytes (uploads, or an
    optional rendered snapshot). If artifact_id is given, overwrites in place.
    If not, checks for an exact title+entity collision first and refuses to
    silently create a near-duplicate.
    """
    if artifact_id is None:
        existing = _rpc("agent_find_artifact_by_title", {
            "search_title": title,
            "search_entity_name": entity_name,
        })
        if isinstance(existing, list) and existing:
            match = existing[0]
            return {
                "error": "duplicate_title",
                "message": (
                    f"An artifact titled '{match['title']}' already exists "
                    f"(id {match['artifact_id']}). Pass artifact_id to overwrite it, "
                    f"or use a different title."
                ),
                "existing_artifact_id": match["artifact_id"],
            }
        artifact_id = str(uuid.uuid4())

    storage_path = None
    if file_base64:
        file_bytes = base64.b64decode(file_base64)
        storage_path = f"{artifact_id}/{title.replace('/', '-')}.{format}"
        _upload_artifact_file(storage_path, file_bytes, format)

    searchable_text = content or title
    memory_id = _create_artifact_companion_memory(title, searchable_text)

    result = _rpc("agent_save_artifact", {
        "target_artifact_id": artifact_id,
        "new_title": title,
        "new_kind": kind,
        "new_format": format,
        "new_source_content": content,
        "new_storage_path": storage_path,
        "new_tags": tags or [],
        "new_entity_name": entity_name,
        "source_memory_id": memory_id,
    })
    return result[0] if isinstance(result, list) and result else {}


def tool_search_artifacts(query: Optional[str] = None) -> list[dict]:
    """Search artifacts by title, tag, entity, or content."""
    result = _rpc("agent_search_artifacts", {"query": query})
    return result if isinstance(result, list) else []


def tool_get_artifact(artifact_id: str, include_file: bool = False) -> dict:
    """
    Get an artifact's metadata and text content. If include_file is true and
    the artifact has a stored binary, also returns the file bytes (base64).
    """
    result = _rpc("agent_get_artifact", {"target_artifact_id": artifact_id})
    if not (isinstance(result, list) and result):
        return {}
    artifact = result[0]

    if include_file and artifact.get("storage_path"):
        url = f"{_SUPABASE_URL}/storage/v1/object/{_ARTIFACTS_BUCKET}/{artifact['storage_path']}"
        with httpx.Client(timeout=30) as client:
            r = client.get(url, headers=_headers())
            r.raise_for_status()
            artifact["file_base64"] = base64.b64encode(r.content).decode("ascii")

    return artifact


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
