-- ============================================================
-- L58 — Inventaire : statut « En stock »
-- ============================================================
-- Contexte
--   Le statut d'un article n'avait que 4 valeurs : Actif, Hors Service,
--   Vendu, Perdu. Besoin d'un statut « En stock » pour un article acheté /
--   réceptionné mais pas encore affecté/déployé (avant de passer « Actif »).
--
-- À exécuter dans : Supabase → SQL Editor
-- Dépend de       : l10 (colonne inventory_items.status)
-- ============================================================

BEGIN;

ALTER TABLE inventory_items DROP CONSTRAINT IF EXISTS inventory_items_status_check;
ALTER TABLE inventory_items
  ADD CONSTRAINT inventory_items_status_check
  CHECK (status IN ('en_stock', 'actif', 'hors_service', 'vendu', 'perdu'));

COMMIT;
