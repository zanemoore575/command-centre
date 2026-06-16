"""
One-time backfill: generate embeddings for completed memories that have
embeddings = null. Run after the ingest pipeline fix so search has
something to find for older rows.

Usage:
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... OPENAI_API_KEY=... python3 backfill_embeddings.py
"""

import os
import sys
import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

if not (SUPABASE_URL and SUPABASE_KEY and OPENAI_API_KEY):
    sys.exit("Set SUPABASE_URL, SUPABASE_SERVICE_KEY, and OPENAI_API_KEY first.")

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def fetch_memories_missing_embeddings(client: httpx.Client) -> list[dict]:
    r = client.get(
        f"{SUPABASE_URL}/rest/v1/memories",
        headers=SUPABASE_HEADERS,
        params={
            "status": "eq.completed",
            "embeddings": "is.null",
            "select": "id,summary,title,transcript",
        },
    )
    r.raise_for_status()
    return r.json()


def text_for_embedding(memory: dict) -> str:
    return memory.get("summary") or memory.get("title") or (memory.get("transcript") or "")[:2000]


def embed(client: httpx.Client, text: str) -> list[float]:
    r = client.post(
        "https://api.openai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
        json={"model": "text-embedding-3-small", "input": text},
    )
    r.raise_for_status()
    return r.json()["data"][0]["embedding"]


def update_embedding(client: httpx.Client, memory_id: int, embedding: list[float]) -> None:
    r = client.patch(
        f"{SUPABASE_URL}/rest/v1/memories",
        headers=SUPABASE_HEADERS,
        params={"id": f"eq.{memory_id}"},
        json={"embeddings": embedding},
    )
    r.raise_for_status()


def main() -> None:
    with httpx.Client(timeout=30) as client:
        memories = fetch_memories_missing_embeddings(client)
        print(f"{len(memories)} completed memories missing embeddings")
        for m in memories:
            text = text_for_embedding(m)
            if not text.strip():
                print(f"  skip {m['id']}: no text to embed")
                continue
            embedding = embed(client, text)
            update_embedding(client, m["id"], embedding)
            print(f"  embedded memory {m['id']}")


if __name__ == "__main__":
    main()
