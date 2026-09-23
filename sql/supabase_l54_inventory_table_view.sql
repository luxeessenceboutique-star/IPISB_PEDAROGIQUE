-- ============================================================
-- L54 — Inventaire : vue tableau (caractéristiques, unité, prix TTC,
--        ventilation par local, demandeur des sorties)
-- ============================================================
-- Contexte
--   La vue inventaire se limitait à une liste nom + quantité + valeur. Les
--   gérants veulent un tableau filtrable façon feuille Excel :
--     code article · article · caractéristiques · unité · état de stock ·
--     prix unité TTC · prix total stock · total entré · demandeurs ·
--     total sorti · affectation par local.
--
--   Cette migration ajoute :
--     • inventory_items.caracteristiques   (texte libre — specs / modèle)
--     • inventory_items.unite              (pièce, kg, L, carton…)
--     • inventory_items.prix_unitaire_ttc  (prix TTC unitaire)
--     • inventory_items.tva_percent        (taux TVA, défaut 20)
--     • inventory_movements.beneficiary    (demandeur d'une sortie de stock)
--     • table inventory_allocations        (quantités ventilées par local)
--
--   Aucune donnée existante n'est touchée ; `location` (emplacement unique)
--   reste en place et sert de valeur par défaut de la ventilation.
--
-- À exécuter dans : Supabase → SQL Editor
-- Dépend de       : l10 (tables inventory_items / inventory_movements)
-- ============================================================

BEGIN;

ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS caracteristiques  text;
ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS unite             text;
ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS prix_unitaire_ttc numeric CHECK (prix_unitaire_ttc IS NULL OR prix_unitaire_ttc >= 0);
ALTER TABLE inventory_items ADD COLUMN IF NOT EXISTS tva_percent       numeric DEFAULT 20 CHECK (tva_percent IS NULL OR tva_percent >= 0);

ALTER TABLE inventory_movements ADD COLUMN IF NOT EXISTS beneficiary text;

CREATE TABLE IF NOT EXISTS inventory_allocations (
  id                uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  inventory_item_id uuid        NOT NULL REFERENCES inventory_items(id) ON DELETE CASCADE,
  location          text        NOT NULL,
  quantity          numeric     NOT NULL DEFAULT 0 CHECK (quantity >= 0),
  created_at        timestamptz DEFAULT now(),
  updated_at        timestamptz DEFAULT now(),
  UNIQUE (inventory_item_id, location)
);

CREATE INDEX IF NOT EXISTS idx_inventory_allocations_item ON inventory_allocations(inventory_item_id);

ALTER TABLE inventory_allocations ENABLE ROW LEVEL SECURITY;
-- Comme le reste de la compta : pas de policy → seul le backend (service key) lit/écrit.

COMMIT;
