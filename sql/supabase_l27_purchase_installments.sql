-- ============================================================
-- IPISB Connect — L27 : Échéancier de paiement (prévisionnel) du bon de commande
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
--
-- Contexte : un bon de commande peut être réglé en plusieurs versements
-- échelonnés convenus avec le fournisseur (ex. : avance « en noir », solde par
-- chèque à la livraison, mensualités d'un service sur 3 mois…). Cette table
-- stocke le PLAN de paiement (prévisionnel) — distinct des paiements réellement
-- décaissés qui vivent dans `purchase_payments`. Aucun impact sur le journal de
-- caisse à ce stade (phase 1 : planification uniquement).
-- ============================================================

CREATE TABLE IF NOT EXISTS public.purchase_installments (
  id            uuid          DEFAULT gen_random_uuid() PRIMARY KEY,
  purchase_id   uuid          NOT NULL REFERENCES public.purchases(id) ON DELETE CASCADE,
  rank          integer       NOT NULL DEFAULT 1,               -- ordre d'affichage
  label         text,                                            -- jalon : avance, à la livraison, contrôle qualité, mensualité…
  amount        numeric(12, 2) NOT NULL DEFAULT 0 CHECK (amount >= 0),
  payment_mode  text          NOT NULL CHECK (payment_mode IN ('ov_permanent', 'ov_ponctuel', 'cheque', 'versement', 'espece', 'autre')),
  nc            text          NOT NULL DEFAULT 'comptable' CHECK (nc IN ('noir', 'comptable')),
  due_date      date,                                            -- échéance prévue (nullable)
  created_by    uuid          REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at    timestamptz   NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_purchase_installments_purchase ON public.purchase_installments(purchase_id);

COMMENT ON TABLE  public.purchase_installments             IS 'Échéancier prévisionnel de paiement d''un bon de commande (versements planifiés, non décaissés).';
COMMENT ON COLUMN public.purchase_installments.label       IS 'Jalon : avance, à la livraison, contrôle qualité, mensualité…';
COMMENT ON COLUMN public.purchase_installments.nc          IS 'Axe caisse : noir (Caisse sociale) | comptable. Dérivé du mode (versement|espece → noir).';
COMMENT ON COLUMN public.purchase_installments.due_date    IS 'Date/échéance prévue du versement (nullable).';
