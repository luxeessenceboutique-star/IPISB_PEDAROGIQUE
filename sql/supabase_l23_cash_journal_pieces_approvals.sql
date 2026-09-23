-- ============================================================
-- IPISB Connect — Journal de caisse : validation caissier (N+1) + pièces jointes
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
-- ============================================================
--
-- Objectif :
--   1) Le CAISSIER peut désormais CRÉER, MODIFIER et SUPPRIMER des lignes du
--      journal de caisse, mais chaque opération passe par la file de validation
--      N+1 (`pending_operations`) et doit être approuvée par un ADMIN.
--      On élargit donc la contrainte CHECK de `op_type` pour accepter :
--        - cash_journal_create : création d'une ligne (caissier)
--        - cash_journal_edit   : modification d'une ligne (caissier / comptable)
--        - cash_journal_delete : suppression d'une ligne manuelle (caissier)
--      (cash_journal_edit était déjà utilisé côté code sans être autorisé ici.)
--
--   2) On peut joindre une PIÈCE JUSTIFICATIVE directement à une ligne de caisse
--      (surtout les saisies manuelles). On ajoute donc 'cash_journal' aux
--      entity_type autorisés de `accounting_attachments`. Au passage, on
--      reconstitue le SUR-ENSEMBLE complet des entity_type réellement utilisés
--      par le code (des migrations antérieures avaient divergé : L16 en avait
--      retiré plusieurs et 'purchase_payment' n'a jamais figuré dans la contrainte).

-- ------------------------------------------------------------
-- 1. op_type de pending_operations : ajouter les opérations de caisse
-- ------------------------------------------------------------
ALTER TABLE pending_operations DROP CONSTRAINT IF EXISTS pending_operations_op_type_check;

ALTER TABLE pending_operations
  ADD CONSTRAINT pending_operations_op_type_check
  CHECK (op_type IN (
    'tuition_payment', 'student_enrollment', 'class_create', 'student_transfer',
    'cash_journal_create', 'cash_journal_edit', 'cash_journal_delete'
  ));

COMMENT ON COLUMN pending_operations.op_type IS
  'tuition_payment | student_enrollment | class_create | student_transfer | cash_journal_create | cash_journal_edit | cash_journal_delete';

-- ------------------------------------------------------------
-- 2. entity_type de accounting_attachments : ajouter 'cash_journal'
--    (+ reconstitution du sur-ensemble complet réellement utilisé)
-- ------------------------------------------------------------
ALTER TABLE accounting_attachments
  DROP CONSTRAINT IF EXISTS accounting_attachments_entity_type_check;

ALTER TABLE accounting_attachments
  ADD CONSTRAINT accounting_attachments_entity_type_check
  CHECK (entity_type IN (
    'purchase', 'invoice', 'quotation', 'expense', 'revenue',
    'purchase_request', 'reception', 'inventory_item',
    'tuition_payment', 'purchase_payment', 'cash_journal'
  ));

COMMENT ON CONSTRAINT accounting_attachments_entity_type_check ON accounting_attachments IS
  'Sur-ensemble des entités portant des pièces jointes, y compris cash_journal (pièce justificative d''une ligne de caisse).';

-- Vérification :
-- SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
-- WHERE conname IN ('pending_operations_op_type_check', 'accounting_attachments_entity_type_check');
a