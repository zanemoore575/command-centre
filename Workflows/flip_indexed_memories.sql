-- =============================================================================
-- Wave 4 hygiene: flip legacy 'indexed' memories to 'completed' (2026-07-17)
-- Run in the Supabase SQL Editor on erwxszdcisyuyjmefvbj.
--
-- The recall RPCs (agent_get_recent_memories, agent_search_by_theme,
-- agent_search_memories_by_embedding) all filter status = 'completed'. A handful
-- of old voice rows (~33 at the 07-11 audit, ~4 remaining) sit at status
-- 'indexed' — they were embedded and summarised but never reached the terminal
-- status, so recall silently skips them.
--
-- They already have embeddings, so once flipped they are immediately picked up by
-- the Wave 3a hybrid semantic search (no re-extraction needed). We do NOT re-run
-- the 7-way extraction on them — that would re-flood entities/decisions, exactly
-- what Wave 2 was cleaning up. Making them recallable is the goal.
--
-- 'indexed' is not a status the poller recycles (agent_reclaim_stale_memories
-- only touches 'claimed'/'extracting'), so this one-off is how they get cleared.
--
-- Idempotent: once flipped, the WHERE matches nothing on re-run.
-- =============================================================================

-- Preview first (optional):
--   SELECT id, source, created_at, (embeddings IS NOT NULL) AS has_embedding
--   FROM memories WHERE status = 'indexed' ORDER BY created_at;

UPDATE memories
SET status = 'completed'
WHERE status = 'indexed';

-- Verify (optional): expect 0 rows left at 'indexed'.
--   SELECT COUNT(*) AS still_indexed FROM memories WHERE status = 'indexed';
