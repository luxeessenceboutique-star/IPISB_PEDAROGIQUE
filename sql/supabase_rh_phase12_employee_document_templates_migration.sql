-- ============================================================
-- IPISB Platform — RH Phase 12 Migration: Employee Document Templates
-- Run this ONCE in the Supabase SQL Editor.
--
-- Extends the existing document-templates system (originally student-only)
-- to also generate employee documents (contrats, fiches de poste…) from
-- an uploaded example — same "detect once, reuse forever" engine, just a
-- second audience.
-- ============================================================

ALTER TABLE document_templates
  ADD COLUMN IF NOT EXISTS target_type text NOT NULL DEFAULT 'student';
ALTER TABLE document_templates DROP CONSTRAINT IF EXISTS document_templates_target_type_check;
ALTER TABLE document_templates ADD CONSTRAINT document_templates_target_type_check
  CHECK (target_type IN ('student', 'employee'));

ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS employee_id uuid REFERENCES employees(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_documents_employee ON documents(employee_id);
