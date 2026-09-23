-- ============================================================
-- IPISB Platform — Track content edits for PDF-staleness detection
-- Run this ONCE in the Supabase SQL Editor.
--
-- The PDF-staleness warning (courses.pdf_generated_at / pdf_chapter_count)
-- only caught chapters being published/unpublished — it had no idea when
-- someone just edited the TEXT of an already-published chapter, so a typo
-- fix could go live in the app instantly while the compiled PDF in
-- Resources silently kept showing the old wording. This column lets the
-- staleness check catch that too.
-- ============================================================

ALTER TABLE course_lessons ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();
