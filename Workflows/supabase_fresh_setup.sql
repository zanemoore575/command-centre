-- =============================================================================
-- CAiS COMMAND CENTRE - FRESH SUPABASE SETUP
-- =============================================================================
-- Run this entire file in the Supabase SQL Editor (one paste, one run).
-- PREREQUISITE: Enable the pgvector extension first:
--   Dashboard → Database → Extensions → search "vector" → Enable
-- =============================================================================


-- =============================================================================
-- SECTION 1: CORE TABLES
-- =============================================================================

CREATE TABLE IF NOT EXISTS memories (
  id          BIGSERIAL PRIMARY KEY,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ DEFAULT now(),
  source      TEXT,
  content_type TEXT,
  raw_file_url TEXT,
  transcript  TEXT,
  title       TEXT,
  summary     TEXT,
  status      TEXT DEFAULT 'pending',
  embeddings  VECTOR(1536)
);

CREATE TABLE IF NOT EXISTS telegram_sessions (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  chat_id       BIGINT NOT NULL,
  started_at    TIMESTAMPTZ DEFAULT now(),
  last_activity TIMESTAMPTZ DEFAULT now(),
  messages      JSONB DEFAULT '[]'::jsonb,
  status        TEXT DEFAULT 'active',
  memory_id     BIGINT REFERENCES memories(id)
);

CREATE TABLE IF NOT EXISTS entities (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  memory_id   BIGINT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  created_at  TIMESTAMPTZ DEFAULT now(),
  entity_type TEXT NOT NULL,
  entity_name TEXT NOT NULL,
  context     TEXT
);

CREATE TABLE IF NOT EXISTS decisions (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  memory_id              BIGINT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  created_at             TIMESTAMPTZ DEFAULT now(),
  decision               TEXT NOT NULL,
  category               TEXT,
  reasoning              TEXT,
  alternatives_considered JSONB DEFAULT '[]'::jsonb,
  confidence_level       TEXT,
  emotional_context      TEXT
);

CREATE TABLE IF NOT EXISTS reflections (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  memory_id       BIGINT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  created_at      TIMESTAMPTZ DEFAULT now(),
  reflection_type TEXT,
  reflection      TEXT NOT NULL,
  topic           TEXT,
  emotional_tone  TEXT
);

CREATE TABLE IF NOT EXISTS strategic_insights (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  memory_id           BIGINT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  created_at          TIMESTAMPTZ DEFAULT now(),
  insight_category    TEXT,
  insight             TEXT NOT NULL,
  supporting_evidence JSONB DEFAULT '[]'::jsonb,
  confidence          TEXT,
  actionable          BOOLEAN DEFAULT false,
  suggested_action    TEXT
);

CREATE TABLE IF NOT EXISTS customer_insights (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  memory_id             BIGINT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  created_at            TIMESTAMPTZ DEFAULT now(),
  customer_name         TEXT NOT NULL,
  customer_type         TEXT,
  pain_point            TEXT,
  desire                TEXT,
  objection             TEXT,
  automation_opportunity TEXT,
  quote                 TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  memory_id    BIGINT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  created_at   TIMESTAMPTZ DEFAULT now(),
  task         TEXT NOT NULL,
  context      TEXT,
  urgency      TEXT,
  category     TEXT,
  completed    BOOLEAN DEFAULT false,
  completed_at TIMESTAMPTZ,
  status       TEXT DEFAULT 'open'
);

CREATE TABLE IF NOT EXISTS themes (
  id                           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  memory_id                    BIGINT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  created_at                   TIMESTAMPTZ DEFAULT now(),
  main_theme                   TEXT NOT NULL,
  sub_themes                   JSONB DEFAULT '[]'::jsonb,
  conversation_type            TEXT,
  business_relevance           TEXT,
  contains_decisions           BOOLEAN DEFAULT false,
  contains_customer_insights   BOOLEAN DEFAULT false,
  contains_personal_breakthrough BOOLEAN DEFAULT false,
  contains_action_items        BOOLEAN DEFAULT false,
  key_takeaways                JSONB DEFAULT '[]'::jsonb
);

CREATE TABLE IF NOT EXISTS living_context (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id              TEXT DEFAULT 'zane',
  updated_at           TIMESTAMPTZ DEFAULT now(),
  business_hypotheses  JSONB DEFAULT '[]'::jsonb,
  directional_summary  JSONB DEFAULT '{}'::jsonb,
  patterns             JSONB DEFAULT '{}'::jsonb,
  identity_notes       JSONB DEFAULT '{}'::jsonb,
  active_threads       TEXT[] DEFAULT '{}'::text[]
);

-- Seed one living_context row for Zane (required by the bot)
INSERT INTO living_context (user_id) VALUES ('zane')
ON CONFLICT DO NOTHING;


