-- ============================================================
-- IPISB Connect — L28 : Lien paiement réel ↔ échéance planifiée
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
--
-- Le pointage « payé » se fait dans l'onglet Paiements et se rattache à une
-- échéance de l'échéancier prévisionnel défini sur le bon de commande (L27).
-- Un versement peut aussi être libre (installment_id NULL = hors échéancier).
-- ============================================================

ALTER TABLE public.purchase_payments
  ADD COLUMN IF NOT EXISTS installment_id uuid REFERENCES public.purchase_installments(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_purchase_payments_installment ON public.purchase_payments(installment_id);

COMMENT ON COLUMN public.purchase_payments.installment_id IS 'Échéance planifiée (échéancier du bon de commande, L27) réglée par ce versement. NULL = versement hors échéancier.';
