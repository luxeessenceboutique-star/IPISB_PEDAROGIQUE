-- ============================================================
-- IPISB Connect — Références automatiques + champ commentaire uniforme
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
-- ============================================================
--
-- Objectif :
--   • Donner à CHAQUE enregistrement de la comptabilité une référence
--     unique, lisible et immuable, générée automatiquement à la création.
--   • Format des nouvelles références : PRÉFIXE-2026-0001
--     (année + compteur 4 chiffres, réinitialisé chaque année).
--   • Réutiliser l'existant sans le modifier :
--       revenues.revenue_number  = REC-000001  (compteur global existant)
--       purchases.purchase_number = PUR-000001 (compteur global existant)
--       purchase_requests.request_number = DA-000001 (compteur global existant)
--       inventory_items.code_unique = code auto existant
--     On se contente de COMBLER les manques sur les autres tables.
--   • Ajouter un champ « commentaire » libre uniforme sur chaque partie de saisie.
--
-- Ordre des instructions : compteurs → fonctions → références par table → commentaires.

-- ------------------------------------------------------------
-- 1. Compteur par (préfixe, année)
-- ------------------------------------------------------------
-- Une ligne par couple (préfixe, année). Le compteur repart à 1 chaque année
-- pour chaque préfixe. C'est la source d'unicité des nouvelles références.
CREATE TABLE IF NOT EXISTS reference_counters (
  prefix  text NOT NULL,
  year    int  NOT NULL,
  counter int  NOT NULL DEFAULT 0,
  PRIMARY KEY (prefix, year)
);

-- ------------------------------------------------------------
-- 2. Fonctions de génération
-- ------------------------------------------------------------
-- next_reference : incrémente atomiquement le compteur de (préfixe, année)
-- et renvoie la référence formatée PRÉFIXE-AAAA-NNNN. Si p_year est NULL,
-- on utilise l'année courante. Utilisée comme DEFAULT SQL sur chaque table.
CREATE OR REPLACE FUNCTION next_reference(p_prefix text, p_year int DEFAULT NULL) RETURNS text AS $$
DECLARE y int := COALESCE(p_year, EXTRACT(year FROM now())::int); n int;
BEGIN
  INSERT INTO reference_counters(prefix, year, counter) VALUES (p_prefix, y, 1)
  ON CONFLICT (prefix, year) DO UPDATE SET counter = reference_counters.counter + 1
  RETURNING counter INTO n;
  RETURN p_prefix || '-' || y::text || '-' || lpad(n::text, 4, '0');
END; $$ LANGUAGE plpgsql;

-- backfill_references : attribue chronologiquement une référence aux lignes
-- existantes dont reference est NULL. Chaque ligne prend l'année de son
-- created_at, ce qui préserve la cohérence historique des compteurs annuels.
CREATE OR REPLACE FUNCTION backfill_references(p_table text, p_prefix text) RETURNS void AS $$
DECLARE r record;
BEGIN
  FOR r IN EXECUTE format('SELECT id, created_at FROM %I WHERE reference IS NULL ORDER BY created_at', p_table) LOOP
    EXECUTE format('UPDATE %I SET reference = next_reference(%L, %s) WHERE id = $1',
                   p_table, p_prefix, EXTRACT(year FROM r.created_at)::int) USING r.id;
  END LOOP;
END; $$ LANGUAGE plpgsql;

