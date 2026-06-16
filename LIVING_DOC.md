# CAiS Command Centre — Living Project Status

Updated: 2026-06-17

## Purpose
- Capture business context in journal entries.
- Extract people, commitments, pain points, and insights automatically.
- Enable grounded question answering over the business history.
- Provide Claude Code-style phase-separated AI UX for transparent reasoning.

## Current status
- Foundation (backend + frontend scaffold) — complete
- Journal entry system — complete
- AI entity extraction — complete
- Phase-separated chat streaming UX — complete
- People tracking / relationship timeline — planned
- Dashboard / timeline visualization — planned
- Claude Code / MCP integration / docs sync — active
- MCP server hosting — migrated from local Mac + ngrok to Render (complete, 2026-06-17)

## What is complete
- FastAPI backend with PostgreSQL / optional SQLite support.
- Next.js frontend with journal CRUD and basic navigation.
- Claude-powered entity extraction pipeline for entries.
- Phase 1/2/3 streaming UI experience.
- Top-level docs cleanup plan and living status workflow.

## Current priorities
1. Confirm feature status and remove outdated phase-only docs.
2. Finish people tracking and relationship views.
3. Build dashboard timeline and progress visualizations.
4. Sync Claude Code project context and living docs.
5. Keep `LIVING_DOC.md` updated with each progress change.

## Next actions
- Review backend and frontend feature completeness.
- Archive old phase-specific notes if they are no longer the primary source.
- Add a short summary to `Workflows/CLAUDE_CODE_CONTEXT.md` for Claude Code helpers.
- Use this file as the source of truth for progress, scope, and next steps.

## How to use this doc with Claude Code
- `README.md` is the project landing page.
- `LIVING_DOC.md` is the active progress tracker.
- `Workflows/CLAUDE_CODE_CONTEXT.md` provides Claude Code-specific system context.
- When any progress or scope changes, update `LIVING_DOC.md` first.

## Important links
- Setup guides: `SETUP_TUTORIAL.md`, `QUICK_START.md`, `EASIEST_SETUP.md`
- Backend docs: `backend/README.md`
- Frontend docs: `frontend/README.md`
- MCP / Claude connector: `README_MCP.md`
- Claude Code context: `Workflows/CLAUDE_CODE_CONTEXT.md`
- Implementation reference: `archive/IMPLEMENTATION_SUMMARY.md`
- Archived docs: `archive/`

## Notes
- Keep this file lean and current.
- Preserve detailed phase or troubleshooting docs as reference, not as the primary status source.
- If the project direction changes, update the status, priorities, and next actions here.

## Archived docs
The root directory has been decluttered. Old phase-specific implementation and troubleshooting docs are now in `archive/`.

## Current issue summary
- The phase-separated UI is implemented and working.
- There is a current backend streaming issue: Claude API calls can block for 20-30 seconds, causing tool events to arrive in a burst instead of real time.
- The backend needs a streaming refactor to deliver true Claude Code-style phase streaming.

## Write/ingest path fix (2026-06-17)
- **Problem:** memories written via Claude's `log_memory` MCP tool (`backend/app/mcp/supabase_tools.py`) were inserted into Supabase with `status: pending` but nothing ever triggered the n8n extraction pipeline — only the voice-note path called the ingest webhook. Pending rows stayed unprocessed forever: no entities/decisions/themes extracted, no embedding, invisible to `get_recent_memories` and `search_memories`.
- **Fix (source-agnostic, DB-driven):**
  - New n8n workflow `Workflows/n8n workflows/pending-memory-poller-workflow.json` — runs every 2 minutes, selects `memories` where `status = 'pending'`, immediately flips each to `claimed` (avoids double-processing since n8n webhooks ack before the workflow finishes), then POSTs to a new `/webhook/ingest-pending` endpoint.
  - `Workflows/n8n workflows/ingest-workflow.json` — added a second entry point (`Webhook Pending` → `Update Memory To Extracting`) that updates the existing row in place instead of inserting a duplicate, then flows into the same extraction/embedding nodes the voice path already uses. The original `/webhook/ingest-conversation` path is untouched.
  - Also fixed a real embedding bug found along the way: the "Insert Embeddings" node was `JSON.stringify`-ing the embedding array before writing to the pgvector `embeddings` column; changed to pass the raw array, matching the working voice-path pattern.
  - Added `Workflows/backfill_embeddings.py` — one-time script to embed existing `completed` memories that had `embeddings: null`. Run once; not part of the ongoing pipeline.
- **Now true for any future write source:** anything inserted into `memories` with `status: pending` gets picked up automatically — no per-source code changes needed (e.g. `log_memory` itself didn't need to change).
- **Verified live (2026-06-17):** test memory 217 went `pending` → fully extracted (theme, entities, strategic insights) → embedded → returned by both `search_memories` and `get_recent_memories`. `search_memories("Jake")` confirmed returning 9 pre-existing memories. `discover_database` showed embeddings count (210) at parity with completed memories (202), up from ~2 before the fix.

## MCP server hosting (2026-06-17)
- Moved the MCP server (`backend/app/mcp/server.py`) off the local Mac + ngrok tunnel and onto **Render** as an always-on Web Service: `https://cais-mcp-server.onrender.com`.
- Repo is now on GitHub at `zanemoore575/cais-command-centre` (private) — required for Render's GitHub-based deploy.
- Code changes made to support hosting:
  - Server now reads `PORT` (Render-injected) ahead of `MCP_PUBLIC_URL`/`MCP_PORT`, and defaults host to `0.0.0.0`.
  - Added a `/health` route for Render's health check.
  - Pinned `backend/runtime.txt` to `python-3.12.7` (also set as `PYTHON_VERSION` env var in Render — needed because pydantic-core had no prebuilt wheel for the Python 3.14 Render defaulted to).
  - Unpinned `pydantic==2.10.2` to `pydantic>=2.11.0` in `backend/requirements.txt` — the old pin conflicted with `mcp>=1.27`'s requirement of `pydantic>=2.11.0`.
- Render config: Root Directory `backend`, Build Command `pip install -r requirements.txt`, Start Command `python -m app.mcp.server`, Starter instance (not Free — avoids cold-start spin-down), single instance (no autoscaling, since OAuth/session state is in-memory).
- Secrets (`SUPABASE_SERVICE_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_CLIENT_SECRET`, etc.) live only in Render's Environment tab, never committed — `backend/.env` stays gitignored.
- Google OAuth client's authorized redirect URIs now include `https://cais-mcp-server.onrender.com/oauth/google/callback` alongside the old ngrok one.
- claude.ai connector repointed at `https://cais-mcp-server.onrender.com/mcp`; verified `get_recent_memories`, `get_tasks`, `search_memories` all working end-to-end.
- Local MCP server process and ngrok tunnel have been stopped — the Mac is no longer required for the MCP connector to work.
- Known item noted at the time: `search_memories` sometimes appeared to be missing entries. Root cause turned out to be the write/ingest path, not credentials — see "Write/ingest path fix (2026-06-17)" above.
