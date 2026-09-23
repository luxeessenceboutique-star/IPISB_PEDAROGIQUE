-- ============================================================
-- IPISB Platform — RH Phase 7 Migration: Payslip File Uploads
-- Run this ONCE in the Supabase SQL Editor.
--
-- Lets HR upload the actual payslip file (scanned/prepared "fiche de
-- paie") for a given employee/month/year, on top of the PDF the app
-- already generates from computed figures. Reuses the existing
-- payroll_records row (one per employee/month/year — see the UNIQUE
-- constraint added in supabase_rh_migration.sql) rather than a new table.
--
-- Files are stored in the private "payslips" bucket (create it by hand
-- in the Supabase dashboard, same as candidate-cvs / leave-documents)
-- under the path {employee_id}/{year}/{month}/filename — one folder per
-- employee, one subfolder per year, one subfolder per month.
-- ============================================================

ALTER TABLE payroll_records ADD COLUMN IF NOT EXISTS document_path text;
ALTER TABLE payroll_records ADD COLUMN IF NOT EXISTS document_filename text;
