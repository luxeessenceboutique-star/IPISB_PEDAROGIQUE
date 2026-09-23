-- L31 — Livraison sur les devis : « incluse dans le total » + coût optionnel
-- • delivery_included : la livraison est-elle DÉJÀ comprise dans `amount` ?
--     - true  → le total du devis inclut la livraison (on n'ajoute rien).
--     - false → la livraison s'ajoute au montant (affichage décomposé « 4800 + 50 »).
-- • delivery_cost devient NULLABLE : NULL = prix de livraison inconnu / à préciser
--   (0 = livraison gratuite reste distinct de NULL = inconnu).
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.

alter table public.quotations
  add column if not exists delivery_included boolean not null default false;

alter table public.quotations
  alter column delivery_cost drop not null;

comment on column public.quotations.delivery_included is
  'La livraison est-elle déjà comprise dans le montant (amount) du devis ? Sinon elle s''ajoute au total.';
comment on column public.quotations.delivery_cost is
  'Coût de la livraison. 0 = gratuite, NULL = inconnu / à préciser.';
