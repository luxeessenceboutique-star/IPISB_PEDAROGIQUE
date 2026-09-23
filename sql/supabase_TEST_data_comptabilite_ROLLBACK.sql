-- ============================================================
-- IPISB Connect — SUPPRESSION du jeu de données de TEST · Comptabilité
-- Annule supabase_TEST_data_comptabilite.sql.
--
-- Supprime UNIQUEMENT les lignes de test : leur id est dans la plage
--   7e570000-…  →  7e57ffff-…
-- Les vraies données (UUID aléatoires) ne sont JAMAIS touchées.
-- Ordre : tables enfants d'abord, tables parents ensuite (contraintes FK).
-- ============================================================

BEGIN;

-- Plage commune à toutes les lignes de test : id commençant par « 7e57 ».
-- (préfixe volontaire ; une vraie ligne aléatoire n'atterrit jamais ici)

DELETE FROM inventory_movements  WHERE id BETWEEN '7e570000-0000-0000-0000-000000000000' AND '7e57ffff-ffff-ffff-ffff-ffffffffffff';
DELETE FROM inventory_items      WHERE id BETWEEN '7e570000-0000-0000-0000-000000000000' AND '7e57ffff-ffff-ffff-ffff-ffffffffffff';
DELETE FROM purchase_payments    WHERE id BETWEEN '7e570000-0000-0000-0000-000000000000' AND '7e57ffff-ffff-ffff-ffff-ffffffffffff';
DELETE FROM purchase_receptions  WHERE id BETWEEN '7e570000-0000-0000-0000-000000000000' AND '7e57ffff-ffff-ffff-ffff-ffffffffffff';
DELETE FROM invoices             WHERE id BETWEEN '7e570000-0000-0000-0000-000000000000' AND '7e57ffff-ffff-ffff-ffff-ffffffffffff';
DELETE FROM quotations           WHERE id BETWEEN '7e570000-0000-0000-0000-000000000000' AND '7e57ffff-ffff-ffff-ffff-ffffffffffff';
DELETE FROM purchases            WHERE id BETWEEN '7e570000-0000-0000-0000-000000000000' AND '7e57ffff-ffff-ffff-ffff-ffffffffffff';
DELETE FROM purchase_requests    WHERE id BETWEEN '7e570000-0000-0000-0000-000000000000' AND '7e57ffff-ffff-ffff-ffff-ffffffffffff';
DELETE FROM revenues             WHERE id BETWEEN '7e570000-0000-0000-0000-000000000000' AND '7e57ffff-ffff-ffff-ffff-ffffffffffff';
DELETE FROM expenses             WHERE id BETWEEN '7e570000-0000-0000-0000-000000000000' AND '7e57ffff-ffff-ffff-ffff-ffffffffffff';
DELETE FROM budgets              WHERE id BETWEEN '7e570000-0000-0000-0000-000000000000' AND '7e57ffff-ffff-ffff-ffff-ffffffffffff';
DELETE FROM suppliers            WHERE id BETWEEN '7e570000-0000-0000-0000-000000000000' AND '7e57ffff-ffff-ffff-ffff-ffffffffffff';
DELETE FROM accounting_categories WHERE id BETWEEN '7e570000-0000-0000-0000-000000000000' AND '7e57ffff-ffff-ffff-ffff-ffffffffffff';

COMMIT;

-- ============================================================
-- Après exécution : toutes les données de test sont supprimées.
-- Le tableau de bord revient à l'état d'avant l'import.
-- ============================================================
