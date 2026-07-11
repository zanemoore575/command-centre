"""
Live daily check-in page, served by the MCP server.

GET  /checkin?token=...   — the page, rendered from live Supabase data on every load
POST /checkin/action      — {token, task_id, action, until?} → complete / archive /
                            promote / snooze via the agent_* RPCs

Auth: CHECKIN_TOKEN env var (unset → routes return 503). The token gates a
personal read/act page, not MCP OAuth — keep the URL private, serve over HTTPS.
"""

import hmac
import html
import json
import os
import re
from collections import Counter
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response

from app.mcp.supabase_tools import _rest, _rpc

_TZ = ZoneInfo(os.environ.get("CHECKIN_TZ", "Pacific/Auckland"))
_TOKEN = os.environ.get("CHECKIN_TOKEN", "")

# Tasks created before this are the pre-write-back backlog: counted, never listed.
FRESH_CUTOFF = "2026-06-17"

WORKSTREAMS = [
    ("Jake · Core Finance", re.compile(r"jake|core finance|intake assistant|salestrekker|broker", re.I)),
    ("Greenmachine", re.compile(r"greenmachine|green machine", re.I)),
    ("Moore AI Studios", re.compile(r"moore ai|carousel|instagram|founder.intro|home ?page|content bank", re.I)),
    ("Command Centre", re.compile(r"command centre|command center|mcp|supabase|check.?in|daily brief", re.I)),
]
ENTITY_MAP = {
    "jake": "Jake · Core Finance", "core finance": "Jake · Core Finance",
    "greenmachine": "Greenmachine", "moore ai studios": "Moore AI Studios",
}
URGENCY_LABEL = {"immediate": "now", "this_week": "this week", "soon": "soon", "someday": "someday"}
URGENCY_ORDER = {"immediate": 0, "this_week": 1, "soon": 2, "someday": 3}
SOURCE_LABEL = {
    "claude_conversation": "claude.ai", "shortcut_voice": "voice note",
    "claude_task_creation": "task log", "artifact": "artifact",
}
STATUS_NOTES = {
    "completed": ("good", "fully processed, visible to recall"),
    "indexed": ("warn", "embedded but no extraction — invisible to recall tools"),
    "claimed": ("crit", "claimed by poller, extraction never finished — re-drive"),
    "transcribed": ("warn", "stuck mid-pipeline"),
    "extracting": ("warn", "stuck mid-pipeline"),
    "pending": ("warn", "awaiting poller pickup"),
}

ACTIONS = {
    "complete": ("agent_complete_task", lambda tid, until: {"target_task_id": tid}),
    "archive": ("agent_archive_task", lambda tid, until: {"target_task_id": tid}),
    "promote": ("agent_promote_task", lambda tid, until: {"target_task_id": tid}),
    "snooze": ("agent_snooze_task", lambda tid, until: {"target_task_id": tid, "until_date": until}),
}

# Small dot before each workstream heading, so multiple clients read apart at a glance.
WORKSTREAM_SLUG = {
    "Jake · Core Finance": "g-jake", "Greenmachine": "g-green",
    "Moore AI Studios": "g-moore", "Command Centre": "g-cmd", "General": "g-general",
}

