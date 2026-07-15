# Command Centre — Living Project Status

Updated: 2026-07-16 (Wave 1 built: current-truth layer + decision outcome loop — see changelog; migrations pending a live-DB run)

## What this system is now

A persistent business memory and task system for Zane, served to Claude everywhere via MCP.

The original vision (Telegram bot with a custom agentic n8n layer, plus a Next.js
journal frontend) has been **deliberately retired**. Trying to remake Claude inside
Telegram was the mistake — the claude.ai app already is that interface. The system
that survived is better than what was envisioned:

- **claude.ai app** (desktop + mobile) connects to the Command Centre through the
  MCP connector — conversation capture, recall, task write-back, artifacts.
- **Claude Code** connects to the *same* MCP server — so coding sessions log to and
  read from the same memory.
- **iOS Shortcut voice notes** still flow in through the n8n webhook path.
- n8n survives only as the **ingest/extraction pipeline** (not as an agent).

### Retired (kept in repo/git history for reference only)
- Telegram bot + session handling (`Workflows/n8n workflows/telegram_*.json`)
- Hierarchical specialist-agent system (Memory/Entity/Strategy specialists)
- Next.js frontend + FastAPI journal app (`frontend/`, `backend/` app routes —
  the backend folder still matters, but only for `backend/app/mcp/`, the MCP server)
- `living_context` table (empty; was updated by the Telegram `/end` flow, which no longer runs
  — superseded 2026-07-16 by `current_state`, see below)

## Architecture (current)

```
CAPTURE                      PROCESS                     STORE                SERVE
claude.ai conversations ─┐   n8n pending-memory poller   Supabase             MCP server on Render
Claude Code sessions ────┼─► (every 2 min) ──► n8n       (Postgres+pgvector)  https://cais-mcp-server.onrender.com
  (log_memory via MCP)   │   ingest workflow: 7-way      memories, tasks,       ▲            ▲
iOS voice notes ─────────┘   extraction + embeddings     entities, decisions,   │            │
  (n8n webhook direct)                                   insights, artifacts  claude.ai   Claude Code
```

- **Supabase project:** `https://erwxszdcisyuyjmefvbj.supabase.co` (the URL in older
  docs, `wwqdkiphfpdczgmnxxrt`, is the *old* project — dead)
- **MCP server:** `backend/app/mcp/server.py`, deployed on Render (Starter instance,
  root dir `backend`, start `python -m app.mcp.server`), GitHub repo
  `zanemoore575/cais-command-centre` (private)
- **n8n:** `https://n8n-latest-rllq.onrender.com` — ingest workflow + pending
  poller + voice-note webhook + daily brief are the load-bearing workflows
- **MCP tools (22):** discover_database, get_current_state, get_tasks,
  get_recent_memories, search_memories, search_entities, get_memory,
  get_decisions, get_decisions_due_for_review, get_reflections,
  get_strategic_insights, get_customer_insights, log_memory,
  update_current_state, record_decision_outcome, create_task, complete_task,
  update_task, merge_tasks, archive_task, promote_task, snooze_task,
  save_artifact, search_artifacts, get_artifact
- **Live check-in page:** served by the MCP server at `/checkin?token=…`
  (token-gated, rendered from live data on every load; complete/snooze/dismiss
  and decision-review buttons write back through the agent_* RPCs)
- **Current-truth layer:** `current_state` table — one canonical row per topic,
  overwritten (not appended) on supersession. **Not yet seeded or confirmed
  live** — migration written 2026-07-16, awaiting a Supabase SQL Editor run.
- **Decision outcome loop:** `decisions` gained outcome tracking columns +
  a "due for review" selector surfaced on the check-in page and in the 6am
  brief. Same pending-migration caveat as above.

## Live data snapshot (2026-07-11)

| Table | Rows | Notes |
|---|---|---|
| memories | 442 | Apr 2025 → today; 303 claude_conversation, 65 shortcut_voice, 53 claude_task_creation, 13 artifact |
| tasks | 1,391 | **1,281 open** — see task-flood issue below |
| entities | 3,548 | 140 people, 221 companies, 433 projects, 237 tools |
| decisions | 1,152 | |
| reflections | 1,561 | |
| strategic_insights | 1,655 | |
| customer_insights | 449 | |
| themes | 313 | |
| artifacts | 13 | all `authored`, mostly Jake/Core Finance Phase 1 docs |

## Active workstreams (reconstructed from live memories, 17 Jun → 11 Jul)

