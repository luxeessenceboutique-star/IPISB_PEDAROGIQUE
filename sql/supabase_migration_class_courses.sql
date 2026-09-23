-- Run this in the Supabase Dashboard → SQL Editor
-- Creates the class_courses join table so courses can be assigned to classes

CREATE TABLE IF NOT EXISTS class_courses (
    id         UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    class_id   UUID        NOT NULL REFERENCES classes(id)  ON DELETE CASCADE,
    course_id  UUID        NOT NULL REFERENCES courses(id)  ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(class_id, course_id)
);

ALTER TABLE class_courses ENABLE ROW LEVEL SECURITY;

-- Service role has full access (backend uses service key)
CREATE POLICY "service_role_all" ON class_courses
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Authenticated users can read (so students can see their courses)
CREATE POLICY "authenticated_read" ON class_courses
    FOR SELECT TO authenticated USING (true);