-- =============================================================================
-- SECTION 2: MEMORY OVERVIEW VIEW
-- =============================================================================

CREATE OR REPLACE VIEW memory_overview AS
SELECT
  m.id,
  m.title,
  m.source,
  m.content_type,
  m.status,
  m.created_at,
  t.main_theme,
  t.conversation_type,
  t.business_relevance,
  (SELECT COUNT(*) FROM entities e       WHERE e.memory_id = m.id) AS entity_count,
  (SELECT COUNT(*) FROM decisions d      WHERE d.memory_id = m.id) AS decision_count,
  (SELECT COUNT(*) FROM strategic_insights s WHERE s.memory_id = m.id) AS insight_count,
  (SELECT COUNT(*) FROM reflections r    WHERE r.memory_id = m.id) AS reflection_count,
  (SELECT COUNT(*) FROM strategic_insights s WHERE s.memory_id = m.id) AS strategic_count,
  (SELECT COUNT(*) FROM tasks tk         WHERE tk.memory_id = m.id) AS task_count
FROM memories m
LEFT JOIN themes t ON t.memory_id = m.id;


-- =============================================================================
-- SECTION 3: SESSION MANAGEMENT RPC FUNCTIONS
-- =============================================================================

-- Returns existing active session for a chat_id, or creates a new one
CREATE OR REPLACE FUNCTION get_or_create_session(p_chat_id BIGINT)
RETURNS telegram_sessions
LANGUAGE plpgsql
AS $$
DECLARE
  v_session telegram_sessions;
BEGIN
  SELECT * INTO v_session
  FROM telegram_sessions
  WHERE chat_id = p_chat_id
    AND status = 'active'
  ORDER BY started_at DESC
  LIMIT 1;

  IF NOT FOUND THEN
    INSERT INTO telegram_sessions (chat_id, status, messages)
    VALUES (p_chat_id, 'active', '[]'::jsonb)
    RETURNING * INTO v_session;
  ELSE
    UPDATE telegram_sessions
    SET last_activity = now()
    WHERE id = v_session.id;
  END IF;

  RETURN v_session;
END;
$$;

-- Appends a single message object to the session's messages array
CREATE OR REPLACE FUNCTION append_session_message(
  p_session_id UUID,
  p_role       TEXT,
  p_content    TEXT
)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  UPDATE telegram_sessions
  SET
    messages      = messages || jsonb_build_object('role', p_role, 'content', p_content),
    last_activity = now()
  WHERE id = p_session_id;
END;
$$;

-- Compiles all messages in a session into a single transcript string
CREATE OR REPLACE FUNCTION compile_session_transcript(p_session_id UUID)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
  v_transcript TEXT := '';
  v_msg        JSONB;
BEGIN
  FOR v_msg IN
    SELECT jsonb_array_elements(messages)
    FROM telegram_sessions
    WHERE id = p_session_id
  LOOP
    v_transcript := v_transcript
      || upper(v_msg->>'role') || ': '
      || (v_msg->>'content') || E'\n\n';
  END LOOP;

  RETURN TRIM(v_transcript);
END;
$$;

-- Updates living_context for 'zane' — called after /end to persist session insights
CREATE OR REPLACE FUNCTION update_living_context(
  p_user_id            TEXT,
  p_business_hypotheses JSONB DEFAULT NULL,
  p_directional_summary JSONB DEFAULT NULL,
  p_patterns           JSONB DEFAULT NULL,
  p_identity_notes     JSONB DEFAULT NULL,
  p_active_threads     TEXT[] DEFAULT NULL
)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  UPDATE living_context
  SET
    updated_at           = now(),
    business_hypotheses  = COALESCE(p_business_hypotheses, business_hypotheses),
    directional_summary  = COALESCE(p_directional_summary, directional_summary),
    patterns             = COALESCE(p_patterns, patterns),
    identity_notes       = COALESCE(p_identity_notes, identity_notes),
    active_threads       = COALESCE(p_active_threads, active_threads)
  WHERE user_id = p_user_id;
END;
$$;

-- Returns the living context row for a given user
CREATE OR REPLACE FUNCTION get_living_context(p_user_id TEXT DEFAULT 'zane')
RETURNS living_context
LANGUAGE plpgsql
AS $$
DECLARE
  v_ctx living_context;
BEGIN
  SELECT * INTO v_ctx FROM living_context WHERE user_id = p_user_id LIMIT 1;
  RETURN v_ctx;
END;
$$;


-- =============================================================================
-- SECTION 4: AGENT TOOL RPC FUNCTIONS
-- =============================================================================