1. **Jake / Core Finance — Phase 1 Intake Assistant.** The main event. Built,
   QA'd, and showcased live; Jake responded very positively (5 Jul) and pricing
   strategy was refined the same day. Since then: PII-free analytics layer (7 Jul),
   n8n bug fixes + repo hygiene (8 Jul), Phase 2 scoped as post-call brokerage
   admin automation (8 Jul), plain-English system guide (10 Jul), all Sonnet API
   calls upgraded to Claude Sonnet 5 (11 Jul). Open question: how the Salestrekker
   paste block gets used (task, 10 Jul).
2. **Moore AI Studios relaunch.** Instagram launch strategy + founder-intro
   carousel (5–9 Jul), evergreen content bank ("The chasing is the job" carousel
   built and QA'd 8–11 Jul), home-page copy rewrite pending (task, 4 Jul).
3. **Greenmachine chatbot** — final polish sweep pending (shipping info, task 2 Jul).
4. **Command Centre itself** — this doc refresh; daily check-in page (see below).

## Known issues (found auditing live DB, 2026-07-11)

1. **Task flood: 1,281 open tasks, ~989 created in June 2026** — the bulk history
   import + per-conversation extraction generated tasks faster than anything closes
   them. → **Fix built 2026-07-12** (bulk archive + `suggested` inbox + strict
   extraction prompt), pending `SETUP_CHECKIN_BRIEF.md` step 1/4.
2. **`agent_get_tasks` is hard-capped at `LIMIT 25`** and sorts stale February
   "immediate" tasks first, so the MCP get_tasks tool never surfaces fresh tasks.
   → **Fix built 2026-07-12** (`task_triage_migration.sql`), pending migration run.
3. **62 memories (14%) are invisible to recall tools**, which filter on
   `status='completed'`:
   - 26 stuck at `claimed` (23–29 Jun, all claude_conversation) — the poller claimed
     them but extraction never completed; a week of Claude conversations is
     un-recallable. Needs re-drive (reset to `pending`).
   - 33 at `indexed` (16 Jun–1 Jul, mostly shortcut_voice) — have embeddings and
     summaries but **zero extracted entities**, and are skipped by
     `get_recent_memories`/theme search. `indexed` is a status the docs never knew
     about; either the voice pipeline changed, or these should be flipped to
     `completed` after backfilling extraction.
   - 2 `transcribed` (23–24 Jun voice notes), 1 `extracting` (Dec 2025) — stuck.
4. **`living_context` is empty and orphaned** — its updater (Telegram `/end`) is
   retired. → **Fix built 2026-07-16**: `current_state` table replaces the concept
   (`current_state_migration.sql`), pending a live-DB run. `living_context` left
   in place, unused, not dropped.
5. **claude.ai MCP connector token expires** and requires manual re-auth in
   claude.ai connector settings (hit on 2026-07-11 from Claude Code). Worth checking
   whether the server can issue longer-lived/refresh tokens.
6. **Docs drift** — `Workflows/CLAUDE_CODE_CONTEXT.md` pointed at the dead Supabase
   project and described the retired Telegram architecture as primary (fixed
   2026-07-11, this refresh).

## Daily task system (built 2026-07-11/12, pending go-live)

Three layers, all coded and verified — manual go-live steps in `SETUP_CHECKIN_BRIEF.md`:

1. **Triage** (`Workflows/task_triage_migration.sql` + staged ingest changes):
   bulk-archives the June task flood (~1,238 rows, preserved not deleted), fixes
   `agent_get_tasks` (parameterised limit, useful sort, task's own created_at),
   adds `archived`/`suggested` statuses + snooze. New extracted tasks land as
   `suggested` (an inbox to keep/dismiss) with a much stricter extraction prompt
   (hard cap 5/conversation). Dedup also suppresses re-suggesting anything
   dismissed in the last 30 days.
2. **Live check-in** (`backend/app/mcp/checkin.py`): `/checkin` on the MCP
   server — live-rendered, mobile-friendly, light/dark; tick to complete
   (timestamped, filed to "Done today"), snooze 1d/1w, dismiss, keep/dismiss the
   suggested inbox. Token-gated (`CHECKIN_TOKEN`); attach `checkin.<domain>` to
   the Render service to put it behind the website. Verified 11/11 end-to-end
   against the live DB. The static generator (`daily-checkin/`) still works for
   snapshots/artifacts.
3. **6am daily brief** (`Workflows/n8n workflows/daily-brief-workflow.json`):
   n8n cron 6:00 Pacific/Auckland → pulls open + suggested tasks + recent
   memories → claude-sonnet-5 writes the plan (top 3 with why, board by client,
   inbox, watch items) → Telegram push (new bot, push-only) with a link to the
   live page.

## Current priorities

1. **Run the two Wave 1 migrations** (`Workflows/current_state_migration.sql`,
   `Workflows/decision_outcomes_migration.sql`) in the Supabase SQL Editor on
   `erwxszdcisyuyjmefvbj` — Claude Code has no DDL credentials for this project
   (only REST/service-key access), so this step needs Zane. Once run: seed
   `current_state` (~15–25 topics from the last ~60 days of memories) and
   verify end-to-end.
2. **Go-live checklist in `SETUP_CHECKIN_BRIEF.md`** — Supabase migration,
   Render env + deploy, custom domain, n8n imports, new Telegram bot.
3. Re-drive the 62 stuck/invisible memories and align on one terminal status
   (`completed`) so recall sees everything.
4. Re-authorize the claude.ai MCP connector (and Gmail/Calendar connectors).
5. Keep this doc updated with each progress change.

## Changelog

### 2026-07-16 — Wave 1: current-truth layer + decision outcome loop
- `current_state` table + `get_current_state`/`update_current_state` MCP tools —
  one canonical, overwritten-not-appended row per topic; supersession preserved
  in `history`. Replaces the orphaned `living_context` concept.
- `decisions` gains outcome tracking (`outcome`, `outcome_status`,
  `outcome_recorded_at`, `review_after`) + `record_decision_outcome`/
  `get_decisions_due_for_review` MCP tools — closes the loop on which past
  decisions were actually right.
- Check-in page: new "Decision review" card (both the live server page and the
  read-only static generator).
- Daily Brief n8n workflow: surfaces decisions due for review as brief item 6;
  removed an orphaned, disconnected `Telegram Trigger` node (dead cruft from
  the retired conversational-bot era) that was blocking workflow updates.
- **Pending**: both SQL migrations are written but not yet run against the live
  DB (see Current priorities #1) — `current_state` and decision-outcome tools
  will 404/degrade gracefully until then.

### 2026-07-12 — Task triage + live check-in + 6am daily brief (all three phases)
- **Triage:** `task_triage_migration.sql` (archived/suggested statuses, snooze,
  bulk archive of pre-17-Jun open tasks, `agent_get_tasks` limit/sort fix, new
  archive/promote/snooze RPCs, dedup covers suggested + recent dismissals);
  ingest workflow staged: `Insert Tasks` → `status='suggested'`, strict
  extraction prompt.
- **Live check-in:** new `/checkin` page + `/checkin/action` endpoint on the MCP
  server; three new MCP tools (archive_task, promote_task, snooze_task);
  `get_tasks` gains `limit` + new statuses. End-to-end tested locally against
  live Supabase (11/11 checks).
- **Daily brief:** new n8n workflow, 6am NZT, Sonnet 5-written plan pushed via
  a new Telegram bot (push-only — the Telegram *agent* stays retired).
- Decision: skipped Trello — second source of truth, sync tax; the tasks table
  + live page + push covers the same need with one datastore.

### 2026-07-11 — Doc refresh + daily check-in
- Rewrote LIVING_DOC/README/CLAUDE_CODE_CONTEXT against the live database after
  3.5 weeks of drift; recorded the Telegram→claude.ai pivot as permanent.
- Added `daily-checkin/generate_checkin.py` + first generated page.
- Audited pipeline health; logged the six known issues above.

### 2026-06-17 — Task write-back + artifact storage + hosting (condensed)
- **Write/ingest fix:** `log_memory` rows sat at `pending` forever; added the
  pending-memory poller (every 2 min) + `/webhook/ingest-pending` update-in-place
  entry point; fixed pgvector `JSON.stringify` embedding bug; backfilled embeddings.
  Any future writer just inserts with `status='pending'`.
- **MCP hosting:** moved off Mac+ngrok to Render (`cais-mcp-server.onrender.com`);
  repo to GitHub; Python 3.12 pin; pydantic unpin; secrets live only in Render env.
- **Task write-back:** complete/update/create/merge MCP tools; `priority`,
  `due_date`, `entity_name` columns; pg_trgm dedup-on-ingest (>0.45 similarity
  drops near-duplicates); rewrote extraction prompt for real urgency spread.
- **Artifact storage:** `artifacts` table + private Storage bucket; save (upsert,
  dedup-refusal), search, get tools; companion memory row embedded server-side
  (OpenAI text-embedding-3-small, needs OPENAI_API_KEY on the MCP server);
  authored docs store canonical markdown, uploads store binary.
- Full detail: git history 2026-06-17 and `Workflows/CLAUDE_CODE_CONTEXT.md` changelog.

## Notes
- Keep this file lean and current; update it first when progress changes.
- `README.md` is the landing page; `Workflows/CLAUDE_CODE_CONTEXT.md` is the deep
  technical reference (schema, RPCs, data flows).
- Old phase docs live in `archive/` — reference only.
