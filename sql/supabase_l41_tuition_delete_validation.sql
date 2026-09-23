-- ============================================================
-- L41 — Validation N+1 de la suppression d'un paiement de scolarité
-- ============================================================
-- Contexte
--   Supprimer un versement de scolarité efface une recette : la ligne du
--   journal (caisse ou comptes) est retirée, la pièce sort du registre des
--   règlements et la facture remise à la famille n'a plus de contrepartie en
--   base. C'était jusqu'ici une action immédiate, réservée aux admins.
--
--   La suppression passe désormais par la file d'attente `pending_operations`,
--   au même titre qu'un décaissement bancaire : l'admin qui demande n'exécute
--   rien, un second administrateur valide (règle des quatre yeux — sauf s'il
--   n'existe qu'un seul compte admin, auquel cas le circuit serait bloqué).
--
--   Cette migration n'ajoute qu'une valeur à la contrainte CHECK de `op_type`.
--   Aucune donnée existante n'est touchée.
--
-- À exécuter dans : Supabase → SQL Editor
-- Dépend de       : l38 (dernier état de la contrainte)
-- ============================================================

BEGIN;

ALTER TABLE pending_operations DROP CONSTRAINT IF EXISTS pending_operations_op_type_check;

ALTER TABLE pending_operations
  ADD CONSTRAINT pending_operations_op_type_check
  CHECK (op_type IN (
    'tuition_payment', 'tuition_payment_delete',
    'student_enrollment', 'class_create', 'student_transfer',
    'cash_journal_create', 'cash_journal_edit', 'cash_journal_delete',
    'cheque_payment', 'bank_payment'
  ));

COMMENT ON COLUMN pending_operations.op_type IS
  'tuition_payment | tuition_payment_delete (suppression d''un versement, validée par un second admin) | '
  'student_enrollment | class_create | student_transfer | '
  'cash_journal_create | cash_journal_edit | cash_journal_delete | '
  'bank_payment (règlement bancaire : chèque, versement, virement, OV)';

COMMIT;

-- ------------------------------------------------------------
-- Contrôle
-- ------------------------------------------------------------
-- SELECT pg_get_constraintdef(oid)
--   FROM pg_constraint
--  WHERE conname = 'pending_operations_op_type_check';
--
-- Demandes de suppression en attente :
-- SELECT id, payload->>'reference' AS versement, amount, created_by, created_at
--   FROM pending_operations
--  WHERE op_type = 'tuition_payment_delete' AND status = 'pending'
--  ORDER BY created_at DESC;
