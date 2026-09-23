-- ============================================================
-- IPISB Platform — Student Details Migration
-- Applied 2026-07-17 via Supabase MCP (kept here for reference)
-- ============================================================

-- Structured student identity/contact fields — only what gets PRINTED on
-- generated documents or used to reach the student. Everything else stays
-- in the scanned dossier files (readable on demand via the AI analysis).
-- 1:1 with profiles; kept separate so admin/prof rows stay lean.
CREATE TABLE IF NOT EXISTS student_details (
  student_id      uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  nom             text,
  prenom          text,
  date_naissance  date,
  lieu_naissance  text,
  cin             text,
  matricule       text,
  telephone       text,
  email_personnel text,
  adresse         text,
  bac_annee       text,
  updated_by      uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  updated_at      timestamptz DEFAULT now()
);

ALTER TABLE student_details ENABLE ROW LEVEL SECURITY;
-- No policies: only the backend (service key) reads/writes, same as student_files.
