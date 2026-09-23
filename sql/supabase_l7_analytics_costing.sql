-- ============================================================
-- IPISB Connect — Coût de revient formateur (charges directes + indirectes)
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
-- ============================================================

-- % de charges sociales patronales appliqué à la rémunération du formateur.
--   Salarié  -> ~20 (CNSS + AMO + taxe formation).
--   Vacataire payé sur facture -> 0.
ALTER TABLE trainer_rates
  ADD COLUMN IF NOT EXISTS social_charge_percent numeric NOT NULL DEFAULT 0;

-- ------------------------------------------------------------
-- Rappel de calcul (côté backend) :
--   Coût direct    = (tarif horaire × heures) × (1 + social_charge_percent/100)
--   Taux indirect  = charges indirectes de la période ÷ total heures enseignées
--   Coût indirect  = taux indirect × heures du formateur
--   Coût de revient = coût direct + coût indirect
-- Les charges indirectes de la période sont saisies dans l'UI (non persistées),
-- réparties à l'heure sur formateurs et sessions.
-- ------------------------------------------------------------
