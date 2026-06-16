-- =============================================================================
-- AGENTIC MEMORY TOOLS FOR CAIS COMMAND CENTRE
-- =============================================================================
-- These RPC functions are designed to be called by an AI Agent via n8n.
-- Each function returns structured data the agent can use to gather context.
-- Run this in your Supabase SQL Editor.
-- =============================================================================

-- Drop existing functions to avoid conflicts
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

-- =============================================================================
-- 1. SEMANTIC MEMORY SEARCH (requires embedding from n8n)
-- =============================================================================
-- This is called after n8n embeds the query text
CREATE OR REPLACE FUNCTION agent_search_memories_by_embedding(
  query_embedding VECTOR(1536),
  match_threshold FLOAT DEFAULT 0.35,
  match_count INT DEFAULT 8
)
RETURNS TABLE (
  memory_id BIGINT,
  title TEXT,
  summary TEXT,
  transcript_preview TEXT,
  source TEXT,
  created_at TIMESTAMPTZ,
  similarity FLOAT,
  main_theme TEXT,
  has_decisions BOOLEAN,
  has_reflections BOOLEAN,
  entity_count BIGINT,
  decision_count BIGINT
)
LANGUAGE plpgsql
AS $$
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
    (SELECT COUNT(*) FROM entities e WHERE e.memory_id = m.id) AS entity_count,
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

