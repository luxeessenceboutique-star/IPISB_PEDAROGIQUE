-- ============================================================
-- IPISB Platform — RH Phase 10 Migration: Employee Dossier Analysis
-- Run this ONCE in the Supabase SQL Editor.
--
-- Stores the AI dossier analysis for an employee (one row, upserted on
-- every re-run) — mirrors student_analyses exactly, scoped to employees.
-- No policies: only the backend (service key) reads/writes.
-- ============================================================

CREATE TABLE IF NOT EXISTS employee_analyses (
  employee_id uuid        PRIMARY KEY REFERENCES employees(id) ON DELETE CASCADE,
  data        jsonb       NOT NULL,
  file_ids    jsonb       NOT NULL DEFAULT '[]'::jsonb,
  analyzed_by uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  analyzed_at timestamptz DEFAULT now()
);

ALTER TABLE employee_analyses ENABLE ROW LEVEL SECURITY;