DROP FUNCTION IF EXISTS agent_search_memories(TEXT, FLOAT, INT);
DROP FUNCTION IF EXISTS agent_search_memories_by_embedding(VECTOR(1536), FLOAT, INT);
DROP FUNCTION IF EXISTS agent_get_entity_details(TEXT);
DROP FUNCTION IF EXISTS agent_get_decisions(TEXT, INT);
DROP FUNCTION IF EXISTS agent_get_reflections(TEXT, INT);
DROP FUNCTION IF EXISTS agent_get_tasks(TEXT);
DROP FUNCTION IF EXISTS agent_get_strategic_insights(TEXT, INT);
DROP FUNCTION IF EXISTS agent_get_customer_insights(TEXT);
DROP FUNCTION IF EXISTS agent_get_memory_context(BIGINT);
DROP FUNCTION IF EXISTS agent_get_recent_memories(INT, TEXT);
DROP FUNCTION IF EXISTS agent_search_by_theme(TEXT, INT);
DROP FUNCTION IF EXISTS get_memory_enrichment(BIGINT[]);
DROP FUNCTION IF EXISTS agent_discover_database();

-- 1. Semantic memory search (n8n embeds the query before calling this)
CREATE OR REPLACE FUNCTION agent_search_memories_by_embedding(
  query_embedding VECTOR(1536),
  match_threshold FLOAT DEFAULT 0.35,
  match_count     INT DEFAULT 8
)
RETURNS TABLE (
  memory_id        BIGINT,
  title            TEXT,
  summary          TEXT,
  transcript_preview TEXT,
  source           TEXT,
  created_at       TIMESTAMPTZ,
  similarity       FLOAT,
  main_theme       TEXT,
  has_decisions    BOOLEAN,
  has_reflections  BOOLEAN,
  entity_count     BIGINT,
  decision_count   BIGINT
)
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    m.id AS memory_id,
    m.title,
    m.summary,
    LEFT(m.transcript, 500) AS transcript_preview,
    m.source,
    m.created_at,
    (1 - (m.embeddings <=> query_embedding))::FLOAT AS similarity,
    t.main_theme,
    COALESCE(t.contains_decisions, false) AS has_decisions,
    COALESCE(t.contains_personal_breakthrough, false) AS has_reflections,
    (SELECT COUNT(*) FROM entities e  WHERE e.memory_id = m.id) AS entity_count,
    (SELECT COUNT(*) FROM decisions d WHERE d.memory_id = m.id) AS decision_count
  FROM memories m
  LEFT JOIN themes t ON t.memory_id = m.id
  WHERE m.embeddings IS NOT NULL
    AND m.status = 'completed'
    AND (1 - (m.embeddings <=> query_embedding)) > match_threshold
  ORDER BY m.embeddings <=> query_embedding
  LIMIT match_count;
END;
$$;

-- 2. Entity search
CREATE OR REPLACE FUNCTION agent_get_entity_details(search_name TEXT)
RETURNS TABLE (
  entity_id    BIGINT,
  entity_name  TEXT,
  entity_type  TEXT,
  context      TEXT,
  memory_id    BIGINT,
  memory_title TEXT,
  memory_date  TIMESTAMPTZ,
  mention_count BIGINT
)
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  WITH entity_matches AS (
    SELECT e.id, e.entity_name, e.entity_type, e.context, e.memory_id
    FROM entities e
    WHERE e.entity_name ILIKE '%' || search_name || '%'
  ),
  aggregated AS (
    SELECT em.entity_name, em.entity_type, COUNT(*) AS mention_count
    FROM entity_matches em
    GROUP BY em.entity_name, em.entity_type
  )
  SELECT
    em.id AS entity_id,
    em.entity_name,
    em.entity_type,
    em.context,
    em.memory_id,
    m.title AS memory_title,
    m.created_at AS memory_date,
    a.mention_count
  FROM entity_matches em
  JOIN memories m    ON m.id = em.memory_id
  JOIN aggregated a  ON a.entity_name = em.entity_name AND a.entity_type = em.entity_type
  ORDER BY a.mention_count DESC, m.created_at DESC
  LIMIT 20;
END;
$$;

-- 3. Decisions search
CREATE OR REPLACE FUNCTION agent_get_decisions(
  search_topic TEXT DEFAULT NULL,
  recent_days  INT DEFAULT 365
)
RETURNS TABLE (
  decision_id    BIGINT,
  decision_text  TEXT,
  category       TEXT,
  reasoning      TEXT,
  confidence_level TEXT,
  emotional_context TEXT,
  memory_id      BIGINT,
  memory_title   TEXT,
  decision_date  TIMESTAMPTZ
)
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    d.id AS decision_id,
    d.decision AS decision_text,
    d.category,
    d.reasoning,
    d.confidence_level,
    d.emotional_context,
    d.memory_id,
    m.title AS memory_title,
    m.created_at AS decision_date
  FROM decisions d
  JOIN memories m ON m.id = d.memory_id
  WHERE m.created_at > NOW() - (recent_days || ' days')::INTERVAL
    AND (
      search_topic IS NULL
      OR d.decision  ILIKE '%' || search_topic || '%'
      OR d.category  ILIKE '%' || search_topic || '%'
      OR d.reasoning ILIKE '%' || search_topic || '%'
    )
  ORDER BY m.created_at DESC
  LIMIT 15;
