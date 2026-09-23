-- ============================================================
-- IPISB Connect — Phase 3 : Réception, Paiements, Inventaire & Amortissement
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
-- ============================================================

-- ------------------------------------------------------------
-- 1. Réceptions et contrôle qualité
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS purchase_receptions (
  id                          uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  purchase_id                 uuid        NOT NULL REFERENCES purchases(id) ON DELETE CASCADE,
  received_quantity           numeric     NOT NULL DEFAULT 1 CHECK (received_quantity >= 0),
  received_by                 uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  received_at                 timestamptz DEFAULT now(),
  quality_status              text        NOT NULL CHECK (quality_status IN ('conforme', 'non_conforme_partiel', 'non_conforme_total', 'retourne')),
  qhse_checked                boolean     NOT NULL DEFAULT false,
  inclure_rapport_comptable   boolean     NOT NULL DEFAULT false,
  validation_cg               boolean     NOT NULL DEFAULT false,
  comment                     text,
  created_by                  uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at                  timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_purchase_receptions_purchase ON purchase_receptions(purchase_id);
CREATE INDEX IF NOT EXISTS idx_purchase_receptions_by ON purchase_receptions(received_by);

-- ------------------------------------------------------------
-- 2. Paiements fractionnés (installments)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS purchase_payments (
  id                          uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  purchase_id                 uuid        NOT NULL REFERENCES purchases(id) ON DELETE CASCADE,
  amount                      numeric     NOT NULL CHECK (amount > 0),
  payment_date                date        NOT NULL DEFAULT CURRENT_DATE,
  payment_method              text        NOT NULL CHECK (payment_method IN ('ov_permanent', 'ov_ponctuel', 'cheque', 'versement', 'espece', 'autre')),
  reference                   text,
  created_by                  uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at                  timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_purchase_payments_purchase ON purchase_payments(purchase_id);

-- ------------------------------------------------------------
-- 3. Inventaire / Actifs
-- ------------------------------------------------------------
CREATE SEQUENCE IF NOT EXISTS inventory_item_seq;

CREATE TABLE IF NOT EXISTS inventory_items (
  id                          uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  name                        text        NOT NULL,
  asset_category              text        NOT NULL CHECK (asset_category IN ('consommable', 'equipement', 'locaux', 'service')),
  purchase_id                 uuid        REFERENCES purchases(id) ON DELETE SET NULL,
  reception_id                uuid        REFERENCES purchase_receptions(id) ON DELETE SET NULL,
  code_unique                 text        NOT NULL UNIQUE DEFAULT ('INV-' || lpad(nextval('inventory_item_seq')::text, 6, '0')),
  initial_value               numeric     NOT NULL DEFAULT 0 CHECK (initial_value >= 0),
  purchase_date               date,
  status                      text        NOT NULL DEFAULT 'actif' CHECK (status IN ('actif', 'hors_service', 'vendu', 'perdu')),
  amortissement_duree_annees  integer     CHECK (amortissement_duree_annees > 0),
  niveau_alerte               numeric     CHECK (niveau_alerte >= 0),
  quantity                    numeric     NOT NULL DEFAULT 1 CHECK (quantity >= 0),
  location                    text,
  created_by                  uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at                  timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_inventory_items_category ON inventory_items(asset_category);
CREATE INDEX IF NOT EXISTS idx_inventory_items_purchase ON inventory_items(purchase_id);
CREATE INDEX IF NOT EXISTS idx_inventory_items_reception ON inventory_items(reception_id);

-- ------------------------------------------------------------
-- 4. Mouvements de stock
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS inventory_movements (
  id                          uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  inventory_item_id           uuid        NOT NULL REFERENCES inventory_items(id) ON DELETE CASCADE,
  movement_type               text        NOT NULL CHECK (movement_type IN ('entree', 'sortie', 'ajustement')),
  quantity                    numeric     NOT NULL,
  movement_date               date        NOT NULL DEFAULT CURRENT_DATE,
  description                 text,
  created_by                  uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at                  timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_inventory_movements_item ON inventory_movements(inventory_item_id);

-- ------------------------------------------------------------
-- 5. Pièces jointes : Extension CHECK contrainte
-- ------------------------------------------------------------
ALTER TABLE accounting_attachments
  DROP CONSTRAINT IF EXISTS accounting_attachments_entity_type_check;

ALTER TABLE accounting_attachments
  ADD CONSTRAINT accounting_attachments_entity_type_check
  CHECK (entity_type IN ('purchase', 'invoice', 'quotation', 'expense', 'revenue', 'purchase_request', 'reception', 'inventory_item'));

-- ------------------------------------------------------------
-- 6. Activation RLS
-- ------------------------------------------------------------
ALTER TABLE purchase_receptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE purchase_payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory_movements ENABLE ROW LEVEL SECURITY;
