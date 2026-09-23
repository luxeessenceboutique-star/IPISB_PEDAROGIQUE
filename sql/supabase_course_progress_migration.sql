-- ============================================================
-- IPISB Platform — student progress + resume tracking
-- Run this ONCE in the Supabase SQL Editor.
--
-- One row per (student, chapter) they've visited — doubles as both the
-- "which chapters has this student completed" signal and the "resume where
-- I left off" signal (most-recent completed_at = last position), without
-- needing two separate tables. A chapter is marked visited the moment a
-- student opens it in the reader — there's no separate quiz/exercise gate
-- at chapter level yet (that's Phase 8), so "viewed" is the completion
-- proxy for now.
-- ============================================================

CREATE TABLE IF NOT EXISTS course_progress (
    id uuid primary key default gen_random_uuid(),
    student_id uuid not null references auth.users(id) on delete cascade,
    course_id uuid not null references courses(id) on delete cascade,
    module_id uuid not null references course_modules(id) on delete cascade,
    completed_at timestamptz not null default now(),
    unique(student_id, module_id)
);
CREATE INDEX IF NOT EXISTS course_progress_student_course_idx ON course_progress(student_id, course_id);
