# Command Centre — Technical Context for Claude Code

> Deep technical reference: schema, RPCs, data flows, pipelines. Update this file
> when architecture changes. Project status and priorities live in `../LIVING_DOC.md`.

---

## Project Overview

**Purpose**: Persistent business memory + task system for Zane. Claude (claude.ai
app and Claude Code) connects via an MCP server to capture conversations, recall
context semantically, manage tasks, and save documents. Voice notes arrive via an
iOS Shortcut.

**Architecture**: MCP server (FastAPI-based, on Render) + Supabase (PostgreSQL +
pgvector) + n8n ingest pipeline + OpenAI embeddings + Anthropic Claude extraction.

**What it is NOT anymore**: the Telegram bot, the hierarchical n8n specialist-agent
system, and the Next.js journal frontend are retired (see "Retired era" at the
bottom). n8n is a pipeline, not an agent.

---

## Deployed Components

| Component | Where | Notes |
|---|---|---|
| MCP server | Render: `https://cais-mcp-server.onrender.com` | `backend/app/mcp/server.py`, start `python -m app.mcp.server`, root dir `backend`, Python 3.12.7, Starter instance, single instance (in-memory OAuth state). `/health` for health checks |
| GitHub repo | `zanemoore575/cais-command-centre` (private) | Render deploys from it |
| Supabase | `https://erwxszdcisyuyjmefvbj.supabase.co` | **Current** project. `wwqdkiphfpdczgmnxxrt` (in old docs) is the dead original |
| n8n | `https://n8n-service-8act.onrender.com` | Hosts the three load-bearing workflows below |
| Secrets | Render Environment tab (server) / n8n credentials (pipeline) | `backend/.env` is local-only, gitignored. MCP server needs `SUPABASE_SERVICE_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` (artifact embeddings), Google OAuth pair |

## Load-bearing n8n workflows

| Workflow | File | Purpose |
|---|---|---|
| Ingestion Pipeline | `n8n workflows/ingest-workflow.json` | 7-way extraction (entities, decisions, reflections, insights, customer insights, tasks, themes) + embedding. Two entry points: `/webhook/ingest-conversation` (voice path — inserts row) and `/webhook/ingest-pending` (poller path — updates row in place). Task extraction dedups via `agent_find_similar_open_task` (>0.45 trigram) before insert |
| Pending Memory Poller | `n8n workflows/pending-memory-poller-workflow.json` | Every 2 min: claims any `memories` row at `status='pending'` (→`claimed`), POSTs to `/webhook/ingest-pending`. Makes ingestion source-agnostic — any writer just inserts with `status='pending'` |
| Shortcut Voice | `shortcut_voicenote_workflow.json` | iOS Shortcut voice-note ingestion |

`n8n workflows/telegram_*.json` are retired — do not modify or deploy them.

## MCP tools (18, defined in `backend/app/mcp/server.py` + `supabase_tools.py`)

- **Read:** `discover_database`, `get_tasks`, `get_recent_memories`,
  `search_memories`, `search_entities`, `get_memory`, `get_decisions`,
  `get_reflections`, `get_strategic_insights`, `get_customer_insights`
- **Write:** `log_memory`, `create_task`, `complete_task`, `update_task`,
  `merge_tasks`, `save_artifact`, `search_artifacts`, `get_artifact`

---

## Database (Supabase)

### Core tables

