-- =============================================================================
-- Entity resolution migration (Wave 2b, 2026-07-16)
-- Run in the Supabase SQL Editor on erwxszdcisyuyjmefvbj.
--
-- Problem: 4,456 entity rows / 2,326 distinct lowercased names — "Jake" alone in
-- 24 variants. search_entities/get_customer_insights only ILIKE-match, so none
-- of that duplication is actually searchable as one entity.
--
-- Adds a canonical-entity registry + a live matching RPC n8n calls at ingest
-- time for every extracted entity:
--   score >= 0.90            -> silent auto-merge into the matched canonical
--   0.35 <= score < 0.90      -> new standalone canonical + a row in
--                                entity_match_review for Zane to confirm/reject
--                                (surfaced on the check-in page + get_entity_matches_due_for_review)
--   score < 0.35 / no match  -> new canonical, nothing to review
--
-- NOTE: floor was 0.20 in the first version of this migration; raised to 0.35
-- (2026-07-16, post-backfill) after inspecting real agent_best_canonical_match
-- scores on the 'tool' entity backfill — everything below ~0.35 was noise
-- ("DocuSign" vs "Docker" at 0.23, "Revit" vs "React" at 0.2), everything
-- above was a sensible question ("Claude Code" vs "Claude" at 0.7). If you're
-- re-running this file fresh, this comment is just history — the function
-- below already has the corrected floor.
--
-- Requires pg_trgm (already enabled by task_writeback_migration.sql).
-- Safe to re-run: IF NOT EXISTS / CREATE OR REPLACE / idempotent inserts.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Schema
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS canonical_entities (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  canonical_name TEXT NOT NULL,
  entity_type    TEXT NOT NULL,             -- person | company | project | tool
  aliases        TEXT[] DEFAULT '{}',
  notes          TEXT,
  created_at     TIMESTAMPTZ DEFAULT now(),
  updated_at     TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE entities ADD COLUMN IF NOT EXISTS canonical_id UUID REFERENCES canonical_entities(id);

CREATE TABLE IF NOT EXISTS entity_match_review (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_id              UUID REFERENCES entities(id) ON DELETE CASCADE,
  memory_id              BIGINT REFERENCES memories(id),
  candidate_name         TEXT NOT NULL,      -- what was actually extracted, e.g. "Jake"
  candidate_canonical_id UUID REFERENCES canonical_entities(id),
  suggested_name         TEXT NOT NULL,      -- best existing guess, e.g. "Jake Shirley"
  suggested_canonical_id UUID REFERENCES canonical_entities(id),
  similarity             REAL,
  status                 TEXT DEFAULT 'pending',  -- pending | confirmed | rejected
  note                   TEXT,                     -- Zane's free-text clarification
  created_at             TIMESTAMPTZ DEFAULT now(),
  resolved_at            TIMESTAMPTZ
);

ALTER TABLE strategic_insights ADD COLUMN IF NOT EXISTS importance INT;

CREATE INDEX IF NOT EXISTS idx_canonical_entities_type ON canonical_entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_canonical_id ON entities(canonical_id);
CREATE INDEX IF NOT EXISTS idx_entity_match_review_status ON entity_match_review(status);

-- -----------------------------------------------------------------------------
-- 2. Matching helper — best canonical match for a candidate name, same entity_type.
--    score = 1.0 exact (case/whitespace-insensitive); else the greater of trigram
--    similarity and a 0.6 "containment" bonus when one name is a whole-word
--    substring of the other (deliberately kept below the 0.90 auto-merge bar —
--    "Jake" vs "Jake Shirley" should ask, not silently merge).
-- -----------------------------------------------------------------------------
DROP FUNCTION IF EXISTS agent_best_canonical_match(TEXT, TEXT);
CREATE OR REPLACE FUNCTION agent_best_canonical_match(
  candidate_name TEXT,
  candidate_type TEXT
)
RETURNS TABLE (
  canonical_id   UUID,
  canonical_name TEXT,
  score          REAL
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  WITH candidates AS (
    SELECT
      ce.id,
      ce.canonical_name,
      GREATEST(
        CASE WHEN lower(trim(candidate_name)) = lower(trim(ce.canonical_name)) THEN 1.0 ELSE 0 END,
        CASE WHEN lower(trim(candidate_name)) = ANY (SELECT lower(trim(a)) FROM unnest(ce.aliases) a) THEN 1.0 ELSE 0 END,
        similarity(lower(candidate_name), lower(ce.canonical_name)),
        COALESCE((SELECT MAX(similarity(lower(candidate_name), lower(a))) FROM unnest(ce.aliases) a), 0),
        -- Whole-word containment (e.g. "Jake" inside "Jake Shirley"), done via
        -- plain word-array membership rather than a dynamic regex — entity
        -- names can contain regex metacharacters ('.', '(', etc.) that would
        -- otherwise break or misbehave in a ~* pattern built from raw text.
        CASE WHEN lower(trim(candidate_name)) = ANY (regexp_split_to_array(lower(ce.canonical_name), '\s+'))
               OR lower(trim(ce.canonical_name)) = ANY (regexp_split_to_array(lower(candidate_name), '\s+'))
             THEN 0.6 ELSE 0 END
      )::REAL AS score
    FROM canonical_entities ce
    WHERE ce.entity_type = candidate_type
  )
  SELECT c.id, c.canonical_name, c.score
  FROM candidates c
  ORDER BY c.score DESC
  LIMIT 1;
END;
$$;

-- -----------------------------------------------------------------------------
-- 3. agent_ingest_entity — replaces the direct "Insert Entities" write in n8n.
--    Always inserts the entities row and always resolves it to some canonical_id;
--    ambiguous matches (0.35-0.90) additionally log an entity_match_review row.
-- -----------------------------------------------------------------------------
DROP FUNCTION IF EXISTS agent_ingest_entity(BIGINT, TEXT, TEXT, TEXT);
CREATE OR REPLACE FUNCTION agent_ingest_entity(
  p_memory_id  BIGINT,
  p_entity_type TEXT,
  p_entity_name TEXT,
  p_context     TEXT DEFAULT NULL
)
RETURNS TABLE (
  entity_id     TEXT,
  canonical_id  TEXT,
  match_status  TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
  v_match       RECORD;
  v_canonical   UUID;
  v_entity      UUID;
  v_status      TEXT;
  v_candidate   UUID;
BEGIN
  SELECT * INTO v_match FROM agent_best_canonical_match(p_entity_name, p_entity_type);

  IF v_match.canonical_id IS NULL OR v_match.score < 0.35 THEN
    -- Nothing plausible exists yet: brand-new canonical, nothing to review.
    INSERT INTO canonical_entities (canonical_name, entity_type, aliases)
    VALUES (p_entity_name, p_entity_type, ARRAY[p_entity_name])
    RETURNING id INTO v_canonical;
    v_status := 'new';

  ELSIF v_match.score >= 0.90 THEN
    -- Confident match: silent auto-merge, expand aliases if this is a new surface form.
    v_canonical := v_match.canonical_id;
    UPDATE canonical_entities
    SET aliases = CASE
          WHEN lower(trim(p_entity_name)) = ANY (SELECT lower(trim(a)) FROM unnest(aliases) a)
               OR lower(trim(p_entity_name)) = lower(trim(canonical_name))
          THEN aliases
          ELSE array_append(aliases, p_entity_name)
        END,
        updated_at = now()
    WHERE id = v_canonical;
    v_status := 'auto';

  ELSE
    -- Ambiguous: stand up a separate canonical for now, flag it for Zane to confirm.
    INSERT INTO canonical_entities (canonical_name, entity_type, aliases)
    VALUES (p_entity_name, p_entity_type, ARRAY[p_entity_name])
    RETURNING id INTO v_candidate;
    v_canonical := v_candidate;
    v_status := 'ambiguous';
  END IF;

  INSERT INTO entities (memory_id, entity_type, entity_name, context, canonical_id)
  VALUES (p_memory_id, p_entity_type, p_entity_name, p_context, v_canonical)
  RETURNING id INTO v_entity;

  IF v_status = 'ambiguous' THEN
    INSERT INTO entity_match_review (
      entity_id, memory_id, candidate_name, candidate_canonical_id,
      suggested_name, suggested_canonical_id, similarity
    ) VALUES (
      v_entity, p_memory_id, p_entity_name, v_candidate,
      v_match.canonical_name, v_match.canonical_id, v_match.score
    );
  END IF;

  RETURN QUERY SELECT v_entity::TEXT, v_canonical::TEXT, v_status;
END;
$$;

-- -----------------------------------------------------------------------------
-- 4. Review queue — surfaced on the check-in page + an MCP tool.
-- -----------------------------------------------------------------------------
DROP FUNCTION IF EXISTS agent_get_entity_matches_due_for_review(INT);
CREATE OR REPLACE FUNCTION agent_get_entity_matches_due_for_review(
  limit_count INT DEFAULT 3
)
RETURNS TABLE (
  match_id        TEXT,
  candidate_name  TEXT,
  suggested_name  TEXT,
  similarity      REAL,
  memory_id       BIGINT,
  memory_title    TEXT,
  created_date    TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    r.id::TEXT AS match_id,
    r.candidate_name,
    r.suggested_name,
    r.similarity,
    r.memory_id,
    m.title      AS memory_title,
    r.created_at AS created_date
  FROM entity_match_review r
  LEFT JOIN memories m ON m.id = r.memory_id
  WHERE r.status = 'pending'
  ORDER BY r.similarity DESC, r.created_at ASC
  LIMIT LEAST(GREATEST(limit_count, 1), 20);
END;
$$;

-- -----------------------------------------------------------------------------
-- 5. agent_resolve_entity_match — Zane's confirm/reject from the check-in page
--    (or a Claude Code/claude.ai session on his behalf).
-- -----------------------------------------------------------------------------
DROP FUNCTION IF EXISTS agent_resolve_entity_match(TEXT, TEXT, TEXT);
CREATE OR REPLACE FUNCTION agent_resolve_entity_match(
  match_id TEXT,
  action   TEXT,
  new_note TEXT DEFAULT NULL
)
RETURNS TABLE (
  match_id_out     TEXT,
  status           TEXT,
  canonical_id_out TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
  v_row RECORD;
BEGIN
  SELECT * INTO v_row FROM entity_match_review WHERE id = match_id::UUID;
  IF NOT FOUND THEN
    RETURN;
  END IF;

  IF action = 'confirm' THEN
    -- Fold the standalone candidate canonical into the suggested one.
    UPDATE canonical_entities suggested
    SET aliases = (
          SELECT ARRAY(SELECT DISTINCT unnest(suggested.aliases || candidate.aliases))
          FROM canonical_entities candidate WHERE candidate.id = v_row.candidate_canonical_id
        ),
        updated_at = now()
    WHERE suggested.id = v_row.suggested_canonical_id;

    UPDATE entities SET canonical_id = v_row.suggested_canonical_id
    WHERE canonical_id = v_row.candidate_canonical_id;

    -- Repoint any review rows referencing the candidate canonical (including
    -- this one) before deleting it, so its own FK doesn't block the delete.
    UPDATE entity_match_review
    SET candidate_canonical_id = v_row.suggested_canonical_id
    WHERE candidate_canonical_id = v_row.candidate_canonical_id;

    DELETE FROM canonical_entities WHERE id = v_row.candidate_canonical_id;

    UPDATE entity_match_review
    SET status = 'confirmed', resolved_at = now(), note = COALESCE(new_note, note)
    WHERE id = match_id::UUID;

    RETURN QUERY SELECT match_id, 'confirmed'::TEXT, v_row.suggested_canonical_id::TEXT;

  ELSIF action = 'reject' THEN
    -- Different entity — leave the two canonicals separate, keep Zane's clarification.
    UPDATE canonical_entities SET notes = COALESCE(new_note, notes), updated_at = now()
    WHERE id = v_row.candidate_canonical_id;

    UPDATE entity_match_review
    SET status = 'rejected', resolved_at = now(), note = COALESCE(new_note, note)
    WHERE id = match_id::UUID;

    RETURN QUERY SELECT match_id, 'rejected'::TEXT, v_row.candidate_canonical_id::TEXT;
  END IF;
END;
$$;

-- -----------------------------------------------------------------------------
-- 6. agent_get_entity_details — now resolves through canonical_entities + aliases
--    so "Jake" returns every variant, not just literal "Jake" substring matches.
--    Falls back to a raw ILIKE scan for canonical_id IS NULL rows (concept-type
--    entities, intentionally excluded from canonicalization, and anything from
--    before the backfill runs).
--
--    Caps each matched canonical/name group to 5 example rows (most recent
--    first) instead of a flat mention-count-desc ordering with one global
--    LIMIT. Found via testing: 'Jake' has 111 raw entities rows on its own —
--    a flat LIMIT 40 ordered by mention_count meant the correctly-still-
--    separate 'Jake Shirley' (6 rows, pending review) and 'Jake Murray'
--    (1 row) canonicals never appeared in results at all, even though the
--    underlying data was correct. Capping per-group guarantees every matched
--    canonical gets at least some representation.
-- -----------------------------------------------------------------------------
DROP FUNCTION IF EXISTS agent_get_entity_details(TEXT);
CREATE OR REPLACE FUNCTION agent_get_entity_details(
  search_name TEXT
)
RETURNS TABLE (
  entity_id      TEXT,
  entity_name    TEXT,
  entity_type    TEXT,
  context        TEXT,
  memory_id      BIGINT,
  memory_title   TEXT,
  memory_date    TIMESTAMPTZ,
  mention_count  BIGINT,
  canonical_name TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  WITH matched_canonicals AS (
    SELECT ce.id, ce.canonical_name
    FROM canonical_entities ce
    WHERE ce.canonical_name ILIKE '%' || search_name || '%'
       OR EXISTS (SELECT 1 FROM unnest(ce.aliases) a WHERE a ILIKE '%' || search_name || '%')
  ),
  entity_matches AS (
    SELECT e.id::TEXT AS entity_id, e.entity_name, e.entity_type, e.context, e.memory_id,
           mc.canonical_name, mc.id::TEXT AS group_key
    FROM entities e
    JOIN matched_canonicals mc ON mc.id = e.canonical_id
    UNION ALL
    SELECT e.id::TEXT, e.entity_name, e.entity_type, e.context, e.memory_id,
           NULL::TEXT AS canonical_name, e.entity_name AS group_key
    FROM entities e
    WHERE e.canonical_id IS NULL
      AND e.entity_name ILIKE '%' || search_name || '%'
  ),
  grouped AS (
    SELECT
      em.*,
      m.title      AS memory_title,
      m.created_at AS memory_date,
      COUNT(*) OVER (PARTITION BY em.group_key)                              AS mention_count,
      ROW_NUMBER()  OVER (PARTITION BY em.group_key ORDER BY m.created_at DESC) AS rn
    FROM entity_matches em
    JOIN memories m ON m.id = em.memory_id
  )
  SELECT
    g.entity_id, g.entity_name, g.entity_type, g.context, g.memory_id,
    g.memory_title, g.memory_date, g.mention_count, g.canonical_name
  FROM grouped g
  WHERE g.rn <= 5
  ORDER BY g.mention_count DESC, g.memory_date DESC
  LIMIT 60;
END;
$$;

-- -----------------------------------------------------------------------------
-- 7. agent_get_customer_insights — expands search_customer into every alias of
--    any matching canonical entity. customer_insights has no FK into
--    entities/canonical_entities (separate extraction path, untouched this
--    wave), so this is a query-time expansion, not a stored link.
-- -----------------------------------------------------------------------------
DROP FUNCTION IF EXISTS agent_get_customer_insights(TEXT);
CREATE OR REPLACE FUNCTION agent_get_customer_insights(
  search_customer TEXT DEFAULT NULL
)
RETURNS TABLE (
  insight_id             TEXT,
  customer_name          TEXT,
  customer_type          TEXT,
  pain_point             TEXT,
  desire                 TEXT,
  objection              TEXT,
  automation_opportunity TEXT,
  customer_quote         TEXT,
  memory_id              BIGINT,
  memory_title           TEXT,
  insight_date           TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
DECLARE
  v_aliases TEXT[];
BEGIN
  IF search_customer IS NOT NULL THEN
    SELECT ARRAY(
      SELECT DISTINCT a
      FROM canonical_entities ce, unnest(ce.aliases || ce.canonical_name) a
      WHERE ce.canonical_name ILIKE '%' || search_customer || '%'
         OR EXISTS (SELECT 1 FROM unnest(ce.aliases) a2 WHERE a2 ILIKE '%' || search_customer || '%')
    ) INTO v_aliases;
  END IF;

  RETURN QUERY
  SELECT
    c.id::TEXT AS insight_id,
    c.customer_name,
    c.customer_type,
    c.pain_point,
    c.desire,
    c.objection,
    c.automation_opportunity,
    c.quote     AS customer_quote,
    c.memory_id,
    m.title     AS memory_title,
    m.created_at AS insight_date
  FROM customer_insights c
  JOIN memories m ON m.id = c.memory_id
  WHERE search_customer IS NULL
    OR c.customer_name ILIKE '%' || search_customer || '%'
    OR c.customer_type ILIKE '%' || search_customer || '%'
    OR (v_aliases IS NOT NULL AND EXISTS (
          SELECT 1 FROM unnest(v_aliases) al WHERE c.customer_name ILIKE '%' || al || '%'
        ))
  ORDER BY m.created_at DESC
  LIMIT 20;
END;
$$;

-- -----------------------------------------------------------------------------
-- 8. agent_get_strategic_insights — surfaces importance, sorts high-value rows
--    first so low-value ones age out of view without being deleted.
-- -----------------------------------------------------------------------------
DROP FUNCTION IF EXISTS agent_get_strategic_insights(TEXT, INT);
CREATE OR REPLACE FUNCTION agent_get_strategic_insights(
  search_category TEXT DEFAULT NULL,
  recent_days     INT  DEFAULT 365
)
RETURNS TABLE (
  insight_id          TEXT,
  insight_text        TEXT,
  insight_category    TEXT,
  supporting_evidence TEXT,
  confidence          TEXT,
  importance          INT,
  suggested_action    TEXT,
  memory_id           BIGINT,
  memory_title        TEXT,
  insight_date        TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    s.id::TEXT                       AS insight_id,
    s.insight                        AS insight_text,
    s.insight_category,
    s.supporting_evidence::TEXT      AS supporting_evidence,
    s.confidence,
    s.importance,
    s.suggested_action,
    s.memory_id,
    m.title                          AS memory_title,
    m.created_at                     AS insight_date
  FROM strategic_insights s
  JOIN memories m ON m.id = s.memory_id
  WHERE m.created_at > NOW() - (recent_days || ' days')::INTERVAL
    AND (
      search_category IS NULL
      OR s.insight_category ILIKE '%' || search_category || '%'
      OR s.insight          ILIKE '%' || search_category || '%'
    )
  ORDER BY s.importance DESC NULLS LAST, m.created_at DESC
  LIMIT 15;
END;
$$;

-- -----------------------------------------------------------------------------
-- 9. One-off cleanup of the existing "Zane" noise rows (explicitly banned by the
--    extraction prompt already; 151 slipped through pre-discipline). Safe to
--    re-run — WHERE clause matches nothing once they're gone.
-- -----------------------------------------------------------------------------
DELETE FROM entities WHERE entity_name ILIKE 'zane';

-- -----------------------------------------------------------------------------
-- 10. Grants
-- -----------------------------------------------------------------------------
GRANT EXECUTE ON FUNCTION agent_best_canonical_match(TEXT, TEXT)          TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION agent_ingest_entity(BIGINT, TEXT, TEXT, TEXT)   TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION agent_get_entity_matches_due_for_review(INT)    TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION agent_resolve_entity_match(TEXT, TEXT, TEXT)    TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION agent_get_entity_details(TEXT)                  TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION agent_get_customer_insights(TEXT)               TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION agent_get_strategic_insights(TEXT, INT)         TO anon, authenticated, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON canonical_entities    TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON entity_match_review   TO service_role;
GRANT SELECT ON canonical_entities   TO anon, authenticated;
GRANT SELECT ON entity_match_review  TO anon, authenticated;

-- -----------------------------------------------------------------------------
-- Verification (run after the above succeeds)
-- -----------------------------------------------------------------------------
-- SELECT * FROM agent_ingest_entity(1, 'person', 'Jake', 'test');
-- SELECT * FROM agent_ingest_entity(1, 'person', 'Jake Shirley', 'test');  -- should come back 'ambiguous'
-- SELECT * FROM agent_get_entity_matches_due_for_review(5);
-- SELECT * FROM agent_get_entity_details('Jake');
