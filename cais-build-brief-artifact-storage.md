# CAiS Command Centre — Build Brief (DRAFT, not yet built)
## Artifact storage: let Claude.ai save, find, and overwrite real files

*For: Claude.ai review/refinement before handing back to Claude Code to build.*
*Context: Part A (task write-back + dedup) is built, verified, and deployed. This is the next piece — "Out of scope" item flagged in the previous build brief, now being scoped properly.*

---

## The use case (Zane's words)

> "I can build a proposal in Claude.ai, we make edits and changes, and Claude uploads the finished PDF to Supabase. If I come back 3 weeks later and ask about it, it can find it, pull the original PDF, and then we can make changes again, and it could overwrite that existing PDF again — so the workflow could repeat without going back to a stale PDF."

Generalized: Claude.ai needs to save real files (.md, .txt, .pdf, .docx) that it creates or that Zane shares, tag them so they're findable later by topic/client/project, retrieve the exact original file on request (not a re-summarized version), and overwrite/update that same artifact in place when the work continues — without creating stale duplicates.

This is explicitly **not** just "save text Claude generated" — it's closer to a working-document store with an edit/save/recall/re-edit loop, where the saved object is the literal file (PDF bytes, not just extracted text).

---

## Decisions made so far (in conversation with Claude Code)

- **Storage backend**: Supabase Storage (new bucket), metadata in a new Postgres table — Supabase already hosts everything else in this system, and Render's filesystem is ephemeral (wiped on every deploy), so local disk was ruled out.
- **Versioning**: replace-only for v1 — overwriting an artifact replaces the stored file and updates its metadata row in place. No version history/rollback for now (deferred, not rejected).
- **Bytes transport**: leaning toward Claude.ai passing file bytes base64-encoded as an MCP tool argument (`save_artifact(title, file_base64, format, tags)`), since MCP tool calls can only carry text/JSON, not raw multipart uploads. Not fully settled — see open questions below.
- **Upload routing**: undecided between (a) MCP tool calls Supabase Storage directly, vs (b) MCP tool POSTs to an n8n webhook (mirroring how `log_memory` and the voice-note pipeline already work), with n8n doing the actual Storage write + metadata insert. Zane wants to keep n8n in the loop where it already owns this kind of plumbing, but the trigger should still originate from an MCP tool call inside Claude.ai — not a separate manual step outside the chat.

---

## What already exists (so this isn't designed in a vacuum)

- **MCP server** (`backend/app/mcp/server.py` + `supabase_tools.py`): FastMCP server on Render, Google OAuth, ~15 tools currently, all reading/writing Supabase via REST/RPC. Recently added task write-back tools (`complete_task`, `update_task`, `create_task`, `merge_tasks`) follow the same pattern: Python tool function → Supabase RPC → registered as `@mcp.tool()`.
- **n8n ingest pipeline** (`Workflows/n8n workflows/ingest-workflow.json`): webhook-triggered, does 7 parallel LLM extractions over a `memories` row, writes structured data to typed tables (`entities`, `decisions`, `tasks`, etc.). Has a sibling "pending poller" workflow that claims `status: pending` rows and re-triggers ingest — this is the same mechanism `log_memory` uses today (write `pending` row → poller fires → ingest runs).
- **No existing artifact/file infrastructure in Supabase** — no Storage bucket currently referenced anywhere in the schema or workflows, no `artifacts` table. This is a clean build.
- **A `file_storage_service.py` exists in `backend/app/services/`** but it's local-disk storage for an old, separate SQLite-backed journal app (different system entirely, not connected to the Supabase MCP/memories system) — not reusable as-is, mostly informative as prior art on filename/path handling.
- **PyPDF2 is installed in the venv but missing from `requirements.txt`** (would not survive a fresh Render build) — a loose end from that old journal app, relevant only if PDF text-extraction server-side becomes part of this build.

---

