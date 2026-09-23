-- ============================================================
-- IPISB Platform — RH Phase 9 Migration: Employee Profile Photo
-- Run this ONCE in the Supabase SQL Editor.
--
-- Adds a photo_url column to employees, set automatically whenever a
-- "photo" file is uploaded via the Fichiers tab (employee_files router) —
-- mirrors how student_files.py backs profiles.photo_url.
-- ============================================================

ALTER TABLE employees ADD COLUMN IF NOT EXISTS photo_url text;
