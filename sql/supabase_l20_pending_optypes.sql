-- ============================================================
-- IPISB Connect — Élargit les types d'opérations en validation N+1
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
-- ============================================================
--
-- Objectif : autoriser le caissier à CRÉER une classe et à TRANSFÉRER un élève
-- d'une classe à une autre (même filière uniquement — contrôle côté backend),
-- ces deux saisies passant par la file `pending_operations` (validation admin).
--
-- On remplace la contrainte CHECK de `op_type` pour y ajouter :
--   * class_create      : création d'une classe/promo
--   * student_transfer  : transfert d'un élève vers une autre classe (même filière)

ALTER TABLE pending_operations DROP CONSTRAINT IF EXISTS pending_operations_op_type_check;

ALTER TABLE pending_operations
  ADD CONSTRAINT pending_operations_op_type_check
  CHECK (op_type IN ('tuition_payment', 'student_enrollment', 'class_create', 'student_transfer'));

COMMENT ON COLUMN pending_operations.op_type IS
  'tuition_payment | student_enrollment | class_create | student_transfer';
