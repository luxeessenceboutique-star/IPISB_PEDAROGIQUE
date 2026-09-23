-- ============================================================
-- IPISB Platform — AI-generated course content structure
-- Run this ONCE in the Supabase SQL Editor, AFTER
-- supabase_library_files_migration.sql (source material this generates from).
--
-- `courses` is metadata-only today (title/code/credits/semester) — no actual
-- content lives anywhere. This adds the two tables the AI course-generation
-- pipeline populates: a module (chapter) breakdown per course, and lesson
-- content per module. Draft/published at BOTH levels so a professor can
-- review and approve module-by-module rather than all-or-nothing.
-- ============================================================

CREATE TABLE IF NOT EXISTS course_modules (
  id                  uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  course_id           uuid        NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  order_num           integer     NOT NULL DEFAULT 1,
  title               text        NOT NULL,
  objectives          text,
  hours_theory        numeric,
  hours_practice      numeric,
  status              text        NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published')),
  -- Which filière's library_files grounded this generation — traceability,
  -- not a constraint (a course can only belong to one filière via its class,
  -- but the source docs used may be tagged "général").
  source_specialty_id uuid        REFERENCES specialties(id) ON DELETE SET NULL,
  generated_at        timestamptz,
  created_at          timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_course_modules_course ON course_modules(course_id);

CREATE TABLE IF NOT EXISTS course_lessons (
  id            uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  module_id     uuid        NOT NULL REFERENCES course_modules(id) ON DELETE CASCADE,
  order_num     integer     NOT NULL DEFAULT 1,
  title         text        NOT NULL,
  content       text,       -- full lesson text, markdown
  status        text        NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published')),
  generated_at  timestamptz,
  created_at    timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_course_lessons_module ON course_lessons(module_id);

ALTER TABLE course_modules ENABLE ROW LEVEL SECURITY;
ALTER TABLE course_lessons ENABLE ROW LEVEL SECURITY;
-- No policies defined: service-role-only, same as every other table added
-- in this feature line (specialties, library_files, ...).