# Moore AI Studios emblem, inlined so the page stays a single self-contained document.
EMBLEM = (
    '<svg class="emblem" viewBox="0 0 454 452" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
    '<path d="M226.616 3.69434C349.741 3.69457 449.537 103.234 449.537 226C449.537 348.766 349.741 448.305 226.616 448.306C103.491 448.306 3.69434 348.766 3.69434 226C3.69434 103.234 103.491 3.69434 226.616 3.69434Z" fill="#F7F3EA" stroke="black" stroke-width="7.38965"/>'
    '<path d="M160.725 319.602H189.052L264.796 201.984L325.76 319.602H351.624L280.191 177.967V170.578V136.708L208.142 245.706L99.7603 138.556V319.602H123.777V206.91V194.594L197.057 264.796L160.725 319.602Z" fill="black" stroke="black" stroke-width="1.23161"/>'
    '<path d="M161.656 320.218H149.235L185.257 264.796L124.392 204.447V193.362L197.057 264.796L161.656 320.218Z" fill="#0057A4"/>'
    '<path d="M197.673 320.218H189.668L264.796 201.984L325.76 320.218H315.907L263.564 217.995L197.673 320.218Z" fill="#F2C230"/>'
    '<path d="M339.308 165.651V276.496L315.907 232.774V165.651H339.308Z" fill="black" stroke="black" stroke-width="1.23161"/>'
    '<path d="M344.85 134.245C344.85 143.768 337.13 151.488 327.608 151.488C318.085 151.488 310.365 143.768 310.365 134.245C310.365 124.722 318.085 117.003 327.608 117.003C337.13 117.003 344.85 124.722 344.85 134.245Z" fill="#111111"/>'
    '<rect x="192" y="265" width="148" height="8" fill="#0057A4"/>'
    '<rect x="186" y="273" width="154" height="8" fill="#F2C230"/>'
    '</svg>'
)


def _authorized(supplied: str) -> bool:
    return bool(_TOKEN) and hmac.compare_digest(supplied or "", _TOKEN)


def esc(s):
    return html.escape(str(s or ""), quote=True)


def _workstream(task) -> str:
    entity = (task.get("entity_name") or "").lower()
    for k, v in ENTITY_MAP.items():
        if k in entity:
            return v
    text = f"{task.get('task_text', '')} {task.get('context', '')}"
    for name, rx in WORKSTREAMS:
        if rx.search(text):
            return name
    return "General"


def _days_ago(iso: str, today) -> str:
    d = datetime.strptime(iso[:10], "%Y-%m-%d").date()
    n = (today - d).days
    return "today" if n == 0 else ("yesterday" if n == 1 else f"{n}d ago")


def _get_tasks(status: str, limit: int) -> list:
    """agent_get_tasks with limit; falls back to the pre-migration signature."""
    try:
        return _rpc("agent_get_tasks", {"task_status": status, "limit_count": limit})
    except httpx.HTTPStatusError:
        return _rpc("agent_get_tasks", {"task_status": status})


