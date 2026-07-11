# Command Centre

Zane's persistent business memory and task system. Claude — in the claude.ai app
and in Claude Code — connects to it over MCP to capture conversations, recall
context, manage tasks, and save documents. Voice notes flow in from an iOS
Shortcut. Everything lands in one Supabase database with semantic search.

## Living project status
- `LIVING_DOC.md` is the primary source of truth for progress, priorities, and next steps.
- `Workflows/CLAUDE_CODE_CONTEXT.md` is the deep technical reference (schema, RPCs, data flows).

## Current architecture
- **Serve:** MCP server (`backend/app/mcp/`) hosted on Render at
  `https://cais-mcp-server.onrender.com` — used by both claude.ai and Claude Code
- **Store:** Supabase (Postgres + pgvector) — memories, tasks, entities, decisions,
  insights, artifacts
- **Process:** n8n ingest pipeline + pending-memory poller (extraction + embeddings)
- **Capture:** claude.ai conversations, Claude Code sessions (`log_memory`),
  iOS Shortcut voice notes
- **Daily check-in:** `daily-checkin/generate_checkin.py` renders a self-contained
  HTML status page from live data

## Retired (reference only — see `archive/` and git history)
The Telegram bot, the hierarchical n8n specialist-agent system, and the
Next.js/FastAPI journal frontend were the original build. They were retired in
favour of the claude.ai app + MCP: remaking Claude inside Telegram was the wrong
problem to solve. `frontend/` and the non-MCP parts of `backend/` are kept for
reference only.

## How this repo is organized
- `backend/app/mcp/` — the MCP server (the only deployed code)
- `Workflows/` — n8n workflow JSON, Supabase SQL migrations, import/backfill scripts
- `daily-checkin/` — daily check-in HTML generator
- `LIVING_DOC.md` — active project status and priorities
- `frontend/`, rest of `backend/` — retired journal app (reference)
- `archive/` — historical phase docs

## Update process
1. Update `LIVING_DOC.md` first when progress changes.
2. Sync `Workflows/CLAUDE_CODE_CONTEXT.md` when schema, tools, or pipelines change.
3. Keep this README short and stable.
