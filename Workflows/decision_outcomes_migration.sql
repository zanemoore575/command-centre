-- =============================================================================
-- Decision outcome loop migration (Wave 1b, 2026-07-16)
-- Run in the Supabase SQL Editor on erwxszdcisyuyjmefvbj.
--
-- 1,348 decisions logged, zero knowledge of which were right. Adds an outcome
-- loop: outcome/outcome_status/review_after columns, a record-outcome RPC, and
-- a due-for-review selector (surfaced on the check-in page + daily brief).
--
-- Safe to re-run: IF NOT EXISTS / CREATE OR REPLACE.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Schema additions
-- -----------------------------------------------------------------------------
ALTER TABLE decisions ADD COLUMN IF NOT EXISTS outcome              TEXT;
ALTER TABLE decisions ADD COLUMN IF NOT EXISTS outcome_status       TEXT DEFAULT 'pending';  -- pending | worked | didnt_work | mixed | obsolete
ALTER TABLE decisions ADD COLUMN IF NOT EXISTS outcome_recorded_at  TIMESTAMPTZ;
ALTER TABLE decisions ADD COLUMN IF NOT EXISTS review_after         DATE;

-- Backfill nulls from before this migration so the due-for-review filter
-- (outcome_status = 'pending') covers every existing decision.
UPDATE decisions SET outcome_status = 'pending' WHERE outcome_status IS NULL;

-- -----------------------------------------------------------------------------
-- 2. agent_record_decision_outcome — Zane (or Claude on his behalf) closes the
--    loop on a past decision from the check-in page or a chat.
-- -----------------------------------------------------------------------------
DROP FUNCTION IF EXISTS agent_record_decision_outcome(TEXT, TEXT, TEXT);
CREATE OR REPLACE FUNCTION agent_record_decision_outcome(
  target_decision_id TEXT,
  new_outcome_status  TEXT,
  new_outcome_text    TEXT DEFAULT NULL
)
RETURNS TABLE (
  decision_id         TEXT,
  decision_text       TEXT,
  outcome_status      TEXT,
  outcome             TEXT,
  outcome_recorded_at TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  UPDATE decisions d
  SET outcome_status      = new_outcome_status,
      outcome             = COALESCE(new_outcome_text, d.outcome),
      outcome_recorded_at = now()
  WHERE d.id = target_decision_id::UUID
  RETURNING d.id::TEXT, d.decision, d.outcome_status, d.outcome, d.outcome_recorded_at;
END;
$$;

-- -----------------------------------------------------------------------------
-- 3. agent_get_decisions_due_for_review — selection: still pending, and either
--    past its explicit review_after date or (no review_after set — true for
--    every pre-migration decision) at least 14 days old. Certain-confidence
--    and strategy/pricing/pivot categories surface first. 1-2/day by default.
-- -----------------------------------------------------------------------------
DROP FUNCTION IF EXISTS agent_get_decisions_due_for_review(INT);
CREATE OR REPLACE FUNCTION agent_get_decisions_due_for_review(
  limit_count INT DEFAULT 2
)
RETURNS TABLE (
  decision_id      TEXT,
  decision_text    TEXT,
  category         TEXT,
  reasoning        TEXT,
  confidence_level TEXT,
  memory_id        BIGINT,
  memory_title     TEXT,
  decision_date    TIMESTAMPTZ,
  review_after     DATE
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    d.id::TEXT AS decision_id,
    d.decision AS decision_text,
    d.category,
    d.reasoning,
    d.confidence_level,
    d.memory_id,
    m.title      AS memory_title,
    m.created_at AS decision_date,
    d.review_after
  FROM decisions d
  JOIN memories m ON m.id = d.memory_id
  WHERE COALESCE(d.outcome_status, 'pending') = 'pending'
    AND (
      (d.review_after IS NOT NULL AND d.review_after <= CURRENT_DATE)
      OR (d.review_after IS NULL AND m.created_at <= now() - INTERVAL '14 days')
    )
  ORDER BY
    CASE WHEN d.confidence_level = 'certain' THEN 0 ELSE 1 END,
    CASE WHEN d.category ILIKE ANY(ARRAY['%strategy%', '%pricing%', '%pivot%']) THEN 0 ELSE 1 END,
    d.review_after NULLS LAST,
    m.created_at ASC
  LIMIT LEAST(GREATEST(limit_count, 1), 10);
END;
$$;

-- -----------------------------------------------------------------------------
-- 4. Grants
-- -----------------------------------------------------------------------------
GRANT EXECUTE ON FUNCTION agent_record_decision_outcome(TEXT, TEXT, TEXT) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION agent_get_decisions_due_for_review(INT)         TO anon, authenticated, service_role;

-- -----------------------------------------------------------------------------
-- Verification (run after the above succeeds)
-- -----------------------------------------------------------------------------
-- SELECT * FROM agent_get_decisions_due_for_review(5);
-- SELECT * FROM agent_record_decision_outcome('<a real decision UUID>', 'worked', 'Confirmed via...');
