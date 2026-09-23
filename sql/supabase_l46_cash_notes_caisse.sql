-- L46 — Caisse visée sur les notes de caisse (choisie à la création)
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
--
-- Contexte : la note de caisse déclare désormais, dès sa création, la caisse
-- physique visée pour son règlement (Caisse comptable / Caisse sociale) — au
-- lieu de ne se décider qu'à l'exécution du paiement (colonne payment_method,
-- inchangée, reste modifiable à ce moment-là). Les deux caisses restent
-- comptabilisées : nc vaut toujours 'comptable', quelle que soit la caisse
-- choisie — ceci n'est pas une réintroduction du hors-comptes.
--
-- « caisse_sociale » = nom de clé historique = libellé « Caisse comptable » ;
-- « caisse_secondaire » = libellé « Caisse sociale ». Mêmes clés que
-- payment_method (accounting_cash_notes.py / accounting_cash_journal.py).

ALTER TABLE public.cash_notes
  ADD COLUMN IF NOT EXISTS caisse text NOT NULL DEFAULT 'caisse_sociale'
  CHECK (caisse IN ('caisse_sociale', 'caisse_secondaire'));

COMMENT ON COLUMN public.cash_notes.caisse IS
  'Caisse physique visée par l''avance, choisie à la création : caisse_sociale = Caisse comptable (nom de clé historique), caisse_secondaire = Caisse sociale. Les deux sont comptabilisées (nc reste toujours ''comptable'').';
