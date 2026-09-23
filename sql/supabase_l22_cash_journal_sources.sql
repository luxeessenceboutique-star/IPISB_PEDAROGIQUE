-- ============================================================
-- IPISB Connect — Journal de caisse : élargir les sources auto (source_type)
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
-- ============================================================
--
-- Objectif :
--   Le journal de caisse est désormais alimenté AUTOMATIQUEMENT par TOUS les
--   flux d'argent de la comptabilité (et plus seulement l'émission d'une
--   commande). On élargit donc la contrainte CHECK sur `source_type` pour
--   accepter les nouvelles origines :
--       - 'manual'           : saisie admin
--       - 'purchase_request' : émission d'une commande (DA)
--       - 'revenue'          : recette encaissée
--       - 'expense'          : dépense directe
--       - 'purchase_payment' : paiement/reçu d'achat
--       - 'tuition_payment'  : versement de scolarité (validé par l'admin)

-- ------------------------------------------------------------
-- 1. Remplacer la contrainte CHECK sur source_type
-- ------------------------------------------------------------
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cash_journal_source_type_check') THEN
    ALTER TABLE cash_journal DROP CONSTRAINT cash_journal_source_type_check;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cash_journal_source_type_check') THEN
    ALTER TABLE cash_journal
      ADD CONSTRAINT cash_journal_source_type_check
      CHECK (source_type IN (
        'manual', 'purchase_request', 'revenue',
        'expense', 'purchase_payment', 'tuition_payment'
      ));
  END IF;
END $$;

COMMENT ON COLUMN cash_journal.source_type IS
  'manual = saisie admin | purchase_request = émission de commande | revenue = recette | expense = dépense | purchase_payment = paiement d''achat | tuition_payment = scolarité.';
