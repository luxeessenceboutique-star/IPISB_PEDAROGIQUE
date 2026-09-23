-- ============================================================
-- IPISB Platform — Course PDF staleness tracking
-- Run this ONCE in the Supabase SQL Editor, AFTER
-- supabase_course_content_migration.sql.
--
-- The compiled course PDF (routers/course_generation.py generate_pdf) is a
-- point-in-time snapshot of whichever chapters were published/present at
-- generation time — it does NOT auto-regenerate when a new chapter gets
-- published afterward. Without a record of "when was this last compiled,
-- and how many chapters did it include", a professor publishing chapter 4
-- has no way to tell the PDF in Resources is now stale except by comparing
-- page counts by eye. These two columns let the UI warn instead.
-- ============================================================

ALTER TABLE courses ADD COLUMN IF NOT EXISTS pdf_generated_at timestamptz;
ALTER TABLE courses ADD COLUMN IF NOT EXISTS pdf_chapter_count integer;