END;
$$;

-- 4. Reflections search
CREATE OR REPLACE FUNCTION agent_get_reflections(
  search_topic TEXT DEFAULT NULL,
  recent_days  INT DEFAULT 365
)
RETURNS TABLE (
  reflection_id   BIGINT,
  reflection_text TEXT,
  reflection_type TEXT,
  topic           TEXT,
  emotional_tone  TEXT,
  memory_id       BIGINT,
  memory_title    TEXT,
  reflection_date TIMESTAMPTZ
)
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    r.id AS reflection_id,
    r.reflection AS reflection_text,
    r.reflection_type,
    r.topic,
    r.emotional_tone,
    r.memory_id,
    m.title AS memory_title,
    m.created_at AS reflection_date
  FROM reflections r
  JOIN memories m ON m.id = r.memory_id
  WHERE m.created_at > NOW() - (recent_days || ' days')::INTERVAL
    AND (
      search_topic IS NULL
      OR r.reflection      ILIKE '%' || search_topic || '%'
      OR r.topic           ILIKE '%' || search_topic || '%'
      OR r.reflection_type ILIKE '%' || search_topic || '%'
    )
  ORDER BY m.created_at DESC
  LIMIT 15;
END;
$$;

-- 5. Tasks
CREATE OR REPLACE FUNCTION agent_get_tasks(task_status TEXT DEFAULT 'open')
RETURNS TABLE (
  task_id      BIGINT,
  task_text    TEXT,
  context      TEXT,
  urgency      TEXT,
  category     TEXT,
  status       TEXT,
  memory_id    BIGINT,
  memory_title TEXT,
  created_date TIMESTAMPTZ
)
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    t.id AS task_id,
    t.task AS task_text,
    t.context,
    t.urgency,
    t.category,
    COALESCE(t.status, 'open') AS status,
    t.memory_id,
    m.title AS memory_title,
    m.created_at AS created_date
  FROM tasks t
  JOIN memories m ON m.id = t.memory_id
  WHERE task_status = 'all'
    OR COALESCE(t.status, 'open') = task_status
  ORDER BY
    CASE t.urgency
      WHEN 'immediate' THEN 1
      WHEN 'this_week' THEN 2
      WHEN 'soon'      THEN 3
      ELSE 4
    END,
    m.created_at DESC
  LIMIT 25;
END;
$$;

-- 6. Strategic insights
CREATE OR REPLACE FUNCTION agent_get_strategic_insights(
  search_category TEXT DEFAULT NULL,
  recent_days     INT DEFAULT 365
)
RETURNS TABLE (
  insight_id        BIGINT,
  insight_text      TEXT,
  insight_category  TEXT,
  supporting_evidence TEXT,
  confidence        TEXT,
  suggested_action  TEXT,
  memory_id         BIGINT,
  memory_title      TEXT,
  insight_date      TIMESTAMPTZ
)
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    s.id AS insight_id,
    s.insight AS insight_text,
    s.insight_category,
    s.supporting_evidence,
    s.confidence,
    s.suggested_action,
    s.memory_id,
    m.title AS memory_title,
    m.created_at AS insight_date
  FROM strategic_insights s
  JOIN memories m ON m.id = s.memory_id
  WHERE m.created_at > NOW() - (recent_days || ' days')::INTERVAL
    AND (
      search_category IS NULL
      OR s.insight_category ILIKE '%' || search_category || '%'
      OR s.insight          ILIKE '%' || search_category || '%'
    )
  ORDER BY m.created_at DESC
  LIMIT 15;
END;
$$;

-- 7. Customer insights
CREATE OR REPLACE FUNCTION agent_get_customer_insights(search_customer TEXT DEFAULT NULL)
RETURNS TABLE (
  insight_id           BIGINT,
  customer_name        TEXT,
  customer_type        TEXT,
  pain_point           TEXT,
  desire               TEXT,
  objection            TEXT,
  automation_opportunity TEXT,
  customer_quote       TEXT,
  memory_id            BIGINT,
  memory_title         TEXT,
  insight_date         TIMESTAMPTZ
)
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    c.id AS insight_id,
    c.customer_name,
    c.customer_type,
    c.pain_point,
    c.desire,
    c.objection,
    c.automation_opportunity,
    c.quote AS customer_quote,
    c.memory_id,
    m.title AS memory_title,
    m.created_at AS insight_date
  FROM customer_insights c
  JOIN memories m ON m.id = c.memory_id
  WHERE search_customer IS NULL
    OR c.customer_name ILIKE '%' || search_customer || '%'
    OR c.customer_type ILIKE '%' || search_customer || '%'
  ORDER BY m.created_at DESC
  LIMIT 20;
