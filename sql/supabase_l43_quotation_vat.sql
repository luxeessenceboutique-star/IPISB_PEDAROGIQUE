-- L43 — TVA sur les devis (consultation fournisseurs / demandes d'achat)
-- Le montant du devis (`amount`) reste le montant HORS TAXES saisi par
-- l'utilisateur. `vat_percent` est le taux de TVA renseigné par l'utilisateur
-- (20% par défaut). `total_incl_vat` est calculé automatiquement — TTC sur la
-- base HT + livraison éventuelle (payante et non comprise dans `amount`),
-- cohérent avec quoteTrueTotal() côté frontend et avec le même pattern déjà
-- utilisé sur purchases/expenses/revenues/invoices (colonne générée STORED).

alter table public.quotations
  add column if not exists vat_percent numeric(5, 2) not null default 20;

alter table public.quotations
  add column if not exists total_incl_vat numeric GENERATED ALWAYS AS (
    (amount + CASE WHEN delivery_required AND NOT delivery_included THEN COALESCE(delivery_cost, 0) ELSE 0 END)
    * (1 + vat_percent / 100)
  ) STORED;

comment on column public.quotations.vat_percent is 'Taux de TVA (%) saisi par l''utilisateur — 20% par défaut.';
comment on column public.quotations.total_incl_vat is 'Montant TTC calculé : (amount + livraison éventuelle) × (1 + vat_percent/100).';
