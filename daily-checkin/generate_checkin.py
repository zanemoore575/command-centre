#!/usr/bin/env python3
"""Generate the daily check-in page from live Command Centre data.

Pulls open tasks (write-back era only), recent memories, and pipeline health
straight from Supabase and renders a single self-contained HTML page.

Usage:
    python3 daily-checkin/generate_checkin.py

Outputs (into daily-checkin/):
    checkin.html          — full standalone document (host anywhere / open locally)
    checkin-artifact.html — body-only variant for publishing as a Claude artifact

Credentials: SUPABASE_URL / SUPABASE_SERVICE_KEY from the environment, falling
back to backend/.env. Read-only by design — task write-back stays in claude.ai /
Claude Code via the MCP tools.
"""

import html
import json
import os
import re
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = Path(__file__).resolve().parent

# Tasks created before this date are the pre-write-back backlog (June 2026 bulk
# import flood + older auto-extractions). They are counted, not listed.
FRESH_CUTOFF = "2026-06-17"


def load_env():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not (url and key):
        env_file = REPO_ROOT / "backend" / ".env"
        for line in env_file.read_text().splitlines():
            if line.startswith("SUPABASE_URL=") and not url:
                url = line.split("=", 1)[1].strip()
            if line.startswith("SUPABASE_SERVICE_KEY=") and not key:
                key = line.split("=", 1)[1].strip()
    if not (url and key):
        sys.exit("Missing SUPABASE_URL / SUPABASE_SERVICE_KEY (env or backend/.env)")
    return url, key


SUPABASE_URL, KEY = load_env()


def supabase(path, method="GET", body=None, count=False):
    req = urllib.request.Request(f"{SUPABASE_URL}{path}", method=method)
    req.add_header("apikey", KEY)
    req.add_header("Authorization", f"Bearer {KEY}")
    req.add_header("Content-Type", "application/json")
    if count:
        req.add_header("Prefer", "count=exact")
        req.add_header("Range", "0-0")
    data = json.dumps(body).encode() if body is not None else None
    with urllib.request.urlopen(req, data=data, timeout=30) as resp:
        if count:
            rng = resp.headers.get("Content-Range", "/0")
            return int(rng.split("/")[1])
        return json.loads(resp.read())


WORKSTREAMS = [
    ("Jake · Core Finance", re.compile(r"jake|core finance|intake assistant|salestrekker|broker", re.I)),
    ("Greenmachine", re.compile(r"greenmachine|green machine", re.I)),
    ("Moore AI Studios", re.compile(r"moore ai|carousel|instagram|founder.intro|home ?page|content bank", re.I)),
    ("Command Centre", re.compile(r"command centre|command center|mcp|supabase|check.?in", re.I)),
]

ENTITY_MAP = {
    "jake": "Jake · Core Finance", "core finance": "Jake · Core Finance",
    "greenmachine": "Greenmachine", "moore ai studios": "Moore AI Studios",
}


def workstream(task):
    entity = (task.get("entity_name") or "").lower()
    for k, v in ENTITY_MAP.items():
        if k in entity:
            return v
    text = f"{task.get('task', '')} {task.get('context', '')}"
    for name, rx in WORKSTREAMS:
        if rx.search(text):
            return name
    return "General"


def days_ago(iso, today):
    d = datetime.strptime(iso[:10], "%Y-%m-%d").date()
    n = (today - d).days
    return "today" if n == 0 else ("yesterday" if n == 1 else f"{n}d ago")


