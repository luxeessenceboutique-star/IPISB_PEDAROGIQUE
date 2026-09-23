-- ============================================================
-- IPISB Platform — RH Phase 11 Migration: Expanded Employee Fields
-- Run this ONCE in the Supabase SQL Editor.
--
-- The AI dossier analysis (Analyser le dossier) can read far more off a
-- CIN/contrat/diplôme than the original employees table had columns for.
-- This adds every field that's realistically extractable so nothing gets
-- discarded, grouped by category. All nullable/optional — nothing here is
-- required to create or edit an employee by hand.
-- ============================================================

ALTER TABLE employees
  -- Identité complémentaire
  ADD COLUMN IF NOT EXISTS gender                text,   -- 'M' | 'F'
  ADD COLUMN IF NOT EXISTS place_of_birth         text,
  ADD COLUMN IF NOT EXISTS marital_status         text,   -- célibataire | marié(e) | divorcé(e) | veuf(ve)
  ADD COLUMN IF NOT EXISTS dependents_count       integer,
  ADD COLUMN IF NOT EXISTS blood_type             text,
  ADD COLUMN IF NOT EXISTS postal_code            text,
  ADD COLUMN IF NOT EXISTS country                text DEFAULT 'Maroc',
  ADD COLUMN IF NOT EXISTS personal_email         text,

  -- Pièce d'identité
  ADD COLUMN IF NOT EXISTS cin_issue_date         date,
  ADD COLUMN IF NOT EXISTS cin_expiry_date        date,
  ADD COLUMN IF NOT EXISTS passport_number        text,

  -- Contact d'urgence
  ADD COLUMN IF NOT EXISTS emergency_contact_name     text,
  ADD COLUMN IF NOT EXISTS emergency_contact_phone    text,
  ADD COLUMN IF NOT EXISTS emergency_contact_relation text,

  -- Poste / conditions de travail
  ADD COLUMN IF NOT EXISTS grade                 text,   -- échelon / niveau
  ADD COLUMN IF NOT EXISTS work_location          text,   -- site / lieu de travail
  ADD COLUMN IF NOT EXISTS weekly_hours           numeric,

  -- Administratif / paie
  ADD COLUMN IF NOT EXISTS bank_name              text,
  ADD COLUMN IF NOT EXISTS amo_number             text,   -- N° AMO / mutuelle
  ADD COLUMN IF NOT EXISTS tax_id                 text,   -- identifiant fiscal (IF)
  ADD COLUMN IF NOT EXISTS cimr_number            text;   -- retraite complémentaire (optionnel)
