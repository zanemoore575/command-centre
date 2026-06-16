"""
Import Claude conversation export (conversations.json) into CAiS via the n8n
ingest webhook. Each conversation becomes one memory.

Usage:
    python3 import_claude_conversations.py                        # dry run (all)
    python3 import_claude_conversations.py --send                 # send all
    python3 import_claude_conversations.py --send --min-score 4   # strategic only (~267)
    python3 import_claude_conversations.py --send --min-score 6   # high signal only (~185)
    python3 import_claude_conversations.py --score-preview        # show scored list, no send
    python3 import_claude_conversations.py --send --limit 5       # send first 5 matches

Relevance scoring:
    Conversations mentioning clients (Jake, Aaron, Rachel...), business topics
    (pricing, strategy, real estate, automation agency) or personal reflection
    keywords score higher. Pure technical debugging scores lower.
    --min-score 4 is recommended for the first import run.
"""

import json
import sys
import time
import argparse
import httpx
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

WEBHOOK_URL = "https://n8n-service-8act.onrender.com/webhook/ingest-conversation"
EXPORT_FILE = Path(__file__).parent.parent / "conversations.json"

MIN_CHARS = 800
DELAY_SECONDS = 30

# ---------------------------------------------------------------------------
# Relevance scoring
# ---------------------------------------------------------------------------

STRATEGIC_KEYWORDS = [
    "strategy", "strateg", "pivot", "pricing", "market", "business model",
    "customer", "client", "discovery", "sales", "pitch", "outreach",
    "reflection", "journey", "identity", "values", "integrity", "fear",
    "decision", "direction", "focus", "positioning",
    "jake", "aaron", "rachel", "william", "justin", "jay", "felice", "rach",
    "mandy", "cais", "command centre", "real estate", "trades", "tradie",
    "whangarei", "nz", "new zealand",
    "proposal", "revenue", "income", "charging", "retainer",
    "voice ai", "receptionist", "agent", "automation agency",
    "greenmachine", "green machine", "core finance",
    "tate", "lake", "oakley", "nadia", "tim",
    "journal", "brain dump", "voice note",
    "anxiety", "struggle", "breakthrough", "clarity",
    "what i want", "what am i", "who am i",
    "carousel", "fat camel", "phase 1", "phase 2",
    "warm intro", "follow up",
]

TECH_NOISE_KEYWORDS = [
    "zod schema", "docker", "css", "html", "json payload", "javascript filter",
    "pdf extract", "image resiz", "url validation", "shopify data comparison",
    "brave search", "web scraping", "pinecone", "chatbot styling",
    "markdown formatting", "prompt greeting", "chat widget styling",
    "fertiliser", "plant data", "gardening question",
]


def relevance_score(conv: dict) -> int:
    title = conv.get("name", "").lower()
    msgs = conv.get("chat_messages", [])
    first_human = next((m.get("text", "") for m in msgs if m.get("sender") == "human"), "")
    text = (title + " " + first_human[:500]).lower()

    score = 0
    for kw in STRATEGIC_KEYWORDS:
        if kw in text:
            score += 2
    for kw in TECH_NOISE_KEYWORDS:
        if kw in text:
            score -= 3

    chars = sum(len(m.get("text") or "") for m in msgs)
    if chars > 10000:
        score += 2
    if chars > 30000:
        score += 2
    if chars < 1500:
        score -= 2
    return score


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_transcript(messages: list) -> str:
    lines = []
    for m in messages:
        sender = "ZANE" if m.get("sender") == "human" else "CLAUDE"
        text = (m.get("text") or "").strip()
        if not text:
            for block in m.get("content", []):
                t = (block.get("text") or "").strip()
                if t:
                    text = t
                    break
        if text:
            lines.append(f"{sender}: {text}")
    return "\n\n".join(lines)


def total_chars(messages: list) -> int:
    return sum(len(m.get("text") or "") for m in messages)


