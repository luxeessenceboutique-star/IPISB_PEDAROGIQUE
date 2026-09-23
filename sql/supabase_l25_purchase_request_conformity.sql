-- ============================================================
-- IPISB Connect — L25 : Demande d'achat — Conformité
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
-- Contexte : le demandeur précise les exigences de conformité du produit
--            (texte libre : « bœuf congelé »… + critères standard cochés :
--            produit frais, congelé, emballage scellé/fermé, péremption, norme).
-- ============================================================

ALTER TABLE purchase_requests
  ADD COLUMN IF NOT EXISTS conformity_note     text,
  ADD COLUMN IF NOT EXISTS conformity_criteria text[] NOT NULL DEFAULT '{}';
