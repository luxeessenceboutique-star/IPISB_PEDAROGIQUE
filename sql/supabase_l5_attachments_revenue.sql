-- ============================================================
-- IPISB Connect — Phase 1.5 : pièces jointes pour Recettes
-- Étend accounting_attachments.entity_type pour accepter 'revenue'
-- ('expense' est déjà autorisé par la migration L4).
-- À exécuter UNE fois dans le SQL Editor de Supabase.
-- Idempotent.
-- ============================================================

ALTER TABLE accounting_attachments
  DROP CONSTRAINT IF EXISTS accounting_attachments_entity_type_check;

ALTER TABLE accounting_attachments
  ADD CONSTRAINT accounting_attachments_entity_type_check
  CHECK (entity_type IN ('purchase', 'invoice', 'quotation', 'expense', 'revenue'));

-- Vérification :
-- SELECT conname, pg_get_constraintdef(oid)
-- FROM pg_constraint
-- WHERE conname = 'accounting_attachments_entity_type_check';
