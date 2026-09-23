-- ============================================================
-- L59 — Factures : suivi paiement (date + mode)
-- ============================================================
-- Contexte
--   Page de suivi des factures : date, N°, fournisseur, montant, N° de
--   commande (déjà porté par invoices.purchase_id — juste pas exploité côté
--   UI/API), état + date de réception (calculés depuis purchase_receptions,
--   comme la vue Livraisons — aucune colonne supplémentaire nécessaire),
--   état + date + mode de paiement, commentaire.
--
--   Seuls la date et le mode de paiement manquaient réellement en base :
--   `payment_status` (état) et `comment` existaient déjà.
--
-- À exécuter dans : Supabase → SQL Editor
-- Dépend de       : l4 (table invoices), l10 (purchase_receptions, pour le
--                   statut de réception calculé côté API)
-- ============================================================

BEGIN;

ALTER TABLE invoices ADD COLUMN IF NOT EXISTS payment_date   date;
ALTER TABLE invoices ADD COLUMN IF NOT EXISTS payment_method text;  -- 'ov_permanent'|'ov_ponctuel'|'cheque'|'versement'|'espece'|'autre'

COMMIT;