```
memories
├── id (BIGINT, AUTO)
├── source (TEXT) - 'claude_conversation' | 'shortcut_voice' | 'claude_task_creation'
│                   | 'artifact' | 'local_*' | legacy telegram/chatgpt values
├── transcript (TEXT)
├── title (TEXT)
├── summary (TEXT)
├── status (TEXT) - lifecycle: 'pending' → 'claimed' → 'extracting' → 'completed'
│     ⚠ observed in the wild (2026-07-11): 'indexed' (33 voice rows, embedded but
│     no entity extraction), 'transcribed' (2), stuck 'claimed' (26). Recall tools
│     filter on 'completed' — anything else is INVISIBLE to search/recent tools
├── embeddings (VECTOR(1536))  -- NOTE: plural column name!
└── created_at (TIMESTAMPTZ)

entities        (memory_id FK, entity_type, entity_name, context)
decisions       (memory_id FK, decision, category, reasoning, confidence_level, emotional_context)
reflections     (memory_id FK, reflection, reflection_type, topic, emotional_tone)
strategic_insights (memory_id FK, insight, insight_category, confidence, suggested_action)
customer_insights  (memory_id FK, customer_name, customer_type, pain_point, desire, quote)
themes          (memory_id FK, main_theme, sub_themes JSONB, conversation_type, key_takeaways JSONB)

tasks
├── id (UUID)
├── memory_id (FK)
├── task (TEXT)
├── urgency (TEXT) - 'immediate' | 'this_week' | 'soon' | 'someday' (+ stray LLM values)
├── priority (TEXT) - 'high' | 'medium' | 'low'  ⚠ null on ~every row in practice
├── due_date (DATE, nullable)
├── entity_name (TEXT, nullable) ⚠ null on ~96% of rows
├── category (TEXT) - 'build' | 'outreach' | 'content' | 'research' | 'follow_up' | 'personal' | pipe-combos
├── status (TEXT) - 'open' | 'completed' | 'merged'
├── completed (BOOLEAN)
└── completed_at (TIMESTAMPTZ)

artifacts
├── id (UUID)
├── title (TEXT) - overwrite-matching identity together with entity_name
├── kind (TEXT) - 'authored' (Claude-made) | 'uploaded' (real file in Storage)
├── format (TEXT) - 'md' | 'txt' | 'pdf' | 'docx'
├── source_content (TEXT, nullable) - canonical editable text for 'authored'
├── storage_path (TEXT, nullable) - path in private 'artifacts' Storage bucket
├── extracted_text (TEXT, nullable)
├── tags (JSONB)
├── entity_name (TEXT, nullable)
└── memory_id (FK, nullable) - companion memory row for embedding/search

living_context  ⚠ orphaned: updater was the Telegram /end flow. Empty. Candidate
                for deletion or re-homing as a periodic Claude-written summary.
telegram_sessions  ⚠ retired era, no longer written.
```

### RPC functions (agent tools)

**Read:**
```sql
agent_discover_database() → TABLE
agent_search_memories_by_embedding(query_embedding, match_threshold, match_count) → TABLE
agent_get_entity_details(search_name TEXT) → TABLE
agent_get_decisions(search_topic TEXT, recent_days INT) → TABLE
agent_get_reflections(search_topic TEXT, recent_days INT) → TABLE
agent_get_tasks(task_status TEXT) → TABLE
  -- ⚠ hard LIMIT 25 (task_writeback_migration.sql:251) and priority→due_date→urgency
  -- sort: with 1,281 open rows and null priorities it only ever returns the oldest
  -- 'immediate' tasks. Known issue — see LIVING_DOC priorities.
agent_get_strategic_insights(search_category TEXT, recent_days INT) → TABLE
agent_get_customer_insights(search_customer TEXT) → TABLE
agent_get_memory_context(target_memory_id BIGINT) → TABLE
agent_get_recent_memories(limit_count INT, filter_source TEXT) → TABLE  -- status='completed' only
agent_search_by_theme(theme_keywords TEXT, limit_count INT) → TABLE     -- status='completed' only
```

**Task write-back:**
```sql
agent_complete_task(target_task_id TEXT) → TABLE
agent_update_task(target_task_id TEXT, new_task, new_urgency, new_priority, new_due_date, new_category) → TABLE
agent_create_task(new_task TEXT, new_context, new_urgency, new_category, new_due_date, new_entity_name, source_memory_id) → TABLE
agent_merge_tasks(keep_task_id TEXT, merge_task_ids TEXT[]) → TABLE
agent_find_similar_open_task(candidate_text TEXT, match_threshold FLOAT) → TABLE  -- pg_trgm dedup
```

**Artifacts:**
```sql
agent_save_artifact(target_artifact_id TEXT, new_title, new_kind, new_format, new_source_content,
                    new_storage_path, new_tags, new_entity_name, source_memory_id, new_extracted_text) → TABLE
agent_find_artifact_by_title(search_title TEXT, search_entity_name TEXT) → TABLE
agent_search_artifacts(query TEXT) → TABLE
agent_get_artifact(target_artifact_id TEXT) → TABLE
```

**SQL files (run in order on a fresh project, or individually to update):**
1. `supabase_fresh_setup.sql` — table CREATEs (its inline RPCs are outdated; see file header)
2. `apply_agent_functions.sql` — all read-only agent_* RPCs, correct types
3. `task_writeback_migration.sql` — write-back tools, task columns, dedup RPC
4. `artifact_storage_migration.sql` — artifacts table + Storage bucket + RPCs

Superseded SQL lives in `../archive/sql/`.

---

## Data flows

### Claude write (claude.ai or Claude Code → `log_memory`)
```
1. Claude calls log_memory(content) on the MCP server
2. Row inserted into memories (status='pending') — the server never calls n8n itself
3. Pending Memory Poller (2 min) claims the row (status='claimed')
4. Poller POSTs {memory_id, transcript, title, source} to /webhook/ingest-pending
5. "Update Memory To Extracting" updates the SAME row (no duplicate)
6. 7-way extraction + embedding (text-embedding-3-small)
7. status='completed' → now visible to recall tools
```

