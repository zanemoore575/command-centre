"""
One-time backfill: canonicalize the pre-Wave-2 entity flood (4,456 rows / 2,326
distinct lowercased names before this ran) now that canonical_entities +
entities.canonical_id exist (entity_resolution_migration.sql must be applied
first — this script assumes the schema is already live).

Mirrors the live agent_ingest_entity matching tiers, applied per group instead
of per mention — and calls the SAME agent_best_canonical_match RPC the live
ingest loop uses (pg_trgm-based), rather than a second Python-side heuristic.
An earlier version of this script scored candidates with difflib instead and
flagged ~1,035 of 3,005 rows for review — plain character-ratio similarity is
noisy on short strings ("outlook"/"trello" scored 0.46, "docker"/"render"
scored 0.5). Switching to the live RPC (pg_trgm) cut that to 123/251 on a
first real run against entity_type='tool' — much better, but inspecting the
actual scores showed a real quality cliff around 0.35 (everything above reads
as a sensible question — "Claude Code" vs "Claude" at 0.7, "Google Sheets
API" vs "Google Sheets" at 0.78 — everything below was noise: "DocuSign" vs
"Docker" at 0.23, "Revit" vs "React" at 0.2). The floor here is set to 0.35
based on that inspection, not the 0.20 the live agent_ingest_entity RPC
originally shipped with — both were raised together so the backfill and the
ongoing live loop keep agreeing on what counts as the same entity:
  - Rows are first grouped by normalized (lowercased/whitespace-collapsed) name
    — pure case/punctuation-spacing variants collapse silently, no review needed.
  - Each group is then scored (heaviest group first) against whatever
    canonicals already exist for that type via agent_best_canonical_match:
      score >= 0.90            -> merges into that canonical directly (rare at
                                    this stage — exact dupes are already grouped)
      0.35 <= score < 0.90      -> stays its OWN standalone canonical (never
                                    silently merged) + one entity_match_review
                                    row against the closest existing match, so
                                    ambiguous historical names surface on the
                                    check-in page exactly like new ones do
      score < 0.35 / no match  -> new canonical, nothing to review
  - 'concept'-type rows are left untouched entirely (canonical_id stays null)
    — themes already cover them and they don't behave like names.
  - Stray entity_type values (not person/company/project/tool/concept) are
    retyped to the closest standard type first.

Zane's call (2026-07-16): "Zane" rows are already deleted by the SQL migration
itself (step 9) — nothing to do here. Claude makes the clustering/retype calls
directly; this script prints a summary at the end instead of asking per-row.

Usage:
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... python3 backfill_canonical_entities.py [type]
    # [type] optionally restricts the run to one of person/company/project/tool,
    # for inspecting results incrementally instead of all four at once.
"""

import os
import re
import sys
from collections import Counter, defaultdict
from typing import Optional

import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

if not (SUPABASE_URL and SUPABASE_KEY):
    sys.exit("Set SUPABASE_URL and SUPABASE_SERVICE_KEY first.")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

STANDARD_TYPES = {"person", "company", "project", "tool"}
RETYPE_KEYWORDS = [
    (("tool", "platform", "software", "service", "app"), "tool"),
    (("compan", "business", "vendor", "client business"), "company"),
    (("project", "implementation", "product"), "project"),
    (("person", "individual", "contact", "people"), "person"),
]

AUTO_MERGE_FLOOR = 0.35  # below this: unrelated, brand-new canonical (see module docstring)


def _get_all(path: str, params: dict) -> list[dict]:
    """GET every row from a Supabase REST endpoint, paginating past the default page cap."""
    out, offset, page = [], 0, 1000
    with httpx.Client(timeout=30) as client:
        while True:
            r = client.get(
                f"{SUPABASE_URL}/rest/v1/{path}", headers=HEADERS,
                params={**params, "limit": page, "offset": offset},
            )
            r.raise_for_status()
            rows = r.json()
            out.extend(rows)
            if len(rows) < page:
                break
            offset += page
    return out


def _patch(path: str, body: dict, params: dict) -> None:
    with httpx.Client(timeout=30) as client:
        r = client.patch(f"{SUPABASE_URL}/rest/v1/{path}", headers=HEADERS, params=params, json=body)
        r.raise_for_status()


def _post(path: str, body: dict) -> dict:
    with httpx.Client(timeout=30) as client:
        r = client.post(f"{SUPABASE_URL}/rest/v1/{path}", headers=HEADERS, json=body)
        r.raise_for_status()
        rows = r.json()
        return rows[0] if rows else {}


def _rpc(fn: str, body: dict) -> list:
    with httpx.Client(timeout=30) as client:
        r = client.post(f"{SUPABASE_URL}/rest/v1/rpc/{fn}", headers=HEADERS, json=body)
        r.raise_for_status()
        return r.json()


