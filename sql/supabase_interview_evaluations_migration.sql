-- ============================================================
-- IPISB Platform — Évaluation d'entretien (Grille + Fiche + Décision)
-- Run this ONCE in the Supabase SQL Editor
--
-- Digitalise les 2 formulaires RH papier : "Grille d'Entretien de
-- Recrutement" (colonne `grille`) et "Fiche d'Entretien d'Embauche"
-- (colonne `fiche`), + le champ Décision qui n'existait nulle part dans
-- le code. Une évaluation par entretien (partagée si plusieurs
-- interviewers assignés — cf. interview_interviewers), pas par candidat :
-- un candidat peut avoir plusieurs entretiens (rh/technical/final), donc
-- plusieurs évaluations.
--
-- `grille`/`fiche` en JSONB : la structure des 2 formulaires est fixe
-- (pas configurable par l'utilisateur) donc encodée côté code
-- (backend/models.py + frontend/src/components/rh/InterviewEvaluation.tsx),
-- pas ~40 colonnes séparées. Précédent déjà en place : employees.ai_extracted.
-- ============================================================

CREATE TABLE IF NOT EXISTS interview_evaluations (
  id                 uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  interview_id       uuid        NOT NULL UNIQUE REFERENCES interviews(id) ON DELETE CASCADE,
  grille             jsonb       NOT NULL DEFAULT '{}'::jsonb,
  fiche              jsonb       NOT NULL DEFAULT '{}'::jsonb,
  decision           text        CHECK (decision IN ('negative', 'standby', 'other_interview', 'offer', 'other_entity')),
  decision_detail    text,
  salary_current     text,
  salary_expected    text,
  interviewer_visa   text,
  entite_affectation text,
  type_entretien     text        CHECK (type_entretien IN ('presentiel', 'distance')),
  duree_entretien    text,
  submitted_by       uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  submitted_at       timestamptz,
  created_at         timestamptz DEFAULT now(),
  updated_at         timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_interview_evaluations_interview ON interview_evaluations(interview_id);

ALTER TABLE interview_evaluations ENABLE ROW LEVEL SECURITY;
-- Pas de policy : accès exclusivement via le backend service-role.

DROP TRIGGER IF EXISTS trg_interview_evaluations_updated_at ON interview_evaluations;
CREATE TRIGGER trg_interview_evaluations_updated_at
  BEFORE UPDATE ON interview_evaluations
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
