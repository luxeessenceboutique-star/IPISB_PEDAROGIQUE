-- ============================================================
-- L61 — Notes de caisse : HT/TVA/TTC par ligne + mode de remise
-- ============================================================
-- Contexte
--   1. Chaque ligne du tableau (article/prestataire/montant) n'avait qu'un
--      montant unique. On ajoute HT + TVA% par ligne (le TTC — colonne
--      `montant` existante — est recalculé par le backend, jamais fait
--      confiance au montant envoyé par le client). `items` est un jsonb :
--      aucune migration de colonne n'est nécessaire pour ces deux nouvelles
--      clés, seul le code API change.
--
--   2. Nouveau choix à la création de la note : comment l'avance sera remise
--      au bénéficiaire — Espèces ou Versement bancaire. Distinct du mode de
--      règlement choisi plus tard dans Paiements (qui recharge la caisse /
--      règle la note — inchangé).
--
-- À exécuter dans : Supabase → SQL Editor
-- Dépend de       : l32 (table cash_notes)
-- ============================================================

BEGIN;

ALTER TABLE cash_notes
  ADD COLUMN IF NOT EXISTS disbursement_method text NOT NULL DEFAULT 'espece';

ALTER TABLE cash_notes DROP CONSTRAINT IF EXISTS cash_notes_disbursement_method_check;
ALTER TABLE cash_notes
  ADD CONSTRAINT cash_notes_disbursement_method_check
  CHECK (disbursement_method IN ('espece', 'versement'));

COMMIT;