END;
$$;

-- 8. Full memory context (deep dive)
CREATE OR REPLACE FUNCTION agent_get_memory_context(target_memory_id BIGINT)
RETURNS TABLE (
  memory_id         BIGINT,
  title             TEXT,
  full_transcript   TEXT,
  source            TEXT,
  created_at        TIMESTAMPTZ,
  main_theme        TEXT,
  sub_themes        TEXT,
  conversation_type TEXT,
  key_takeaways     TEXT,
  entities          JSONB,
  decisions         JSONB,
  reflections       JSONB,
  strategic_insights JSONB,
  tasks             JSONB
)
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    m.id AS memory_id,
    m.title,
    m.transcript AS full_transcript,
    m.source,
    m.created_at,
    t.main_theme,
    t.sub_themes,
    t.conversation_type,
    t.key_takeaways,
    COALESCE(
      (SELECT jsonb_agg(jsonb_build_object('name', e.entity_name, 'type', e.entity_type, 'context', e.context))
       FROM entities e WHERE e.memory_id = m.id), '[]'::jsonb) AS entities,
    COALESCE(
      (SELECT jsonb_agg(jsonb_build_object('decision', d.decision, 'category', d.category, 'reasoning', d.reasoning, 'confidence', d.confidence_level))
       FROM decisions d WHERE d.memory_id = m.id), '[]'::jsonb) AS decisions,
    COALESCE(
      (SELECT jsonb_agg(jsonb_build_object('reflection', r.reflection, 'type', r.reflection_type, 'topic', r.topic, 'tone', r.emotional_tone))
       FROM reflections r WHERE r.memory_id = m.id), '[]'::jsonb) AS reflections,
    COALESCE(
      (SELECT jsonb_agg(jsonb_build_object('insight', s.insight, 'category', s.insight_category, 'confidence', s.confidence, 'action', s.suggested_action))
       FROM strategic_insights s WHERE s.memory_id = m.id), '[]'::jsonb) AS strategic_insights,
    COALESCE(
      (SELECT jsonb_agg(jsonb_build_object('task', tk.task, 'urgency', tk.urgency, 'category', tk.category, 'status', COALESCE(tk.status, 'open')))
       FROM tasks tk WHERE tk.memory_id = m.id), '[]'::jsonb) AS tasks
  FROM memories m
  LEFT JOIN themes t ON t.memory_id = m.id
  WHERE m.id = target_memory_id;
END;
$$;

-- 9. Recent memories
CREATE OR REPLACE FUNCTION agent_get_recent_memories(
  limit_count   INT DEFAULT 10,
  filter_source TEXT DEFAULT NULL
)
RETURNS TABLE (
  memory_id        BIGINT,
  title            TEXT,
  summary          TEXT,
  source           TEXT,
  created_at       TIMESTAMPTZ,
  main_theme       TEXT,
  conversation_type TEXT,
  entity_count     BIGINT,
  decision_count   BIGINT,
  reflection_count BIGINT
)
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    m.id AS memory_id,
    m.title,
    m.summary,
    m.source,
    m.created_at,
    t.main_theme,
    t.conversation_type,
    (SELECT COUNT(*) FROM entities e   WHERE e.memory_id = m.id) AS entity_count,
    (SELECT COUNT(*) FROM decisions d  WHERE d.memory_id = m.id) AS decision_count,
    (SELECT COUNT(*) FROM reflections r WHERE r.memory_id = m.id) AS reflection_count
  FROM memories m
  LEFT JOIN themes t ON t.memory_id = m.id
  WHERE m.status = 'completed'
    AND (filter_source IS NULL OR m.source = filter_source)
  ORDER BY m.created_at DESC
  LIMIT limit_count;
END;
$$;

