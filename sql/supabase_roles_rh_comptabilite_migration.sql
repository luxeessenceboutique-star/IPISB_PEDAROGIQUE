-- ============================================================
-- IPISB Platform — New Roles Migration: rh, assistant_rh, comptabilite
-- Run this ONCE in the Supabase SQL Editor.
--
-- Adds three new values to the app_role enum used by user_roles.role:
--   - rh            : full access to the RH module only (not Accounting,
--                     not Courses, not other admin-only areas)
--   - assistant_rh  : same RH access as 'rh', except payroll/salary data
--   - comptabilite  : full read+write access to the Accounting module
--                     only (equivalent to what admin currently has there)
--
-- NOTE: ALTER TYPE ... ADD VALUE cannot run inside the same transaction
-- as a statement that USES the new value, but each statement below is
-- safe to run as-is in the Supabase SQL Editor (each ADD VALUE commits
-- on its own before anything references the new value).
-- ============================================================

ALTER TYPE app_role ADD VALUE IF NOT EXISTS 'rh';
ALTER TYPE app_role ADD VALUE IF NOT EXISTS 'assistant_rh';
ALTER TYPE app_role ADD VALUE IF NOT EXISTS 'comptabilite';
