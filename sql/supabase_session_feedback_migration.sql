-- ============================================================
-- IPISB Platform — Teaching Session Feedback (Phase 3)
-- Run this ONCE in the Supabase SQL Editor, AFTER
-- supabase_teaching_sessions_migration.sql.
--
-- This is feedback about a classroom SESSION ("Évaluation de la séance"),
-- deliberately not built on top of exams/exam_questions/exam_responses —
-- it is not an academic assessment and has different rules (same 5
-- questions for everyone, order randomized per student, no right answer).
-- Three tables:
--   session_feedback_questions  — centrally defined, not per-session/per-student
--   session_feedback_requests   — one row per (session, student): WHO was
--                                  invited + their randomized question order,
--                                  generated once when the session ends and
--                                  never recomputed on reopen (spec §26)
--   session_feedback_responses  — one row per (session, student), answers
--                                  keyed by real question_id in a jsonb dict
--                                  (same shape as the existing exam_responses.
--                                  answers column) so display order can never
--                                  corrupt which answer belongs to which
--                                  question, and a real DB UNIQUE constraint
--                                  enforces one submission per student.
-- ============================================================

CREATE TABLE IF NOT EXISTS session_feedback_questions (
  id          uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  order_num   integer     NOT NULL UNIQUE,
  text_fr     text        NOT NULL,
  text_en     text,
  scale_min   integer     NOT NULL DEFAULT 1,
  scale_max   integer     NOT NULL DEFAULT 5,
  is_active   boolean     NOT NULL DEFAULT true,
  created_at  timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS session_feedback_requests (
  id                   uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  teaching_session_id  uuid        NOT NULL REFERENCES teaching_sessions(id) ON DELETE CASCADE,
  student_id           uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  question_order       jsonb       NOT NULL,   -- [question_id, ...], fixed at creation
  -- Not enforced yet — reserved so a "questionnaire expires N hours after
  -- the session" rule (spec §15) can be added later without a new column.
  expires_at           timestamptz,
  created_at           timestamptz DEFAULT now(),
  UNIQUE(teaching_session_id, student_id)
);
CREATE INDEX IF NOT EXISTS idx_sfr_student ON session_feedback_requests(student_id);

CREATE TABLE IF NOT EXISTS session_feedback_responses (
  id                   uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  teaching_session_id  uuid        NOT NULL REFERENCES teaching_sessions(id) ON DELETE CASCADE,
  student_id           uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  answers              jsonb       NOT NULL DEFAULT '{}'::jsonb,  -- {question_id: 1..5}
  submitted_at         timestamptz DEFAULT now(),
  UNIQUE(student_id, teaching_session_id)
);
CREATE INDEX IF NOT EXISTS idx_sfresp_session ON session_feedback_responses(teaching_session_id);

ALTER TABLE session_feedback_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_feedback_requests  ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_feedback_responses ENABLE ROW LEVEL SECURITY;
-- No policies defined: service-role-only, same as teaching_sessions.

-- MVP question set (spec §11) — centrally defined, same five for everyone.
-- order_num is the canonical/reference order, NOT display order; display
-- order is the randomized session_feedback_requests.question_order.
INSERT INTO session_feedback_questions (order_num, text_fr, text_en) VALUES
  (1, 'Comment évaluez-vous la qualité du cours ?', 'How do you rate the quality of the course?'),
  (2, 'Comment évaluez-vous la qualité du formateur ?', 'How do you rate the quality of the trainer?'),
  (3, 'Le contenu présenté était-il clair ?', 'Was the content presented clearly?'),
  (4, 'Le rythme de la séance était-il adapté ?', 'Was the pace of the session appropriate?'),
  (5, 'La séance vous a-t-elle permis de mieux comprendre le sujet ?', 'Did the session help you better understand the topic?')
ON CONFLICT (order_num) DO NOTHING;