def normalize(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def retype(stray_type: str) -> Optional[str]:
    lowered = (stray_type or "").lower()
    for keywords, target in RETYPE_KEYWORDS:
        if any(k in lowered for k in keywords):
            return target
    return None


def retype_stray_entities() -> dict[str, int]:
    rows = _get_all("entities", {"select": "id,entity_type", "canonical_id": "is.null"})
    stray_types = {t for t in {r["entity_type"] for r in rows} if t not in STANDARD_TYPES and t != "concept"}
    retyped = Counter()
    unresolved = Counter()
    for stray in stray_types:
        target = retype(stray)
        ids = [r["id"] for r in rows if r["entity_type"] == stray]
        if target:
            for eid in ids:
                _patch("entities", {"entity_type": target}, {"id": f"eq.{eid}"})
            retyped[f"{stray} -> {target}"] += len(ids)
        else:
            unresolved[stray] += len(ids)
    return {"retyped": dict(retyped), "unresolved": dict(unresolved)}


def canonicalize_type(entity_type: str) -> dict:
    rows = _get_all("entities", {
        "select": "id,entity_name,context,memory_id",
        "entity_type": f"eq.{entity_type}",
        "canonical_id": "is.null",
    })
    if not rows:
        return {"groups": 0, "rows": 0, "review_rows": 0, "merged": 0}

    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[normalize(r["entity_name"])].append(r)

    # Heaviest (most-mentioned) groups processed first, so common names become
    # the established canonicals that rarer variants get compared against.
    ordered = sorted(groups.items(), key=lambda kv: -len(kv[1]))
    review_rows = 0
    merged = 0

    for norm_key, group_rows in ordered:
        surface_forms = Counter(r["entity_name"] for r in group_rows)
        canonical_name = max(surface_forms.items(), key=lambda kv: (kv[1], len(kv[0])))[0]

        matches = _rpc("agent_best_canonical_match", {
            "candidate_name": canonical_name, "candidate_type": entity_type,
        })
        best = matches[0] if matches else None
        score = (best or {}).get("score") or 0.0

        if best and score >= 0.90:
            # Confident match against something already canonicalized this run
            # — merge directly rather than creating a redundant duplicate.
            canonical_id = best["canonical_id"]
            existing_aliases = _get_all("canonical_entities", {
                "select": "aliases", "id": f"eq.{canonical_id}",
            })[0]["aliases"]
            _patch("canonical_entities",
                   {"aliases": list(dict.fromkeys(existing_aliases + list(surface_forms.keys())))},
                   {"id": f"eq.{canonical_id}"})
            merged += 1
        else:
            canonical = _post("canonical_entities", {
                "canonical_name": canonical_name,
                "entity_type": entity_type,
                "aliases": list(surface_forms.keys()),
            })
            canonical_id = canonical["id"]
            if best and AUTO_MERGE_FLOOR <= score < 0.90:
                _post("entity_match_review", {
                    "memory_id": group_rows[0]["memory_id"],
                    "candidate_name": canonical_name,
                    "candidate_canonical_id": canonical_id,
                    "suggested_name": best["canonical_name"],
                    "suggested_canonical_id": best["canonical_id"],
                    "similarity": round(score, 3),
                })
                review_rows += 1

        for r in group_rows:
            _patch("entities", {"canonical_id": canonical_id}, {"id": f"eq.{r['id']}"})

    return {"groups": len(groups), "rows": len(rows), "review_rows": review_rows, "merged": merged}


def main() -> None:
    only_type = next((a for a in sys.argv[1:] if a in STANDARD_TYPES), None)

    if not only_type:
        print("Retyping stray entity_type values...")
        retype_summary = retype_stray_entities()
        print(f"  retyped: {retype_summary['retyped']}")
        if retype_summary["unresolved"]:
            print(f"  left as-is (no confident mapping): {retype_summary['unresolved']}")

    totals = Counter()
    for entity_type in sorted([only_type] if only_type else STANDARD_TYPES):
        print(f"\nCanonicalizing entity_type='{entity_type}'...")
        result = canonicalize_type(entity_type)
        print(f"  {result['rows']} rows -> {result['groups']} canonicals "
              f"({result['merged']} merged into an existing one), "
              f"{result['review_rows']} flagged for check-in review")
        totals.update(result)

    print(f"\nDone. {totals['rows']} rows processed into {totals['groups']} canonical "
          f"entities ({totals['merged']} merged into existing ones); {totals['review_rows']} "
          f"ambiguous groups queued in entity_match_review for Zane to confirm on the check-in page.")
    print("'concept'-type rows and any already-canonicalized rows were left untouched.")


if __name__ == "__main__":
    main()
