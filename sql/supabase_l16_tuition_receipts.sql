-- ============================================================
-- IPISB Connect — Reçu/justificatif pour les versements de scolarité
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
-- ============================================================

ALTER TABLE tuition_payments
  ADD COLUMN IF NOT EXISTS receipt_reference text;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE table_name = 'accounting_attachments'
      AND constraint_type = 'CHECK'
      AND constraint_name = 'accounting_attachments_entity_type_check'
  ) THEN
    ALTER TABLE accounting_attachments
      DROP CONSTRAINT accounting_attachments_entity_type_check;
  END IF;

  ALTER TABLE accounting_attachments
    ADD CONSTRAINT accounting_attachments_entity_type_check
    CHECK (entity_type IN ('purchase', 'invoice', 'quotation', 'expense', 'tuition_payment'));
EXCEPTION
  WHEN duplicate_object THEN
    NULL;
END $$;
