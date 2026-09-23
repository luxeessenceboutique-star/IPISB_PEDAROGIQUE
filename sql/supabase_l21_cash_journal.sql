-- ============================================================
-- IPISB Connect — Journal de caisse (auto-alimenté par les DA) + champ n/c
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
-- ============================================================
--
-- Objectif :
--   * Créer le JOURNAL DE CAISSE : registre chronologique des mouvements de
--     caisse. Il est ALIMENTÉ AUTOMATIQUEMENT à l'émission d'une commande
--     (validation admin d'une demande d'achat), et accepte aussi quelques
--     saisies manuelles (admin) pour les mouvements hors DA.
--   * Ajouter l'axe `nc` (« n/c ») = nature de l'opération :
--       - 'noir'      : espèces non déclarées (caisse noire)
--       - 'comptable' : opération déclarée / comptabilisée
--   * Le champ `nc` est aussi porté par la demande d'achat (choisi à la
--     validation de la commande, puis recopié sur l'entrée de caisse).
--
-- IMPORTANT (workflow) : la 2e validation « comptable » sur les commandes est
-- SUPPRIMÉE. Désormais UNE SEULE validation admin émet la commande et crée
-- l'entrée de caisse correspondante (validation N+1).

-- ------------------------------------------------------------
-- 1. Journal de caisse
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cash_journal (
  id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  entry_date   date        NOT NULL DEFAULT current_date,   -- Date
  type         text        NOT NULL CHECK (type IN ('entree', 'sortie')),  -- Type
  action       text        NOT NULL,                        -- Action (libellé)
  prestataire  text,                                        -- Prestataire (fournisseur / tiers)
  amount       numeric     NOT NULL DEFAULT 0,              -- Montant (DH), valeur positive
  justificatif text,                                        -- Justificatif (n° pièce / n° DA / n° commande)
  nc           text        NOT NULL DEFAULT 'comptable'
                 CHECK (nc IN ('noir', 'comptable')),       -- n/c
  source_type  text        NOT NULL DEFAULT 'manual'
                 CHECK (source_type IN ('manual', 'purchase_request')),
  source_id    uuid,                                        -- id de la commande (purchases) si auto
  created_by   uuid,
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS cash_journal_entry_date_idx ON cash_journal (entry_date);
CREATE INDEX IF NOT EXISTS cash_journal_source_idx     ON cash_journal (source_type, source_id);

-- RLS : le backend utilise la clé service_role (RLS contournée). On verrouille
-- par défaut et on autorise explicitement service_role (même schéma que L19).
ALTER TABLE cash_journal ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS cash_journal_service_all ON cash_journal;
CREATE POLICY cash_journal_service_all
  ON cash_journal FOR ALL
  TO service_role
  USING (true) WITH CHECK (true);

COMMENT ON TABLE  cash_journal            IS 'Journal de caisse : mouvements auto (émission de commande DA) + saisies manuelles admin.';
COMMENT ON COLUMN cash_journal.type       IS 'entree (encaissement) | sortie (décaissement).';
COMMENT ON COLUMN cash_journal.nc         IS 'noir = espèces non déclarées (caisse noire) | comptable = opération déclarée.';
COMMENT ON COLUMN cash_journal.source_type IS 'manual = saisie admin | purchase_request = généré à l''émission d''une commande.';

-- ------------------------------------------------------------
-- 2. Champ n/c sur la demande d'achat
-- ------------------------------------------------------------
ALTER TABLE purchase_requests
  ADD COLUMN IF NOT EXISTS nc text NOT NULL DEFAULT 'comptable';

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'purchase_requests_nc_check') THEN
    ALTER TABLE purchase_requests
      ADD CONSTRAINT purchase_requests_nc_check CHECK (nc IN ('noir', 'comptable'));
  END IF;
END $$;

COMMENT ON COLUMN purchase_requests.nc IS 'n/c choisi à la validation de la commande : noir | comptable.';

-- ------------------------------------------------------------
-- Rappel : la colonne purchases.valide_comptable_* reste présente mais n'est
-- plus une étape distincte. La validation unique (POST .../validate-order)
-- pose responsable + comptable en une fois, émet la commande et alimente le
-- journal de caisse.
-- ------------------------------------------------------------