def fmt_date(dt_str: str) -> str:
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    except Exception:
        return dt_str


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true", help="Actually POST to n8n (default is dry run)")
    parser.add_argument("--limit", type=int, default=0, help="Stop after N conversations sent")
    parser.add_argument("--skip", type=int, default=0, help="Skip first N after sorting")
    parser.add_argument("--min-chars", type=int, default=MIN_CHARS, help=f"Min total chars (default {MIN_CHARS})")
    parser.add_argument("--min-score", type=int, default=None, help="Only send conversations with relevance score >= N (recommended: 4 or 6)")
    parser.add_argument("--score-preview", action="store_true", help="Print scored list and exit — no sending")
    args = parser.parse_args()

    print(f"Loading {EXPORT_FILE} ...")
    with open(EXPORT_FILE, encoding="utf-8") as f:
        conversations = json.load(f)
    print(f"Total conversations in export: {len(conversations)}")

    # Sort oldest-first so memories land in chronological order
    conversations.sort(key=lambda c: c.get("created_at", ""))

    if args.skip:
        conversations = conversations[args.skip:]
        print(f"Skipping first {args.skip} → {len(conversations)} remaining")

    if args.score_preview:
        scored = [(relevance_score(c), c.get("name", ""), total_chars(c.get("chat_messages", []))) for c in conversations]
        scored.sort(reverse=True)
        print(f"\n{'SCORE':>5}  {'TITLE':<70}  CHARS")
        for s, name, chars in scored:
            marker = "  ✓" if s >= 4 else ("  ~" if s >= 2 else "   ")
            print(f"{s:5d}{marker}  {name[:70]!r:<72}  {chars:,}")
        total_4 = sum(1 for s, _, _ in scored if s >= 4)
        total_6 = sum(1 for s, _, _ in scored if s >= 6)
        print(f"\nScore >= 4: {total_4} conversations  |  Score >= 6: {total_6} conversations")
        return

    sent = skipped_short = skipped_empty = skipped_score = 0
    errors = []

    for i, conv in enumerate(conversations):
        if args.limit and sent >= args.limit:
            print(f"\nReached --limit {args.limit}, stopping.")
            break

        name = conv.get("name") or "Untitled"
        created_at = fmt_date(conv.get("created_at", ""))
        messages = conv.get("chat_messages", [])

        if not messages:
            skipped_empty += 1
            continue

        chars = total_chars(messages)
        if chars < args.min_chars:
            skipped_short += 1
            continue

        if args.min_score is not None:
            score = relevance_score(conv)
            if score < args.min_score:
                skipped_score += 1
                print(f"  SKIP  [{i+1:4d}] (score {score:3d}) {name[:55]!r}")
                continue

        transcript = build_transcript(messages)
        payload = {
            "title": name,
            "transcript": transcript,
            "created_at": created_at,
            "source": "claude_conversation",
        }

        if not args.send:
            score_str = f"score {relevance_score(conv):3d}" if args.min_score is not None else ""
            print(f"  DRY   [{i+1:4d}] {score_str}  {name[:55]!r}  ({chars:,} chars, {len(messages)} msgs)")
            sent += 1
            continue

        try:
            r = httpx.post(WEBHOOK_URL, json=payload, timeout=30)
            if r.is_success:
                print(f"  OK    [{i+1:4d}] {name[:60]!r}  ({chars:,} chars)")
                sent += 1
            else:
                print(f"  ERR   [{i+1:4d}] {name[:60]!r}  HTTP {r.status_code}: {r.text[:120]}")
                errors.append((name, r.status_code))
        except Exception as e:
            print(f"  EXC   [{i+1:4d}] {name[:60]!r}  {e}")
            errors.append((name, str(e)))

        time.sleep(DELAY_SECONDS)

    print()
    print("=== Summary ===")
    print(f"  Sent:           {sent}")
    print(f"  Skipped short:  {skipped_short}")
    print(f"  Skipped empty:  {skipped_empty}")
    if skipped_score:
        print(f"  Skipped score:  {skipped_score}")
    if errors:
        print(f"  Errors:         {len(errors)}")
        for name, detail in errors[:10]:
            print(f"    {name[:60]}: {detail}")
    if not args.send:
        print()
        print("DRY RUN — nothing was posted. Add --send to actually ingest.")


if __name__ == "__main__":
    main()
