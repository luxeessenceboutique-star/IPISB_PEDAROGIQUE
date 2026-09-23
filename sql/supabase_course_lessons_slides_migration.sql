-- ============================================================
-- IPISB Platform — Phase 2: visual slide editor data model
-- Run this ONCE in the Supabase SQL Editor.
--
-- The slide deck for a lesson is stored as ONE jsonb document — an array of
-- slide objects, each with an ordered array of positioned elements (text,
-- image, ...). This is deliberately a single JSON blob per lesson rather
-- than normalized course_slides/course_slide_elements tables: the deck is
-- always read and saved as one cohesive unit by the editor (undo/redo,
-- autosave, "did I lose my edits on refresh" all operate on the whole
-- document), so a join-per-element model would add complexity without
-- buying anything for how this is actually used. Matches the shape used
-- throughout the editor UI: [{ id, elements: [{ id, type, x, y, ... }] }].
-- ============================================================

ALTER TABLE course_lessons ADD COLUMN IF NOT EXISTS slides jsonb DEFAULT '[]'::jsonb;
