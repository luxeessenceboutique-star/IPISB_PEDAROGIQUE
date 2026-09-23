-- ============================================================
-- IPISB Platform — Teacher-added images per lesson
-- Run this ONCE in the Supabase SQL Editor, AFTER
-- supabase_course_content_migration.sql.
--
-- Images uploaded by the professor to illustrate a chapter (diagrams,
-- photos, schemas they already have) — embedded into the compiled PDF
-- alongside the AI-generated text. Stored in the existing 'course-materials'
-- bucket, but under {course_id}/lesson-images/{lesson_id}/... rather than
-- {course_id}/files/ — keeps them out of the "Ressources" file list (they
-- aren't a standalone downloadable resource, they're chapter illustrations).
-- ============================================================

CREATE TABLE IF NOT EXISTS course_lesson_images (
  id          uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  lesson_id   uuid        NOT NULL REFERENCES course_lessons(id) ON DELETE CASCADE,
  file_path   text        NOT NULL,   -- path within the 'course-materials' bucket
  caption     text,
  order_num   integer     NOT NULL DEFAULT 1,
  uploaded_by uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at  timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_course_lesson_images_lesson ON course_lesson_images(lesson_id);

ALTER TABLE course_lesson_images ENABLE ROW LEVEL SECURITY;
-- No policies defined: service-role-only, same as every other table added
-- in this feature line.
