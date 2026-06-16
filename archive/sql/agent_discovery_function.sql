-- =============================================================================
-- AGENT DISCOVERY TOOL - Database Schema Introspection
-- =============================================================================
-- This function helps the AI agent understand what data exists in the database
-- before attempting targeted searches. Solves the "chicken and egg" problem
-- where the agent doesn't know what to query for.
--
-- Run this in your Supabase SQL Editor.
-- =============================================================================

DROP FUNCTION IF EXISTS agent_discover_database();

CREATE OR REPLACE FUNCTION agent_discover_database()
RETURNS TABLE (
  category TEXT,
  data_type TEXT,
  available_values TEXT[],
  total_count BIGINT
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY

  -- =============================================================================
  -- ENTITY DISCOVERY: Who/what has been mentioned?
  -- =============================================================================

  -- Entity types available
  SELECT
    'entities'::TEXT as category,
    'entity_types'::TEXT as data_type,
    ARRAY_AGG(DISTINCT e.entity_type ORDER BY e.entity_type)::TEXT[] as available_values,
    COUNT(DISTINCT e.entity_type) as total_count
  FROM entities e

  UNION ALL

  -- Top mentioned people (by frequency)
  SELECT
    'entities'::TEXT,
    'people'::TEXT,
    (SELECT ARRAY_AGG(entity_name ORDER BY mention_count DESC)
     FROM (
       SELECT entity_name, COUNT(*) as mention_count
       FROM entities
       WHERE entity_type = 'person'
       GROUP BY entity_name
       ORDER BY COUNT(*) DESC
       LIMIT 30
     ) sub)::TEXT[],
    (SELECT COUNT(DISTINCT entity_name) FROM entities WHERE entity_type = 'person')

  UNION ALL

  -- Companies mentioned
  SELECT
    'entities'::TEXT,
    'companies'::TEXT,
    (SELECT ARRAY_AGG(entity_name ORDER BY mention_count DESC)
     FROM (
       SELECT entity_name, COUNT(*) as mention_count
       FROM entities
       WHERE entity_type = 'company'
       GROUP BY entity_name
       ORDER BY COUNT(*) DESC
       LIMIT 30
     ) sub)::TEXT[],
    (SELECT COUNT(DISTINCT entity_name) FROM entities WHERE entity_type = 'company')

  UNION ALL

  -- Projects mentioned
  SELECT
    'entities'::TEXT,
    'projects'::TEXT,
    (SELECT ARRAY_AGG(entity_name ORDER BY mention_count DESC)
     FROM (
       SELECT entity_name, COUNT(*) as mention_count
       FROM entities
       WHERE entity_type = 'project'
       GROUP BY entity_name
       ORDER BY COUNT(*) DESC
       LIMIT 30
     ) sub)::TEXT[],
    (SELECT COUNT(DISTINCT entity_name) FROM entities WHERE entity_type = 'project')

  UNION ALL

  -- Tools/software mentioned
  SELECT
    'entities'::TEXT,
    'tools'::TEXT,
    (SELECT ARRAY_AGG(entity_name ORDER BY mention_count DESC)
     FROM (
       SELECT entity_name, COUNT(*) as mention_count
       FROM entities
       WHERE entity_type = 'tool'
       GROUP BY entity_name
       ORDER BY COUNT(*) DESC
       LIMIT 30
     ) sub)::TEXT[],
    (SELECT COUNT(DISTINCT entity_name) FROM entities WHERE entity_type = 'tool')

  UNION ALL

  -- =============================================================================
  -- DECISION DISCOVERY: What categories of decisions exist?
  -- =============================================================================

  SELECT
    'decisions'::TEXT,
    'categories'::TEXT,
    ARRAY_AGG(DISTINCT d.category ORDER BY d.category)::TEXT[],
    COUNT(DISTINCT d.category)
  FROM decisions d
  WHERE d.category IS NOT NULL

  UNION ALL

  -- Sample decision keywords (from decision text)
  SELECT
    'decisions'::TEXT,
    'total_decisions'::TEXT,
    ARRAY['Total decisions recorded: ' || COUNT(*)::TEXT]::TEXT[],
    COUNT(*)
  FROM decisions

  UNION ALL

  -- =============================================================================
  -- REFLECTION DISCOVERY: What topics have reflections?
  -- =============================================================================

  SELECT
    'reflections'::TEXT,
    'topics'::TEXT,
    (SELECT ARRAY_AGG(topic ORDER BY cnt DESC)
     FROM (
       SELECT topic, COUNT(*) as cnt
       FROM reflections
       WHERE topic IS NOT NULL
       GROUP BY topic
       ORDER BY COUNT(*) DESC
       LIMIT 30
     ) sub)::TEXT[],
    (SELECT COUNT(DISTINCT topic) FROM reflections WHERE topic IS NOT NULL)

  UNION ALL

  SELECT
    'reflections'::TEXT,
    'reflection_types'::TEXT,
    ARRAY_AGG(DISTINCT r.reflection_type ORDER BY r.reflection_type)::TEXT[],
    COUNT(DISTINCT r.reflection_type)
  FROM reflections r
  WHERE r.reflection_type IS NOT NULL

  UNION ALL

  SELECT
    'reflections'::TEXT,
    'emotional_tones'::TEXT,
    ARRAY_AGG(DISTINCT r.emotional_tone ORDER BY r.emotional_tone)::TEXT[],
    COUNT(DISTINCT r.emotional_tone)
  FROM reflections r
  WHERE r.emotional_tone IS NOT NULL

  UNION ALL

  -- =============================================================================
  -- CUSTOMER INSIGHTS DISCOVERY: Which customers have insights?
  -- =============================================================================

  SELECT
    'customer_insights'::TEXT,
    'customer_names'::TEXT,
    (SELECT ARRAY_AGG(customer_name ORDER BY cnt DESC)
     FROM (
       SELECT customer_name, COUNT(*) as cnt
       FROM customer_insights
       GROUP BY customer_name
       ORDER BY COUNT(*) DESC
       LIMIT 30
     ) sub)::TEXT[],
    (SELECT COUNT(DISTINCT customer_name) FROM customer_insights)

  UNION ALL

  SELECT
    'customer_insights'::TEXT,
    'customer_types'::TEXT,
    ARRAY_AGG(DISTINCT c.customer_type ORDER BY c.customer_type)::TEXT[],
    COUNT(DISTINCT c.customer_type)
  FROM customer_insights c
  WHERE c.customer_type IS NOT NULL

  UNION ALL

  -- =============================================================================
  -- STRATEGIC INSIGHTS DISCOVERY: What strategy categories exist?
  -- =============================================================================

  SELECT
    'strategic_insights'::TEXT,
    'insight_categories'::TEXT,
    ARRAY_AGG(DISTINCT s.insight_category ORDER BY s.insight_category)::TEXT[],
    COUNT(DISTINCT s.insight_category)
  FROM strategic_insights s
  WHERE s.insight_category IS NOT NULL

  UNION ALL

  SELECT
    'strategic_insights'::TEXT,
    'total_insights'::TEXT,
    ARRAY['Total strategic insights: ' || COUNT(*)::TEXT]::TEXT[],
    COUNT(*)
  FROM strategic_insights

  UNION ALL

  -- =============================================================================
  -- THEMES DISCOVERY: What main themes exist?
  -- =============================================================================

  SELECT
    'themes'::TEXT,
    'main_themes'::TEXT,
    (SELECT ARRAY_AGG(main_theme ORDER BY cnt DESC)
     FROM (
       SELECT main_theme, COUNT(*) as cnt
       FROM themes
       WHERE main_theme IS NOT NULL
       GROUP BY main_theme
       ORDER BY COUNT(*) DESC
       LIMIT 40
     ) sub)::TEXT[],
    (SELECT COUNT(DISTINCT main_theme) FROM themes WHERE main_theme IS NOT NULL)

  UNION ALL

  SELECT
    'themes'::TEXT,
    'conversation_types'::TEXT,
    ARRAY_AGG(DISTINCT t.conversation_type ORDER BY t.conversation_type)::TEXT[],
    COUNT(DISTINCT t.conversation_type)
  FROM themes t
  WHERE t.conversation_type IS NOT NULL

  UNION ALL

  -- =============================================================================
  -- TASKS DISCOVERY: Task categories and urgency levels
  -- =============================================================================

  SELECT
    'tasks'::TEXT,
    'categories'::TEXT,
    ARRAY_AGG(DISTINCT tk.category ORDER BY tk.category)::TEXT[],
    COUNT(DISTINCT tk.category)
  FROM tasks tk
  WHERE tk.category IS NOT NULL

  UNION ALL

  SELECT
    'tasks'::TEXT,
    'urgency_levels'::TEXT,
    ARRAY_AGG(DISTINCT tk.urgency ORDER BY tk.urgency)::TEXT[],
    COUNT(DISTINCT tk.urgency)
  FROM tasks tk
  WHERE tk.urgency IS NOT NULL

  UNION ALL

  SELECT
    'tasks'::TEXT,
    'open_tasks_count'::TEXT,
    ARRAY['Open tasks: ' || COUNT(*)::TEXT]::TEXT[],
    COUNT(*)
  FROM tasks
  WHERE completed = false OR completed IS NULL

  UNION ALL

  -- =============================================================================
  -- MEMORY OVERVIEW: General stats
  -- =============================================================================

  SELECT
    'memories'::TEXT,
    'sources'::TEXT,
    ARRAY_AGG(DISTINCT m.source ORDER BY m.source)::TEXT[],
    COUNT(DISTINCT m.source)
  FROM memories m
  WHERE m.source IS NOT NULL AND m.status = 'completed'

  UNION ALL

  SELECT
    'memories'::TEXT,
    'statistics'::TEXT,
    ARRAY[
      'Total completed memories: ' || (SELECT COUNT(*) FROM memories WHERE status = 'completed')::TEXT,
      'Date range: ' || (SELECT MIN(created_at)::DATE::TEXT FROM memories WHERE status = 'completed') ||
        ' to ' || (SELECT MAX(created_at)::DATE::TEXT FROM memories WHERE status = 'completed'),
      'With embeddings: ' || (SELECT COUNT(*) FROM memories WHERE embeddings IS NOT NULL)::TEXT
    ]::TEXT[],
    (SELECT COUNT(*) FROM memories WHERE status = 'completed');

END;
$$;

-- Grant permissions
GRANT EXECUTE ON FUNCTION agent_discover_database() TO anon;
GRANT EXECUTE ON FUNCTION agent_discover_database() TO authenticated;

-- =============================================================================
-- TEST THE FUNCTION
-- =============================================================================
-- Run this to verify it works:
-- SELECT * FROM agent_discover_database();
