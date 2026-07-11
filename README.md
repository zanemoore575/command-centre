# Command Centre

Personal AI system for capturing business context, extracting insights, and tracking progress with Claude-style phase-separated AI UX.

## Living project status
- This repository uses `LIVING_DOC.md` as the primary source of truth for progress, priorities, and next steps.
- For Claude Code helpers, use `Workflows/CLAUDE_CODE_CONTEXT.md` together with `LIVING_DOC.md`.

## Quick links
- Living doc: `LIVING_DOC.md`
- Setup guides: `SETUP_TUTORIAL.md`, `QUICK_START.md`, `EASIEST_SETUP.md`
- Backend docs: `backend/README.md`
- Frontend docs: `frontend/README.md`
- Claude / MCP connector: `README_MCP.md`
- Implementation reference: `archive/IMPLEMENTATION_SUMMARY.md`
- Archived phase docs: `archive/`

## Current high-level status
- Foundation: complete
- Journal entry system: complete
- AI entity extraction: complete
- Phase-separated chat streaming UX: complete
- People tracking / relationships: planned
- Dashboard / timeline: planned
- Claude Code / MCP integration: active — writes via `log_memory` and voice notes both flow through the same ingest pipeline (fixed 2026-06-17)
- MCP server hosting: live on Render (`https://cais-mcp-server.onrender.com`), no longer dependent on the local Mac/ngrok
- Task write-back: complete — Claude can close, edit, create, and merge tasks, with dedup-on-ingest and real priority extraction (2026-06-17)
- Artifact storage: complete — Claude can save, find, and recall documents (proposals, guides, uploads) it works on with Zane (2026-06-17)

## Architecture overview
- Backend: FastAPI + SQLAlchemy + Alembic
- Frontend: Next.js + TypeScript + Tailwind CSS
- AI: Anthropic Claude / Claude Sonnet 4.5
- Optional connector: Google OAuth + MCP for Claude integration

## How this repo is organized
- `backend/` — Python backend and API
- `frontend/` — React frontend and UI
- `Workflows/` — Claude Code / n8n context and workflow assets
- `LIVING_DOC.md` — active project status and priorities
- `README.md` — landing page and documentation index

## Update process
1. Update `LIVING_DOC.md` first when progress changes.
2. Keep the top-level `README.md` short and stable.
3. Use archived phase docs as reference only.
4. Sync `Workflows/CLAUDE_CODE_CONTEXT.md` when AI-related architecture changes.

## Notes
- This repo contains a lot of historical phase docs. They are useful as reference, but the living doc should be the current source of truth.
- If you want to check feature details or troubleshooting, follow the links above.
