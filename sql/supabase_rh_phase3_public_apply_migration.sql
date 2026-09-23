-- ============================================================
-- IPISB Platform — RH Phase 3 Migration: Public Job Applications
-- Run this ONCE in the Supabase SQL Editor, AFTER supabase_rh_phase2_migration.sql
--
-- Adds the columns needed for the public "Apply" page (candidate
-- self-service application + AI CV extraction) to the existing
-- `employees` table. Recruitment candidates are still just rows with
-- status='candidate' (phase 2 convention) — no new tables.
--
-- RLS enabled with no policies, same convention as every other IPISB
-- migration: all access goes through the FastAPI service-role backend.
-- The public apply endpoint has no auth dependency, but it still only
-- ever talks to Postgres via the service-role key.
--
-- Also requires a private Supabase Storage bucket named "candidate-cvs"
-- (Public: OFF) — create it manually via the Supabase dashboard Storage
-- tab, same as the student-files bucket was created.
-- ============================================================

ALTER TABLE employees
  ADD COLUMN IF NOT EXISTS source              text NOT NULL DEFAULT 'manual',
  ADD COLUMN IF NOT EXISTS applied_ad_id        uuid REFERENCES recruitment_ads(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS cv_path              text,
  ADD COLUMN IF NOT EXISTS cv_filename          text,
  ADD COLUMN IF NOT EXISTS education            text,
  ADD COLUMN IF NOT EXISTS experience_summary   text,
  ADD COLUMN IF NOT EXISTS skills               text,
  ADD COLUMN IF NOT EXISTS ai_extracted         jsonb;

ALTER TABLE employees DROP CONSTRAINT IF EXISTS employees_source_check;
ALTER TABLE employees ADD CONSTRAINT employees_source_check
  CHECK (source IN ('manual', 'public_application'));

-- Sparse indexes — only candidates that came through the public link or
-- are linked to an ad need to be found this way; no point indexing NULLs.
CREATE INDEX IF NOT EXISTS idx_employees_applied_ad
  ON employees(applied_ad_id) WHERE applied_ad_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_employees_source_public
  ON employees(source) WHERE source = 'public_application';
