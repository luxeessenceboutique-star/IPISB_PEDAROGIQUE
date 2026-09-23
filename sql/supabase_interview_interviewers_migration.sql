-- ============================================================
-- IPISB Platform — Entretiens : plusieurs interviewers (jusqu'à 3)
-- Run this ONCE in the Supabase SQL Editor
--
-- Remplace l'ancienne colonne unique `interviews.recruiter_id` (jamais
-- exposée côté frontend) par une table de liaison, pour assigner un
-- entretien à plusieurs personnes (RH / Assistant RH). Le plafond de 3
-- est appliqué côté API (backend/routers/rh_recruitment.py), pas en base,
-- pour rester facile à ajuster plus tard.
-- ============================================================

CREATE TABLE IF NOT EXISTS interview_interviewers (
  interview_id  uuid        NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
  user_id       uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  created_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (interview_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_interview_interviewers_user ON interview_interviewers(user_id);

ALTER TABLE interview_interviewers ENABLE ROW LEVEL SECURITY;
-- Pas de policy : accès exclusivement via le backend service-role.
