-- ============================================================
-- IPISB Connect — L30 : Fusion des modes 'versement' + 'espece' → 'caisse_sociale'
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
--
-- Périmètre : CHAÎNE ACHATS uniquement (DA, commande, paiements d'achat,
-- échéancier). Ces deux modes étaient tous deux classés « caisse sociale »
-- ('noir') : on les fusionne en un seul mode 'caisse_sociale'.
--
-- NON concernés (sémantique différente, laissés tels quels) :
--   • Recettes (revenues.payment_method) : 'versement' = versement BANCAIRE,
--     'espece' = espèces — distinction utilisée par l'export « Versements bancaires ».
--   • Dépenses (expenses.payment_method) et Scolarité (tuition_payments.method) :
--     champs libres, listes propres.
--
-- ORDRE IMPORTANT : on DROP les anciennes contraintes CHECK AVANT de faire
-- l'UPDATE des données. Sinon l'ancienne contrainte (qui ne connaît pas encore
-- 'caisse_sociale') fait échouer l'UPDATE (ERROR 23514). DROP → UPDATE → ADD.
-- ============================================================

BEGIN;

-- 1) Suppression des anciennes contraintes CHECK (drop robuste : quel que soit
--    le nom auto-généré). purchases.payment_method n'a pas de contrainte (l4).
DO $$
DECLARE c text;
BEGIN
  -- purchase_requests.payment_mode
  FOR c IN SELECT conname FROM pg_constraint
           WHERE conrelid = 'public.purchase_requests'::regclass AND contype = 'c'
             AND pg_get_constraintdef(oid) ILIKE '%payment_mode%'
  LOOP EXECUTE format('ALTER TABLE public.purchase_requests DROP CONSTRAINT %I', c); END LOOP;

  -- purchase_payments.payment_method
  FOR c IN SELECT conname FROM pg_constraint
           WHERE conrelid = 'public.purchase_payments'::regclass AND contype = 'c'
             AND pg_get_constraintdef(oid) ILIKE '%payment_method%'
  LOOP EXECUTE format('ALTER TABLE public.purchase_payments DROP CONSTRAINT %I', c); END LOOP;

  -- purchase_installments.payment_mode
  FOR c IN SELECT conname FROM pg_constraint
           WHERE conrelid = 'public.purchase_installments'::regclass AND contype = 'c'
             AND pg_get_constraintdef(oid) ILIKE '%payment_mode%'
  LOOP EXECUTE format('ALTER TABLE public.purchase_installments DROP CONSTRAINT %I', c); END LOOP;
END $$;

-- 2) Reprise des données existantes (chaîne achats). Plus aucune contrainte ne bloque.
UPDATE public.purchase_requests    SET payment_mode   = 'caisse_sociale' WHERE payment_mode   IN ('versement', 'espece');
UPDATE public.purchases             SET payment_method = 'caisse_sociale' WHERE payment_method IN ('versement', 'espece');
UPDATE public.purchase_payments     SET payment_method = 'caisse_sociale' WHERE payment_method IN ('versement', 'espece');
UPDATE public.purchase_installments SET payment_mode   = 'caisse_sociale' WHERE payment_mode   IN ('versement', 'espece');

-- 3) Réajout des contraintes CHECK avec le nouvel ensemble (valide les données déjà migrées).
ALTER TABLE public.purchase_requests
  ADD CONSTRAINT purchase_requests_payment_mode_check
  CHECK (payment_mode IN ('ov_permanent', 'ov_ponctuel', 'cheque', 'caisse_sociale'));

ALTER TABLE public.purchase_payments
  ADD CONSTRAINT purchase_payments_payment_method_check
  CHECK (payment_method IN ('ov_permanent', 'ov_ponctuel', 'cheque', 'caisse_sociale', 'autre'));

ALTER TABLE public.purchase_installments
  ADD CONSTRAINT purchase_installments_payment_mode_check
  CHECK (payment_mode IN ('ov_permanent', 'ov_ponctuel', 'cheque', 'caisse_sociale', 'autre'));

COMMIT;
