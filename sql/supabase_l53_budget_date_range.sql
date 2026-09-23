-- ============================================================
-- L53 — Budgets : période « du … au … » (plage de dates libre)
-- ============================================================
-- Contexte
--   Un budget prévisionnel se rattachait jusqu'ici soit à une année entière
--   (month IS NULL), soit à un mois précis (month 1–12). Les gérants ont
--   besoin d'une troisième maille : une plage de dates arbitraire — un
--   trimestre, une session de formation, la durée d'un chantier…
--
--   On ajoute deux colonnes nullables `start_date` / `end_date`. Une ligne
--   « plage » a month IS NULL et les deux dates renseignées ; une ligne
--   annuelle ou mensuelle garde start_date / end_date à NULL. Aucune donnée
--   existante n'est touchée.
--
--   La contrainte UNIQUE (category_id, year, month) reste en place : deux
--   plages distinctes de la même catégorie/année ont toutes deux month NULL
--   et Postgres considère les NULL comme distincts, donc pas de collision.
--   Un index d'unicité partiel empêche seulement deux plages *identiques*.
--
-- À exécuter dans : Supabase → SQL Editor
-- Dépend de       : l4 (création de la table budgets)
-- ============================================================

BEGIN;

ALTER TABLE budgets ADD COLUMN IF NOT EXISTS start_date date;
ALTER TABLE budgets ADD COLUMN IF NOT EXISTS end_date   date;

-- Cohérence : soit les deux dates, soit aucune ; et début <= fin.
ALTER TABLE budgets DROP CONSTRAINT IF EXISTS budgets_date_range_chk;
ALTER TABLE budgets
  ADD CONSTRAINT budgets_date_range_chk CHECK (
    (start_date IS NULL AND end_date IS NULL)
    OR (start_date IS NOT NULL AND end_date IS NOT NULL AND start_date <= end_date)
  );

-- Une plage exclut le rattachement à un mois.
ALTER TABLE budgets DROP CONSTRAINT IF EXISTS budgets_range_no_month_chk;
ALTER TABLE budgets
  ADD CONSTRAINT budgets_range_no_month_chk CHECK (
    start_date IS NULL OR month IS NULL
  );

-- Pas deux plages strictement identiques pour une même catégorie/année.
CREATE UNIQUE INDEX IF NOT EXISTS idx_budgets_range_unique
  ON budgets (category_id, year, start_date, end_date)
  WHERE start_date IS NOT NULL;

COMMIT;
