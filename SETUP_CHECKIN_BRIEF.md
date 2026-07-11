# Go-live checklist — task triage, live check-in, 6am daily brief

Built 2026-07-11/12. Everything is coded and verified locally; these are the manual
steps only you can do, **in this order**. Est. 30–40 minutes total.

## 1. Supabase — run the triage migration (5 min, do this first)

Supabase dashboard → SQL Editor → paste and run `Workflows/task_triage_migration.sql`.

What it does:
- Adds `archived_at` + `snoozed_until` columns and the `archived`/`suggested` statuses.
- **Bulk-archives the ~1,238 pre-17-June open tasks** (the June import flood). Nothing
  is deleted — `status='archived'`, resurrectable any time via `promote_task`.
- Fixes `agent_get_tasks`: real `limit_count` param (was hard-capped at 25),
  due-date/urgency-first sort with recent tasks winning (was surfacing February),
  and it now excludes snoozed tasks from 'open'.
- New RPCs: `agent_archive_task`, `agent_promote_task`, `agent_snooze_task`;
  dedup check now also covers `suggested` + recently-dismissed tasks.

Verify: `select status, count(*) from tasks group by 1;` → open should be ~43.

## 2. Render (MCP server) — env + deploy (10 min)

1. Render dashboard → `cais-mcp-server` → Environment → add:
   - `CHECKIN_TOKEN` = `***REMOVED-CHECKIN-TOKEN***` (same value as local
     `backend/.env`; rotate any time — it's the password for the check-in page)
2. Commit + push the repo changes (server code is in `backend/app/mcp/`) — Render
   auto-deploys from GitHub. Changed files: `server.py`, `supabase_tools.py`,
   new `checkin.py`.
3. Test: open `https://cais-mcp-server.onrender.com/checkin?token=***REMOVED-CHECKIN-TOKEN***`
   — you should see the live Daily Check-in with checkboxes. Tick a task; it
   completes in Supabase instantly (Claude sees it too).

New MCP tools also go live with this deploy: `archive_task`, `promote_task`,
`snooze_task`, and `get_tasks(status, limit)` now supports `suggested`/`snoozed`/`archived`.

## 3. Your domain (5 min, optional but recommended)

Your website is on Render, so the same pattern applies to the MCP service:
1. Render → `cais-mcp-server` → Settings → Custom Domains → add e.g.
   `checkin.<yourdomain>`.
2. At your DNS provider, add the CNAME Render shows you.
3. Add a second Render env var: `CHECKIN_PUBLIC_HOST` = `checkin.<yourdomain>`
   (lets the server accept the new Host header), then redeploy.
4. Your check-in is now `https://checkin.<yourdomain>/checkin?token=...` —
   bookmark it on your phone. (The token stays in the URL; treat the bookmark
   like a password.)

## 4. n8n — import the two workflow changes (10 min)

1. **Ingest workflow** (existing): re-import/update from
   `Workflows/n8n workflows/ingest-workflow.json`. Two changes:
   - `Insert Tasks` now writes `status='suggested'` — extracted tasks land in an
     inbox instead of polluting your open list.
   - `Extract Action Items` prompt is much stricter (hard cap 5/conversation,
     only explicit commitments; most conversations should produce 0–2).
2. **Daily brief** (new): import `Workflows/n8n workflows/daily-brief-workflow.json`.
   Runs 6:00am Pacific/Auckland. Before activating, follow the sticky note in
   the workflow:
   - Create the new bot with @BotFather → add token as an n8n Telegram credential
     → select it on the `Send Telegram Brief` node.
   - Message the bot once, get your chat id (@userinfobot), paste into Chat ID.
   - In `Format For Telegram`, replace `REPLACE_WITH_CHECKIN_TOKEN` with the
     CHECKIN_TOKEN (use the custom-domain URL from step 3 if you set it up).
   - Run it once manually to test, then activate.

The brief is Claude-written (claude-sonnet-5, matching the rest of your n8n stack):
top 3 for the day with reasoning, the rest of the board by client, the suggested-task
inbox to triage, and anything to watch — with a link to the live check-in page.
Push-only by design: acting on tasks happens on the page or in claude.ai.

## 5. Re-authorize connectors (2 min)

claude.ai → Settings → Connectors → re-auth **CAiS Command Centre** (token expired
2026-07-11; Claude Code fell back to direct Supabase REST). Gmail + Calendar also
pending if you want them.

## Daily flow once live

6:00am — Telegram brief lands: today's plan, written from live data.
Tap through — live check-in page: tick done ✓, snooze (1d/1w), dismiss ✕,
keep/dismiss inbox suggestions. Everything writes back to Supabase instantly.
During the day — work with Claude as usual; complete/create/archive tasks
conversationally. The page and the brief always reflect the same live state.

## Rollback notes

- Bulk archive: `update tasks set status='open', archived_at=null where status='archived' and archived_at >= '2026-07-11';`
- Suggested-status ingest: remove the `status` field from the `Insert Tasks` node.
- Check-in page: remove `CHECKIN_TOKEN` from Render env → routes return 503.