def fetch_all():
    today = datetime.now(timezone.utc).date()
    week_ago = (today - timedelta(days=7)).isoformat()

    fresh = supabase(
        "/rest/v1/tasks?select=id,task,context,urgency,category,entity_name,due_date,created_at"
        f"&status=eq.open&created_at=gte.{FRESH_CUTOFF}&order=created_at.desc&limit=200")
    total_open = supabase("/rest/v1/tasks?select=id&status=eq.open", count=True)
    mem_meta = supabase("/rest/v1/memories?select=id,status,source,created_at&limit=2000")
    recent = supabase("/rest/v1/rpc/agent_get_recent_memories", method="POST",
                      body={"limit_count": 30})
    try:
        decisions_7d = supabase(
            f"/rest/v1/decisions?select=id&created_at=gte.{week_ago}", count=True)
    except Exception:
        decisions_7d = None
    try:
        decisions_due = supabase("/rest/v1/rpc/agent_get_decisions_due_for_review", method="POST",
                                  body={"limit_count": 2})
    except Exception:
        decisions_due = []  # decision_outcomes_migration.sql not applied yet

    return {
        "today": today,
        "fresh": fresh,
        "total_open": total_open,
        "backlog": total_open - len(fresh),
        "mem_status": Counter(m["status"] for m in mem_meta),
        "mem_week": sum(1 for m in mem_meta if m["created_at"] >= week_ago),
        "recent": [m for m in recent if m["created_at"] >= week_ago],
        "decisions_7d": decisions_7d,
        "decisions_due": decisions_due,
    }


URGENCY_ORDER = {"immediate": 0, "this_week": 1, "soon": 2, "someday": 3}
URGENCY_LABEL = {"immediate": "now", "this_week": "this week", "soon": "soon", "someday": "someday"}

SOURCE_LABEL = {
    "claude_conversation": "claude.ai", "shortcut_voice": "voice note",
    "claude_task_creation": "task log", "artifact": "artifact", "local_chat": "local",
}

STATUS_NOTES = {
    "completed": ("good", "fully processed, visible to recall"),
    "indexed": ("warn", "embedded but no extraction — invisible to recall tools"),
    "claimed": ("crit", "claimed by poller, extraction never finished — re-drive"),
    "transcribed": ("warn", "stuck mid-pipeline"),
    "extracting": ("warn", "stuck mid-pipeline"),
    "pending": ("warn", "awaiting poller pickup"),
}

# Coloured dot before each workstream heading, so multiple clients read apart at a glance.
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


def esc(s):
    return html.escape(str(s or ""), quote=True)


def task_body_html(raw):
    """Task text as a card body: short in full, long clamped to two lines behind
    a native <details> 'Show more' toggle (no JS needed)."""
    text = esc(raw)
    if len(raw or "") <= 110:
        return f'<div class="task-body"><p class="task-text">{text}</p></div>'
    return (f'<div class="task-body"><details class="task-x"><summary>'
            f'<span class="task-text">{text}</span></summary></details></div>')


