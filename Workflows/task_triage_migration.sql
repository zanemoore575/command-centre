-- =============================================================================
-- Task triage migration (2026-07-11)
-- Run in the Supabase SQL Editor on erwxszdcisyuyjmefvbj.
--
-- 1. New lifecycle statuses:
--      'suggested' — auto-extracted by the ingest pipeline, awaiting Zane's
--                    keep/dismiss (extracted tasks stop polluting 'open')
--      'archived'  — dismissed / bulk-triaged; preserved, never deleted
--    plus snooze support on open tasks (snoozed_until).
-- 2. Fixes agent_get_tasks: parameterised limit (was hard LIMIT 25),
--    urgency/due-date-first sort with recent tasks winning ties (was
--    priority-first, which with null priorities surfaced the oldest backlog),
--    ORDER BY the task's own created_at (was the memory's), excludes snoozed.
-- 3. New RPCs: agent_archive_task, agent_promote_task, agent_snooze_task.
-- 4. Bulk archive of the pre-2026-06-17 open-task flood (June bulk import).
--    NOTE: the status flip in section 4 was already executed live via REST on
--    2026-07-11; the statement here is idempotent and backfills archived_at.
--
-- Safe to re-run: IF NOT EXISTS / CREATE OR REPLACE / idempotent UPDATEs.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Schema additions
-- -----------------------------------------------------------------------------
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS archived_at   TIMESTAMPTZ;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS snoozed_until DATE;

-- -----------------------------------------------------------------------------
-- 2. agent_get_tasks — parameterised limit + useful sort
--    Statuses: 'open' (default, excludes snoozed), 'snoozed', 'suggested',
--    'completed', 'archived', 'merged', 'all'.
--    Return shape unchanged except created_date is now the TASK's created_at
--    (the memory's date made extracted tasks look months older than they were).
-- -----------------------------------------------------------------------------
DROP FUNCTION IF EXISTS agent_get_tasks(TEXT);
DROP FUNCTION IF EXISTS agent_get_tasks(TEXT, INT);
CREATE OR REPLACE FUNCTION agent_get_tasks(
  task_status TEXT DEFAULT 'open',
  limit_count INT  DEFAULT 50
)
RETURNS TABLE (
  task_id      TEXT,
  task_text    TEXT,
  context      TEXT,
  urgency      TEXT,
  priority     TEXT,
  category     TEXT,
  due_date     DATE,
  entity_name  TEXT,
  status       TEXT,
  memory_id    BIGINT,
  memory_title TEXT,
  created_date TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    t.id::TEXT AS task_id,
    t.task     AS task_text,
    t.context,
    t.urgency,
    t.priority,
    t.category,
    t.due_date,
    t.entity_name,
    COALESCE(t.status, 'open') AS status,
    t.memory_id,
    m.title      AS memory_title,
    t.created_at AS created_date
  FROM tasks t
  LEFT JOIN memories m ON m.id = t.memory_id
  WHERE CASE task_status
    WHEN 'all'     THEN true
    WHEN 'open'    THEN COALESCE(t.status, 'open') = 'open'
                        AND (t.snoozed_until IS NULL OR t.snoozed_until <= current_date)
    WHEN 'snoozed' THEN COALESCE(t.status, 'open') = 'open'
                        AND t.snoozed_until > current_date
    ELSE COALESCE(t.status, 'open') = task_status
  END
  ORDER BY
    t.due_date NULLS LAST,
    CASE t.urgency
      WHEN 'immediate' THEN 1
      WHEN 'this_week' THEN 2
      WHEN 'soon'      THEN 3
      ELSE 4
    END,
    t.created_at DESC
  LIMIT LEAST(GREATEST(limit_count, 1), 200);
END;
$$;

-- -----------------------------------------------------------------------------
-- 3. Triage RPCs
-- -----------------------------------------------------------------------------

-- Dismiss a task (from 'open' or 'suggested'). Preserved, not deleted.
DROP FUNCTION IF EXISTS agent_archive_task(TEXT);
CREATE OR REPLACE FUNCTION agent_archive_task(
  target_task_id TEXT
)
RETURNS TABLE (
  task_id     TEXT,
  task_text   TEXT,
  status      TEXT,
  archived_at TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  UPDATE tasks t
  SET status = 'archived',
      archived_at = now()
  WHERE t.id = target_task_id::UUID
  RETURNING t.id::TEXT, t.task, t.status, t.archived_at;
END;
$$;

-- Promote a 'suggested' task to 'open' (or resurrect an archived one).
DROP FUNCTION IF EXISTS agent_promote_task(TEXT);
CREATE OR REPLACE FUNCTION agent_promote_task(
  target_task_id TEXT
)
RETURNS TABLE (
  task_id   TEXT,
  task_text TEXT,
  status    TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  UPDATE tasks t
  SET status = 'open',
      archived_at = NULL,
      snoozed_until = NULL
  WHERE t.id = target_task_id::UUID
  RETURNING t.id::TEXT, t.task, t.status;
END;
$$;

-- Hide an open task until a date (it stays 'open', just out of the default view).
DROP FUNCTION IF EXISTS agent_snooze_task(TEXT, DATE);
CREATE OR REPLACE FUNCTION agent_snooze_task(
  target_task_id TEXT,
  until_date     DATE
)
RETURNS TABLE (
  task_id       TEXT,
  task_text     TEXT,
  status        TEXT,
  snoozed_until DATE
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  UPDATE tasks t
  SET snoozed_until = until_date
  WHERE t.id = target_task_id::UUID
  RETURNING t.id::TEXT, t.task, t.status, t.snoozed_until;
END;
$$;

-- -----------------------------------------------------------------------------
-- 3b. Dedup check now covers the 'suggested' inbox and recent dismissals —
--     a re-mentioned topic must not refill the inbox, and a task Zane
--     dismissed stays dismissed for 30 days even if it comes up again.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION agent_find_similar_open_task(
  candidate_text TEXT,
  match_threshold FLOAT DEFAULT 0.45
)
RETURNS TABLE (
  task_id    TEXT,
  task_text  TEXT,
  similarity REAL
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    t.id::TEXT AS task_id,
    t.task     AS task_text,
    similarity(t.task, candidate_text) AS similarity
  FROM tasks t
  WHERE (
      COALESCE(t.status, 'open') IN ('open', 'suggested')
      OR (t.status = 'archived' AND t.archived_at > now() - INTERVAL '30 days')
    )
    AND similarity(t.task, candidate_text) > match_threshold
  ORDER BY similarity(t.task, candidate_text) DESC
  LIMIT 1;
END;
$$;

-- -----------------------------------------------------------------------------
-- 4. Bulk archive: the pre-write-back-era open-task flood.
--    (Status flip already applied live 2026-07-11 via REST; this backfills
--    archived_at and re-applies safely if new pre-cutoff rows appear.)
-- -----------------------------------------------------------------------------
UPDATE tasks
SET status = 'archived'
WHERE status = 'open'
  AND created_at < '2026-06-17';

UPDATE tasks
SET archived_at = '2026-07-11T00:00:00+00:00'
WHERE status = 'archived'
  AND archived_at IS NULL;

-- -----------------------------------------------------------------------------
-- 5. Grants
-- -----------------------------------------------------------------------------
GRANT EXECUTE ON FUNCTION agent_get_tasks(TEXT, INT)     TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION agent_archive_task(TEXT)       TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION agent_promote_task(TEXT)       TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION agent_snooze_task(TEXT, DATE)  TO anon, authenticated, service_role;
