-- ============================================================
-- IPISB Platform — Session questionnaire v2: feedback + learning check
-- Run this ONCE in the Supabase SQL Editor, AFTER
-- supabase_session_feedback_migration.sql.
--
-- The 5-question session questionnaire now has two parts:
--   Q1-Q2 (unchanged): permanent feedback ratings — session_feedback_questions
--   Q3-Q5 (new):       AI-generated knowledge-check QCM, generated fresh per
--                       session from the content actually covered
--                       (teaching_sessions.start_position -> end_position),
--                       shared by every student in that session (not global
--                       like the feedback questions — one set per session).
--
-- The old order_num 3/4/5 rows are deactivated, not deleted — historical
-- responses referencing them stay intact and interpretable.
-- ============================================================

UPDATE session_feedback_questions SET is_active = false WHERE order_num IN (3, 4, 5);

CREATE TABLE IF NOT EXISTS session_knowledge_questions (
  id                   uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  teaching_session_id  uuid        NOT NULL REFERENCES teaching_sessions(id) ON DELETE CASCADE,
  order_num            integer     NOT NULL,          -- 1-3 within this session's generated set
  question             text        NOT NULL,
  options              jsonb       NOT NULL,           -- [4 strings]
  correct_index        integer     NOT NULL,           -- 0-3, hidden from students until they answer
  explanation          text,
  created_at           timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_skq_session ON session_knowledge_questions(teaching_session_id);

ALTER TABLE session_knowledge_questions ENABLE ROW LEVEL SECURITY;
-- No policies: service-role-only, same as every other table in this feature line.
