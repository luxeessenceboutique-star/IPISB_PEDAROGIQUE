-- L44 — Retrait de l'axe « noir » (caisse sociale hors-comptes)
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
--
-- Contexte : la distinction nc='noir' (caisse sociale, non comptabilisée) vs
-- nc='comptable' est retirée du produit — tous les modules (Journal de
-- caisse, Notes de caisse, Frais de mission, Demandes d'achat/échéancier)
-- rattachent désormais systématiquement leurs opérations au journal
-- comptable (le code applicatif ne pose plus jamais 'noir' en écriture).
-- Cette migration met à jour les lignes existantes en conséquence, pour que
-- les données historiques reflètent la même règle.

update public.cash_journal        set nc = 'comptable' where nc = 'noir';
update public.cash_notes          set nc = 'comptable' where nc = 'noir';
update public.mission_notes       set nc = 'comptable' where nc = 'noir';
update public.purchase_installments set nc = 'comptable' where nc = 'noir';

-- purchase_requests.nc existe aussi (migration l21) mais n'est plus lu ni
-- écrit par le code applicatif (l'échéancier vit sur purchase_installments) ;
-- alignée par cohérence.
update public.purchase_requests   set nc = 'comptable' where nc = 'noir';
