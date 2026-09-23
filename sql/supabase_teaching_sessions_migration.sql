-- ============================================================
-- IPISB Platform — Teaching Sessions (Classroom Teaching Session, Phase 1)
-- Run this ONCE in the Supabase SQL Editor.
--
-- A TeachingSession is a historical record of one physical classroom
-- occurrence of a course — distinct from `courses` (what CAN be taught)
-- and from `course_progress` (what an individual STUDENT has completed/
-- viewed). Feedback questionnaires are a later phase; this migration only
-- covers the session itself.
--
-- Position (start/current/end) is stored as jsonb shaped
-- {module_id, lesson_id, slide_id} rather than six separate FK columns:
-- slide_id has no FK target of its own (slides live inside
-- course_lessons.slides as a jsonb array, not a table), and not every
-- lesson has slides (markdown-only lessons use slide_id: null). Bundling
-- the three into one value per position matches how the reader already
-- addresses content and keeps "no slide" a normal, representable case
-- instead of a special one.
-- ============================================================

CREATE TABLE IF NOT EXISTS teaching_sessions (
  id                uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  course_id         uuid        NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  class_id          uuid        NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
  professor_id      uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  status            text        NOT NULL DEFAULT 'active'
                                 CHECK (status IN ('scheduled', 'active', 'completed', 'cancelled')),
  started_at        timestamptz NOT NULL DEFAULT now(),
  ended_at          timestamptz,
  duration_seconds  integer,
  -- {module_id, lesson_id, slide_id} — slide_id nullable for text-only lessons
  start_position    jsonb,
  -- live position while ACTIVE; also the session-recovery signal after a
  -- refresh/disconnect (spec §21) — becomes frozen once status='completed'
  current_position  jsonb,
  end_position      jsonb,
  created_at        timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_teaching_sessions_professor ON teaching_sessions(professor_id);
CREATE INDEX IF NOT EXISTS idx_teaching_sessions_course ON teaching_sessions(course_id);
CREATE INDEX IF NOT EXISTS idx_teaching_sessions_class ON teaching_sessions(class_id);

-- At most one ACTIVE session per professor+course+class — doubles as the
-- fast "does an active session already exist" lookup for the resume flow,
-- and as a real DB-level guard against duplicate active sessions from a
-- double-click or two tabs (rather than trusting an app-level check).
CREATE UNIQUE INDEX IF NOT EXISTS idx_teaching_sessions_one_active
  ON teaching_sessions(professor_id, course_id, class_id)
  WHERE status = 'active';

ALTER TABLE teaching_sessions ENABLE ROW LEVEL SECURITY;
-- No policies defined: service-role-only, same as every other table added
-- in the course-content feature line (course_modules, course_lessons, ...).
