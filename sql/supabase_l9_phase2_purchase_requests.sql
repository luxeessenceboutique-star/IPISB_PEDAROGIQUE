-- ============================================================
-- IPISB Connect — Phase 2 : Workflow Demande d'Achat (DA)
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
-- Circuit : Expression de besoin → Classement → Consultation/Devis (≤5)
--           → Commande (double validation responsable + comptable).
-- Enums modélisés en text + CHECK (cohérent avec le schéma existant).
-- ============================================================

-- Numérotation auto "DA-000001"
CREATE SEQUENCE IF NOT EXISTS purchase_request_seq;

-- ------------------------------------------------------------
-- 1. Demandes d'achat
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS purchase_requests (
  id                    uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  request_number        text        NOT NULL UNIQUE
                          DEFAULT ('DA-' || lpad(nextval('purchase_request_seq')::text, 6, '0')),

  -- Expression de besoin
  company               text,
  service               text,
  requester_name        text,
  project               text,
  activity              text,
  justification         text,
  request_type          text        NOT NULL DEFAULT 'nouveau_besoin'
                          CHECK (request_type IN ('nouveau_besoin', 'renouvellement')),
  asset_category        text        NOT NULL DEFAULT 'consommable'
                          CHECK (asset_category IN ('consommable', 'equipement', 'locaux', 'service')),
  characteristics       text,       -- Caractéristiques / CDC

  -- Classement
  article_code          text,
  quantity              numeric     NOT NULL DEFAULT 1,
  budget_estimate       numeric     NOT NULL DEFAULT 0,
  duration              text,

  -- Décision du besoin
  need_decision         text        NOT NULL DEFAULT 'en_attente'
                          CHECK (need_decision IN ('en_attente', 'validation', 'retour', 'annulation')),
  need_decision_comment text,
  need_decided_by       uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  need_decided_at       timestamptz,

  -- Consultation / devis
  quote_synthesis       text,
  payment_mode          text
                          CHECK (payment_mode IN ('ov_permanent', 'ov_ponctuel', 'cheque', 'versement', 'espece')),
  payment_terms_days    integer,
  quote_decision        text        NOT NULL DEFAULT 'en_attente'
                          CHECK (quote_decision IN ('en_attente', 'validation', 'retour', 'annulation')),
  quote_decision_comment text,
  quote_decided_by      uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  quote_decided_at      timestamptz,

  -- Workflow global
  status                text        NOT NULL DEFAULT 'brouillon'
                          CHECK (status IN ('brouillon', 'besoin_valide', 'en_consultation',
                                            'devis_valide', 'commande_emise', 'retournee', 'annulee')),

  created_by            uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at            timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_purchase_requests_status ON purchase_requests(status);

ALTER TABLE purchase_requests ENABLE ROW LEVEL SECURITY;
-- Backend service key bypasse la RLS ; pas de policy SELECT (accès backend only).

-- ------------------------------------------------------------
-- 2. Devis rattachés à une DA (table quotations déjà créée en L4)
-- ------------------------------------------------------------
ALTER TABLE quotations
  ADD COLUMN IF NOT EXISTS purchase_request_id uuid REFERENCES purchase_requests(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS rank     integer,
  ADD COLUMN IF NOT EXISTS currency text    NOT NULL DEFAULT 'MAD',
  ADD COLUMN IF NOT EXISTS retenu   boolean NOT NULL DEFAULT false;

-- Rang 1..5 (contrainte ajoutée seulement si absente)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'quotations_rank_range') THEN
    ALTER TABLE quotations ADD CONSTRAINT quotations_rank_range CHECK (rank IS NULL OR rank BETWEEN 1 AND 5);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_quotations_purchase_request ON quotations(purchase_request_id);

-- ------------------------------------------------------------
-- 3. Commande = ligne purchases liée à la DA + double validation
-- ------------------------------------------------------------
ALTER TABLE purchases
  ADD COLUMN IF NOT EXISTS purchase_request_id   uuid REFERENCES purchase_requests(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS quotation_id          uuid REFERENCES quotations(id)        ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS edited_by             uuid REFERENCES auth.users(id)        ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS edited_at             timestamptz,
  ADD COLUMN IF NOT EXISTS valide_responsable_by uuid REFERENCES auth.users(id)        ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS valide_responsable_at timestamptz,
  ADD COLUMN IF NOT EXISTS valide_comptable_by   uuid REFERENCES auth.users(id)        ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS valide_comptable_at   timestamptz;

CREATE INDEX IF NOT EXISTS idx_purchases_purchase_request ON purchases(purchase_request_id);

-- ------------------------------------------------------------
-- Rappel transitions (backend) :
--   brouillon --need-decision(validation)--> besoin_valide
--   besoin_valide --(ajout devis)--> en_consultation
--   en_consultation --quote-decision(validation, devis retenu)--> devis_valide
--   devis_valide --create-order--> (purchases créée) --validate-responsable + validate-comptable--> commande_emise
--   retour --> retournee ; annulation --> annulee
-- ------------------------------------------------------------