def render(d):
    today = d["today"]
    nice_date = today.strftime("%A %-d %B %Y")

    urgent = [t for t in d["fresh"] if t["urgency"] in ("immediate", "this_week")]
    later = [t for t in d["fresh"] if t["urgency"] not in ("immediate", "this_week")]
    stuck = sum(v for k, v in d["mem_status"].items() if k != "completed")

    def task_rows(tasks):
        groups = {}
        for t in tasks:
            groups.setdefault(workstream(t), []).append(t)
        order = [n for n, _ in WORKSTREAMS] + ["General"]
        out = []
        for name in sorted(groups, key=lambda n: order.index(n) if n in order else 99):
            rows = sorted(groups[name],
                          key=lambda t: (URGENCY_ORDER.get(t["urgency"], 9), t["created_at"]))
            slug = WORKSTREAM_SLUG.get(name, "g-general")
            out.append(f'<h3 class="group {slug}">{esc(name)} <span class="count">{len(rows)}</span></h3>')
            for t in rows:
                u = t["urgency"] if t["urgency"] in URGENCY_LABEL else "soon"
                dd = t.get("due_date")
                overdue = " overdue" if dd and dd < today.isoformat() else ""
                due = f'<span class="due{overdue}">due {esc(dd)}</span>' if dd else ""
                out.append(
                    f'<div class="task">'
                    f'<div class="task-top"><span class="chip u-{u}">{URGENCY_LABEL[u]}</span>'
                    f'<span class="meta">{esc(t.get("category") or "")} · {days_ago(t["created_at"], today)} {due}</span></div>'
                    f'{task_body_html(t["task"])}</div>')
        return "\n".join(out)

    mem_rows = []
    for m in d["recent"]:
        theme = m.get("main_theme") or m.get("summary") or "(processing)"
        theme = theme.split("\n")[0]
        theme = theme if len(theme) <= 160 else theme[:157] + "…"
        src = SOURCE_LABEL.get(m["source"], m["source"])
        mem_rows.append(
            f'<div class="mem"><span class="mem-date">{esc(m["created_at"][5:10])}</span>'
            f'<span class="chip src">{esc(src)}</span><p>{esc(theme)}</p></div>')

    health_rows = []
    for status, n in sorted(d["mem_status"].items(), key=lambda kv: -kv[1]):
        tone, note = STATUS_NOTES.get(status, ("warn", "unknown status"))
        health_rows.append(
            f'<div class="health-row"><span class="dot {tone}"></span>'
            f'<span class="h-status">{esc(status)}</span><span class="h-n">{n}</span>'
            f'<span class="h-note">{esc(note)}</span></div>')

    decision_rows = []
    for rev in d["decisions_due"]:
        made = days_ago(rev.get("decision_date") or "2026-01-01", today)
        cat = esc(rev.get("category") or "uncategorised")
        reasoning = f'<p class="decision-reasoning">{esc(rev["reasoning"])}</p>' if rev.get("reasoning") else ""
        decision_rows.append(
            f'<div class="decision"><div class="decision-top"><span class="meta">{cat} · decided {made}</span></div>'
            f'<div class="decision-body"><p class="decision-text">{esc(rev["decision_text"])}</p>{reasoning}</div></div>')

    dec = f'{d["decisions_7d"]}' if d["decisions_7d"] is not None else "—"
    generated = datetime.now().strftime("%-d %b %Y, %-I:%M %p")
    stuck_cls = "crit" if stuck else "good"

    body = f"""<title>Daily Check-in — Command Centre</title>
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
:root[data-theme="dark"] {{
  --bg:#0E1621; --surface:#16202D; --ink:#E8ECF1; --muted:#93A2B4; --line:#27313F;
  --accent:#4F97DA; --accent-ink:#88B9EC; --accent-soft:#182B3E;
  --gold:#F2C230; --gold-soft:#33290F;
  --warn:#DFA35C; --warn-soft:#31281A; --crit:#E06B5F; --crit-soft:#36201D;
  --good:#5FB97D; --good-soft:#1C3024;
}}
:root[data-theme="light"] {{
  --bg:#F7F1E8; --surface:#FFFFFF; --ink:#111827; --muted:#5B6775; --line:#E7DDCC;
  --accent:#0F4E8A; --accent-ink:#0C3D6E; --accent-soft:#E3EAF4;
  --gold:#F2C230; --gold-soft:#FBEFC9;
  --warn:#9A5B0B; --warn-soft:#F5ECDD; --crit:#B3382D; --crit-soft:#F7E7E4;
  --good:#1F7A44; --good-soft:#E4F1E8;
}}
* {{ box-sizing:border-box; margin:0; }}
body {{
  background:var(--bg); color:var(--ink);
  font-family:"Avenir Next","Seravek",ui-sans-serif,system-ui,sans-serif;
  line-height:1.5; -webkit-font-smoothing:antialiased;
}}
.wrap {{ max-width:860px; margin:0 auto; padding:44px 24px 64px; }}
.masthead {{ display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:14px;
  border-bottom:3px solid var(--accent); padding-bottom:16px; position:relative; }}
.masthead::after {{ content:""; position:absolute; left:0; right:0; bottom:-6px; height:3px; background:var(--gold); border-radius:2px; }}
.brand {{ display:flex; align-items:center; gap:13px; }}
.emblem {{ width:42px; height:42px; flex:none; }}
.masthead h1 {{ font-size:26px; font-weight:600; letter-spacing:-0.01em; }}
.masthead .date {{ font-size:15px; color:var(--muted); }}
.kicker {{ font-size:12px; text-transform:uppercase; letter-spacing:0.1em; color:var(--accent-ink); font-weight:600; margin-bottom:4px; }}
.stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; margin:24px 0 8px; }}
.stat {{ background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:14px 16px; }}
.stat .label {{ font-size:11px; text-transform:uppercase; letter-spacing:0.08em; color:var(--muted); font-weight:600; }}
.stat .n {{ font-size:30px; font-weight:600; font-variant-numeric:tabular-nums; margin-top:2px; }}
.stat .sub {{ font-size:12px; color:var(--muted); }}
.stat.crit .n {{ color:var(--crit); }} .stat.good .n {{ color:var(--good); }}
section {{ margin-top:36px; }}
.eyebrow {{ font-size:12px; text-transform:uppercase; letter-spacing:0.1em; color:var(--muted); font-weight:600;
  border-bottom:1px solid var(--line); padding-bottom:6px; margin-bottom:14px; }}
.eyebrow.hot {{ border-bottom-color:var(--gold); color:var(--accent-ink); }}
.group {{ font-size:14px; font-weight:600; margin:18px 0 6px; color:var(--accent-ink); display:flex; align-items:center; gap:7px; }}
.group::before {{ content:""; width:8px; height:8px; border-radius:50%; background:var(--dot,var(--accent)); flex:none; }}
.g-jake {{ --dot:var(--accent); }} .g-green {{ --dot:var(--good); }} .g-moore {{ --dot:var(--gold); }} .g-cmd {{ --dot:var(--muted); }} .g-general {{ --dot:var(--muted); }}
.group .count {{ color:var(--muted); font-weight:500; font-size:12px; }}
.task {{ padding:14px 16px; border:1px solid var(--line); border-radius:12px; background:var(--surface); margin-bottom:10px; }}
.task-top {{ display:flex; align-items:center; gap:9px; flex-wrap:wrap; margin-bottom:8px; }}
.task-body {{ min-width:0; }}
.task-text {{ font-size:15px; overflow-wrap:anywhere; }}
details.task-x > summary {{ list-style:none; cursor:pointer; }}
details.task-x > summary::-webkit-details-marker {{ display:none; }}
details.task-x .task-text {{ display:-webkit-box; -webkit-box-orient:vertical; -webkit-line-clamp:2; line-clamp:2; overflow:hidden; }}
details.task-x[open] .task-text {{ display:block; -webkit-line-clamp:unset; line-clamp:unset; overflow:visible; }}
details.task-x > summary::after {{ content:"Show more"; display:inline-block; margin-top:7px; font-size:12px; font-weight:600; color:var(--accent); }}
details.task-x[open] > summary::after {{ content:"Show less"; }}
.task .meta, .due {{ font-size:12px; color:var(--muted); font-family:ui-monospace,Menlo,monospace; }}
.decision {{ padding:14px 16px; border:1px solid var(--line); border-radius:12px; background:var(--surface); margin-bottom:10px; }}
.decision-top {{ margin-bottom:6px; }}
.decision-top .meta {{ font-size:12px; color:var(--muted); font-family:ui-monospace,Menlo,monospace; }}
.decision-text {{ font-size:15px; overflow-wrap:anywhere; }}
.decision-reasoning {{ font-size:13px; color:var(--muted); margin-top:4px; }}
.due.overdue {{ color:var(--crit); font-weight:600; }}
.chip {{ flex:none; font-size:11px; font-weight:600; padding:2px 9px; border-radius:99px;
  letter-spacing:0.02em; white-space:nowrap; }}
.u-immediate {{ background:var(--accent); color:var(--bg); }}
.u-this_week {{ background:var(--accent-soft); color:var(--accent-ink); }}
.u-soon {{ border:1px solid var(--line); color:var(--muted); background:var(--surface); }}
.u-someday {{ color:var(--muted); background:transparent; border:1px dashed var(--line); }}
.chip.src {{ background:var(--surface); border:1px solid var(--line); color:var(--muted); font-weight:500; }}
.callout {{ background:var(--surface); border:1px solid var(--line); border-left:3px solid var(--warn);
  border-radius:8px; padding:12px 16px; font-size:14px; color:var(--muted); margin-top:16px; }}
.callout b {{ color:var(--ink); }}
.mem {{ display:flex; gap:10px; align-items:baseline; padding:7px 0; border-bottom:1px solid var(--line); }}
.mem:last-child {{ border-bottom:none; }}
.mem-date {{ font-family:ui-monospace,Menlo,monospace; font-size:12px; color:var(--muted); flex:none; }}
.mem p {{ font-size:14px; }}
.health {{ background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:6px 16px; }}
.health-row {{ display:flex; gap:10px; align-items:baseline; padding:8px 0; border-bottom:1px solid var(--line); font-size:14px; }}
.health-row:last-child {{ border-bottom:none; }}
.dot {{ width:9px; height:9px; border-radius:50%; flex:none; align-self:center; }}
.dot.good {{ background:var(--good); }} .dot.warn {{ background:var(--warn); }} .dot.crit {{ background:var(--crit); }}
.h-status {{ font-family:ui-monospace,Menlo,monospace; font-size:13px; min-width:96px; }}
.h-n {{ font-weight:600; font-variant-numeric:tabular-nums; min-width:40px; text-align:right; }}
.h-note {{ color:var(--muted); font-size:13px; }}
footer {{ margin-top:44px; padding-top:14px; border-top:1px solid var(--line);
  font-size:12px; color:var(--muted); font-family:ui-monospace,Menlo,monospace; }}
footer p {{ margin-bottom:4px; }}
@media (prefers-reduced-motion: no-preference) {{
  .wrap {{ animation:rise .35s ease-out; }}
  @keyframes rise {{ from {{ opacity:0; transform:translateY(6px); }} to {{ opacity:1; transform:none; }} }}
}}
</style>
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
    <div class="stat"><div class="label">Focus tasks</div><div class="n">{len(urgent)}</div>
      <div class="sub">now + this week</div></div>
    <div class="stat"><div class="label">Open (fresh)</div><div class="n">{len(d["fresh"])}</div>
      <div class="sub">since {FRESH_CUTOFF}</div></div>
    <div class="stat"><div class="label">Memories · 7d</div><div class="n">{d["mem_week"]}</div>
      <div class="sub">{dec} decisions logged</div></div>
    <div class="stat {stuck_cls}"><div class="label">Stuck in pipeline</div><div class="n">{stuck}</div>
      <div class="sub">memories not fully processed</div></div>
  </div>

  <section>
    <div class="eyebrow hot">Today’s focus</div>
    {task_rows(urgent) or '<p class="callout">Nothing marked immediate or this-week. Pull something up from the later list.</p>'}
  </section>

  {'<section><div class="eyebrow">Decision review · ' + str(len(decision_rows)) + ' to close out</div>' + "".join(decision_rows) + '<div class="callout">Read-only here — record outcomes from the live check-in page or Claude.</div></section>' if decision_rows else ''}

  <section>
    <div class="eyebrow">Coming up · {len(later)} tasks</div>
    {task_rows(later)}
    <div class="callout"><b>{d["backlog"]:,} older open tasks</b> are hidden from this view —
      mostly auto-extracted before {FRESH_CUTOFF} (June bulk import). Triage pending:
      tell Claude to bulk-close or merge them.</div>
  </section>

  <section>
    <div class="eyebrow">This week in memory · {len(d["recent"])} captured</div>
    {"".join(mem_rows)}
  </section>

  <section>
    <div class="eyebrow">Pipeline health · {sum(d["mem_status"].values())} memories total</div>
    <div class="health">{"".join(health_rows)}</div>
  </section>

  <footer>
    <p>Generated {generated} · read-only snapshot of the live Command Centre.</p>
    <p>To act on a task, tell Claude (claude.ai or Claude Code): “complete / update / merge task …”.</p>
    <p>Regenerate: python3 daily-checkin/generate_checkin.py</p>
  </footer>
</div>"""
    return body


def main():
    d = fetch_all()
    body = render(d)
    (OUT_DIR / "checkin-artifact.html").write_text(body)
    head_part, content = body.split('<div class="wrap">', 1)
    (OUT_DIR / "checkin.html").write_text(
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        + head_part + "</head>\n<body>\n" + '<div class="wrap">' + content
        + "\n</body>\n</html>\n")
    print(f"Wrote {OUT_DIR / 'checkin.html'}")
    print(f"Wrote {OUT_DIR / 'checkin-artifact.html'}")
    print(f"Fresh open: {len(d['fresh'])} | total open: {d['total_open']} | "
          f"memories 7d: {d['mem_week']} | statuses: {dict(d['mem_status'])}")


if __name__ == "__main__":
    main()
