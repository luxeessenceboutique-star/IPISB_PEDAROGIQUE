-- L50 — Double validation (2 admins distincts) sur les décaissements bancaires
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
--
-- Contexte : jusqu'ici, un seul administrateur (autre que l'auteur de la
-- saisie) suffisait à valider ET exécuter un chèque/virement. Ces deux
-- colonnes permettent de tracer une PREMIÈRE validation sans exécuter le
-- paiement, en attendant qu'un SECOND administrateur, distinct du premier
-- ET de l'auteur, valide à son tour (routers/approvals.py::approve_operation).
-- pending_operations.status reste 'pending' pendant l'attente de la seconde
-- validation — il ne passe à 'approved' qu'une fois les deux obtenues.

ALTER TABLE public.pending_operations
  ADD COLUMN IF NOT EXISTS first_approved_by uuid REFERENCES auth.users(id) ON DELETE SET NULL;
ALTER TABLE public.pending_operations
  ADD COLUMN IF NOT EXISTS first_approved_at timestamptz;

COMMENT ON COLUMN public.pending_operations.first_approved_by IS
  'Décaissements bancaires (bank_payment/cheque_payment) uniquement : administrateur ayant donné la 1ère validation. Le paiement n''est exécuté qu''après une 2e validation par un administrateur DIFFÉRENT (et différent de l''auteur).';
