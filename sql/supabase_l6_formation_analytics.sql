-- ============================================================
-- IPISB Connect — Indicateurs de pilotage formation
-- CA par session · Encours de facturation · Coût de revient formateur
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
-- ============================================================

-- 1. Frais de scolarité par élève, au niveau de la promo (classe)
ALTER TABLE classes
  ADD COLUMN IF NOT EXISTS tuition_per_student numeric NOT NULL DEFAULT 0;

-- 2. Montant spécifique pour un élève (bourse / remise). NULL => on prend
--    le tarif par défaut de la classe (classes.tuition_per_student).
ALTER TABLE class_students
  ADD COLUMN IF NOT EXISTS tuition_amount numeric;

-- 3. Rattachement des encaissements (recettes) à une promo + un élève
ALTER TABLE revenues
  ADD COLUMN IF NOT EXISTS class_id   uuid REFERENCES classes(id)    ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS student_id uuid REFERENCES auth.users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_revenues_class   ON revenues(class_id);
CREATE INDEX IF NOT EXISTS idx_revenues_student ON revenues(student_id);

-- 4. Tarif horaire du formateur (coût de revient)
CREATE TABLE IF NOT EXISTS trainer_rates (
  user_id     uuid        PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  hourly_rate numeric     NOT NULL DEFAULT 0,
  currency    text        NOT NULL DEFAULT 'MAD',
  updated_by  uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  updated_at  timestamptz DEFAULT now()
);

ALTER TABLE trainer_rates ENABLE ROW LEVEL SECURITY;
-- Backend service key bypasses RLS ; pas de policy SELECT (accès backend uniquement).

-- ------------------------------------------------------------
-- Rappels de calcul (implémentés côté backend) :
--   CA facturable (classe)   = Σ COALESCE(cs.tuition_amount, c.tuition_per_student)
--                              pour les élèves inscrits
--   Encaissé (classe)        = Σ revenues.amount WHERE class_id = c AND status = 'received'
--   Encours de facturation   = CA facturable − Encaissé
--   Coût formateur           = trainer_rates.hourly_rate × heures (schedules)
-- ------------------------------------------------------------
