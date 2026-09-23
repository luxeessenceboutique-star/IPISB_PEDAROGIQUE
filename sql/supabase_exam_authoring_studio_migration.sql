-- ============================================================
-- IPISB Platform — Exam Authoring Studio, Phase 1 foundation
-- Run this ONCE in the Supabase SQL Editor (or via `apply_migration`).
--
-- Extends the EXISTING exam system (exams / exam_questions /
-- exam_responses) rather than creating a parallel one:
--   - exam_questions gains type/difficulty/points/image/source, so a
--     question can be MCQ or True/False, carry an image, and point back
--     to the course_modules/course_lessons content it was written from.
--   - exams gains content_scope + generation_config (what course content
--     was selected, and how the exam should be built) plus randomization
--     flags — persisted server-side, not kept in frontend state only.
--   - exam_responses gains started_at, and a uniqueness guarantee, so the
--     backend can authoritatively enforce duration_minutes instead of
--     trusting the browser's countdown.
-- ============================================================

-- ---- exam_questions -------------------------------------------------
ALTER TABLE exam_questions
  ADD COLUMN IF NOT EXISTS type              text    NOT NULL DEFAULT 'multiple_choice',
  ADD COLUMN IF NOT EXISTS difficulty        text    NOT NULL DEFAULT 'medium',
  ADD COLUMN IF NOT EXISTS points            numeric NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS image_path        text,
  ADD COLUMN IF NOT EXISTS image_caption     text,
  ADD COLUMN IF NOT EXISTS source_module_id  uuid REFERENCES course_modules(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS source_lesson_id  uuid REFERENCES course_lessons(id) ON DELETE SET NULL;

ALTER TABLE exam_questions
  DROP CONSTRAINT IF EXISTS exam_questions_type_check;
ALTER TABLE exam_questions
  ADD CONSTRAINT exam_questions_type_check CHECK (type IN ('multiple_choice', 'true_false'));

ALTER TABLE exam_questions
  DROP CONSTRAINT IF EXISTS exam_questions_difficulty_check;
ALTER TABLE exam_questions
  ADD CONSTRAINT exam_questions_difficulty_check CHECK (difficulty IN ('easy', 'medium', 'hard'));

ALTER TABLE exam_questions
  DROP CONSTRAINT IF EXISTS exam_questions_points_check;
ALTER TABLE exam_questions
  ADD CONSTRAINT exam_questions_points_check CHECK (points > 0);

-- correct_index must reference a real option — catches a malformed AI
-- generation or a manual edit that desyncs the two before it ever reaches
-- a student.
ALTER TABLE exam_questions
  DROP CONSTRAINT IF EXISTS exam_questions_correct_index_check;
ALTER TABLE exam_questions
  ADD CONSTRAINT exam_questions_correct_index_check
  CHECK (correct_index >= 0 AND correct_index < jsonb_array_length(options));

CREATE INDEX IF NOT EXISTS idx_exam_questions_exam ON exam_questions(exam_id);
CREATE INDEX IF NOT EXISTS idx_exam_questions_source_lesson ON exam_questions(source_lesson_id);
CREATE INDEX IF NOT EXISTS idx_exam_questions_source_module ON exam_questions(source_module_id);

-- ---- exams ------------------------------------------------------------
ALTER TABLE exams
  ADD COLUMN IF NOT EXISTS content_scope      jsonb,   -- {"mode": "full_course"|"selected", "module_ids": [...], "lesson_ids": [...]}
  ADD COLUMN IF NOT EXISTS generation_config  jsonb,   -- {"target_question_count", "question_types", "difficulty_mix", "default_points"}
  ADD COLUMN IF NOT EXISTS randomize_questions boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS randomize_answers   boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS updated_at          timestamptz DEFAULT now();

-- ---- exam_responses -----------------------------------------------------
-- started_at is set by the new POST /exams/{id}/start endpoint the first
-- time a student opens the exam; submitted_at (already nullable, already
-- defaults to now()) is left untouched by /start so "started but not yet
-- submitted" is a real, queryable state instead of being conflated with
-- "submitted at row-creation time".
ALTER TABLE exam_responses
  ADD COLUMN IF NOT EXISTS started_at timestamptz;

-- One response row per student per exam, so /start and /submit can use a
-- clean upsert instead of manual existence checks. Turns out a
-- UNIQUE(exam_id, student_id) constraint already existed on this table
-- (exam_responses_exam_id_student_id_key) — nothing to add here, just
-- confirmed it's there and relied on it in the backend.
