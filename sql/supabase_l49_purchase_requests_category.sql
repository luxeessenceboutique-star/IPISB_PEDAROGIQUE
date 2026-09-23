-- L49 — Catégorie budgétaire sur les demandes d'achat (DA)
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
--
-- Contexte : la DA n'avait qu'un classement générique (asset_category :
-- Consommable/Équipement/Locaux/Service). Le sélecteur « Catégorie » du
-- formulaire de création utilise désormais la MÊME liste que l'onglet
-- Dépenses (accounting_categories), pour que la catégorie choisie dès la
-- DA soit cohérente avec le suivi budgétaire. asset_category est conservé
-- (colonne existante, non supprimée) pour les DA déjà créées.

ALTER TABLE public.purchase_requests
  ADD COLUMN IF NOT EXISTS category_id uuid REFERENCES public.accounting_categories(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_purchase_requests_category ON public.purchase_requests(category_id);

COMMENT ON COLUMN public.purchase_requests.category_id IS
  'Catégorie budgétaire (accounting_categories) — même liste que Comptabilité > Dépenses, choisie à la création de la DA.';
