-- ============================================================
-- L57 — Dépenses : caractéristiques, fin de garantie, demandeur
-- ============================================================
-- Contexte
--   Pour une dépense d'équipement (ex. catégorie « Matériel pédagogique »),
--   les gérants veulent tracer : les caractéristiques (modèle/specs), la date
--   de fin de garantie, et l'utilisateur/demandeur du matériel. Les pièces
--   jointes existent déjà (accounting_attachments, entity_type='expense') —
--   seuls 3 nouveaux types de document sont ajoutés côté API (Photo, Fiche
--   technique, Garantie ; « Facture » existe déjà sous kind='invoice') : la
--   colonne `kind` est du texte libre, sans CHECK, donc aucune migration
--   n'est nécessaire pour ça.
--
-- À exécuter dans : Supabase → SQL Editor
-- Dépend de       : l4 (table expenses)
-- ============================================================

BEGIN;

ALTER TABLE expenses ADD COLUMN IF NOT EXISTS caracteristiques  text;
ALTER TABLE expenses ADD COLUMN IF NOT EXISTS warranty_end_date date;
ALTER TABLE expenses ADD COLUMN IF NOT EXISTS beneficiary       text;  -- utilisateur / demandeur

COMMIT;
