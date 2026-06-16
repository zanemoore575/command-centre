# CAiS Command Centre — Living Project Status

Updated: 2026-06-16

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