-- =============================================================================
-- 2. ENTITY SEARCH - Find people, companies, projects, tools by name
-- =============================================================================
CREATE OR REPLACE FUNCTION agent_get_entity_details(
  search_name TEXT
)
RETURNS TABLE (
  entity_id BIGINT,
  entity_name TEXT,
  entity_type TEXT,
  context TEXT,
  memory_id BIGINT,
  memory_title TEXT,
  memory_date TIMESTAMPTZ,
  mention_count BIGINT
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  WITH entity_matches AS (
    SELECT
      e.id,
      e.entity_name,
      e.entity_type,
      e.context,
      e.memory_id
    FROM entities e
    WHERE e.entity_name ILIKE '%' || search_name || '%'
  ),
  aggregated AS (
    SELECT
      em.entity_name,
      em.entity_type,
      COUNT(*) AS mention_count
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
  JOIN memories m ON m.id = em.memory_id
  JOIN aggregated a ON a.entity_name = em.entity_name AND a.entity_type = em.entity_type
  ORDER BY a.mention_count DESC, m.created_at DESC
  LIMIT 20;
END;
$$;

-- =============================================================================
-- 3. DECISIONS SEARCH - Find past decisions by topic or category
-- =============================================================================
CREATE OR REPLACE FUNCTION agent_get_decisions(
  search_topic TEXT DEFAULT NULL,
  recent_days INT DEFAULT 365
)
RETURNS TABLE (
  decision_id BIGINT,
  decision_text TEXT,
  category TEXT,
  reasoning TEXT,
  confidence_level TEXT,
  emotional_context TEXT,
  memory_id BIGINT,
  memory_title TEXT,
  decision_date TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
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
      OR d.decision ILIKE '%' || search_topic || '%'
      OR d.category ILIKE '%' || search_topic || '%'
      OR d.reasoning ILIKE '%' || search_topic || '%'
    )
  ORDER BY m.created_at DESC
  LIMIT 15;
END;
$$;

-- =============================================================================
-- 4. REFLECTIONS SEARCH - Personal insights and breakthroughs
-- =============================================================================
CREATE OR REPLACE FUNCTION agent_get_reflections(
  search_topic TEXT DEFAULT NULL,
  recent_days INT DEFAULT 365
)
RETURNS TABLE (
  reflection_id BIGINT,
  reflection_text TEXT,
  reflection_type TEXT,
  topic TEXT,
  emotional_tone TEXT,
  memory_id BIGINT,
  memory_title TEXT,
  reflection_date TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
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
      OR r.reflection ILIKE '%' || search_topic || '%'
      OR r.topic ILIKE '%' || search_topic || '%'
      OR r.reflection_type ILIKE '%' || search_topic || '%'
    )
  ORDER BY m.created_at DESC
  LIMIT 15;
END;
$$;

-- =============================================================================
-- 5. TASKS - Get open tasks with optional status filter
-- =============================================================================
CREATE OR REPLACE FUNCTION agent_get_tasks(
  task_status TEXT DEFAULT 'open'
)
RETURNS TABLE (
  task_id BIGINT,
  task_text TEXT,
  context TEXT,
  urgency TEXT,
  category TEXT,
  status TEXT,
  memory_id BIGINT,
  memory_title TEXT,
  created_date TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
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
      WHEN 'soon' THEN 3
      ELSE 4
    END,
    m.created_at DESC
  LIMIT 25;
END;
$$;

-- =============================================================================
-- 6. STRATEGIC INSIGHTS - Business insights and patterns
-- =============================================================================
CREATE OR REPLACE FUNCTION agent_get_strategic_insights(
  search_category TEXT DEFAULT NULL,
  recent_days INT DEFAULT 365
)
RETURNS TABLE (
  insight_id BIGINT,
  insight_text TEXT,
  insight_category TEXT,
  supporting_evidence TEXT,
  confidence TEXT,
  suggested_action TEXT,
  memory_id BIGINT,
  memory_title TEXT,
  insight_date TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
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
      OR s.insight ILIKE '%' || search_category || '%'
    )
  ORDER BY m.created_at DESC
  LIMIT 15;
END;
$$;

-- =============================================================================
-- 7. CUSTOMER INSIGHTS - Specific customer feedback and pain points
-- =============================================================================
CREATE OR REPLACE FUNCTION agent_get_customer_insights(
  search_customer TEXT DEFAULT NULL
)
RETURNS TABLE (
  insight_id BIGINT,
  customer_name TEXT,
  customer_type TEXT,
  pain_point TEXT,
  desire TEXT,
  objection TEXT,
  automation_opportunity TEXT,
  customer_quote TEXT,
  memory_id BIGINT,
  memory_title TEXT,
  insight_date TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
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

-- =============================================================================
-- 8. GET FULL MEMORY CONTEXT - Deep dive into a specific memory
-- =============================================================================
CREATE OR REPLACE FUNCTION agent_get_memory_context(
  target_memory_id BIGINT
)
RETURNS TABLE (
  memory_id BIGINT,
  title TEXT,
  full_transcript TEXT,
  source TEXT,
  created_at TIMESTAMPTZ,
  main_theme TEXT,
  sub_themes TEXT,
  conversation_type TEXT,
  key_takeaways TEXT,
  entities JSONB,
  decisions JSONB,
  reflections JSONB,
  strategic_insights JSONB,
  tasks JSONB
)
LANGUAGE plpgsql
AS $$
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
      (SELECT jsonb_agg(jsonb_build_object(
        'name', e.entity_name,
        'type', e.entity_type,
        'context', e.context
      )) FROM entities e WHERE e.memory_id = m.id),
      '[]'::jsonb
    ) AS entities,
    COALESCE(
      (SELECT jsonb_agg(jsonb_build_object(
        'decision', d.decision,
        'category', d.category,
        'reasoning', d.reasoning,
        'confidence', d.confidence_level
      )) FROM decisions d WHERE d.memory_id = m.id),
      '[]'::jsonb
    ) AS decisions,
    COALESCE(
      (SELECT jsonb_agg(jsonb_build_object(
        'reflection', r.reflection,
        'type', r.reflection_type,
        'topic', r.topic,
        'tone', r.emotional_tone
      )) FROM reflections r WHERE r.memory_id = m.id),
      '[]'::jsonb
    ) AS reflections,
    COALESCE(
      (SELECT jsonb_agg(jsonb_build_object(
        'insight', s.insight,
        'category', s.insight_category,
        'confidence', s.confidence,
        'action', s.suggested_action
      )) FROM strategic_insights s WHERE s.memory_id = m.id),
      '[]'::jsonb
    ) AS strategic_insights,
    COALESCE(
      (SELECT jsonb_agg(jsonb_build_object(
        'task', tk.task,
        'urgency', tk.urgency,
        'category', tk.category,
        'status', COALESCE(tk.status, 'open')
      )) FROM tasks tk WHERE tk.memory_id = m.id),
      '[]'::jsonb
    ) AS tasks
  FROM memories m
  LEFT JOIN themes t ON t.memory_id = m.id
  WHERE m.id = target_memory_id;
END;
$$;

-- =============================================================================
-- 9. RECENT MEMORIES - Browse recent conversations
-- =============================================================================
CREATE OR REPLACE FUNCTION agent_get_recent_memories(
  limit_count INT DEFAULT 10,
  filter_source TEXT DEFAULT NULL
)
RETURNS TABLE (
  memory_id BIGINT,
  title TEXT,
  summary TEXT,
  source TEXT,
  created_at TIMESTAMPTZ,
  main_theme TEXT,
  conversation_type TEXT,
  entity_count BIGINT,
  decision_count BIGINT,
  reflection_count BIGINT
)
LANGUAGE plpgsql
AS $$
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
    (SELECT COUNT(*) FROM entities e WHERE e.memory_id = m.id) AS entity_count,
    (SELECT COUNT(*) FROM decisions d WHERE d.memory_id = m.id) AS decision_count,
    (SELECT COUNT(*) FROM reflections r WHERE r.memory_id = m.id) AS reflection_count
  FROM memories m
  LEFT JOIN themes t ON t.memory_id = m.id
  WHERE m.status = 'completed'
    AND (filter_source IS NULL OR m.source = filter_source)
  ORDER BY m.created_at DESC
  LIMIT limit_count;
END;
$$;

-- =============================================================================
-- 10. SEARCH BY THEME - Find memories by theme/topic keywords
-- =============================================================================
CREATE OR REPLACE FUNCTION agent_search_by_theme(
  theme_keywords TEXT,
  limit_count INT DEFAULT 10
)
RETURNS TABLE (
  memory_id BIGINT,
  title TEXT,
  summary TEXT,
  main_theme TEXT,
  sub_themes TEXT,
  conversation_type TEXT,
  created_at TIMESTAMPTZ,
  relevance_score INT
)
LANGUAGE plpgsql
AS $$
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
      CASE WHEN m.title ILIKE '%' || theme_keywords || '%' THEN 2 ELSE 0 END +
      CASE WHEN m.summary ILIKE '%' || theme_keywords || '%' THEN 1 ELSE 0 END
    )::INT AS relevance_score
  FROM memories m
  LEFT JOIN themes t ON t.memory_id = m.id
  WHERE m.status = 'completed'
    AND (
      t.main_theme ILIKE '%' || theme_keywords || '%'
      OR t.sub_themes ILIKE '%' || theme_keywords || '%'
      OR m.title ILIKE '%' || theme_keywords || '%'
      OR m.summary ILIKE '%' || theme_keywords || '%'
    )
  ORDER BY relevance_score DESC, m.created_at DESC
  LIMIT limit_count;
END;
$$;

-- =============================================================================
-- 11. ENRICHMENT FUNCTION (updated version of existing)
-- =============================================================================
CREATE OR REPLACE FUNCTION get_memory_enrichment(memory_ids BIGINT[])
RETURNS TABLE (
  memory_id BIGINT,
  entities JSONB,
  decisions JSONB,
  reflections JSONB,
  strategic_insights JSONB,
  customer_insights JSONB,
  tasks JSONB,
  themes JSONB
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    m.id AS memory_id,
    COALESCE(
      (SELECT jsonb_agg(DISTINCT jsonb_build_object(
        'name', e.entity_name,
        'type', e.entity_type,
        'context', e.context
      )) FROM entities e WHERE e.memory_id = m.id),
      '[]'::jsonb
    ) AS entities,
    COALESCE(
      (SELECT jsonb_agg(DISTINCT jsonb_build_object(
        'decision', d.decision,
        'category', d.category,
        'reasoning', d.reasoning
      )) FROM decisions d WHERE d.memory_id = m.id),
      '[]'::jsonb
    ) AS decisions,
    COALESCE(
      (SELECT jsonb_agg(DISTINCT jsonb_build_object(
        'reflection', r.reflection,
        'type', r.reflection_type,
        'topic', r.topic
      )) FROM reflections r WHERE r.memory_id = m.id),
      '[]'::jsonb
    ) AS reflections,
    COALESCE(
      (SELECT jsonb_agg(DISTINCT jsonb_build_object(
        'insight', s.insight,
        'category', s.insight_category,
        'action', s.suggested_action
      )) FROM strategic_insights s WHERE s.memory_id = m.id),
      '[]'::jsonb
    ) AS strategic_insights,
    COALESCE(
      (SELECT jsonb_agg(DISTINCT jsonb_build_object(
        'customer', c.customer_name,
        'type', c.customer_type,
        'pain_point', c.pain_point,
        'desire', c.desire
      )) FROM customer_insights c WHERE c.memory_id = m.id),
      '[]'::jsonb
    ) AS customer_insights,
    COALESCE(
      (SELECT jsonb_agg(DISTINCT jsonb_build_object(
        'task', tk.task,
        'urgency', tk.urgency,
        'status', COALESCE(tk.status, 'open')
      )) FROM tasks tk WHERE tk.memory_id = m.id),
      '[]'::jsonb
    ) AS tasks,
    COALESCE(
      (SELECT jsonb_agg(DISTINCT jsonb_build_object(
        'theme', t.main_theme,
        'sub_themes', t.sub_themes,
        'type', t.conversation_type
      )) FROM themes t WHERE t.memory_id = m.id),
      '[]'::jsonb
    ) AS themes
  FROM unnest(memory_ids) AS m(id);
END;
$$;

-- =============================================================================
-- GRANT PERMISSIONS (adjust role name if needed)
-- =============================================================================
-- If using Supabase with anon/authenticated roles:
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO anon;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO authenticated;
