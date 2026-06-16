"""
Migrates historical data from the local SQLite database into Supabase.

SQLite schema (FastAPI):     journal_entries, people, commitments, topics,
                              insights, events, challenges, wins, pain_points

Supabase schema (n8n):       memories, entities, decisions, tasks,
                              strategic_insights, customer_insights,
                              reflections, themes

Mapping:
  journal_entry  → memory  (transcript = content, source = entry_type)
  people         → entities (entity_type = 'person')
  topics         → entities (entity_type = 'project') + themes
  commitments    → tasks
  insights       → strategic_insights
  challenges     → reflections (reflection_type = 'challenge')
  wins           → reflections (reflection_type = 'win')
  pain_points    → customer_insights
"""

import sqlite3
import json
import os
import sys
import httpx
from datetime import datetime

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SQLITE_PATH = os.path.join(os.path.dirname(__file__), "../backend/cais_command_center.db")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://erwxszdcisyuyjmefvbj.supabase.co")
SUPABASE_KEY = os.environ.get(
    "SUPABASE_SERVICE_KEY",
    "***REMOVED-SUPABASE-SERVICE-KEY***"
)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sb_post(path: str, body) -> dict | list:
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    with httpx.Client(timeout=15) as client:
        r = client.post(url, headers=HEADERS, json=body)
        if not r.is_success:
            print(f"  ERROR {r.status_code} on {path}: {r.text[:300]}")
            r.raise_for_status()
        return r.json()


def clean(text: str | None) -> str | None:
    """Remove null bytes that PostgreSQL rejects."""
    if text is None:
        return None
    return text.replace("\x00", "")


def fmt(dt_str: str | None) -> str | None:
    if not dt_str:
        return None
    # SQLite stores datetimes without timezone; add Z for Supabase
    try:
        dt = datetime.fromisoformat(str(dt_str).replace(" ", "T"))
        return dt.isoformat() + "Z"
    except Exception:
        return str(dt_str)


# ---------------------------------------------------------------------------
# Load SQLite data
# ---------------------------------------------------------------------------

conn = sqlite3.connect(SQLITE_PATH)
conn.row_factory = sqlite3.Row


def load(table: str) -> list[dict]:
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {table}")
    return [dict(r) for r in cur.fetchall()]


journal_entries = load("journal_entries")
people          = load("people")
commitments     = load("commitments")
topics          = load("topics")
insights        = load("insights")
events          = load("events")
challenges      = load("challenges")
wins            = load("wins")
pain_points     = load("pain_points")

conn.close()

print(f"Loaded from SQLite:")
print(f"  {len(journal_entries)} journal entries")
print(f"  {len(people)} people")
print(f"  {len(commitments)} commitments")
print(f"  {len(topics)} topics")
print(f"  {len(insights)} insights")
print(f"  {len(events)} events")
print(f"  {len(challenges)} challenges")
print(f"  {len(wins)} wins")
print(f"  {len(pain_points)} pain points")
print()

# ---------------------------------------------------------------------------
# Map journal_entry_id → supabase memory_id
# ---------------------------------------------------------------------------

entry_to_memory: dict[int, int] = {}  # sqlite journal id → supabase memory id

# Map people by SQLite id → name (for pain_points lookup)
people_by_id = {p["id"]: p for p in people}

# Group child rows by journal_entry_id
def by_entry(rows: list[dict]) -> dict[int, list[dict]]:
    result: dict[int, list[dict]] = {}
    for r in rows:
        eid = r.get("journal_entry_id")
        if eid:
            result.setdefault(eid, []).append(r)
    return result

commitments_by  = by_entry(commitments)
topics_by       = by_entry(topics)
insights_by     = by_entry(insights)
events_by       = by_entry(events)
challenges_by   = by_entry(challenges)
wins_by         = by_entry(wins)
pain_points_by  = by_entry(pain_points)


# ---------------------------------------------------------------------------
# Step 1: Insert memories
# ---------------------------------------------------------------------------

print("=== Step 1: Inserting memories ===")

