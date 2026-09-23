-- ============================================================
-- L56 — Inventaire : catégories d'actifs gérables
-- ============================================================
-- Contexte
--   `inventory_items.asset_category` était figé par un CHECK à 4 valeurs
--   ('consommable', 'equipement', 'locaux', 'service'), qui pilotaient aussi
--   les 4 onglets de l'écran Inventaire. Besoin de pouvoir ajouter d'autres
--   catégories (Mobilier, Informatique, Pédagogique…) sans repasser par du
--   code : on crée un référentiel `inventory_categories` gérable depuis
--   l'écran Inventaire, et les onglets deviennent dynamiques.
--
--   `asset_category` reste du texte libre en base (contrainte retirée) ; sa
--   valeur doit correspondre à la `key` d'une ligne active de
--   `inventory_categories` — contrôlé côté API (pas de CHECK Postgres, pour
--   rester tolérant si une catégorie est désactivée après coup sur des
--   articles existants).
--
-- À exécuter dans : Supabase → SQL Editor
-- Dépend de       : l10 (colonne inventory_items.asset_category)
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS inventory_categories (
  id         uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  key        text        NOT NULL UNIQUE,   -- slug stable (ex: 'mobilier') — ne change jamais après création
  label      text        NOT NULL,
  sort_order integer     NOT NULL DEFAULT 0,
  active     boolean     NOT NULL DEFAULT true,
  created_by uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

ALTER TABLE inventory_categories ENABLE ROW LEVEL SECURITY;
-- Comme le reste de la compta : pas de policy → accès backend (service key) seul.

-- Amorçage avec les 4 catégories historiques (mêmes clés que l'ancien CHECK).
INSERT INTO inventory_categories (key, label, sort_order) VALUES
  ('consommable', 'Consommables', 1),
  ('equipement',  'Équipements',  2),
  ('locaux',      'Locaux',       3),
  ('service',     'Services',     4)
ON CONFLICT (key) DO NOTHING;

-- La liste devient gérable : on retire la contrainte figée à 4 valeurs.
ALTER TABLE inventory_items DROP CONSTRAINT IF EXISTS inventory_items_asset_category_check;

COMMIT;
