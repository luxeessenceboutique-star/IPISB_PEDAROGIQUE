-- ============================================================
-- IPISB Platform — Student Dossier AI Analysis Migration
-- Applied 2026-07-16 via Supabase MCP (kept here for reference)
-- ============================================================

-- AI analysis of a student's dossier files — one row per student, replaced
-- on each re-run. data holds the structured extraction (resume/infos/alertes)
-- plus the list of file ids that were analyzed (to detect staleness).
CREATE TABLE IF NOT EXISTS student_analyses (
  student_id  uuid        PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  data        jsonb       NOT NULL,
  file_ids    jsonb       NOT NULL DEFAULT '[]'::jsonb,
  analyzed_by uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  analyzed_at timestamptz DEFAULT now()
);

ALTER TABLE student_analyses ENABLE ROW LEVEL SECURITY;
-- No policies: only the backend (service key) reads/writes, same as student_files.