ENTRY_TYPE_TO_SOURCE = {
    "reflection":    "local_reflection",
    "chat":          "local_chat",
    "customer_call": "local_customer_call",
    "document":      "local_document",
}

for entry in journal_entries:
    source = ENTRY_TYPE_TO_SOURCE.get(entry["entry_type"], "local_journal")

    # Build a descriptive title from entry type + date
    title = f"{entry['entry_type'].replace('_', ' ').title()} — {entry['entry_date']}"

    # Build summary from first 200 chars of content
    summary = entry["content"][:200].rstrip() + ("..." if len(entry["content"]) > 200 else "")

    body = {
        "source":       source,
        "content_type": entry["entry_type"],
        "transcript":   clean(entry["content"]),
        "title":        clean(title),
        "summary":      clean(summary),
        "status":       "completed",
        "created_at":   fmt(entry["created_at"]),
        "updated_at":   fmt(entry.get("updated_at") or entry["created_at"]),
    }

    result = sb_post("memories", body)
    memory_id = result[0]["id"]
    entry_to_memory[entry["id"]] = memory_id
    print(f"  ✓ Entry {entry['id']} → memory {memory_id}  ({title})")

print()


# ---------------------------------------------------------------------------
# Step 2: Insert entities (people + topics as projects)
# ---------------------------------------------------------------------------

print("=== Step 2: Inserting entities ===")

# People → entities with entity_type='person'
for person in people:
    # Find which memory to attach to (first journal entry that mentions them)
    # We'll use the first_mentioned_at to guess; fall back to first memory
    memory_id = list(entry_to_memory.values())[0]  # default

    # Check commitments for a journal_entry link
    for c in commitments:
        if c.get("person_id") == person["id"] and c.get("journal_entry_id") in entry_to_memory:
            memory_id = entry_to_memory[c["journal_entry_id"]]
            break

    # Also check pain_points
    for pp in pain_points:
        if pp.get("person_id") == person["id"] and pp.get("journal_entry_id") in entry_to_memory:
            memory_id = entry_to_memory[pp["journal_entry_id"]]
            break

    role_context = " | ".join(filter(None, [person.get("role"), person.get("company")]))
    body = {
        "memory_id":   memory_id,
        "entity_type": "person",
        "entity_name": person["name"],
        "context":     role_context or None,
        "created_at":  fmt(person["created_at"]),
    }
    sb_post("entities", body)
    print(f"  ✓ Person: {person['name']}")

# Topics → entities with entity_type='project'
for topic in topics:
    if topic["journal_entry_id"] not in entry_to_memory:
        continue
    memory_id = entry_to_memory[topic["journal_entry_id"]]
    body = {
        "memory_id":   memory_id,
        "entity_type": "project",
        "entity_name": topic["name"],
        "context":     topic.get("description"),
        "created_at":  fmt(topic["created_at"]),
    }
    sb_post("entities", body)
    print(f"  ✓ Topic/project: {topic['name'][:60]}")

print()


# ---------------------------------------------------------------------------
# Step 3: Insert themes (from topics grouped by entry)
# ---------------------------------------------------------------------------

print("=== Step 3: Inserting themes ===")

for entry_id, entry_topics in topics_by.items():
    if entry_id not in entry_to_memory:
        continue
    memory_id = entry_to_memory[entry_id]
    main_theme = entry_topics[0]["name"] if entry_topics else "General"
    sub_themes = [t["name"] for t in entry_topics[1:]]
    categories = list(set(t.get("category", "") for t in entry_topics if t.get("category")))

    body = {
        "memory_id":          memory_id,
        "main_theme":         main_theme,
        "sub_themes":         sub_themes,
        "conversation_type":  categories[0] if categories else "business",
        "business_relevance": "high",
        "contains_action_items": entry_id in commitments_by,
        "contains_decisions":    False,
        "key_takeaways":         [t["description"] for t in entry_topics if t.get("description")],
    }
    sb_post("themes", body)
    print(f"  ✓ Theme for memory {memory_id}: {main_theme[:60]}")

print()


# ---------------------------------------------------------------------------
# Step 4: Insert tasks (from commitments)
# ---------------------------------------------------------------------------

