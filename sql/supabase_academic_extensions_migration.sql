-- ============================================================
-- IPISB Platform — Academic Extensions Migration
-- Run this ONCE in the Supabase SQL Editor
--
-- Specialty/year on classes, attendance per séance (tied to schedules),
-- a 'type' (examen/quiz) on exams, and per-course configurable
-- continuous-assessment weighting.
--
-- CAVEAT: courses/exams/assignments/submissions/exam_responses/
-- course_enrollments have no committed migration file anywhere in this
-- repo (created directly in the Supabase dashboard) — the ALTER TABLE
-- exams statement below uses ADD COLUMN IF NOT EXISTS defensively.
-- Eyeball this file against the live schema before running.
-- ============================================================

-- ============================================================
-- 1. Specialties (filières)
-- ============================================================
CREATE TABLE IF NOT EXISTS specialties (
  id         uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  name       text        NOT NULL UNIQUE,
  created_by uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at timestamptz DEFAULT now()
);

ALTER TABLE specialties ENABLE ROW LEVEL SECURITY;

-- Seed with the canonical list already used by the chatbot lead-capture
-- flow (backend/chatbot/airtable_client.py) for terminology consistency.
INSERT INTO specialties (name) VALUES
  ('Infirmier Polyvalent'),
  ('Infirmier Auxiliaire'),
  ('Aide-Soignant')
ON CONFLICT (name) DO NOTHING;

-- ============================================================
-- 2. Classes — add specialty + year (each class = ONE specialty + ONE year)
-- ============================================================
ALTER TABLE classes ADD COLUMN IF NOT EXISTS specialty_id uuid REFERENCES specialties(id) ON DELETE SET NULL;
ALTER TABLE classes ADD COLUMN IF NOT EXISTS year_number integer CHECK (year_number BETWEEN 1 AND 5);

CREATE INDEX IF NOT EXISTS idx_classes_specialty ON classes(specialty_id);

-- ============================================================
-- 3. Schedules — link a slot to the course actually being taught
-- ============================================================
ALTER TABLE schedules ADD COLUMN IF NOT EXISTS course_id uuid REFERENCES courses(id) ON DELETE SET NULL;

-- ============================================================
-- 4. Séances (dated occurrence of a schedule slot) + attendance
-- ============================================================
CREATE TABLE IF NOT EXISTS seances (
  id          uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  schedule_id uuid        NOT NULL REFERENCES schedules(id) ON DELETE CASCADE,
  class_id    uuid        REFERENCES classes(id) ON DELETE SET NULL,
  course_id   uuid        REFERENCES courses(id) ON DELETE SET NULL,
  date        date        NOT NULL,
  created_by  uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at  timestamptz DEFAULT now(),
  UNIQUE (schedule_id, date)
);

CREATE INDEX IF NOT EXISTS idx_seances_class ON seances(class_id);

ALTER TABLE seances ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS attendance (
  id         uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  seance_id  uuid        NOT NULL REFERENCES seances(id) ON DELETE CASCADE,
  student_id uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  status     text        NOT NULL DEFAULT 'present' CHECK (status IN ('present', 'absent', 'retard', 'excuse')),
  marked_by  uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  marked_at  timestamptz DEFAULT now(),
  UNIQUE (seance_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance(student_id);

ALTER TABLE attendance ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- 5. Exams — add a type to distinguish full exams from quizzes
-- ============================================================
ALTER TABLE exams ADD COLUMN IF NOT EXISTS type text NOT NULL DEFAULT 'examen' CHECK (type IN ('examen', 'quiz'));

-- ============================================================
-- 6. Per-course continuous-assessment weighting
-- ============================================================
CREATE TABLE IF NOT EXISTS course_grade_weights (
  course_id     uuid        PRIMARY KEY REFERENCES courses(id) ON DELETE CASCADE,
  exam_weight   integer     NOT NULL DEFAULT 50 CHECK (exam_weight BETWEEN 0 AND 100),
  devoir_weight integer     NOT NULL DEFAULT 30 CHECK (devoir_weight BETWEEN 0 AND 100),
  quiz_weight   integer     NOT NULL DEFAULT 20 CHECK (quiz_weight BETWEEN 0 AND 100),
  updated_by    uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  updated_at    timestamptz DEFAULT now(),
  CHECK (exam_weight + devoir_weight + quiz_weight = 100)
);

ALTER TABLE course_grade_weights ENABLE ROW LEVEL SECURITY;
