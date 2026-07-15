-- =============================================================================
-- Current-truth layer migration (Wave 1a, 2026-07-16)
-- Run in the Supabase SQL Editor on erwxszdcisyuyjmefvbj.
--
-- Adds `current_state`: one row per topic (workstream, client position, pricing
-- stance, personal thread) holding the single canonical answer. Rewritten on
-- supersession, never appended — a new fact on a topic OVERWRITES the statement
-- and pushes the prior one into `history`. This is the "overpower older memories
-- with new facts" behaviour, same philosophy as task archival (preserve, don't
-- delete, but never let a stale fact outrank a corrected one).
--
-- `living_context` is superseded by this table (empty/orphaned since the
-- Telegram retirement — see command-centre-pivot memory). Left in place, unused;
-- not dropped.
--
-- Safe to re-run: IF NOT EXISTS / CREATE OR REPLACE.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Table
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS current_state (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  topic             TEXT NOT NULL,
  statement         TEXT NOT NULL,
  detail            TEXT,
  status            TEXT NOT NULL DEFAULT 'active',   -- active | watch | closed
  source_memory_ids BIGINT[] NOT NULL DEFAULT '{}'::BIGINT[],
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  history           JSONB NOT NULL DEFAULT '[]'::jsonb  -- prior {statement, detail, status, superseded_at}
);

-- Case-insensitive uniqueness so "Phase 2 funding" and "phase 2 funding"
-- resolve to the same row instead of silently forking.
CREATE UNIQUE INDEX IF NOT EXISTS current_state_topic_lower_idx ON current_state (lower(topic));

-- -----------------------------------------------------------------------------
-- 2. agent_get_current_state — query this FIRST in a session. No topic returns
--    everything (active topics surfaced before watch/closed).
-- -----------------------------------------------------------------------------
DROP FUNCTION IF EXISTS agent_get_current_state(TEXT);
CREATE OR REPLACE FUNCTION agent_get_current_state(
  search_topic TEXT DEFAULT NULL
)
RETURNS TABLE (
  topic             TEXT,
  statement         TEXT,
  detail            TEXT,
  status            TEXT,
  source_memory_ids BIGINT[],
  updated_at        TIMESTAMPTZ,
  history           JSONB
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    cs.topic, cs.statement, cs.detail, cs.status,
    cs.source_memory_ids, cs.updated_at, cs.history
  FROM current_state cs
  WHERE search_topic IS NULL
     OR cs.topic     ILIKE '%' || search_topic || '%'
     OR cs.statement ILIKE '%' || search_topic || '%'
  ORDER BY
    CASE cs.status WHEN 'active' THEN 0 WHEN 'watch' THEN 1 ELSE 2 END,
    cs.updated_at DESC;
END;
$$;

-- -----------------------------------------------------------------------------
-- 3. agent_update_current_state — upsert by topic (case-insensitive). If the
--    topic exists and the statement/detail actually changed, the prior value
--    is pushed into history before being overwritten (supersession preserved,
--    never appended alongside the new truth).
-- -----------------------------------------------------------------------------
DROP FUNCTION IF EXISTS agent_update_current_state(TEXT, TEXT, TEXT, TEXT, BIGINT);
CREATE OR REPLACE FUNCTION agent_update_current_state(
  p_topic             TEXT,
  p_statement         TEXT,
  p_detail            TEXT DEFAULT NULL,
  p_status            TEXT DEFAULT 'active',
  p_source_memory_id  BIGINT DEFAULT NULL
)
RETURNS TABLE (
  topic             TEXT,
  statement         TEXT,
  detail            TEXT,
  status            TEXT,
  source_memory_ids BIGINT[],
  updated_at        TIMESTAMPTZ,
  history           JSONB
)
LANGUAGE plpgsql
AS $$
DECLARE
  v_existing current_state%ROWTYPE;
BEGIN
  SELECT * INTO v_existing FROM current_state cs WHERE lower(cs.topic) = lower(p_topic);

  IF FOUND THEN
    UPDATE current_state cs
    SET statement = p_statement,
        detail    = COALESCE(p_detail, cs.detail),
        status    = COALESCE(p_status, cs.status),
        source_memory_ids = CASE
          WHEN p_source_memory_id IS NULL THEN cs.source_memory_ids
          WHEN p_source_memory_id = ANY(cs.source_memory_ids) THEN cs.source_memory_ids
          ELSE cs.source_memory_ids || p_source_memory_id
        END,
        updated_at = now(),
        history = CASE
          WHEN v_existing.statement IS DISTINCT FROM p_statement
            OR v_existing.detail IS DISTINCT FROM COALESCE(p_detail, v_existing.detail)
          THEN cs.history || jsonb_build_object(
            'statement', v_existing.statement,
            'detail', v_existing.detail,
            'status', v_existing.status,
            'superseded_at', now()
          )
          ELSE cs.history
        END
    WHERE lower(cs.topic) = lower(p_topic);
  ELSE
    INSERT INTO current_state (topic, statement, detail, status, source_memory_ids, history)
    VALUES (
      p_topic, p_statement, p_detail, COALESCE(p_status, 'active'),
      CASE WHEN p_source_memory_id IS NULL THEN '{}'::BIGINT[] ELSE ARRAY[p_source_memory_id] END,
      '[]'::jsonb
    );
  END IF;

  RETURN QUERY
  SELECT cs.topic, cs.statement, cs.detail, cs.status, cs.source_memory_ids, cs.updated_at, cs.history
  FROM current_state cs WHERE lower(cs.topic) = lower(p_topic);
END;
$$;

-- -----------------------------------------------------------------------------
-- 4. Permissions (single-user system — RLS disabled everywhere else too)
-- -----------------------------------------------------------------------------
GRANT SELECT, INSERT, UPDATE ON current_state TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION agent_get_current_state(TEXT)                         TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION agent_update_current_state(TEXT, TEXT, TEXT, TEXT, BIGINT) TO anon, authenticated, service_role;

ALTER TABLE current_state DISABLE ROW LEVEL SECURITY;

-- -----------------------------------------------------------------------------
-- Verification (run after the above succeeds)
-- -----------------------------------------------------------------------------
-- SELECT * FROM agent_update_current_state('Test topic', 'First statement');
-- SELECT * FROM agent_update_current_state('Test topic', 'Corrected statement');  -- history should now have 1 entry
-- SELECT * FROM agent_get_current_state();
-- DELETE FROM current_state WHERE topic = 'Test topic';  -- clean up the test row
