-- ============================================================
-- IPISB Platform — live in-platform PowerPoint editing (ONLYOFFICE DocSpace)
-- Run this ONCE in the Supabase SQL Editor.
--
-- Stores which DocSpace file backs a course's live-editable deck. The first
-- "Modifier en direct" click generates + uploads a .pptx to DocSpace and
-- remembers its id here; every click after that reopens the SAME file, so
-- a professor's in-progress edits in DocSpace are never silently
-- overwritten by a fresh generation.
-- ============================================================

ALTER TABLE courses ADD COLUMN IF NOT EXISTS docspace_file_id text;