def _fetch():
    now = datetime.now(_TZ)
    today = now.date()
    week_ago = (today - timedelta(days=7)).isoformat()
    day_start_utc = now.replace(hour=0, minute=0, second=0, microsecond=0) \
                       .astimezone(ZoneInfo("UTC")).isoformat()

    open_tasks = [t for t in _get_tasks("open", 150)
                  if (t.get("created_date") or "9999") >= FRESH_CUTOFF]
    try:
        suggested = _get_tasks("suggested", 30)
    except httpx.HTTPStatusError:
        suggested = []
    total_open = len(_rest("tasks", {"select": "id", "status": "eq.open", "limit": "2000"}))
    done_today = _rest("tasks", {
        "select": "id,task,completed_at",
        "status": "eq.completed", "completed_at": f"gte.{day_start_utc}",
        "order": "completed_at.desc",
    })
    mem_meta = _rest("memories", {"select": "id,status,created_at", "limit": "2000"})
    recent = [m for m in _rpc("agent_get_recent_memories", {"limit_count": 30})
              if m["created_at"] >= week_ago]

    return {
        "now": now, "today": today,
        "open": open_tasks, "suggested": suggested,
        "backlog": max(total_open - len(open_tasks), 0),
        "done_today": done_today,
        "mem_status": Counter(m["status"] for m in mem_meta),
        "mem_week": sum(1 for m in mem_meta if m["created_at"] >= week_ago),
        "recent": recent,
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _task_row(t, today, kind="open") -> str:
    tid = esc(t["task_id"])
    u = t.get("urgency") if t.get("urgency") in URGENCY_LABEL else "soon"
    dd = t.get("due_date")
    overdue = " overdue" if dd and dd < today.isoformat() else ""
    due = f'<span class="due{overdue}">due {esc(dd)}</span>' if dd else ""
    meta = f'{esc(t.get("category") or "")} · {_days_ago(t.get("created_date") or "2026-01-01", today)} {due}'
    if kind == "suggested":
        buttons = (f'<button class="act keep" data-action="promote" data-id="{tid}">Keep</button>'
                   f'<button class="act dismiss" data-action="archive" data-id="{tid}">Dismiss</button>')
        lead = '<span class="chip inbox-chip">new</span>'
    else:
        buttons = (f'<button class="act snz" data-action="snooze" data-days="1" data-id="{tid}" title="Snooze until tomorrow">1d</button>'
                   f'<button class="act snz" data-action="snooze" data-days="7" data-id="{tid}" title="Snooze a week">1w</button>'
                   f'<button class="act dismiss" data-action="archive" data-id="{tid}" title="Dismiss — archive this task">✕</button>')
        lead = (f'<button class="tick" data-action="complete" data-id="{tid}" '
                f'title="Mark done" aria-label="Mark done"></button>'
                f'<span class="chip u-{u}">{URGENCY_LABEL[u]}</span>')
    return (f'<div class="task" id="task-{tid}">{lead}'
            f'<div class="task-body"><p>{esc(t["task_text"])}</p>'
            f'<span class="meta">{meta}</span></div>'
            f'<div class="acts">{buttons}</div></div>')


def _grouped(tasks, today) -> str:
    groups = {}
    for t in tasks:
        groups.setdefault(_workstream(t), []).append(t)
    order = [n for n, _ in WORKSTREAMS] + ["General"]
    out = []
    for name in sorted(groups, key=lambda n: order.index(n) if n in order else 99):
        rows = sorted(groups[name],
                      key=lambda t: (URGENCY_ORDER.get(t.get("urgency"), 9),
                                     t.get("due_date") or "9999",
                                     t.get("created_date") or ""))
        slug = WORKSTREAM_SLUG.get(name, "g-general")
        out.append(f'<h3 class="group {slug}">{esc(name)} <span class="count">{len(rows)}</span></h3>')
        out.extend(_task_row(t, today) for t in rows)
    return "\n".join(out)


def render_page(d) -> str:
    today = d["today"]
    nice_date = d["now"].strftime("%A %-d %B %Y")
    focus = [t for t in d["open"] if t.get("urgency") in ("immediate", "this_week")
             or (t.get("due_date") or "9999") <= (today + timedelta(days=2)).isoformat()]
    focus_ids = {t["task_id"] for t in focus}
    later = [t for t in d["open"] if t["task_id"] not in focus_ids]
    stuck = sum(v for k, v in d["mem_status"].items() if k != "completed")
    stuck_cls = "crit" if stuck else "good"

    suggested_html = ""
    if d["suggested"]:
        rows = "\n".join(_task_row(t, today, kind="suggested") for t in d["suggested"])
        suggested_html = (f'<section><div class="eyebrow">Inbox — suggested from conversations · '
                          f'<span id="inbox-n">{len(d["suggested"])}</span> to triage</div>{rows}</section>')

    done_rows = "".join(
        f'<div class="done-row"><span class="done-tick">✓</span><p>{esc(t["task"])}</p>'
        f'<span class="meta">{esc((t.get("completed_at") or "")[11:16])} UTC</span></div>'
        for t in d["done_today"])

    mem_rows = "".join(
        f'<div class="mem"><span class="mem-date">{esc(m["created_at"][5:10])}</span>'
        f'<span class="chip src">{esc(SOURCE_LABEL.get(m["source"], m["source"]))}</span>'
        f'<p>{esc(((m.get("main_theme") or m.get("summary") or "(processing)").splitlines()[0])[:160])}</p></div>'
        for m in d["recent"])

    health_rows = "".join(
        f'<div class="health-row"><span class="dot {STATUS_NOTES.get(s, ("warn",))[0]}"></span>'
        f'<span class="h-status">{esc(s)}</span><span class="h-n">{n}</span>'
        f'<span class="h-note">{esc(STATUS_NOTES.get(s, ("", "unknown status"))[1])}</span></div>'
        for s, n in sorted(d["mem_status"].items(), key=lambda kv: -kv[1]))

    generated = d["now"].strftime("%-d %b %Y, %-I:%M %p %Z")

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Daily Check-in — Command Centre</title>
<style>
:root {{
  --bg:#F7F1E8; --surface:#FFFFFF; --ink:#111827; --muted:#5B6775; --line:#E7DDCC;
  --accent:#0F4E8A; --accent-ink:#0C3D6E; --accent-soft:#E3EAF4;
  --gold:#F2C230; --gold-soft:#FBEFC9;
  --warn:#9A5B0B; --warn-soft:#F5ECDD; --crit:#B3382D; --crit-soft:#F7E7E4;
  --good:#1F7A44; --good-soft:#E4F1E8;
}}
@media (prefers-color-scheme: dark) {{ :root {{
  --bg:#0E1621; --surface:#16202D; --ink:#E8ECF1; --muted:#93A2B4; --line:#27313F;
  --accent:#4F97DA; --accent-ink:#88B9EC; --accent-soft:#182B3E;
  --gold:#F2C230; --gold-soft:#33290F;
  --warn:#DFA35C; --warn-soft:#31281A; --crit:#E06B5F; --crit-soft:#36201D;
  --good:#5FB97D; --good-soft:#1C3024;
}} }}
* {{ box-sizing:border-box; margin:0; }}
body {{ background:var(--bg); color:var(--ink);
  font-family:"Avenir Next","Seravek",ui-sans-serif,system-ui,sans-serif;
  line-height:1.5; -webkit-font-smoothing:antialiased; }}
.wrap {{ max-width:860px; margin:0 auto; padding:36px 20px 64px; }}
.masthead {{ display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;
  border-bottom:3px solid var(--accent); padding-bottom:14px; position:relative; }}
.masthead::after {{ content:""; position:absolute; left:0; right:0; bottom:-6px; height:3px; background:var(--gold); border-radius:2px; }}
.brand {{ display:flex; align-items:center; gap:12px; }}
.emblem {{ width:38px; height:38px; flex:none; }}
.masthead h1 {{ font-size:24px; font-weight:600; letter-spacing:-0.01em; }}
.masthead .date {{ font-size:14px; color:var(--muted); }}
.kicker {{ font-size:11px; text-transform:uppercase; letter-spacing:0.1em; color:var(--accent-ink); font-weight:600; margin-bottom:3px; }}
.stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; margin:20px 0 4px; }}
.stat {{ background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:12px 14px; }}
.stat .label {{ font-size:10.5px; text-transform:uppercase; letter-spacing:0.08em; color:var(--muted); font-weight:600; }}
.stat .n {{ font-size:28px; font-weight:600; font-variant-numeric:tabular-nums; }}
.stat .sub {{ font-size:11.5px; color:var(--muted); }}
.stat.crit .n {{ color:var(--crit); }} .stat.good .n {{ color:var(--good); }}
section {{ margin-top:32px; }}
.eyebrow {{ font-size:11.5px; text-transform:uppercase; letter-spacing:0.1em; color:var(--muted); font-weight:600;
  border-bottom:1px solid var(--line); padding-bottom:6px; margin-bottom:10px; }}
