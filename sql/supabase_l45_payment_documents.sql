-- L45 — Pièce jointe au paiement : type de document + numéro
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
--
-- Contexte : à l'exécution d'un paiement (achat, avance de caisse, frais de
-- mission), l'utilisateur peut désormais joindre un justificatif typé
-- (Facture / Reçu / Autre) avec un numéro de pièce, en plus du scan déjà
-- possible pour les paiements d'achat. Les notes de caisse et frais de
-- mission n'avaient jusqu'ici aucune pièce jointe propre.

-- 1) Numéro de pièce (facultatif) sur chaque pièce jointe.
ALTER TABLE accounting_attachments ADD COLUMN IF NOT EXISTS reference_number text;

-- 2) Ouvre accounting_attachments.entity_type aux avances de caisse et frais
--    de mission (mêmes entity_id que la ligne de journal liée, cf.
--    accounting_cash_notes.CASH_SOURCE / accounting_mission_notes.CASH_SOURCE).
ALTER TABLE accounting_attachments
  DROP CONSTRAINT IF EXISTS accounting_attachments_entity_type_check;

ALTER TABLE accounting_attachments
  ADD CONSTRAINT accounting_attachments_entity_type_check
  CHECK (entity_type IN (
    'purchase', 'invoice', 'quotation', 'expense', 'revenue',
    'purchase_request', 'reception', 'inventory_item',
    'tuition_payment', 'purchase_payment', 'cash_journal',
    'cash_note', 'mission_note'
  ));

COMMENT ON CONSTRAINT accounting_attachments_entity_type_check ON accounting_attachments IS
  'Sur-ensemble des entités portant des pièces jointes, y compris cash_note et mission_note (justificatif joint à l''exécution du paiement).';