-- 10. Search by theme
CREATE OR REPLACE FUNCTION agent_search_by_theme(
  theme_keywords TEXT,
  limit_count    INT DEFAULT 10
)
RETURNS TABLE (
  memory_id        BIGINT,
  title            TEXT,
  summary          TEXT,
  main_theme       TEXT,
  sub_themes       TEXT,
  conversation_type TEXT,
  created_at       TIMESTAMPTZ,
  relevance_score  INT
)
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    m.id AS memory_id,
    m.title,
    m.summary,
    t.main_theme,
    t.sub_themes,
    t.conversation_type,
    m.created_at,
    (
      CASE WHEN t.main_theme ILIKE '%' || theme_keywords || '%' THEN 3 ELSE 0 END +
      CASE WHEN t.sub_themes ILIKE '%' || theme_keywords || '%' THEN 2 ELSE 0 END +
      CASE WHEN m.title      ILIKE '%' || theme_keywords || '%' THEN 2 ELSE 0 END +
      CASE WHEN m.summary    ILIKE '%' || theme_keywords || '%' THEN 1 ELSE 0 END
    )::INT AS relevance_score
  FROM memories m
  LEFT JOIN themes t ON t.memory_id = m.id
  WHERE m.status = 'completed'
    AND (
      t.main_theme ILIKE '%' || theme_keywords || '%'
      OR t.sub_themes ILIKE '%' || theme_keywords || '%'
      OR m.title      ILIKE '%' || theme_keywords || '%'
      OR m.summary    ILIKE '%' || theme_keywords || '%'
    )
  ORDER BY relevance_score DESC, m.created_at DESC
  LIMIT limit_count;
END;
$$;

-- 11. Enrichment (batch context for multiple memory IDs)
CREATE OR REPLACE FUNCTION get_memory_enrichment(memory_ids BIGINT[])
RETURNS TABLE (
  memory_id         BIGINT,
  entities          JSONB,
  decisions         JSONB,
  reflections       JSONB,
  strategic_insights JSONB,
  customer_insights JSONB,
  tasks             JSONB,
  themes            JSONB
)
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    m.id AS memory_id,
    COALESCE((SELECT jsonb_agg(DISTINCT jsonb_build_object('name', e.entity_name, 'type', e.entity_type, 'context', e.context)) FROM entities e WHERE e.memory_id = m.id), '[]'::jsonb) AS entities,
    COALESCE((SELECT jsonb_agg(DISTINCT jsonb_build_object('decision', d.decision, 'category', d.category, 'reasoning', d.reasoning)) FROM decisions d WHERE d.memory_id = m.id), '[]'::jsonb) AS decisions,
    COALESCE((SELECT jsonb_agg(DISTINCT jsonb_build_object('reflection', r.reflection, 'type', r.reflection_type, 'topic', r.topic)) FROM reflections r WHERE r.memory_id = m.id), '[]'::jsonb) AS reflections,
    COALESCE((SELECT jsonb_agg(DISTINCT jsonb_build_object('insight', s.insight, 'category', s.insight_category, 'action', s.suggested_action)) FROM strategic_insights s WHERE s.memory_id = m.id), '[]'::jsonb) AS strategic_insights,
    COALESCE((SELECT jsonb_agg(DISTINCT jsonb_build_object('customer', c.customer_name, 'type', c.customer_type, 'pain_point', c.pain_point, 'desire', c.desire)) FROM customer_insights c WHERE c.memory_id = m.id), '[]'::jsonb) AS customer_insights,
    COALESCE((SELECT jsonb_agg(DISTINCT jsonb_build_object('task', tk.task, 'urgency', tk.urgency, 'status', COALESCE(tk.status, 'open'))) FROM tasks tk WHERE tk.memory_id = m.id), '[]'::jsonb) AS tasks,
    COALESCE((SELECT jsonb_agg(DISTINCT jsonb_build_object('theme', t.main_theme, 'sub_themes', t.sub_themes, 'type', t.conversation_type)) FROM themes t WHERE t.memory_id = m.id), '[]'::jsonb) AS themes
  FROM unnest(memory_ids) AS m(id);
END;
$$;


-- =============================================================================
-- SECTION 5: DISCOVERY FUNCTION
-- =============================================================================

