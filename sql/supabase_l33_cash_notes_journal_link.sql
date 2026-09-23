-- ============================================================
-- IPISB Connect — Lier les notes de caisse au journal de caisse
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
-- Dépend de : cash_notes (l32), cash_journal (l21/l22).
-- ============================================================
--
-- Objectif :
--   * Une note de caisse = un décaissement réel de la caisse. On l'inscrit donc
--     AUTOMATIQUEMENT au journal de caisse (ligne 'sortie'), pour que le
--     Solde Caisse reflète ces sorties. Le backend crée/maj/supprime la ligne.
--   * Ajouter l'axe `nc` (nature) sur la note : 'comptable' (déclaré, défaut)
--     ou 'noir' (caisse sociale). Recopié sur la ligne de journal générée.
--   * Élargir la contrainte CHECK de cash_journal.source_type à 'cash_note'.

-- ------------------------------------------------------------
-- 1. Nature (n/c) sur la note de caisse
-- ------------------------------------------------------------
ALTER TABLE cash_notes
  ADD COLUMN IF NOT EXISTS nc text NOT NULL DEFAULT 'comptable';

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cash_notes_nc_check') THEN
    ALTER TABLE cash_notes
      ADD CONSTRAINT cash_notes_nc_check CHECK (nc IN ('noir', 'comptable'));
  END IF;
END $$;

COMMENT ON COLUMN cash_notes.nc IS 'Nature recopiée sur le journal : comptable (déclaré) | noir (caisse sociale).';

-- ------------------------------------------------------------
-- 2. Autoriser source_type = 'cash_note' dans le journal de caisse
-- ------------------------------------------------------------
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cash_journal_source_type_check') THEN
    ALTER TABLE cash_journal DROP CONSTRAINT cash_journal_source_type_check;
  END IF;
END $$;

ALTER TABLE cash_journal
  ADD CONSTRAINT cash_journal_source_type_check
  CHECK (source_type IN (
    'manual', 'purchase_request', 'revenue',
    'expense', 'purchase_payment', 'tuition_payment', 'cash_note'
  ));

COMMENT ON COLUMN cash_journal.source_type IS
  'manual = saisie admin | purchase_request = émission de commande | revenue = recette | expense = dépense | purchase_payment = paiement d''achat | tuition_payment = scolarité | cash_note = note de caisse.';