-- ------------------------------------------------------------
-- 3. Références — combler les manques (une seule fois par table)
-- ------------------------------------------------------------
-- Motif répété pour chaque table : ajout de la colonne, backfill des lignes
-- existantes, pose du DEFAULT (génération auto à l'INSERT), index unique.
-- On NE touche PAS revenues / purchases / purchase_requests / inventory_items :
-- leur référence existe déjà (revenue_number / purchase_number / request_number / code_unique).

-- Dépenses → DEP
ALTER TABLE expenses ADD COLUMN IF NOT EXISTS reference text;
SELECT backfill_references('expenses', 'DEP');
ALTER TABLE expenses ALTER COLUMN reference SET DEFAULT next_reference('DEP');
CREATE UNIQUE INDEX IF NOT EXISTS idx_expenses_reference ON expenses(reference);

-- Factures → FAC
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS reference text;
SELECT backfill_references('invoices', 'FAC');
ALTER TABLE invoices ALTER COLUMN reference SET DEFAULT next_reference('FAC');
CREATE UNIQUE INDEX IF NOT EXISTS idx_invoices_reference ON invoices(reference);

-- Reçus / Paiements → RCU
-- ATTENTION : purchase_payments.reference existe déjà depuis l10 et sert de
-- référence bancaire/chèque SAISIE par l'utilisateur. On ne la réutilise donc
-- PAS pour l'ID auto (sinon collision : l'INSERT envoie reference = NULL et
-- supprime le DEFAULT). On ajoute une colonne dédiée « recu_number » pour le
-- numéro de reçu auto, et on laisse « reference » tel quel.
ALTER TABLE purchase_payments ADD COLUMN IF NOT EXISTS recu_number text;
-- Nettoyage défensif : une version antérieure de ce script posait (à tort) le
-- DEFAULT RCU + un index unique sur « reference » et y écrivait des n° de reçu.
-- On retire ces artefacts et on rapatrie les n° mal placés vers « recu_number »
-- pour que « reference » redevienne uniquement la réf bancaire/chèque saisie.
DROP INDEX IF EXISTS idx_purchase_payments_reference;
ALTER TABLE purchase_payments ALTER COLUMN reference DROP DEFAULT;
UPDATE purchase_payments
   SET recu_number = reference, reference = NULL
 WHERE reference LIKE 'RCU-%' AND recu_number IS NULL;
-- Backfill dédié (backfill_references() ne cible que la colonne « reference »)
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT id, created_at FROM purchase_payments WHERE recu_number IS NULL ORDER BY created_at LOOP
    UPDATE purchase_payments
       SET recu_number = next_reference('RCU', EXTRACT(year FROM r.created_at)::int)
     WHERE id = r.id;
  END LOOP;
END $$;
ALTER TABLE purchase_payments ALTER COLUMN recu_number SET DEFAULT next_reference('RCU');
CREATE UNIQUE INDEX IF NOT EXISTS idx_purchase_payments_recu ON purchase_payments(recu_number);

-- Scolarité (versements) → VER
ALTER TABLE tuition_payments ADD COLUMN IF NOT EXISTS reference text;
SELECT backfill_references('tuition_payments', 'VER');
ALTER TABLE tuition_payments ALTER COLUMN reference SET DEFAULT next_reference('VER');
CREATE UNIQUE INDEX IF NOT EXISTS idx_tuition_payments_reference ON tuition_payments(reference);

-- Fournisseurs → FRN
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS reference text;
SELECT backfill_references('suppliers', 'FRN');
ALTER TABLE suppliers ALTER COLUMN reference SET DEFAULT next_reference('FRN');
CREATE UNIQUE INDEX IF NOT EXISTS idx_suppliers_reference ON suppliers(reference);

-- Budgets → BUD
ALTER TABLE budgets ADD COLUMN IF NOT EXISTS reference text;
SELECT backfill_references('budgets', 'BUD');
ALTER TABLE budgets ALTER COLUMN reference SET DEFAULT next_reference('BUD');
CREATE UNIQUE INDEX IF NOT EXISTS idx_budgets_reference ON budgets(reference);

-- ------------------------------------------------------------
-- 4. Commentaire uniforme — champ libre optionnel sur chaque partie de saisie
-- ------------------------------------------------------------
-- En plus des champs description/notes existants. Les catégories (simple
-- libellé) sont hors périmètre.
ALTER TABLE expenses          ADD COLUMN IF NOT EXISTS comment text;
ALTER TABLE revenues          ADD COLUMN IF NOT EXISTS comment text;
ALTER TABLE invoices          ADD COLUMN IF NOT EXISTS comment text;
ALTER TABLE purchases         ADD COLUMN IF NOT EXISTS comment text;
ALTER TABLE purchase_requests ADD COLUMN IF NOT EXISTS comment text;
ALTER TABLE purchase_payments ADD COLUMN IF NOT EXISTS comment text;
ALTER TABLE tuition_payments  ADD COLUMN IF NOT EXISTS comment text;
ALTER TABLE suppliers         ADD COLUMN IF NOT EXISTS comment text;
ALTER TABLE budgets           ADD COLUMN IF NOT EXISTS comment text;
ALTER TABLE inventory_items   ADD COLUMN IF NOT EXISTS comment text;
