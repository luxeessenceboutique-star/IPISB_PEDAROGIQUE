-- ============================================================
-- IPISB Connect — Note des Frais de Mission (module de saisie complet)
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
-- Dépend de : next_reference() (migration l14).
-- ============================================================
--
-- Objectif :
--   * Créer la table des NOTES DE FRAIS DE MISSION : document justifiant les
--     frais engagés lors d'une mission (transport, hébergement, repas, divers),
--     ventilés par thème/article ET par jour (matrice J1..J7).
--   * Reproduit le modèle Word « Note des frais de mission.doc » (dossier bébleo/).
--   * Numérotation automatique : NFM-AAAA-NNNN (préfixe NFM, compteur annuel).
--
--   Comme la note de caisse (l32/l34), la note de frais de mission est une
--   AVANCE soumise à circuit :
--     1. Saisie      → status 'pending'   (attente d'approbation N+1)
--     2. Approbation → status 'approved'  (validée par l'admin / Direction)
--     3. Rejet       → status 'rejected'  (motif obligatoire)
--     4. Exécution   → status 'paid'      (décaissement réel dans l'onglet
--                                          Paiements → ligne 'sortie' au journal)
--   La comptabilisation (ligne de journal de caisse) n'a lieu qu'à l'exécution
--   du paiement (voir backend), jamais à la saisie.
--
-- Stockage de la matrice :
--   * days    : jsonb — tableau ordonné des dates des colonnes (≤ 7),
--               ex. ["2026-07-01", "2026-07-02", ""].
--   * amounts : jsonb — objet {clé_article: [montant J1, montant J2, ...]} ;
--               chaque liste est alignée sur `days`. Seules les lignes non nulles
--               sont conservées. Clés d'article (fixes, cf. backend MISSION_CATALOG) :
--                 Transport   : taxi, vehicule, location, train
--                 Hébergement : hotel, heb_forfait
--                 Repas       : repas_justif, repas_forfait
--                 Divers      : telephone, peage, gardiennage, autres
--   * total   : dénormalisé (somme de toutes les cellules), recalculé côté backend.

-- ------------------------------------------------------------
-- 1. Table des notes de frais de mission
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mission_notes (
  id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  reference         text        DEFAULT next_reference('NFM'),  -- N° NFM-AAAA-NNNN (auto)
  note_date         date        NOT NULL DEFAULT current_date,  -- « El Jadida le : ... »
  beneficiary_name  text        NOT NULL,                       -- Nom et Prénom
  beneficiary_cin   text,                                       -- CIN
  accompanied_by    text,                                       -- Accompagné par
  objet             text,                                       -- Objet de mission
  mission_from      date,                                       -- Mission du ...
  mission_to        date,                                       -- ... au ...
  accorded_by       text,                                       -- Accordée par
  days              jsonb       NOT NULL DEFAULT '[]'::jsonb,   -- ["AAAA-MM-JJ", ...] (≤ 7)
  amounts           jsonb       NOT NULL DEFAULT '{}'::jsonb,   -- {article: [montant par jour]}
  total             numeric     NOT NULL DEFAULT 0,             -- Total Globale
  nc                text        NOT NULL DEFAULT 'comptable',   -- nature journal : 'noir' | 'comptable'
  comment           text,
  -- ── Circuit d'approbation N+1 + exécution du paiement ──
  status            text        NOT NULL DEFAULT 'pending',
  approved_by       uuid,
  approved_at       timestamptz,
  rejection_reason  text,
  paid_by           uuid,
  paid_at           timestamptz,
  payment_method    text,   -- ov_permanent | ov_ponctuel | cheque | caisse_sociale | autre
  payment_reference text,   -- n° chèque / virement saisi à l'exécution
  payment_date      date,   -- date effective du décaissement
  created_by        uuid,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_mission_notes_reference ON mission_notes (reference);
CREATE INDEX IF NOT EXISTS mission_notes_date_idx   ON mission_notes (note_date);
CREATE INDEX IF NOT EXISTS mission_notes_status_idx ON mission_notes (status);

-- Backfill défensif : si la table préexistait sans référence, on comble.
UPDATE mission_notes SET reference = next_reference('NFM', EXTRACT(year FROM created_at)::int)
 WHERE reference IS NULL;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'mission_notes_status_check') THEN
    ALTER TABLE mission_notes
      ADD CONSTRAINT mission_notes_status_check
      CHECK (status IN ('pending', 'approved', 'rejected', 'paid'));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'mission_notes_nc_check') THEN
    ALTER TABLE mission_notes
      ADD CONSTRAINT mission_notes_nc_check
      CHECK (nc IN ('noir', 'comptable'));
  END IF;
END $$;

-- ------------------------------------------------------------
-- 2. RLS : le backend passe par la clé service_role (RLS contournée).
--    On verrouille par défaut et on autorise explicitement service_role
--    (même schéma que cash_journal / L19 et cash_notes / L32).
-- ------------------------------------------------------------
ALTER TABLE mission_notes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS mission_notes_service_all ON mission_notes;
CREATE POLICY mission_notes_service_all
  ON mission_notes FOR ALL
  TO service_role
  USING (true) WITH CHECK (true);

COMMENT ON TABLE  mission_notes                IS 'Notes de frais de mission : avances justifiées, ventilées par thème/article et par jour (modèle bébleo « Note des frais de mission »).';
COMMENT ON COLUMN mission_notes.reference      IS 'N° de note auto : NFM-AAAA-NNNN (compteur annuel via next_reference).';
COMMENT ON COLUMN mission_notes.days           IS 'Dates des colonnes de la matrice (≤ 7), ex. ["2026-07-01", ...].';
COMMENT ON COLUMN mission_notes.amounts        IS 'Matrice des montants : {clé_article: [montant J1, montant J2, ...]} alignée sur days.';
COMMENT ON COLUMN mission_notes.total          IS 'Total Globale (somme de toutes les cellules), recalculé par le backend.';
COMMENT ON COLUMN mission_notes.status         IS 'Circuit : pending (attente N+1) | approved (validée) | rejected (refusée) | paid (payée/comptabilisée).';
COMMENT ON COLUMN mission_notes.payment_method IS 'Mode de règlement à l''exécution : ov_permanent | ov_ponctuel | cheque | caisse_sociale | autre.';