### Voice note (iOS Shortcut)
```
Shortcut → shortcut_voicenote workflow → transcription → /webhook/ingest-conversation
(inserts new row) → same extraction/embedding → completed
```

### Task write-back / artifacts
MCP tools call the agent_* RPCs directly against Supabase. `save_artifact` also
writes a companion `memories` row and embeds it server-side via OpenAI —
deliberately skipping the n8n extraction pipeline (no useful signal in proposal
boilerplate).

---

## Live-data health facts (audited 2026-07-11 — recheck before relying on them)

- 442 memories (Apr 2025→now): 380 completed, 33 'indexed', 26 stuck 'claimed'
  (23–29 Jun claude_conversations), 2 'transcribed', 1 'extracting'. The 62
  non-completed rows are invisible to recall tools.
- 1,391 tasks, 1,281 open — ~989 created June 2026 by bulk import + extraction.
  `priority` effectively always null; `entity_name` null on ~96%.
- 13 artifacts, all authored, mostly Jake/Core Finance Phase 1 documents.
- `living_context`: one empty row, orphaned.

---

## Common Issues & Solutions

### A memory written via `log_memory` never shows up in search/recent
`log_memory` only inserts the row (`status='pending'`). Confirm the Pending Memory
Poller is **active** in n8n and check its execution history. If a row sits at
`'pending'`/`'claimed'` for more than a few minutes, the poller or ingest run
failed — reset the row to `'pending'` to re-drive it.

### Memory search returns no results
1. Check `embeddings` populated (plural column name!)
2. Lower `match_threshold` (try 0.3–0.5)
3. Check the row actually reached `status='completed'` — 'indexed'/'claimed'/'transcribed' rows are filtered out
4. pgvector extension enabled

### get_tasks only shows ancient tasks
Known issue: `agent_get_tasks` LIMIT 25 + null priorities means oldest 'immediate'
rows win. Query the `tasks` table directly (filter `created_at` recent, `status=eq.open`)
until the RPC is fixed.

### Supabase RPC returns 404
The function doesn't exist on the current project — run the appropriate SQL file
in the Supabase SQL Editor. Make sure you're on `erwxszdcisyuyjmefvbj`, not the
dead old project.

### claude.ai connector suddenly has no tools / "requires re-authorization"
The connector token expires. Re-authorize in claude.ai → Settings → Connectors.
Claude Code sessions hit the same wall (they share the connector). Direct
Supabase REST access with the service key (from `backend/.env`) is the fallback
for local work.

---

## Retired era (reference only — do not build on)

The first incarnation (Jan–Jun 2026) was a Telegram bot: n8n AI Agent node
(Sonnet 4.5) with a hierarchical specialist system (Memory/Entity/Strategy
sub-agents over 11 webhook tools), telegram_sessions with 30-min timeout
auto-save, `/end`-triggered extraction, a `living_context` table refreshed per
conversation, and a Next.js + FastAPI journal frontend with phase-separated
streaming UX. It worked, but it was remaking Claude inside Telegram — retired
2026-06/07 in favour of the claude.ai app + Claude Code over MCP. Details: git
history, `../archive/`, and the `n8n workflows/telegram_*.json` files.

---

## Changelog

### 2026-07-11: Doc refresh against live DB + architecture reality
- Rewrote this file around the MCP-centric architecture; Telegram era moved to a
  reference note. Corrected the Supabase project URL (old docs pointed at the
  dead `wwqdkiphfpdczgmnxxrt` project).
- Documented real memory statuses ('indexed', stuck 'claimed') and recall
  visibility rules; documented the get_tasks LIMIT 25 issue and the June task
  flood. Added live-data health facts + updated troubleshooting.

### 2026-06-17: Write/ingest fix, Render hosting, task write-back, artifacts
- Pending Memory Poller + `/webhook/ingest-pending` update-in-place entry point;
  fixed pgvector JSON.stringify embedding bug; `backfill_embeddings.py`.
- MCP server moved from Mac+ngrok to Render; repo to GitHub.
- Task write-back tools + schema (priority/due_date/entity_name) + pg_trgm dedup;
  extraction prompt rewritten for real urgency spread.
- Artifact storage: table, Storage bucket, save/search/get tools, server-side
  companion-memory embedding (needs OPENAI_API_KEY).

### 2026-01-22: Hierarchical specialist agents + living context (retired era)
### 2026-01-19: Discovery tool + thorough search behavior (retired era)
### 2026-01-18: Initial agentic Telegram system (retired era)

---

**Last updated**: 2026-07-11 by Claude Code (full refresh against live database)
