-- ============================================================
-- IPISB Connect — Rattachement des factures à une promo + un élève
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
-- ============================================================

-- Une facture (onglet Factures) peut désormais être affectée à une classe
-- (promo) et à l'élève concerné. Les deux colonnes restent NULL pour les
-- factures fournisseurs classiques.
ALTER TABLE invoices
  ADD COLUMN IF NOT EXISTS class_id   uuid REFERENCES classes(id)    ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS student_id uuid REFERENCES auth.users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_invoices_class   ON invoices(class_id);
CREATE INDEX IF NOT EXISTS idx_invoices_student ON invoices(student_id);

-- ------------------------------------------------------------
-- Rappel (côté backend, analytique formation) :
--   Encaissé (promo)  = Σ total_incl_vat des factures rattachées, payment_status = 'paid'
--   Encours (promo)   = Σ total_incl_vat des factures rattachées, statut 'pending'/'partially_paid'
--   invoices.total_incl_vat est déjà une colonne générée (amount × (1 + vat_percent/100)).
-- ------------------------------------------------------------
