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
| n8n | `https://n8n-latest-rllq.onrender.com` | Hosts the four load-bearing workflows below |
| Secrets | Render Environment tab (server) / n8n credentials (pipeline) | `backend/.env` is local-only, gitignored. MCP server needs `SUPABASE_SERVICE_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` (artifact embeddings), Google OAuth pair |

## Load-bearing n8n workflows

| Workflow | File | Purpose |
|---|---|---|
| Ingestion Pipeline | `n8n workflows/ingest-workflow.json` | 7-way extraction (entities, decisions, reflections, insights, customer insights, tasks, themes) + embedding. Two entry points: `/webhook/ingest-conversation` (voice path — inserts row) and `/webhook/ingest-pending` (poller path — updates row in place). Task extraction dedups via `agent_find_similar_open_task` (>0.45 trigram) before insert. Entities go through `agent_ingest_entity` (an HTTP-RPC node, not a direct table insert since 2026-07-16 Wave 2) for live canonical matching — see "Entity resolution" below. All 4 extraction prompts (entities/decisions/strategic insights/reflections) are capped and disciplined as of Wave 2; live model is `gpt-5.6-terra` (upgraded outside any Wave — check `n8n_get_workflow` before assuming it's still `gpt-4.1-mini`) |
| Pending Memory Poller | `n8n workflows/pending-memory-poller-workflow.json` | Every 2 min: claims any `memories` row at `status='pending'` (→`claimed`), POSTs to `/webhook/ingest-pending`. Makes ingestion source-agnostic — any writer just inserts with `status='pending'` |
| Shortcut Voice | `shortcut_voicenote_workflow.json` | iOS Shortcut voice-note ingestion |
| Daily Brief | `n8n workflows/daily-brief-workflow.json` (id `cSXO7IBGQ5qQQY8Z`) | 6:00am Pacific/Auckland cron: open + suggested tasks + recent memories + decisions due for review → Anthropic API (claude-sonnet-5) writes the day plan → Telegram push (new bot, push-only, no reply capture) with a link to the live check-in page. An orphaned, disconnected `Telegram Trigger` node (dead cruft from the retired conversational-bot era, live webhook + credentials but zero connections) was removed 2026-07-16 — it was blocking any partial workflow update. |

`n8n workflows/telegram_*.json` (the old bot/agent) are retired — do not modify
or deploy them. The daily brief's Telegram *push* is deliberate and fine — it's
the conversational agent that stays dead.

## MCP tools (24, defined in `backend/app/mcp/server.py` + `supabase_tools.py`)

- **Read:** `discover_database`, `get_current_state(topic?)` — query this FIRST,
  it's the current-truth layer — `get_tasks(status, limit)`, `get_recent_memories`,
  `search_memories`, `search_entities`, `get_memory`, `get_decisions`,
  `get_decisions_due_for_review(limit)`, `get_reflections`,
  `get_strategic_insights`, `get_customer_insights`,
  `get_entity_matches_due_for_review(limit)` (Wave 2, new)
- **Write:** `log_memory`, `update_current_state(topic, statement, detail?, status?, source_memory_id?)`,
  `record_decision_outcome(decision_id, status, outcome_text?)`, `create_task`,
  `complete_task`, `update_task`, `merge_tasks`, `archive_task`, `promote_task`,
  `snooze_task`, `save_artifact`, `search_artifacts`, `get_artifact`,
  `resolve_entity_match(match_id, action, note?)` (Wave 2, new — confirm/reject
  an ambiguous entity match, e.g. "is 'Jake' the same as 'Jake Shirley'?")

## Live check-in page (added 2026-07-12)

`backend/app/mcp/checkin.py`, registered as custom routes in `server.py`
(outside MCP OAuth, gated by the `CHECKIN_TOKEN` env var; 503 when unset):

- `GET /checkin?token=…` — the daily check-in, rendered live from Supabase on
  every load. Decision-review card (1–2/day, worked/mixed/didn't/obsolete +
  free-text outcome), Entity-match-review card (Wave 2, new — 3/day by
  default, "yes same"/"no different" + optional note), focus tasks grouped by
  workstream, suggested-task inbox (keep/dismiss), done-today, week-in-memory,
  pipeline health.
- `POST /checkin/action` — `{token, task_id, action: complete|archive|promote|snooze, until?}`
  → the corresponding `agent_*` RPC; `{token, action: review_decision, decision_id, status, outcome_text?}`
  → `agent_record_decision_outcome`; or `{token, action: review_entity_match, match_id, status: confirm|reject, note?}`
  → `agent_resolve_entity_match`. Returns 501 with a hint if the relevant
  migration hasn't been run yet.
- The static generator (`daily-checkin/generate_checkin.py`) is read-only by
  design (no write endpoint) — it shows decisions due for review as plain text,
  no action buttons. **Two renderers, keep in sync**: brand tokens/CSS and any
  new card added to `checkin.py` should be mirrored (read-only) here.
- Custom-domain serving: set `CHECKIN_PUBLIC_HOST` so the extra Host header
  passes DNS-rebinding protection; attach the domain to the Render service.
- Task-view rules: only tasks created after `FRESH_CUTOFF` (2026-06-17) are
  listed; older open tasks are counted as backlog. "Done today" is the NZ day
  (`CHECKIN_TZ`, default Pacific/Auckland).

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
├── canonical_id (UUID, nullable, FK → canonical_entities.id, added 2026-07-16 Wave 2)
      NULL for 'concept'-type rows (deliberately excluded from canonicalization —
      themes cover that) and for any genuinely un-retypeable stray entity_type.
      Set by agent_ingest_entity at extraction time; backfilled for pre-Wave-2
      rows by Workflows/backfill_canonical_entities.py.
decisions       (memory_id FK, decision, category, reasoning, confidence_level, emotional_context)
├── outcome (TEXT, nullable, added 2026-07-16)
├── outcome_status (TEXT, added 2026-07-16) - 'pending' | 'worked' | 'didnt_work' | 'mixed' | 'obsolete'
├── outcome_recorded_at (TIMESTAMPTZ, nullable, added 2026-07-16)
└── review_after (DATE, nullable, added 2026-07-16) - explicit review date; NULL falls
      back to "14+ days old" in agent_get_decisions_due_for_review. Set at
      extraction time since Wave 2 (Extract Business Decisions prompt outputs
      suggested_review_days; the Split Decisions code node converts it).
reflections     (memory_id FK, reflection, reflection_type, topic, emotional_tone)
strategic_insights (memory_id FK, insight, insight_category, confidence, suggested_action)
├── importance (INT, nullable, added 2026-07-16 Wave 2) - 1-5, LLM-judged at
      extraction time. agent_get_strategic_insights sorts on this (NULLS LAST)
      before recency, so old rows (no importance) just sink instead of blocking
      new high-value ones.
customer_insights  (memory_id FK, customer_name, customer_type, pain_point, desire, quote)
      -- NOT linked to entities/canonical_entities (separate extraction path,
      -- untouched by Wave 2's entity resolution). agent_get_customer_insights
      -- resolves aliases at query time instead — see RPCs below.
themes          (memory_id FK, main_theme, sub_themes JSONB, conversation_type, key_takeaways JSONB)

canonical_entities  -- added 2026-07-16 (Wave 2) — one row per distinct real-world
                    -- person/company/project/tool; entities.canonical_id points here
├── id (UUID)
├── canonical_name (TEXT) - the fullest/most-complete surface form seen
├── entity_type (TEXT) - person | company | project | tool (never 'concept')
├── aliases (TEXT[]) - every surface form that resolved to this canonical,
│     including canonical_name itself
├── notes (TEXT, nullable) - Zane's free-text clarification from a rejected match
└── created_at / updated_at (TIMESTAMPTZ)

entity_match_review  -- added 2026-07-16 (Wave 2) — ambiguous matches (pg_trgm
                     -- score 0.35-0.90) awaiting a yes/no; surfaced on the
                     -- check-in page + get_entity_matches_due_for_review
├── id (UUID)
├── entity_id (UUID, FK → entities.id)
├── memory_id (BIGINT, FK → memories.id)
├── candidate_name / candidate_canonical_id - what was extracted + its own
│     standalone canonical (created immediately, never silently pre-merged)
├── suggested_name / suggested_canonical_id - the closest existing canonical
├── similarity (REAL) - the pg_trgm-based score from agent_best_canonical_match
├── status (TEXT) - 'pending' | 'confirmed' | 'rejected'
├── note (TEXT, nullable)
└── created_at / resolved_at (TIMESTAMPTZ)

tasks
├── id (UUID)
├── memory_id (FK)
├── task (TEXT)
├── urgency (TEXT) - 'immediate' | 'this_week' | 'soon' | 'someday' (+ stray LLM values)
├── priority (TEXT) - 'high' | 'medium' | 'low'  ⚠ null on ~every row in practice
├── due_date (DATE, nullable)
├── entity_name (TEXT, nullable) ⚠ null on ~96% of rows
├── category (TEXT) - 'build' | 'outreach' | 'content' | 'research' | 'follow_up' | 'personal' | pipe-combos
├── status (TEXT) - 'suggested' | 'open' | 'completed' | 'archived' | 'merged'
│     ('suggested' = extracted, awaiting keep/dismiss; 'archived' = dismissed,
│      preserved — both added 2026-07-12)
├── completed (BOOLEAN)
├── completed_at (TIMESTAMPTZ)
├── archived_at (TIMESTAMPTZ, added 2026-07-12)
└── snoozed_until (DATE, added 2026-07-12 — open but hidden until this date)

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

living_context  ⚠ orphaned: updater was the Telegram /end flow. Empty. Superseded
                by current_state (below) — left in place, unused, not dropped.
telegram_sessions  ⚠ retired era, no longer written.

current_state   -- added 2026-07-16 (Wave 1a) — the "current truth" layer: one
                -- canonical row per topic, overwritten on supersession
├── id (UUID)
├── topic (TEXT) - unique case-insensitively (functional unique index on lower(topic))
├── statement (TEXT) - the one current, canonical answer
├── detail (TEXT, nullable)
├── status (TEXT) - 'active' | 'watch' | 'closed'
├── source_memory_ids (BIGINT[])
├── history (JSONB) - prior {statement, detail, status, superseded_at}, appended
│     only when the statement/detail actually changes — never just on touch
├── created_at / updated_at (TIMESTAMPTZ)
```

### RPC functions (agent tools)

**Read:**
```sql
agent_discover_database() → TABLE
agent_search_memories_by_embedding(query_embedding, match_threshold, match_count) → TABLE
agent_get_entity_details(search_name TEXT) → TABLE
  -- Wave 2: resolves search_name through canonical_entities (name/alias ILIKE),
  -- returns every entities row sharing that canonical_id, PLUS a raw ILIKE
  -- fallback for canonical_id IS NULL rows (concept-type, or pre-backfill).
  -- Results are capped at 5 rows per matched canonical (not a flat LIMIT 40) —
  -- otherwise a dominant canonical (e.g. "Jake" at 111 raw mentions) crowds out
  -- a real but rarely-mentioned one ("Jake Murray", 1 mention) entirely. Found
  -- via testing 2026-07-16; see entity_resolution_migration.sql §6 for the fix.
agent_get_decisions(search_topic TEXT, recent_days INT) → TABLE
agent_get_reflections(search_topic TEXT, recent_days INT) → TABLE
agent_get_tasks(task_status TEXT) → TABLE
  -- ⚠ hard LIMIT 25 (task_writeback_migration.sql:251) and priority→due_date→urgency
  -- sort: with 1,281 open rows and null priorities it only ever returns the oldest
  -- 'immediate' tasks. Known issue — see LIVING_DOC priorities.
agent_get_strategic_insights(search_category TEXT, recent_days INT) → TABLE
  -- Wave 2: now returns `importance`, sorted DESC NULLS LAST before recency.
agent_get_customer_insights(search_customer TEXT) → TABLE
  -- Wave 2: expands search_customer into every alias of any matching canonical
  -- entity (query-time only — customer_insights has no stored FK into
  -- canonical_entities), so "Jake" also matches customer rows under any of
  -- Jake's known aliases.
agent_get_memory_context(target_memory_id BIGINT) → TABLE
agent_get_recent_memories(limit_count INT, filter_source TEXT) → TABLE  -- status='completed' only
agent_search_by_theme(theme_keywords TEXT, limit_count INT) → TABLE     -- status='completed' only
```

**Current-truth layer (`current_state_migration.sql`, 2026-07-16, Wave 1a):**
```sql
agent_get_current_state(search_topic TEXT DEFAULT NULL) → TABLE
  -- no topic → everything, active first then watch then closed, updated_at DESC.
  -- topic ILIKE-matches topic OR statement.
agent_update_current_state(p_topic TEXT, p_statement TEXT, p_detail TEXT DEFAULT NULL,
                            p_status TEXT DEFAULT 'active', p_source_memory_id BIGINT DEFAULT NULL) → TABLE
  -- upsert by lower(topic). If the topic exists and statement/detail actually
  -- changed, the prior value is pushed into history before being overwritten.
  -- No-op touches (same statement, e.g. just re-confirming) update updated_at/
  -- source_memory_ids without bloating history.
```

**Decision outcome loop (`decision_outcomes_migration.sql`, 2026-07-16, Wave 1b):**
```sql
agent_record_decision_outcome(target_decision_id TEXT, new_outcome_status TEXT,
                               new_outcome_text TEXT DEFAULT NULL) → TABLE
agent_get_decisions_due_for_review(limit_count INT DEFAULT 2) → TABLE
  -- pending only; review_after <= today, OR (review_after IS NULL AND 14+ days
  -- old) — covers every pre-migration decision since review_after starts NULL.
  -- certain-confidence + strategy/pricing/pivot categories surface first.
```

**Entity resolution (`entity_resolution_migration.sql`, 2026-07-16, Wave 2):**
```sql
agent_best_canonical_match(candidate_name TEXT, candidate_type TEXT) → TABLE
  -- pg_trgm-based scoring: 1.0 exact (case/whitespace-insensitive), else
  -- GREATEST(trigram similarity, 0.6 if one name is a whole-word substring of
  -- the other). Whole-word check is plain word-array membership, not a
  -- dynamic regex — entity names can contain regex metacharacters.
agent_ingest_entity(p_memory_id BIGINT, p_entity_type TEXT, p_entity_name TEXT,
                     p_context TEXT DEFAULT NULL) → TABLE
  -- Called by the Ingest workflow's "Insert Entities" node (now an HTTP-RPC
  -- node, not a native Supabase insert) instead of a direct table write.
  -- score >= 0.90 → silent auto-merge (alias appended if new surface form)
  -- 0.35 <= score < 0.90 → new STANDALONE canonical (never pre-merged) +
  --   an entity_match_review row against the closest match
  -- score < 0.35 / no match → new canonical, nothing to review
  -- Floor was 0.20 in the first version of this migration; raised to 0.35
  -- after inspecting real backfill scores (see LIVING_DOC changelog).
agent_get_entity_matches_due_for_review(limit_count INT DEFAULT 3) → TABLE
agent_resolve_entity_match(match_id TEXT, action TEXT, new_note TEXT DEFAULT NULL) → TABLE
  -- action='confirm': folds the candidate canonical's aliases into the
  --   suggested one, repoints entities + any other entity_match_review rows
  --   off the candidate canonical, deletes it.
  -- action='reject': leaves both canonicals separate, stores new_note on the
  --   candidate's `notes` field.
```

**Task write-back:**
```sql
agent_complete_task(target_task_id TEXT) → TABLE
agent_update_task(target_task_id TEXT, new_task, new_urgency, new_priority, new_due_date, new_category) → TABLE
agent_create_task(new_task TEXT, new_context, new_urgency, new_category, new_due_date, new_entity_name, source_memory_id) → TABLE
agent_merge_tasks(keep_task_id TEXT, merge_task_ids TEXT[]) → TABLE
agent_find_similar_open_task(candidate_text TEXT, match_threshold FLOAT) → TABLE
  -- pg_trgm dedup; post-triage-migration it matches open + suggested + tasks
  -- archived in the last 30 days (dismissals stay dismissed)
```

**Task triage (task_triage_migration.sql, 2026-07-12):**
```sql
agent_get_tasks(task_status TEXT DEFAULT 'open', limit_count INT DEFAULT 50) → TABLE
  -- REPLACES the old LIMIT-25 version. Statuses: open (excludes snoozed),
  -- snoozed, suggested, completed, archived, merged, all. Sort: due_date →
  -- urgency → task created_at DESC (created_date is now the TASK's date,
  -- not the memory's). Limit clamped 1..200.
agent_archive_task(target_task_id TEXT) → TABLE   -- dismiss; sets archived_at
agent_promote_task(target_task_id TEXT) → TABLE   -- suggested/archived → open
agent_snooze_task(target_task_id TEXT, until_date DATE) → TABLE
```
Task lifecycle: extraction inserts `suggested` → Zane keeps (`open`) or dismisses
(`archived`); `open` can be completed, snoozed (stays open, hidden until date),
or archived. Nothing is deleted.

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
5. `task_triage_migration.sql` — suggested/archived statuses, snooze, triage RPCs
6. `current_state_migration.sql` — current-truth layer table + RPCs (Wave 1a)
7. `decision_outcomes_migration.sql` — decision outcome columns + RPCs (Wave 1b)
8. `entity_resolution_migration.sql` — canonical_entities + entity_match_review
   tables, entities.canonical_id, strategic_insights.importance, matching RPCs
   (Wave 2). Reflects final state inline (the three post-review fixes are
   folded in, not appended as patches) — see LIVING_DOC changelog for the
   fix history if you need it.

Superseded SQL lives in `../archive/sql/`. One-off data scripts (not part of
the ordered schema list): `backfill_embeddings.py`, `backfill_canonical_entities.py`
(Wave 2 — reuses agent_best_canonical_match rather than a second heuristic;
run once per entity_type positional arg, e.g. `python3 backfill_canonical_entities.py tool`,
so results can be sanity-checked incrementally).

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

### 2026-07-16: Extraction discipline + entity resolution (Wave 2)
- **4 extraction prompts tightened** in the live Ingest workflow (applied via
  `n8n_update_partial_workflow` diff ops, not a full overwrite — the live
  workflow's node IDs/positions/credentials had drifted from the local JSON
  mirror since a prior manual reorganization; fetched live state first,
  diffed, then re-synced the mirror to match exactly afterward):
  Entities capped 15-25 → 8, `concept` type killed, canonical-name rules;
  Decisions capped → 3 + `suggested_review_days` → `review_after`; Strategic
  Insights capped → 3 + `importance`; Reflections capped → 2.
- **`entity_resolution_migration.sql`**: `canonical_entities` +
  `entity_match_review` tables, `entities.canonical_id`,
  `strategic_insights.importance`, and the matching RPCs (see above). The
  Ingest workflow's "Insert Entities" node is now an HTTP call to
  `agent_ingest_entity` instead of a direct table insert.
- MCP server: 2 new tools — `get_entity_matches_due_for_review`,
  `resolve_entity_match` (24 total).
- Check-in page: new "Entity match review" card, both `checkin.py`
  (interactive) and `generate_checkin.py` (read-only mirror).
- One-off backfill (`backfill_canonical_entities.py`): 4,334 entity rows →
  1,073 canonical entities across person/company/project/tool; 426 ambiguous
  groups queued for review; 151 banned "Zane" rows deleted; `concept`-type
  rows (1,249) left alone. Rewritten mid-backfill to call the live
  `agent_best_canonical_match` RPC instead of a Python difflib heuristic —
  the heuristic flagged ~1,035 of 3,005 rows for review (noisy on short
  strings); pg_trgm did not have that problem.
- Three bugs found and fixed via live-data testing, each needing a follow-up
  hotfix after the initial migration run: (1) `agent_resolve_entity_match`'s
  own `RETURNS TABLE` column was named `canonical_id`, shadowing
  `entities.canonical_id` inside the function body ("ambiguous column"); (2)
  confirming a match tried to delete the merged-away canonical while
  `entity_match_review.candidate_canonical_id` still FK-referenced it — fixed
  by repointing that reference first; (3) `agent_get_entity_details`'s flat
  `ORDER BY mention_count DESC LIMIT 40` let one dominant canonical (111 raw
  mentions for "Jake") crowd out real but rare ones ("Jake Murray", 1 mention)
  entirely — fixed by capping 5 rows per matched canonical. All three fixes
  are folded into `entity_resolution_migration.sql` directly (reflects final
  state); also raised the "worth asking" score floor 0.20 → 0.35 after
  inspecting real backfill scores (below 0.35 was consistently noise, e.g.
  "DocuSign" vs "Docker" at 0.23).

### 2026-07-16: Current-truth layer + decision outcome loop (Wave 1)
- `current_state_migration.sql`: new `current_state` table + `agent_get_current_state`/
  `agent_update_current_state` RPCs. One canonical row per topic; superseded facts
  preserved in `history`, never left sitting beside their correction. `living_context`
  is superseded (left in place, unused). Confirmed live and working (verified
  2026-07-16 during Wave 2 — `get_decisions_due_for_review` returned real rows).
- `decision_outcomes_migration.sql`: `decisions` gains `outcome`/`outcome_status`/
  `outcome_recorded_at`/`review_after`; `agent_record_decision_outcome` +
  `agent_get_decisions_due_for_review` RPCs. Same confirmed-live status.
- MCP server: 4 new tools — `get_current_state`, `update_current_state`,
  `record_decision_outcome`, `get_decisions_due_for_review` (22 total at the time).
- Check-in page: new "Decision review" card (worked/mixed/didn't work/obsolete +
  free-text outcome), both `checkin.py` (interactive) and `generate_checkin.py`
  (read-only mirror).
- Daily Brief n8n workflow (`cSXO7IBGQ5qQQY8Z`): new `Get Decisions Due` node
  feeds `decisions_due_for_review` into the brief payload/prompt (item 6,
  "Decision check-in"); set `onError: continueRegularOutput` so a missing RPC
  (migration not yet run) degrades gracefully instead of breaking the brief.
  Also removed an orphaned, disconnected `Telegram Trigger` node (dead cruft
  from the retired conversational-bot era) that was blocking any partial
  workflow update.
- Fixed doc drift: n8n URL was still `n8n-service-8act.onrender.com`, live
  instance is `n8n-latest-rllq.onrender.com`.

### 2026-07-12: Task triage + live check-in + daily brief
- `task_triage_migration.sql`: suggested/archived statuses, snooze, bulk archive
  of the pre-17-Jun open-task flood, fixed `agent_get_tasks` (limit param, sane
  sort, task-own created_at), archive/promote/snooze RPCs, dedup extended to
  suggested + recent dismissals.
- MCP server: `/checkin` live page + `/checkin/action` write endpoints
  (`checkin.py`); new tools archive_task/promote_task/snooze_task; get_tasks
  gains limit + statuses; `CHECKIN_TOKEN`/`CHECKIN_PUBLIC_HOST`/`CHECKIN_TZ` env.
- Ingest workflow staged: Insert Tasks → `status='suggested'`; strict extraction
  prompt (hard cap 5 tasks/conversation, explicit commitments only).
- New `daily-brief-workflow.json` (6am NZT, Sonnet 5 plan → Telegram push).
- Go-live steps: `../SETUP_CHECKIN_BRIEF.md`.

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

**Last updated**: 2026-07-16 by Claude Code (Wave 1: current-truth layer + decision outcome loop)
