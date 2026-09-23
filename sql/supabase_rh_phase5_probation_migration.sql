-- ============================================================
-- IPISB Platform — RH Phase 5 Migration: Probationary Period
-- Run this ONCE in the Supabase SQL Editor, AFTER supabase_rh_phase4_cv_fields_migration.sql
--
-- Adds probation tracking to employees (started automatically on hire,
-- via candidates/{id}/promote) and activates the previously-unused
-- performance_goals table (already created in supabase_rh_migration.sql,
-- never wired to any endpoint) as the "objectives during probation" model.
-- No schema change needed for performance_goals — it already has
-- title/description/status/progress/due_date, exactly what's needed.
-- ============================================================

ALTER TABLE employees
  ADD COLUMN IF NOT EXISTS probation_duration_days integer,
  ADD COLUMN IF NOT EXISTS probation_end_date       date,
  ADD COLUMN IF NOT EXISTS probation_status         text NOT NULL DEFAULT 'none';

ALTER TABLE employees DROP CONSTRAINT IF EXISTS employees_probation_status_check;
ALTER TABLE employees ADD CONSTRAINT employees_probation_status_check
  CHECK (probation_status IN ('none', 'in_progress', 'passed', 'failed', 'extended'));

CREATE INDEX IF NOT EXISTS idx_employees_probation_status
  ON employees(probation_status) WHERE probation_status = 'in_progress';