CREATE OR REPLACE FUNCTION agent_discover_database()
RETURNS TABLE (
  category         TEXT,
  data_type        TEXT,
  available_values TEXT[],
  total_count      BIGINT
)
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY

  SELECT 'entities'::TEXT, 'entity_types'::TEXT,
    ARRAY_AGG(DISTINCT e.entity_type ORDER BY e.entity_type)::TEXT[],
    COUNT(DISTINCT e.entity_type)
  FROM entities e

  UNION ALL

  SELECT 'entities'::TEXT, 'people'::TEXT,
    (SELECT ARRAY_AGG(entity_name ORDER BY mention_count DESC) FROM (
      SELECT entity_name, COUNT(*) as mention_count FROM entities WHERE entity_type = 'person'
      GROUP BY entity_name ORDER BY COUNT(*) DESC LIMIT 30) sub)::TEXT[],
    (SELECT COUNT(DISTINCT entity_name) FROM entities WHERE entity_type = 'person')

  UNION ALL

  SELECT 'entities'::TEXT, 'companies'::TEXT,
    (SELECT ARRAY_AGG(entity_name ORDER BY mention_count DESC) FROM (
      SELECT entity_name, COUNT(*) as mention_count FROM entities WHERE entity_type = 'company'
      GROUP BY entity_name ORDER BY COUNT(*) DESC LIMIT 30) sub)::TEXT[],
    (SELECT COUNT(DISTINCT entity_name) FROM entities WHERE entity_type = 'company')

  UNION ALL

  SELECT 'entities'::TEXT, 'projects'::TEXT,
    (SELECT ARRAY_AGG(entity_name ORDER BY mention_count DESC) FROM (
      SELECT entity_name, COUNT(*) as mention_count FROM entities WHERE entity_type = 'project'
      GROUP BY entity_name ORDER BY COUNT(*) DESC LIMIT 30) sub)::TEXT[],
    (SELECT COUNT(DISTINCT entity_name) FROM entities WHERE entity_type = 'project')

  UNION ALL

  SELECT 'entities'::TEXT, 'tools'::TEXT,
    (SELECT ARRAY_AGG(entity_name ORDER BY mention_count DESC) FROM (
      SELECT entity_name, COUNT(*) as mention_count FROM entities WHERE entity_type = 'tool'
      GROUP BY entity_name ORDER BY COUNT(*) DESC LIMIT 30) sub)::TEXT[],
    (SELECT COUNT(DISTINCT entity_name) FROM entities WHERE entity_type = 'tool')

  UNION ALL

  SELECT 'decisions'::TEXT, 'categories'::TEXT,
    ARRAY_AGG(DISTINCT d.category ORDER BY d.category)::TEXT[],
    COUNT(DISTINCT d.category)
  FROM decisions d WHERE d.category IS NOT NULL

  UNION ALL

  SELECT 'decisions'::TEXT, 'total_decisions'::TEXT,
    ARRAY['Total decisions recorded: ' || COUNT(*)::TEXT]::TEXT[], COUNT(*)
  FROM decisions

  UNION ALL

  SELECT 'reflections'::TEXT, 'topics'::TEXT,
    (SELECT ARRAY_AGG(topic ORDER BY cnt DESC) FROM (
      SELECT topic, COUNT(*) as cnt FROM reflections WHERE topic IS NOT NULL
      GROUP BY topic ORDER BY COUNT(*) DESC LIMIT 30) sub)::TEXT[],
    (SELECT COUNT(DISTINCT topic) FROM reflections WHERE topic IS NOT NULL)

  UNION ALL

  SELECT 'reflections'::TEXT, 'reflection_types'::TEXT,
    ARRAY_AGG(DISTINCT r.reflection_type ORDER BY r.reflection_type)::TEXT[],
    COUNT(DISTINCT r.reflection_type)
  FROM reflections r WHERE r.reflection_type IS NOT NULL

  UNION ALL

  SELECT 'reflections'::TEXT, 'emotional_tones'::TEXT,
    ARRAY_AGG(DISTINCT r.emotional_tone ORDER BY r.emotional_tone)::TEXT[],
    COUNT(DISTINCT r.emotional_tone)
  FROM reflections r WHERE r.emotional_tone IS NOT NULL

  UNION ALL

  SELECT 'customer_insights'::TEXT, 'customer_names'::TEXT,
    (SELECT ARRAY_AGG(customer_name ORDER BY cnt DESC) FROM (
      SELECT customer_name, COUNT(*) as cnt FROM customer_insights
      GROUP BY customer_name ORDER BY COUNT(*) DESC LIMIT 30) sub)::TEXT[],
    (SELECT COUNT(DISTINCT customer_name) FROM customer_insights)

  UNION ALL

  SELECT 'customer_insights'::TEXT, 'customer_types'::TEXT,
    ARRAY_AGG(DISTINCT c.customer_type ORDER BY c.customer_type)::TEXT[],
    COUNT(DISTINCT c.customer_type)
  FROM customer_insights c WHERE c.customer_type IS NOT NULL

  UNION ALL

  SELECT 'strategic_insights'::TEXT, 'insight_categories'::TEXT,
    ARRAY_AGG(DISTINCT s.insight_category ORDER BY s.insight_category)::TEXT[],
    COUNT(DISTINCT s.insight_category)
  FROM strategic_insights s WHERE s.insight_category IS NOT NULL

  UNION ALL

  SELECT 'strategic_insights'::TEXT, 'total_insights'::TEXT,
    ARRAY['Total strategic insights: ' || COUNT(*)::TEXT]::TEXT[], COUNT(*)
  FROM strategic_insights

  UNION ALL

  SELECT 'themes'::TEXT, 'main_themes'::TEXT,
    (SELECT ARRAY_AGG(main_theme ORDER BY cnt DESC) FROM (
      SELECT main_theme, COUNT(*) as cnt FROM themes WHERE main_theme IS NOT NULL
      GROUP BY main_theme ORDER BY COUNT(*) DESC LIMIT 40) sub)::TEXT[],
    (SELECT COUNT(DISTINCT main_theme) FROM themes WHERE main_theme IS NOT NULL)

  UNION ALL

  SELECT 'themes'::TEXT, 'conversation_types'::TEXT,
    ARRAY_AGG(DISTINCT t.conversation_type ORDER BY t.conversation_type)::TEXT[],
    COUNT(DISTINCT t.conversation_type)
  FROM themes t WHERE t.conversation_type IS NOT NULL

  UNION ALL

  SELECT 'tasks'::TEXT, 'categories'::TEXT,
    ARRAY_AGG(DISTINCT tk.category ORDER BY tk.category)::TEXT[],
    COUNT(DISTINCT tk.category)
  FROM tasks tk WHERE tk.category IS NOT NULL

  UNION ALL

  SELECT 'tasks'::TEXT, 'urgency_levels'::TEXT,
    ARRAY_AGG(DISTINCT tk.urgency ORDER BY tk.urgency)::TEXT[],
    COUNT(DISTINCT tk.urgency)
  FROM tasks tk WHERE tk.urgency IS NOT NULL

  UNION ALL

  SELECT 'tasks'::TEXT, 'open_tasks_count'::TEXT,
    ARRAY['Open tasks: ' || COUNT(*)::TEXT]::TEXT[], COUNT(*)
  FROM tasks WHERE completed = false OR completed IS NULL

  UNION ALL

  SELECT 'memories'::TEXT, 'sources'::TEXT,
    ARRAY_AGG(DISTINCT m.source ORDER BY m.source)::TEXT[],
    COUNT(DISTINCT m.source)
  FROM memories m WHERE m.source IS NOT NULL AND m.status = 'completed'

  UNION ALL

  SELECT 'memories'::TEXT, 'statistics'::TEXT,
    ARRAY[
      'Total completed memories: ' || (SELECT COUNT(*) FROM memories WHERE status = 'completed')::TEXT,
      'Date range: ' || COALESCE((SELECT MIN(created_at)::DATE::TEXT FROM memories WHERE status = 'completed'), 'none')
        || ' to ' || COALESCE((SELECT MAX(created_at)::DATE::TEXT FROM memories WHERE status = 'completed'), 'none'),
      'With embeddings: ' || (SELECT COUNT(*) FROM memories WHERE embeddings IS NOT NULL)::TEXT
    ]::TEXT[],
    (SELECT COUNT(*) FROM memories WHERE status = 'completed');
