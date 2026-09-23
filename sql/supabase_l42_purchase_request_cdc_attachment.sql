-- ============================================================
-- IPISB Connect — L42 : Demande d'achat — pièce jointe CDC
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
-- Contexte : le champ « Caractéristiques / CDC » (texte libre) peut
--            désormais être complété par un fichier joint (cahier des
--            charges — PDF/JPG/PNG), stocké dans le même bucket que les
--            pièces jointes de devis (voir accounting_quotations.py).
-- ============================================================

ALTER TABLE purchase_requests
  ADD COLUMN IF NOT EXISTS cdc_attachment_path text,
  ADD COLUMN IF NOT EXISTS cdc_attachment_name text;
