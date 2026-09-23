-- L26 — Livraison sur les devis
-- Ajoute l'indication de livraison exigée et son coût (0 = gratuite) à chaque devis.
-- Ces informations sont reportées dans le bon de commande.

alter table public.quotations
  add column if not exists delivery_required boolean not null default false,
  add column if not exists delivery_cost numeric(12, 2) not null default 0;

comment on column public.quotations.delivery_required is 'Le devis exige-t-il une livraison ?';
comment on column public.quotations.delivery_cost is 'Coût de la livraison (0 = gratuite).';
