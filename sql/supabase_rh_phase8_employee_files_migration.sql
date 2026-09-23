-- ============================================================
-- IPISB Platform — RH Phase 8 Migration: Employee Files
-- Run this ONCE in the Supabase SQL Editor.
--
-- General-purpose dossier storage for employees ("Fichiers" tab on the
-- employee detail page) — mirrors student_files, but scoped to employees.
-- Distinct from candidate CVs (recruitment-only) and payslips (payroll-only).
-- ============================================================

CREATE TABLE IF NOT EXISTS employee_files (
  id            uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  employee_id   uuid        NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  type          text        NOT NULL DEFAULT 'autre' CHECK (type IN ('cin', 'diplome', 'photo', 'cv', 'contrat', 'autre')),
  filename      text        NOT NULL,
  file_path     text        NOT NULL,
  content_type  text,
  uploaded_by   uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at    timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_employee_files_employee ON employee_files(employee_id);

ALTER TABLE employee_files ENABLE ROW LEVEL SECURITY;