.eyebrow.hot {{ border-bottom-color:var(--gold); color:var(--accent-ink); }}
.group {{ font-size:13.5px; font-weight:600; margin:16px 0 4px; color:var(--accent-ink); display:flex; align-items:center; gap:7px; }}
.group::before {{ content:""; width:8px; height:8px; border-radius:50%; background:var(--dot,var(--accent)); flex:none; }}
.g-jake {{ --dot:var(--accent); }} .g-green {{ --dot:var(--good); }} .g-moore {{ --dot:var(--gold); }} .g-cmd {{ --dot:var(--muted); }} .g-general {{ --dot:var(--muted); }}
.group .count {{ color:var(--muted); font-weight:500; font-size:12px; }}
.task {{ display:flex; gap:10px; padding:10px 0; border-bottom:1px solid var(--line); align-items:flex-start; }}
.task.gone {{ opacity:0; transform:translateX(12px); transition:opacity .3s, transform .3s; }}
.task p {{ font-size:14.5px; }}
.task .meta, .due, .done-row .meta {{ font-size:11.5px; color:var(--muted); font-family:ui-monospace,Menlo,monospace; }}
.due.overdue {{ color:var(--crit); font-weight:600; }}
.task-body {{ flex:1; min-width:0; }}
.tick {{ flex:none; width:24px; height:24px; margin-top:2px; border-radius:50%;
  border:2px solid var(--accent); background:transparent; cursor:pointer; }}
