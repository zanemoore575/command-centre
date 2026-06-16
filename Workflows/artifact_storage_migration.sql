-- =============================================================================
-- CAiS Command Centre — Artifact Storage Migration
-- =============================================================================
-- Paste this entire file into the Supabase SQL Editor and click Run.
-- Storage bucket 'artifacts' is created separately via the Storage REST API
-- (already done by Claude Code as part of this build — not part of this SQL).
-- Safe to re-run: CREATE TABLE IF NOT EXISTS / CREATE OR REPLACE throughout.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. artifacts table
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS artifacts (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title           TEXT NOT NULL,
  kind            TEXT NOT NULL DEFAULT 'authored',  -- 'authored' | 'uploaded'
  format          TEXT NOT NULL,                      -- 'md' | 'txt' | 'pdf' | 'docx'
  source_content  TEXT,                                -- canonical editable text for 'authored'
  storage_path    TEXT,                                -- Supabase Storage path for binaries
  extracted_text  TEXT,                                -- for 'uploaded' binaries / search
  tags            JSONB DEFAULT '[]'::jsonb,
  entity_name     TEXT,
  memory_id       BIGINT REFERENCES memories(id) ON DELETE SET NULL,
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_artifacts_title_entity ON artifacts (lower(title), entity_name);
CREATE INDEX IF NOT EXISTS idx_artifacts_entity_name ON artifacts (entity_name);

ALTER TABLE artifacts DISABLE ROW LEVEL SECURITY;
GRANT SELECT, INSERT, UPDATE, DELETE ON artifacts TO anon, authenticated, service_role;

-- -----------------------------------------------------------------------------
-- 2. Find an exact title+entity collision (for the "no id given" dedup check)
-- -----------------------------------------------------------------------------
DROP FUNCTION IF EXISTS agent_find_artifact_by_title(TEXT, TEXT);
CREATE OR REPLACE FUNCTION agent_find_artifact_by_title(
  search_title TEXT,
  search_entity_name TEXT DEFAULT NULL
)
RETURNS TABLE (
  artifact_id TEXT,
  title       TEXT,
  entity_name TEXT,
  updated_at  TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    a.id::TEXT AS artifact_id,
    a.title,
    a.entity_name,
    a.updated_at
  FROM artifacts a
  WHERE lower(a.title) = lower(search_title)
    AND (
      (search_entity_name IS NULL AND a.entity_name IS NULL)
      OR a.entity_name = search_entity_name
    )
  LIMIT 1;
END;
$$;

-- -----------------------------------------------------------------------------
-- 3. Create or overwrite-in-place an artifact
-- -----------------------------------------------------------------------------
-- target_artifact_id is REQUIRED — the caller (Python tool) always generates
-- a UUID client-side, even for new artifacts, so the Storage path is known
-- before the row exists. This upserts by id: insert if new, update in place
-- if it already exists (the overwrite case).
DROP FUNCTION IF EXISTS agent_save_artifact(TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, JSONB, TEXT, BIGINT, TEXT);
CREATE OR REPLACE FUNCTION agent_save_artifact(
  target_artifact_id TEXT,
  new_title           TEXT DEFAULT NULL,
  new_kind            TEXT DEFAULT 'authored',
  new_format          TEXT DEFAULT NULL,
  new_source_content  TEXT DEFAULT NULL,
  new_storage_path    TEXT DEFAULT NULL,
  new_tags            JSONB DEFAULT '[]'::jsonb,
  new_entity_name     TEXT DEFAULT NULL,
  source_memory_id    BIGINT DEFAULT NULL,
  new_extracted_text  TEXT DEFAULT NULL
)
RETURNS TABLE (
  artifact_id TEXT,
  title       TEXT,
  kind        TEXT,
  format      TEXT,
  storage_path TEXT,
  updated_at  TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  INSERT INTO artifacts (id, title, kind, format, source_content, storage_path, extracted_text, tags, entity_name, memory_id)
  VALUES (target_artifact_id::UUID, new_title, new_kind, new_format, new_source_content, new_storage_path, new_extracted_text, new_tags, new_entity_name, source_memory_id)
  ON CONFLICT (id) DO UPDATE
  SET title          = COALESCE(EXCLUDED.title, artifacts.title),
      kind            = COALESCE(EXCLUDED.kind, artifacts.kind),
      format          = COALESCE(EXCLUDED.format, artifacts.format),
      source_content  = COALESCE(EXCLUDED.source_content, artifacts.source_content),
      storage_path    = COALESCE(EXCLUDED.storage_path, artifacts.storage_path),
      extracted_text  = COALESCE(EXCLUDED.extracted_text, artifacts.extracted_text),
      tags            = COALESCE(EXCLUDED.tags, artifacts.tags),
      entity_name     = COALESCE(EXCLUDED.entity_name, artifacts.entity_name),
      memory_id       = COALESCE(EXCLUDED.memory_id, artifacts.memory_id),
      updated_at      = now()
  RETURNING artifacts.id::TEXT, artifacts.title, artifacts.kind, artifacts.format, artifacts.storage_path, artifacts.updated_at;
END;
$$;

-- -----------------------------------------------------------------------------
-- 4. Search artifacts by title / tag / entity / content
-- -----------------------------------------------------------------------------
DROP FUNCTION IF EXISTS agent_search_artifacts(TEXT);
CREATE OR REPLACE FUNCTION agent_search_artifacts(
  query TEXT DEFAULT NULL
)
RETURNS TABLE (
  artifact_id  TEXT,
  title        TEXT,
  kind         TEXT,
  format       TEXT,
  entity_name  TEXT,
  tags         JSONB,
  updated_at   TIMESTAMPTZ,
  has_file     BOOLEAN
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    a.id::TEXT AS artifact_id,
    a.title,
    a.kind,
    a.format,
    a.entity_name,
    a.tags,
    a.updated_at,
    (a.storage_path IS NOT NULL) AS has_file
  FROM artifacts a
  WHERE query IS NULL
    OR a.title ILIKE '%' || query || '%'
    OR a.entity_name ILIKE '%' || query || '%'
    OR a.source_content ILIKE '%' || query || '%'
    OR a.extracted_text ILIKE '%' || query || '%'
    OR a.tags::TEXT ILIKE '%' || query || '%'
  ORDER BY a.updated_at DESC
  LIMIT 20;
END;
$$;

-- -----------------------------------------------------------------------------
-- 5. Get a single artifact's full content
-- -----------------------------------------------------------------------------
DROP FUNCTION IF EXISTS agent_get_artifact(TEXT);
CREATE OR REPLACE FUNCTION agent_get_artifact(
  target_artifact_id TEXT
)
RETURNS TABLE (
  artifact_id     TEXT,
  title           TEXT,
  kind            TEXT,
  format          TEXT,
  source_content  TEXT,
  storage_path    TEXT,
  extracted_text  TEXT,
  tags            JSONB,
  entity_name     TEXT,
  memory_id       BIGINT,
  created_at      TIMESTAMPTZ,
  updated_at      TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    a.id::TEXT AS artifact_id,
    a.title,
    a.kind,
    a.format,
    a.source_content,
    a.storage_path,
    a.extracted_text,
    a.tags,
    a.entity_name,
    a.memory_id,
    a.created_at,
    a.updated_at
  FROM artifacts a
  WHERE a.id = target_artifact_id::UUID;
END;
$$;

-- -----------------------------------------------------------------------------
-- 6. Grants
-- -----------------------------------------------------------------------------
GRANT EXECUTE ON FUNCTION agent_find_artifact_by_title(TEXT, TEXT) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION agent_save_artifact(TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, JSONB, TEXT, BIGINT, TEXT) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION agent_search_artifacts(TEXT) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION agent_get_artifact(TEXT) TO anon, authenticated, service_role;