END;
$$;


-- =============================================================================
-- SECTION 6: PERMISSIONS
-- =============================================================================

GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO anon;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO authenticated;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT INSERT, UPDATE ON telegram_sessions TO anon;
GRANT INSERT, UPDATE ON telegram_sessions TO authenticated;
GRANT INSERT ON memories TO anon;
GRANT INSERT ON memories TO authenticated;
GRANT UPDATE ON memories TO anon;
GRANT UPDATE ON memories TO authenticated;
GRANT INSERT ON entities, decisions, reflections, strategic_insights, customer_insights, tasks, themes TO anon;
GRANT INSERT ON entities, decisions, reflections, strategic_insights, customer_insights, tasks, themes TO authenticated;
GRANT UPDATE ON living_context TO anon;
GRANT UPDATE ON living_context TO authenticated;
GRANT USAGE ON SEQUENCE memories_id_seq TO anon;
GRANT USAGE ON SEQUENCE memories_id_seq TO authenticated;


-- =============================================================================
-- SECTION 7: DISABLE ROW LEVEL SECURITY
-- =============================================================================
-- This is a private single-user system. RLS is not needed and blocks service_role
-- access from n8n's Supabase node when using the REST API.

ALTER TABLE memories              DISABLE ROW LEVEL SECURITY;
ALTER TABLE telegram_sessions     DISABLE ROW LEVEL SECURITY;
ALTER TABLE entities              DISABLE ROW LEVEL SECURITY;
ALTER TABLE decisions             DISABLE ROW LEVEL SECURITY;
ALTER TABLE reflections           DISABLE ROW LEVEL SECURITY;
ALTER TABLE strategic_insights    DISABLE ROW LEVEL SECURITY;
ALTER TABLE customer_insights     DISABLE ROW LEVEL SECURITY;
ALTER TABLE tasks                 DISABLE ROW LEVEL SECURITY;
ALTER TABLE themes                DISABLE ROW LEVEL SECURITY;
ALTER TABLE living_context        DISABLE ROW LEVEL SECURITY;


-- =============================================================================
-- VERIFICATION QUERIES (run these after the above succeeds)
-- =============================================================================
-- SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;
-- SELECT * FROM agent_discover_database();
-- SELECT * FROM living_context;
