-- =============================================================================
-- Command Centre — Task Write-Back Migration
-- =============================================================================
-- Paste this entire file into the Supabase SQL Editor and click Run.
-- Adds: due_date, priority, entity_name columns on tasks; pg_trgm for dedup;
-- agent_complete_task, agent_update_task, agent_create_task, agent_merge_tasks,
-- agent_find_similar_open_task RPCs; refreshes agent_get_tasks.
-- Safe to re-run: ALTER ... IF NOT EXISTS / CREATE OR REPLACE throughout.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Schema additions
-- -----------------------------------------------------------------------------
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS due_date    DATE;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS priority    TEXT;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS entity_name TEXT;
-- completed_at already exists (supabase_fresh_setup.sql); kept here as a no-op for safety.
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;

-- -----------------------------------------------------------------------------
-- 2. Fuzzy-match dedup support
-- -----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_tasks_task_trgm ON tasks USING gin (task gin_trgm_ops);

DROP FUNCTION IF EXISTS agent_find_similar_open_task(TEXT, FLOAT);
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
  WHERE COALESCE(t.status, 'open') = 'open'
    AND similarity(t.task, candidate_text) > match_threshold
  ORDER BY similarity(t.task, candidate_text) DESC
  LIMIT 1;
END;
$$;

-- -----------------------------------------------------------------------------
-- 3. Write-back RPCs
-- -----------------------------------------------------------------------------
DROP FUNCTION IF EXISTS agent_complete_task(TEXT);
CREATE OR REPLACE FUNCTION agent_complete_task(
  target_task_id TEXT
)
RETURNS TABLE (
  task_id      TEXT,
  task_text    TEXT,
  status       TEXT,
  completed_at TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  UPDATE tasks t
  SET status = 'completed',
      completed = true,
      completed_at = now()
  WHERE t.id = target_task_id::UUID
  RETURNING t.id::TEXT, t.task, t.status, t.completed_at;
END;
$$;

DROP FUNCTION IF EXISTS agent_update_task(TEXT, TEXT, TEXT, TEXT, DATE, TEXT);
CREATE OR REPLACE FUNCTION agent_update_task(
  target_task_id TEXT,
  new_task       TEXT DEFAULT NULL,
  new_urgency    TEXT DEFAULT NULL,
  new_priority   TEXT DEFAULT NULL,
  new_due_date   DATE DEFAULT NULL,
  new_category   TEXT DEFAULT NULL
)
RETURNS TABLE (
  task_id   TEXT,
  task_text TEXT,
  urgency   TEXT,
  priority  TEXT,
  due_date  DATE,
  category  TEXT,
  status    TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  UPDATE tasks t
  SET task     = COALESCE(new_task, t.task),
      urgency  = COALESCE(new_urgency, t.urgency),
      priority = COALESCE(new_priority, t.priority),
      due_date = COALESCE(new_due_date, t.due_date),
      category = COALESCE(new_category, t.category)
  WHERE t.id = target_task_id::UUID
  RETURNING t.id::TEXT, t.task, t.urgency, t.priority, t.due_date, t.category, t.status;
END;
$$;

DROP FUNCTION IF EXISTS agent_create_task(TEXT, TEXT, TEXT, TEXT, DATE, TEXT, BIGINT);
CREATE OR REPLACE FUNCTION agent_create_task(
  new_task        TEXT,
  new_context     TEXT DEFAULT NULL,
  new_urgency     TEXT DEFAULT 'soon',
  new_category    TEXT DEFAULT NULL,
  new_due_date    DATE DEFAULT NULL,
  new_entity_name TEXT DEFAULT NULL,
  source_memory_id BIGINT DEFAULT NULL
)
RETURNS TABLE (
  task_id   TEXT,
  task_text TEXT,
  urgency   TEXT,
  category  TEXT,
  due_date  DATE,
  status    TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
  v_memory_id BIGINT;
BEGIN
  v_memory_id := source_memory_id;

  IF v_memory_id IS NULL THEN
    INSERT INTO memories (title, transcript, source, status)
    VALUES (
      'Task created directly: ' || LEFT(new_task, 80),
      new_task,
      'claude_task_creation',
      'completed'
    )
    RETURNING id INTO v_memory_id;
  END IF;

  RETURN QUERY
  INSERT INTO tasks (memory_id, task, context, urgency, category, due_date, entity_name, status)
  VALUES (v_memory_id, new_task, new_context, new_urgency, new_category, new_due_date, new_entity_name, 'open')
  RETURNING tasks.id::TEXT, tasks.task, tasks.urgency, tasks.category, tasks.due_date, tasks.status;
END;
$$;

DROP FUNCTION IF EXISTS agent_merge_tasks(TEXT, TEXT[]);
CREATE OR REPLACE FUNCTION agent_merge_tasks(
  keep_task_id TEXT,
  merge_task_ids TEXT[]
)
RETURNS TABLE (
  task_id      TEXT,
  task_text    TEXT,
  due_date     DATE,
  created_at   TIMESTAMPTZ,
  merged_count INT
)
LANGUAGE plpgsql
AS $$
DECLARE
  v_earliest_created TIMESTAMPTZ;
  v_earliest_due     DATE;
BEGIN
  SELECT MIN(t.created_at) INTO v_earliest_created
  FROM tasks t
  WHERE t.id = ANY(merge_task_ids::UUID[]) OR t.id = keep_task_id::UUID;

  SELECT MIN(t.due_date) INTO v_earliest_due
  FROM tasks t
  WHERE (t.id = ANY(merge_task_ids::UUID[]) OR t.id = keep_task_id::UUID)
    AND t.due_date IS NOT NULL;

  UPDATE tasks
  SET status = 'merged', completed = true, completed_at = now()
  WHERE id = ANY(merge_task_ids::UUID[]);

  RETURN QUERY
  UPDATE tasks t
  SET created_at = v_earliest_created,
      due_date   = COALESCE(t.due_date, v_earliest_due)
  WHERE t.id = keep_task_id::UUID
  RETURNING t.id::TEXT, t.task, t.due_date, t.created_at, array_length(merge_task_ids, 1);
END;
$$;

-- -----------------------------------------------------------------------------
-- 4. Refresh agent_get_tasks to surface new columns + sort by priority/due_date
-- -----------------------------------------------------------------------------
DROP FUNCTION IF EXISTS agent_get_tasks(TEXT);
CREATE OR REPLACE FUNCTION agent_get_tasks(
  task_status TEXT DEFAULT 'open'
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
    m.title    AS memory_title,
    m.created_at AS created_date
  FROM tasks t
  JOIN memories m ON m.id = t.memory_id
  WHERE task_status = 'all'
    OR COALESCE(t.status, 'open') = task_status
  ORDER BY
    CASE t.priority
      WHEN 'high'   THEN 1
      WHEN 'medium' THEN 2
      WHEN 'low'    THEN 3
      ELSE 4
    END,
    t.due_date NULLS LAST,
    CASE t.urgency
      WHEN 'immediate'  THEN 1
      WHEN 'this_week'  THEN 2
      WHEN 'soon'       THEN 3
      ELSE 4
    END,
    m.created_at DESC
  LIMIT 25;
END;
$$;

-- -----------------------------------------------------------------------------
-- 5. Grants
-- -----------------------------------------------------------------------------
GRANT EXECUTE ON FUNCTION agent_get_tasks(TEXT)                          TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION agent_find_similar_open_task(TEXT, FLOAT)      TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION agent_complete_task(TEXT)                      TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION agent_update_task(TEXT, TEXT, TEXT, TEXT, DATE, TEXT) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION agent_create_task(TEXT, TEXT, TEXT, TEXT, DATE, TEXT, BIGINT) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION agent_merge_tasks(TEXT, TEXT[])                TO anon, authenticated, service_role;
