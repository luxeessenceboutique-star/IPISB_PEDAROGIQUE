-- ============================================================
-- IPISB Platform — RH Phase 4 Migration: Richer CV Extraction Fields
-- Run this ONCE in the Supabase SQL Editor, AFTER supabase_rh_phase3_public_apply_migration.sql
--
-- Adds two columns HR asked to see at a glance when scanning candidates:
-- years of experience (as a number, for sorting/scanning) and languages
-- spoken (separate from the free-text `skills` field).
-- ============================================================

ALTER TABLE employees
  ADD COLUMN IF NOT EXISTS years_experience numeric,
  ADD COLUMN IF NOT EXISTS languages        text;
