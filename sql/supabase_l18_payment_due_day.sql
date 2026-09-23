-- ============================================================
-- IPISB Connect — Jour d'échéance de paiement + suivi du comportement
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
-- ============================================================
--
-- Objectif : suivre le COMPORTEMENT de paiement des élèves, pas seulement
-- la couverture du montant. Une mensualité payée en retard ne doit plus
-- s'afficher « verte » comme une mensualité payée à l'heure.
--
-- Modèle d'échéance :
--   * Le paiement d'un mois est dû le `due_day` du mois (défaut = 1).
--   * Tolérance : jusqu'à `due_day + grace_days` sans pénalité (défaut 9 → le 9).
--   * Cas exceptionnels PAR ÉLÈVE : certains paient le 15, le 20, etc.
--     → `due_day` réglable par élève.
--
-- Alertes échelonnées (relatif à l'échéance du mois courant) :
--   à J = rappel · à J+5 = danger · à J+10 = critique.

-- 1) Jour d'échéance par élève (1..28 pour éviter les mois courts).
ALTER TABLE class_students
  ADD COLUMN IF NOT EXISTS due_day smallint NOT NULL DEFAULT 1;

-- 2) Jours de tolérance après l'échéance (défaut 9 → paiement toléré jusqu'au 9
--    quand due_day = 1). Réglable par élève si besoin.
ALTER TABLE class_students
  ADD COLUMN IF NOT EXISTS grace_days smallint NOT NULL DEFAULT 9;

-- 3) Contraintes de garde-fou (bornes raisonnables).
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'class_students_due_day_chk'
  ) THEN
    ALTER TABLE class_students
      ADD CONSTRAINT class_students_due_day_chk
      CHECK (due_day BETWEEN 1 AND 28);
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'class_students_grace_days_chk'
  ) THEN
    ALTER TABLE class_students
      ADD CONSTRAINT class_students_grace_days_chk
      CHECK (grace_days BETWEEN 0 AND 27);
  END IF;
END $$;

-- 4) La date réelle d'un paiement sert à mesurer le retard. On s'appuie sur
--    tuition_payments.paid_on si renseigné, sinon created_at. Rien à migrer ici :
--    ces colonnes existent déjà (migration l11 / l16). On documente juste l'usage.
COMMENT ON COLUMN class_students.due_day   IS 'Jour du mois où la mensualité est due (1..28, défaut 1).';
COMMENT ON COLUMN class_students.grace_days IS 'Jours de tolérance après l''échéance avant retard (défaut 9).';
