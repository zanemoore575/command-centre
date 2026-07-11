# Command Centre — Living Project Status

Updated: 2026-07-11 (full refresh against live database — docs had been frozen at 2026-06-17)

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
- `living_context` table (empty; was updated by the Telegram `/end` flow, which no longer runs)

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
- **n8n:** `https://n8n-service-8act.onrender.com` — ingest workflow + pending
  poller + voice-note webhook are the only load-bearing workflows left
- **MCP tools (18):** discover_database, get_tasks, get_recent_memories,
  search_memories, search_entities, get_memory, get_decisions, get_reflections,
  get_strategic_insights, get_customer_insights, log_memory, create_task,
  complete_task, update_task, merge_tasks, save_artifact, search_artifacts,
  get_artifact

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
   them. 965 of the newest 1,000 have no `entity_name`. `priority` is null on
   effectively every row (the 2026-06-17 "real priority extraction" writes urgency
   well, but priority never gets populated). Needs a triage strategy — probably a
   bulk archive of pre-June extractions + tighter extraction criteria.
2. **`agent_get_tasks` is hard-capped at `LIMIT 25`** (task_writeback_migration.sql:251)
   and sorts stale February "immediate" tasks first — so the MCP get_tasks tool
   never surfaces the 53 genuinely fresh July tasks. Fix: raise/parameterise limit,
   sort recent-first, or filter by created window.
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
   retired. Either delete it or re-home the concept (e.g. a periodic Claude-written
   summary memory).
5. **claude.ai MCP connector token expires** and requires manual re-auth in
   claude.ai connector settings (hit on 2026-07-11 from Claude Code). Worth checking
   whether the server can issue longer-lived/refresh tokens.
6. **Docs drift** — `Workflows/CLAUDE_CODE_CONTEXT.md` pointed at the dead Supabase
   project and described the retired Telegram architecture as primary (fixed
   2026-07-11, this refresh).

## Daily check-in page

`daily-checkin/generate_checkin.py` pulls live data (fresh open tasks, recent
memories, decisions, pipeline health) and renders a single self-contained HTML
page — no external requests, light/dark aware, hostable anywhere (drop it behind
the website, open it locally, or publish as a Claude artifact).

Run it:
```bash
python3 daily-checkin/generate_checkin.py     # writes daily-checkin/checkin.html
```
Credentials come from `backend/.env` (SUPABASE_URL / SUPABASE_SERVICE_KEY).
It is read-only by design — closing/editing tasks stays in claude.ai/Claude Code
via the MCP write-back tools. Options for automating the daily run: local cron,
a Claude Code scheduled routine, or a small Render cron job that pushes the HTML
to the website.

## Current priorities

1. Decide the task-triage strategy (bulk-archive June flood? tighten extraction?)
   and fix `agent_get_tasks` (limit + sort) so get_tasks becomes useful again.
2. Re-drive the 62 stuck/invisible memories and align on one terminal status
   (`completed`) so recall sees everything.
3. Make the daily check-in a habit: automate generation + decide hosting.
4. Re-authorize the claude.ai MCP connector (and Gmail/Calendar connectors).
5. Keep this doc updated with each progress change — it froze for 3.5 weeks while
   the system was its most active; the check-in page should help surface drift.

## Changelog

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
