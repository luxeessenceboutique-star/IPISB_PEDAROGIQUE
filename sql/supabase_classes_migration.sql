-- ============================================================
-- IPISB Platform — Classes Migration
-- Run this ONCE in the Supabase SQL Editor
-- ============================================================

-- 1. Classes table (professor groups)
CREATE TABLE IF NOT EXISTS classes (
  id          uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  name        text        NOT NULL,
  description text,
  created_by  uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at  timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_classes_created_by ON classes(created_by);

-- 2. Class–student membership
CREATE TABLE IF NOT EXISTS class_students (
  class_id   uuid REFERENCES classes(id) ON DELETE CASCADE,
  student_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
  added_at   timestamptz DEFAULT now(),
  PRIMARY KEY (class_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_class_students_student ON class_students(student_id);

-- 3. RLS — backend service key bypasses these; they protect direct client access
ALTER TABLE classes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "classes_select_creator" ON classes;
CREATE POLICY "classes_select_creator"
  ON classes FOR SELECT
  USING (auth.uid() = created_by);

ALTER TABLE class_students ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "class_students_select" ON class_students;
CREATE POLICY "class_students_select"
  ON class_students FOR SELECT
  USING (
    auth.uid() = student_id OR
    EXISTS (SELECT 1 FROM classes WHERE id = class_id AND created_by = auth.uid())
  );
