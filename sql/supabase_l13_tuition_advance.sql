-- ============================================================
-- IPISB Connect — Avance sur scolarité (remplace « frais d'inscription »)
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
-- ============================================================
--
-- Modèle de paiement par élève :
--   Mensualité = (Budget − Avance) ÷ nombre de mois de la formation.
--   L'avance est encaissée à l'inscription ; elle peut être vide (0).
--   Les échéances mensuelles courent par cycles de 30 jours depuis la
--   date d'inscription de l'élève (rappel à J+30, alerte rouge à J+37).

ALTER TABLE class_students
  ADD COLUMN IF NOT EXISTS advance numeric NOT NULL DEFAULT 0;

-- Reprise : les anciens « frais d'inscription » deviennent l'avance de départ.
UPDATE class_students
   SET advance = registration_fee
 WHERE advance = 0
   AND registration_fee IS NOT NULL
   AND registration_fee > 0;