print("=== Step 4: Inserting tasks ===")

PRIORITY_TO_URGENCY = {
    "high":   "immediate",
    "medium": "soon",
    "low":    "someday",
}

for c in commitments:
    if c["journal_entry_id"] not in entry_to_memory:
        continue
    memory_id = entry_to_memory[c["journal_entry_id"]]
    person_name = people_by_id.get(c.get("person_id") or -1, {}).get("name")

    body = {
        "memory_id":   memory_id,
        "task":        c["description"],
        "context":     f"Related to: {person_name}" if person_name else None,
        "urgency":     PRIORITY_TO_URGENCY.get(c.get("priority", "medium"), "soon"),
        "category":    "business",
        "completed":   c["status"] == "completed",
        "status":      c["status"] or "open",
        "created_at":  fmt(c["created_at"]),
    }
    if c.get("completed_at"):
        body["completed_at"] = fmt(c["completed_at"])

    sb_post("tasks", body)
    print(f"  ✓ Task: {c['description'][:70]}")

print()


# ---------------------------------------------------------------------------
# Step 5: Insert strategic_insights (from insights)
# ---------------------------------------------------------------------------

print("=== Step 5: Inserting strategic insights ===")

for insight in insights:
    if insight["journal_entry_id"] not in entry_to_memory:
        continue
    memory_id = entry_to_memory[insight["journal_entry_id"]]
    body = {
        "memory_id":        memory_id,
        "insight":          insight["description"],
        "insight_category": insight.get("category", "business"),
        "confidence":       "medium",
        "actionable":       True,
        "created_at":       fmt(insight["created_at"]),
    }
    sb_post("strategic_insights", body)
    print(f"  ✓ Insight: {insight['description'][:70]}")

print()


# ---------------------------------------------------------------------------
# Step 6: Insert reflections (challenges + wins)
# ---------------------------------------------------------------------------

print("=== Step 6: Inserting reflections ===")

for c in challenges:
    if c["journal_entry_id"] not in entry_to_memory:
        continue
    memory_id = entry_to_memory[c["journal_entry_id"]]
    body = {
        "memory_id":       memory_id,
        "reflection":      c["description"],
        "reflection_type": "challenge",
        "topic":           c.get("challenge_type"),
        "emotional_tone":  "frustrated" if c.get("severity") == "high" else "neutral",
        "created_at":      fmt(c["created_at"]),
    }
    sb_post("reflections", body)
    print(f"  ✓ Challenge: {c['description'][:70]}")

for w in wins:
    if w["journal_entry_id"] not in entry_to_memory:
        continue
    memory_id = entry_to_memory[w["journal_entry_id"]]
    body = {
        "memory_id":       memory_id,
        "reflection":      w["description"],
        "reflection_type": "win",
        "topic":           w.get("category"),
        "emotional_tone":  "optimistic",
        "created_at":      fmt(w["created_at"]),
    }
    sb_post("reflections", body)
    print(f"  ✓ Win: {w['description'][:70]}")

print()


# ---------------------------------------------------------------------------
# Step 7: Insert customer_insights (from pain_points)
# ---------------------------------------------------------------------------

print("=== Step 7: Inserting customer insights ===")

for pp in pain_points:
    if pp["journal_entry_id"] not in entry_to_memory:
        continue
    memory_id = entry_to_memory[pp["journal_entry_id"]]
    person = people_by_id.get(pp.get("person_id") or -1, {})
    customer_name = person.get("name", "Unknown")
    customer_role = person.get("role", "")

    body = {
        "memory_id":     memory_id,
        "customer_name": customer_name,
        "customer_type": customer_role[:100] if customer_role else "trade_business",
        "pain_point":    pp["description"],
        "created_at":    fmt(pp.get("first_mentioned_at")),
    }
    sb_post("customer_insights", body)
    print(f"  ✓ Customer insight ({customer_name}): {pp['description'][:60]}")

print()
print("=== Migration complete ===")
print(f"Migrated {len(journal_entries)} journal entries as memories.")
print(f"Memory ID map: {entry_to_memory}")