.tick:hover, .tick:focus-visible {{ background:var(--accent-soft); outline:2px solid var(--accent); outline-offset:2px; }}
.chip {{ flex:none; font-size:10.5px; font-weight:600; padding:2px 8px; border-radius:99px; margin-top:3px;
  letter-spacing:0.02em; white-space:nowrap; }}
.u-immediate {{ background:var(--accent); color:var(--bg); }}
.u-this_week {{ background:var(--accent-soft); color:var(--accent-ink); }}
.u-soon {{ border:1px solid var(--line); color:var(--muted); background:var(--surface); }}
.u-someday {{ color:var(--muted); border:1px dashed var(--line); }}
.inbox-chip {{ background:var(--warn-soft); color:var(--warn); }}
.chip.src {{ background:var(--surface); border:1px solid var(--line); color:var(--muted); font-weight:500; }}
.acts {{ display:flex; gap:6px; flex:none; }}
.act {{ font:inherit; font-size:12px; font-weight:600; padding:6px 11px; min-height:34px; border-radius:7px;
  border:1px solid var(--line); background:var(--surface); color:var(--muted); cursor:pointer; }}
.act:hover, .act:focus-visible {{ border-color:var(--accent); color:var(--accent-ink); outline:none; }}
.act.keep {{ border-color:var(--accent); color:var(--accent-ink); background:var(--accent-soft); }}
.act.dismiss:hover {{ border-color:var(--crit); color:var(--crit); }}
.done-row {{ display:flex; gap:10px; align-items:baseline; padding:7px 0; border-bottom:1px solid var(--line); }}
.done-row:last-child {{ border-bottom:none; }}
.done-row p {{ font-size:14px; color:var(--muted); text-decoration:line-through; flex:1; }}
.done-tick {{ color:var(--good); font-weight:700; }}
details {{ margin-top:8px; }} summary {{ cursor:pointer; font-size:13.5px; color:var(--muted); }}
.callout {{ background:var(--surface); border:1px solid var(--line); border-left:3px solid var(--warn);
  border-radius:8px; padding:11px 14px; font-size:13.5px; color:var(--muted); margin-top:14px; }}
.callout b {{ color:var(--ink); }}
.mem {{ display:flex; gap:10px; align-items:baseline; padding:7px 0; border-bottom:1px solid var(--line); }}
.mem:last-child {{ border-bottom:none; }}
.mem-date {{ font-family:ui-monospace,Menlo,monospace; font-size:11.5px; color:var(--muted); flex:none; }}
.mem p {{ font-size:13.5px; }}
.health {{ background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:4px 14px; }}
.health-row {{ display:flex; gap:10px; align-items:baseline; padding:8px 0; border-bottom:1px solid var(--line); font-size:13.5px; }}
.health-row:last-child {{ border-bottom:none; }}
.dot {{ width:9px; height:9px; border-radius:50%; flex:none; align-self:center; }}
.dot.good {{ background:var(--good); }} .dot.warn {{ background:var(--warn); }} .dot.crit {{ background:var(--crit); }}
.h-status {{ font-family:ui-monospace,Menlo,monospace; font-size:12.5px; min-width:92px; }}
.h-n {{ font-weight:600; font-variant-numeric:tabular-nums; min-width:36px; text-align:right; }}
.h-note {{ color:var(--muted); font-size:12.5px; }}
footer {{ margin-top:40px; padding-top:12px; border-top:1px solid var(--line);
  font-size:11.5px; color:var(--muted); font-family:ui-monospace,Menlo,monospace; }}
