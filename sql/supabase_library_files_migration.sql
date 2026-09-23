-- ============================================================
-- IPISB Platform — Reference Library: DB-backed metadata + filière scoping
-- Run this ONCE in the Supabase SQL Editor, AFTER
-- supabase_reference_library_migration.sql (creates the 'reference-library'
-- bucket) and supabase_academic_extensions_migration.sql (creates
-- 'specialties').
--
-- Why a table now: the original reference-library migration listed files
-- straight from storage (no DB row, folder prefix = category — see
-- backend/routers/library.py before this change). That works for a human
-- browsing tabs, but breaks down once we need to know WHICH FILIÈRE a
-- cdc/programme/fiches_examens file belongs to, so the future AI course
-- generation pipeline can fetch "the CDC for filière X" reliably instead of
-- parsing filenames. This table becomes the source of truth for listing;
-- storage stays the source of truth for bytes.
-- ============================================================

CREATE TABLE IF NOT EXISTS library_files (
  id           uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  category     text        NOT NULL CHECK (category IN ('cdc', 'programmes', 'fiches_examens', 'reglements', 'autres')),
  -- NULL = "toutes filières / général" — always true for reglements/autres,
  -- and a valid choice within cdc/programmes/fiches_examens too (some real
  -- documents, e.g. a coefficient list covering 3 filières in one file,
  -- genuinely aren't scoped to a single filière).
  specialty_id uuid        REFERENCES specialties(id) ON DELETE SET NULL,
  file_path    text        NOT NULL,   -- path within the 'reference-library' bucket
  title        text        NOT NULL,
  mime_type    text,
  size_bytes   bigint,
  uploaded_by  uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at   timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_library_files_category  ON library_files(category);
CREATE INDEX IF NOT EXISTS idx_library_files_specialty ON library_files(specialty_id);

ALTER TABLE library_files ENABLE ROW LEVEL SECURITY;
-- No policies defined: only the backend (service role key) touches this
-- table, same as specialties/seances/attendance in the academic extensions
-- migration — RLS with no policy just means "nobody but service role", which
-- is the intended state since the frontend always goes through the API.