## Open questions for Claude.ai to weigh in on

1. **Bytes transport mechanics**: Is base64-in-a-tool-argument actually the right call for PDF-sized payloads (tens of KB to low MB) over MCP's Streamable HTTP transport? Any practical ceiling Claude.ai is aware of for tool-call argument size, or a better-suited approach (e.g. Claude.ai's file/artifact API uploading directly to a presigned Supabase Storage URL, with the MCP tool only receiving a reference)?
2. **Identity & overwrite matching**: How should "overwrite this existing artifact" be resolved? Options: (a) Claude must pass an explicit `artifact_id` it got from a prior `search_artifacts`/`get_artifact` call, (b) match by title/slug + entity tag with confirmation, (c) something else. Given Zane's flow ("pull the original, edit, overwrite"), should `save_artifact` require an explicit id for updates and only omit it for new artifacts — and should the tool refuse to silently create a near-duplicate if a same-titled artifact already exists (similar problem to the task dedup just solved)?
3. **Tagging/findability**: Should tags be free-text (LLM-assigned at save time, like `category` on tasks), linked to the existing `entity_name` pattern (so an artifact tied to "Jake" shows up alongside his other mentions/tasks), or both?
4. **PDF/docx generation**: When Claude.ai "builds a proposal" and produces a PDF, is that PDF generated client-side within Claude.ai itself (e.g. its document/artifact creation feature) such that Claude already holds well-formed PDF bytes to hand to a tool — or would the MCP server need to do markdown→PDF rendering server-side? This materially changes the build (no rendering code needed vs. needing a PDF generation library on the server).
5. **n8n vs direct-write**: Given Storage uploads are a single atomic operation (unlike the 7-way parallel LLM extraction `log_memory` triggers), is routing through n8n actually buying anything here, or would a direct Supabase Storage write from the MCP tool (consistent with how `complete_task`/`create_task` etc. already work) be simpler and just as correct? Leaning toward direct-write unless there's a concrete reason (e.g. wanting server-side virus scanning, format conversion, or thumbnail generation as a pipeline step later).
6. **Retrieval shape**: When Claude.ai calls `get_artifact`, should it get back the raw file bytes (base64) to reconstruct/re-render, extracted text (so Claude can read/discuss content but not literally re-attach the original PDF), or both — text for "what does it say" questions, raw bytes only when Zane explicitly wants the file back?

---

## Proposed shape (subject to the above being resolved)

**New Supabase Storage bucket**: `artifacts`

**New table**: `artifacts`
- `id` (UUID)
- `title` (TEXT) — also doubles as the human-facing identity for overwrite matching
- `format` (TEXT) — `pdf`, `docx`, `md`, `txt`
- `tags` (TEXT[] or JSONB)
- `entity_name` (TEXT, nullable) — same pattern as the new `tasks.entity_name` column
- `storage_path` (TEXT) — path within the bucket
- `extracted_text` (TEXT, nullable) — for search/recall without re-downloading the binary
- `memory_id` (BIGINT, nullable FK) — link back to the conversation/session that produced it, same pattern as `tasks.memory_id`
- `created_at`, `updated_at`

**New MCP tools** (exact shape depends on open questions above):
- `save_artifact(title, file_content, format, tags, entity_name, artifact_id=None)` — creates new, or overwrites in place if `artifact_id` given
- `search_artifacts(query)` — find by title/tag/entity, returns metadata + ids
- `get_artifact(artifact_id)` — returns the file (or its text) for Claude to read/re-attach

---

## Explicitly not deciding yet

Whether n8n is in the upload path, whether bytes go base64-in-tool-call or via a presigned-URL handoff, and the exact overwrite-matching UX are intentionally left open above — these are the points where Claude.ai's perspective (especially on what's mechanically possible/sane from its side of an MCP tool call, and what its own document-generation capability actually produces) should drive the answer before Claude Code commits to a schema or transport.
