-- ============================================================
-- IPISB Platform — Session feedback/quiz: server-authoritative timer
-- Run this ONCE in the Supabase SQL Editor, AFTER
-- supabase_session_feedback_migration.sql and
-- supabase_session_knowledge_questions_migration.sql.
--
-- Adds the same "server records started_at, deadline is computed from
-- it" pattern exams already use (see exams.py's /start), so the post-
-- session quiz (2 feedback ratings + 3 knowledge-check questions, spec
-- §10/§24-26) can show an instructions screen before the countdown
-- starts, and survive a page refresh without resetting the clock.
-- started_at stays NULL until the student confirms the instructions
-- screen — that's the moment the countdown actually begins.
-- ============================================================

ALTER TABLE session_feedback_requests
  ADD COLUMN IF NOT EXISTS started_at timestamptz;
