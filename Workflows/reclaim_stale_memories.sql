-- Self-healing reclaim for the memory ingest pipeline.
--
-- Problem it fixes: the pending-memory poller only ever re-scans status='pending',
-- and it flips a row to 'claimed' BEFORE calling the ingest webhook. So if an ingest
-- run errors (n8n hiccup, bad temp setting, OpenAI timeout), the whole in-flight set
-- is stranded in 'claimed'/'extracting' with nothing to retry it — which is how 62
-- memories went invisible to recall on 2026-07-11/12.
--
-- This function flips genuinely-stale rows back to 'pending' so the poller re-drives
-- them on its next 2-minute tick. Safe:
--   * 'claimed' rows never reached the extraction insert nodes, so there are no child
--     rows (entities/tasks/etc.) to duplicate.
--   * 'extracting' gets a longer 20-min grace so a legitimately slow run (normal is
--     <3 min) is never interrupted mid-extraction.
-- Idempotent — re-running this file just replaces the function.

create or replace function agent_reclaim_stale_memories()
returns integer
language sql
as $$
  with reset as (
    update memories
       set status = 'pending'
     where (status = 'claimed'    and updated_at < now() - interval '10 minutes')
        or (status = 'extracting' and updated_at < now() - interval '20 minutes')
    returning id
  )
  select count(*)::int from reset;
$$;

grant execute on function agent_reclaim_stale_memories() to service_role;

-- Quick test (optional): should return the number of stale rows reclaimed right now
-- (0 in a healthy pipeline):
--   select agent_reclaim_stale_memories();