footer p {{ margin-bottom:4px; }}
#toast {{ position:fixed; bottom:20px; left:50%; transform:translateX(-50%); background:var(--ink); color:var(--bg);
  padding:9px 18px; border-radius:9px; font-size:13.5px; opacity:0; pointer-events:none; transition:opacity .25s; }}
#toast.show {{ opacity:1; }}
@media (prefers-reduced-motion: reduce) {{ .task.gone, #toast {{ transition:none; }} }}
</style>
</head>
<body>
<div class="wrap">
  <header class="masthead">
    <div class="brand">
      {EMBLEM}
      <div>
        <div class="kicker">Command Centre · Moore AI Studios</div>
        <h1>Daily Check-in</h1>
      </div>
    </div>
    <span class="date">{nice_date}</span>
  </header>

  <div class="stats">
    <div class="stat"><div class="label">Focus today</div><div class="n" id="stat-focus">{len(focus)}</div>
      <div class="sub">due now or this week</div></div>
    <div class="stat"><div class="label">Inbox</div><div class="n" id="stat-inbox">{len(d["suggested"])}</div>
      <div class="sub">suggested, to triage</div></div>
    <div class="stat good"><div class="label">Done today</div><div class="n" id="stat-done">{len(d["done_today"])}</div>
      <div class="sub">{d["mem_week"]} memories this week</div></div>
    <div class="stat {stuck_cls}"><div class="label">Stuck in pipeline</div><div class="n">{stuck}</div>
      <div class="sub">memories not fully processed</div></div>
  </div>

  {suggested_html}

  <section>
    <div class="eyebrow hot">Today’s focus · <span id="focus-n">{len(focus)}</span></div>
    <div id="focus-list">{_grouped(focus, today) or '<p class="callout">Nothing urgent on the board. Pull something up from the later list, or enjoy it.</p>'}</div>
  </section>

  <section>
    <div class="eyebrow">Coming up · {len(later)}</div>
    <details {"open" if len(later) <= 12 else ""}><summary>Show {len(later)} tasks with no near deadline</summary>
    {_grouped(later, today)}</details>
    <div class="callout"><b>{d["backlog"]:,} older open tasks</b> remain hidden here (pre-{FRESH_CUTOFF} backlog).
      Run task_triage_migration.sql to archive them, or ask Claude to triage.</div>
  </section>

  <section>
    <div class="eyebrow">Done today ✓</div>
    <div id="done-list">{done_rows or '<p class="callout" id="done-empty">Nothing checked off yet — the day is young.</p>'}</div>
  </section>

  <section>
    <div class="eyebrow">This week in memory · {len(d["recent"])} captured</div>
    {mem_rows}
  </section>

  <section>
    <div class="eyebrow">Pipeline health · {sum(d["mem_status"].values())} memories total</div>
    <div class="health">{health_rows}</div>
  </section>

  <footer>
    <p>Live from Supabase · rendered {generated} · refresh for latest.</p>
    <p>Checking a box completes the task in the Command Centre itself — Claude sees it too.</p>
  </footer>
</div>
<div id="toast" role="status"></div>
<script>
(function () {{
  var token = new URLSearchParams(location.search).get("token") || "";
  var toastEl = document.getElementById("toast"), toastTimer;
  function toast(msg) {{
    toastEl.textContent = msg; toastEl.classList.add("show");
    clearTimeout(toastTimer); toastTimer = setTimeout(function () {{ toastEl.classList.remove("show"); }}, 2600);
  }}
  function bump(id, delta) {{
    var el = document.getElementById(id);
    if (el) el.textContent = Math.max(0, parseInt(el.textContent || "0", 10) + delta);
  }}
  document.addEventListener("click", function (e) {{
    var btn = e.target.closest("[data-action]");
    if (!btn) return;
    var row = document.getElementById("task-" + btn.dataset.id);
    var action = btn.dataset.action;
    var body = {{ token: token, task_id: btn.dataset.id, action: action }};
    if (action === "snooze") {{
      var until = new Date();
      until.setDate(until.getDate() + parseInt(btn.dataset.days, 10));
      body.until = until.toISOString().slice(0, 10);
    }}
    row.querySelectorAll("button").forEach(function (b) {{ b.disabled = true; }});
    fetch("checkin/action", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify(body)
    }}).then(function (r) {{ return r.json().then(function (j) {{ return {{ ok: r.ok, j: j }}; }}); }})
      .then(function (res) {{
        if (!res.ok) throw new Error(res.j.error || "failed");
        row.classList.add("gone");
        setTimeout(function () {{ row.remove(); }}, 320);
        if (action === "complete") {{
          bump("stat-done", 1); bump("stat-focus", -1); bump("focus-n", -1);
          var done = document.getElementById("done-list");
          var empty = document.getElementById("done-empty");
          if (empty) empty.remove();
          var p = row.querySelector(".task-body p").textContent;
          done.insertAdjacentHTML("afterbegin",
            '<div class="done-row"><span class="done-tick">✓</span><p></p><span class="meta">just now</span></div>');
          done.firstChild.querySelector("p").textContent = p;
          toast("Done ✓ — filed and timestamped");
        }} else if (action === "promote") {{
          bump("stat-inbox", -1); bump("inbox-n", -1);
          toast("Kept — now on the open list (refresh to see it placed)");
        }} else if (action === "archive") {{
          if (row.querySelector(".inbox-chip")) {{ bump("stat-inbox", -1); bump("inbox-n", -1); }}
          toast("Dismissed — archived, not deleted");
        }} else {{
          toast("Snoozed until " + body.until);
        }}
      }})
      .catch(function (err) {{
        row.querySelectorAll("button").forEach(function (b) {{ b.disabled = false; }});
        toast("Couldn’t save: " + err.message);
      }});
  }});
}})();
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Route handlers (registered in server.py via @mcp.custom_route)
# ---------------------------------------------------------------------------

