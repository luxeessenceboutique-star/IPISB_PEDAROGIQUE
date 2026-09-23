-- ============================================================
-- L60 — Réceptions : validation des anomalies qualité
-- ============================================================
-- Contexte
--   Une réception « Non Conforme » (partiel/total) ou « Retourné » créait
--   jusqu'ici l'article en stock immédiatement, comme une réception conforme
--   — aucune étape de contrôle. On ajoute une validation obligatoire pour
--   toute anomalie :
--     - conforme                → finalisée tout de suite (comportement
--                                 inchangé, validation_status='auto')
--     - non_conforme_partiel/total, retourne
--                               → reste « en attente de validation »
--                                 (validation_status='pending'), AUCUN
--                                 article en stock tant que non tranchée
--     - un admin décide ensuite : Accepter (crée l'article en stock,
--       validation_status='validated') ou Rejeter (aucun article,
--       validation_status='rejected') — commentaire obligatoire dans les
--       deux cas, conservé comme historique de la décision.
--
--   Les réceptions déjà enregistrées passent en 'auto' par défaut (compor-
--   tement historique préservé, rien à valider rétroactivement).
--
-- À exécuter dans : Supabase → SQL Editor
-- Dépend de       : l10 (table purchase_receptions)
-- ============================================================

BEGIN;

ALTER TABLE purchase_receptions
  ADD COLUMN IF NOT EXISTS validation_status text NOT NULL DEFAULT 'auto';

ALTER TABLE purchase_receptions DROP CONSTRAINT IF EXISTS purchase_receptions_validation_status_check;
ALTER TABLE purchase_receptions
  ADD CONSTRAINT purchase_receptions_validation_status_check
  CHECK (validation_status IN ('auto', 'pending', 'validated', 'rejected'));

ALTER TABLE purchase_receptions ADD COLUMN IF NOT EXISTS validated_by      uuid REFERENCES auth.users(id) ON DELETE SET NULL;
ALTER TABLE purchase_receptions ADD COLUMN IF NOT EXISTS validated_at      timestamptz;
ALTER TABLE purchase_receptions ADD COLUMN IF NOT EXISTS validation_comment text;

COMMIT;
