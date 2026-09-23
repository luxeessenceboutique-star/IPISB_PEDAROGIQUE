-- ============================================================
-- IPISB Connect — Rôles caisse/comptable + workflow de validation N+1
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
-- ============================================================
--
-- Objectif :
--   * Ajouter 2 rôles applicatifs : `cashier` (caissier / réceptionniste) et
--     `accountant` (comptable). `user_roles.role` est un ENUM Postgres `app_role`.
--   * Chaque SAISIE du caissier (paiement de scolarité, inscription d'un élève)
--     passe par une file d'attente `pending_operations` et doit être validée par
--     un ADMIN (validation N+1 : approuver / rejeter avec commentaire).
--
-- IMPORTANT (enum) : l'ajout de valeurs d'enum doit être COMMITTÉ avant d'être
-- utilisé. Exécutez d'abord ce script en entier ; la création des comptes
-- (seed_staff.py) se fait ENSUITE, dans une transaction séparée.

-- 1) Étendre l'enum app_role (idempotent).
ALTER TYPE app_role ADD VALUE IF NOT EXISTS 'cashier';
ALTER TYPE app_role ADD VALUE IF NOT EXISTS 'accountant';

-- 2) File d'attente des opérations à valider (N+1).
CREATE TABLE IF NOT EXISTS pending_operations (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  op_type        text NOT NULL CHECK (op_type IN ('tuition_payment', 'student_enrollment')),
  status         text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
  payload        jsonb NOT NULL,
  class_id       uuid,
  student_id     uuid,
  amount         numeric,
  created_by     uuid NOT NULL,          -- caissier qui a saisi
  reviewed_by    uuid,                   -- admin qui a tranché
  review_comment text,                   -- motif du rejet (obligatoire au rejet)
  result_id      uuid,                   -- id de l'enregistrement créé après approbation
  created_at     timestamptz NOT NULL DEFAULT now(),
  reviewed_at    timestamptz
);

CREATE INDEX IF NOT EXISTS pending_operations_status_idx     ON pending_operations (status);
CREATE INDEX IF NOT EXISTS pending_operations_created_by_idx ON pending_operations (created_by);

-- 3) RLS : le backend utilise la clé service_role (RLS contournée), mais on
--    verrouille par défaut et on autorise explicitement service_role.
ALTER TABLE pending_operations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS pending_operations_service_all ON pending_operations;
CREATE POLICY pending_operations_service_all
  ON pending_operations FOR ALL
  TO service_role
  USING (true) WITH CHECK (true);

COMMENT ON TABLE  pending_operations            IS 'File de validation N+1 : saisies caissier en attente d''approbation admin.';
COMMENT ON COLUMN pending_operations.op_type    IS 'tuition_payment | student_enrollment';
COMMENT ON COLUMN pending_operations.payload    IS 'Données brutes de la saisie, réinjectées telles quelles à l''approbation.';
COMMENT ON COLUMN pending_operations.result_id  IS 'Id de la ligne créée (tuition_payments / class_students) après approbation.';
