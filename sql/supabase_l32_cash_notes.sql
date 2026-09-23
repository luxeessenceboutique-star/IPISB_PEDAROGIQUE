-- ============================================================
-- IPISB Connect — Note de Caisse (module de saisie complet)
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
-- Dépend de : next_reference() (migration l14).
-- ============================================================
--
-- Objectif :
--   * Créer la table des NOTES DE CAISSE : document justifiant une avance /
--     un remboursement de caisse au profit d'un bénéficiaire, avec un tableau
--     détaillé (Article / Prestataire / Montant), un total et des visas.
--   * Reproduit le modèle Word « Note de Caisse.doc » (dossier bébleo/).
--   * Numérotation automatique : NDC-AAAA-NNNN (préfixe NDC, compteur annuel).
--
-- Le tableau des lignes est stocké en JSONB : [{article, prestataire, montant}].
-- Le total est dénormalisé (recalculé côté backend à chaque écriture).

-- ------------------------------------------------------------
-- 1. Table des notes de caisse
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cash_notes (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  reference        text        DEFAULT next_reference('NDC'),  -- N° NDC-AAAA-NNNN (auto)
  note_date        date        NOT NULL DEFAULT current_date,  -- « El Jadida le : ... »
  beneficiary_name text        NOT NULL,                       -- Nom et Prénom
  beneficiary_cin  text,                                       -- CIN
  objet            text,                                       -- Objet de la note de caisse
  period_from      date,                                       -- « Du ... »
  period_to        date,                                       -- « ... au ... »
  accorded_by      text,                                       -- Accordée par
  items            jsonb       NOT NULL DEFAULT '[]'::jsonb,   -- [{article, prestataire, montant}]
  total            numeric     NOT NULL DEFAULT 0,             -- Total Global
  comment          text,
  created_by       uuid,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_cash_notes_reference ON cash_notes (reference);
CREATE INDEX IF NOT EXISTS cash_notes_date_idx ON cash_notes (note_date);

-- Backfill défensif : si la table préexistait sans référence, on comble.
UPDATE cash_notes SET reference = next_reference('NDC', EXTRACT(year FROM created_at)::int)
 WHERE reference IS NULL;

-- ------------------------------------------------------------
-- 2. RLS : le backend passe par la clé service_role (RLS contournée).
--    On verrouille par défaut et on autorise explicitement service_role
--    (même schéma que cash_journal / L19).
-- ------------------------------------------------------------
ALTER TABLE cash_notes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS cash_notes_service_all ON cash_notes;
CREATE POLICY cash_notes_service_all
  ON cash_notes FOR ALL
  TO service_role
  USING (true) WITH CHECK (true);

COMMENT ON TABLE  cash_notes           IS 'Notes de caisse : avances / remboursements justifiés (modèle bébleo « Note de Caisse »).';
COMMENT ON COLUMN cash_notes.reference IS 'N° de note auto : NDC-AAAA-NNNN (compteur annuel via next_reference).';
COMMENT ON COLUMN cash_notes.items     IS 'Lignes du tableau : [{article, prestataire, montant}].';
COMMENT ON COLUMN cash_notes.total     IS 'Total Global (somme des montants des lignes), recalculé par le backend.';
