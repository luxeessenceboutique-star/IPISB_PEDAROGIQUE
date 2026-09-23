-- ============================================================
-- IPISB Connect — Suivi de paiement mensuel des élèves (échéancier + alertes)
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
-- ============================================================
--
-- Objectif : remplacer l'Excel « suivi paiement » par un suivi dans la plateforme.
--   • Plan de paiement par élève inscrit (mensualité, budget, statut) → sur class_students.
--   • Échéancier ancré sur la promo (mois de départ + nb de mensualités) → sur classes.
--   • Paiements réels, un par versement → nouvelle table tuition_payments.
-- L'onglet « Suivi scolarité » est INDÉPENDANT des factures : il ne modifie pas
-- le calcul Encaissé/Encours de l'onglet Analytique.

-- ------------------------------------------------------------
-- 1. Plan de paiement par élève (extension de l'inscription)
-- ------------------------------------------------------------
ALTER TABLE class_students
  ADD COLUMN IF NOT EXISTS monthly_fee       numeric NOT NULL DEFAULT 0,   -- Mensualité contractuelle
  ADD COLUMN IF NOT EXISTS registration_fee  numeric NOT NULL DEFAULT 0,   -- Frais d'inscription
  ADD COLUMN IF NOT EXISTS annual_budget     numeric NOT NULL DEFAULT 0,   -- Budget Année (saisi)
  ADD COLUMN IF NOT EXISTS enrollment_number text,                          -- N° d'inscription (ex. 001/IP/2024)
  ADD COLUMN IF NOT EXISTS enrollment_date   date,
  ADD COLUMN IF NOT EXISTS enrollment_status text NOT NULL DEFAULT 'actif'
      CHECK (enrollment_status IN ('actif', 'abandon', 'absent', 'suspendu', 'diplome')),
  ADD COLUMN IF NOT EXISTS payment_comment   text;

-- ------------------------------------------------------------
-- 2. Ancrage de l'échéancier sur la promo
-- ------------------------------------------------------------
ALTER TABLE classes
  ADD COLUMN IF NOT EXISTS payment_start_month date,                       -- 1er mois de l'échéancier (ex. 2024-09-01)
  ADD COLUMN IF NOT EXISTS installments_count  int NOT NULL DEFAULT 11;    -- nombre de mensualités attendues

-- ------------------------------------------------------------
-- 3. Paiements réels (un par versement) — matrice mois × élève
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tuition_payments (
  id            uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  class_id      uuid        NOT NULL REFERENCES classes(id)    ON DELETE CASCADE,
  student_id    uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  period_month  date        NOT NULL,                                       -- mois d'imputation, normalisé au 1er du mois
  amount        numeric     NOT NULL DEFAULT 0 CHECK (amount >= 0),
  method        text,                                                       -- espèce/chèque/virement… (libre)
  note          text,
  paid_on       date,
  created_by    uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at    timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tuition_payments_student ON tuition_payments(class_id, student_id);
CREATE INDEX IF NOT EXISTS idx_tuition_payments_month   ON tuition_payments(class_id, period_month);

-- ------------------------------------------------------------
-- 4. Activation RLS (accès via service-key backend uniquement)
-- ------------------------------------------------------------
ALTER TABLE tuition_payments ENABLE ROW LEVEL SECURITY;

-- ------------------------------------------------------------
-- Rappel (côté backend, onglet Suivi scolarité) :
--   Total payé (élève)   = Σ tuition_payments.amount (promo + élève)
--   Reste (élève)        = annual_budget − Total payé
--   Attendu à ce jour    = registration_fee + monthly_fee × (mois écoulés, borné par installments_count)
--   Retard (late_amount) = max(0, Attendu à ce jour − Total payé)   → alerte si > 0
--   Les élèves enrollment_status = 'abandon' sont exclus des alertes.
-- ------------------------------------------------------------