async def checkin_page(request: Request) -> Response:
    if not _TOKEN:
        return Response("Check-in disabled: set CHECKIN_TOKEN.", status_code=503, media_type="text/plain")
    if not _authorized(request.query_params.get("token", "")):
        return Response("Not authorized.", status_code=403, media_type="text/plain")
    page = render_page(_fetch())
    return HTMLResponse(page, headers={"Cache-Control": "no-store"})


async def checkin_action(request: Request) -> Response:
    if not _TOKEN:
        return JSONResponse({"error": "check-in disabled"}, status_code=503)
    try:
        body = json.loads(await request.body())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JSONResponse({"error": "invalid JSON"}, status_code=400)
    if not _authorized(body.get("token", "")):
        return JSONResponse({"error": "not authorized"}, status_code=403)

    action = body.get("action")
    task_id = body.get("task_id", "")
    if action not in ACTIONS:
        return JSONResponse({"error": f"unknown action '{action}'"}, status_code=400)
    if action == "snooze" and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", body.get("until") or ""):
        return JSONResponse({"error": "snooze needs until=YYYY-MM-DD"}, status_code=400)

    fn, params = ACTIONS[action]
    try:
        result = _rpc(fn, params(task_id, body.get("until")))
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return JSONResponse(
                {"error": f"{fn} not found — run task_triage_migration.sql in Supabase first"},
                status_code=501)
        return JSONResponse({"error": f"database error ({e.response.status_code})"}, status_code=502)
    if not result:
        return JSONResponse({"error": "task not found"}, status_code=404)
    return JSONResponse({"ok": True, "task": result[0] if isinstance(result, list) else result})
