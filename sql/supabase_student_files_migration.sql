-- ============================================================
-- IPISB Platform — Student Files (dossier stagiaire) Migration
-- Applied 2026-07-14 via Supabase MCP (kept here for reference)
-- ============================================================

-- Student dossier files (CIN, bac, photo, CV…) uploaded by admins/profs
CREATE TABLE IF NOT EXISTS student_files (
  id           uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  student_id   uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  type         text        NOT NULL DEFAULT 'autre', -- 'cin' | 'bac' | 'photo' | 'cv' | 'motivation' | 'autre'
  filename     text        NOT NULL,
  file_path    text        NOT NULL,                 -- path within the "student-files" bucket
  content_type text        NOT NULL,
  uploaded_by  uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at   timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_student_files_student ON student_files(student_id);

ALTER TABLE student_files ENABLE ROW LEVEL SECURITY;
-- No SELECT policy: only the backend (service key) reads/writes, same as audit_log.

INSERT INTO storage.buckets (id, name, public)
VALUES ('student-files', 'student-files', false)
ON CONFLICT (id) DO NOTHING;
