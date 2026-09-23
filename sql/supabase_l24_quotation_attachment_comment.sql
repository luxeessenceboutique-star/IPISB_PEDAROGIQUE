-- ============================================================
-- IPISB Connect — L24 : Devis (quotations) — pièce jointe + commentaire
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
-- Contexte : après validation du besoin par l'admin, le demandeur (ou l'admin)
--            peut saisir les devis en joignant la pièce du devis + un commentaire.
-- ============================================================

ALTER TABLE quotations
  ADD COLUMN IF NOT EXISTS comment         text,
  ADD COLUMN IF NOT EXISTS attachment_path text,   -- chemin dans le bucket "accounting"
  ADD COLUMN IF NOT EXISTS attachment_name text,   -- nom de fichier d'origine
  ADD COLUMN IF NOT EXISTS created_by      uuid REFERENCES auth.users(id) ON DELETE SET NULL;
