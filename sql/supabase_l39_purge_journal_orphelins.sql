-- ============================================================
-- IPISB Connect — L39 : purge des écritures orphelines (soldes faux)
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
-- Dépend de : l21/l22/l33/l36 (cash_journal), l37/l38 (registre cheques).
-- ============================================================
--
-- Jusqu'ici, supprimer une opération (paiement de scolarité, recette, dépense,
-- paiement d'achat) laissait au journal la ligne créée à son enregistrement :
-- le solde continuait d'inclure un encaissement — ou un décaissement — qui
-- n'existe plus. Le code retire désormais cette ligne à la suppression ; ce
-- script rattrape celles déjà en base.
--
-- Ne sont supprimées QUE les lignes automatiques dont l'opération source a
-- disparu. Les saisies manuelles (source_type = 'manual') ne sont jamais
-- touchées : elles n'ont pas d'origine métier, ce sont elles-mêmes l'origine.
--
-- TOUT tient dans UNE SEULE instruction, volontairement : le SQL Editor de
-- Supabase exécute chaque requête sur une connexion poolée, si bien qu'une
-- table temporaire — ou un BEGIN/COMMIT — ne survit pas d'une instruction à la
-- suivante. Une instruction unique est de toute façon atomique : soit les trois
-- purges passent, soit aucune.
--
-- Le tableau affiché à la fin détaille ce qui a été purgé (bloc « purge »), puis
-- les soldes qui en résultent (bloc « solde après purge »), à comparer à la
-- caisse réelle. Aucune ligne « purge » = rien à rattraper.

WITH
-- ------------------------------------------------------------
-- 1. Journal (caisse + comptes) : lignes sans opération source
-- ------------------------------------------------------------
orphelins_journal AS (
  SELECT j.id
    FROM cash_journal j
   WHERE j.source_id IS NOT NULL
     AND j.source_type <> 'manual'
     AND (
          (j.source_type = 'tuition_payment'  AND NOT EXISTS (SELECT 1 FROM tuition_payments  t WHERE t.id = j.source_id))
       OR (j.source_type = 'revenue'          AND NOT EXISTS (SELECT 1 FROM revenues          t WHERE t.id = j.source_id))
       OR (j.source_type = 'expense'          AND NOT EXISTS (SELECT 1 FROM expenses          t WHERE t.id = j.source_id))
       OR (j.source_type = 'purchase_payment' AND NOT EXISTS (SELECT 1 FROM purchase_payments t WHERE t.id = j.source_id))
       OR (j.source_type = 'cash_note'        AND NOT EXISTS (SELECT 1 FROM cash_notes        t WHERE t.id = j.source_id))
       OR (j.source_type = 'mission_note'     AND NOT EXISTS (SELECT 1 FROM mission_notes     t WHERE t.id = j.source_id))
       OR (j.source_type = 'purchase_request' AND NOT EXISTS (SELECT 1 FROM purchase_requests t WHERE t.id = j.source_id))
     )
),

-- ------------------------------------------------------------
-- 2. Registre des règlements : pièces sans opération source
--    (un chèque dont le paiement a été supprimé resterait « à encaisser »
--    dans les alertes et les statistiques.)
-- ------------------------------------------------------------
orphelins_registre AS (
  SELECT c.id
    FROM cheques c
   WHERE c.source_id IS NOT NULL
     AND c.source_type <> 'manual'
     AND (
          (c.source_type = 'tuition_payment'  AND NOT EXISTS (SELECT 1 FROM tuition_payments  t WHERE t.id = c.source_id))
       OR (c.source_type = 'revenue'          AND NOT EXISTS (SELECT 1 FROM revenues          t WHERE t.id = c.source_id))
       OR (c.source_type = 'expense'          AND NOT EXISTS (SELECT 1 FROM expenses          t WHERE t.id = c.source_id))
       OR (c.source_type = 'purchase_payment' AND NOT EXISTS (SELECT 1 FROM purchase_payments t WHERE t.id = c.source_id))
       OR (c.source_type = 'cash_note'        AND NOT EXISTS (SELECT 1 FROM cash_notes        t WHERE t.id = c.source_id))
       OR (c.source_type = 'mission_note'     AND NOT EXISTS (SELECT 1 FROM mission_notes     t WHERE t.id = c.source_id))
       OR (c.source_type = 'cash_journal'     AND NOT EXISTS (SELECT 1 FROM cash_journal      t WHERE t.id = c.source_id))
     )
),

del_journal AS (
  DELETE FROM cash_journal j
   USING orphelins_journal o
   WHERE j.id = o.id
  RETURNING j.channel, j.source_type, j.type, j.amount
),

-- Pièces jointes des lignes de journal supprimées, plus celles déjà orphelines.
-- On vise explicitement `orphelins_journal` : dans une instruction unique, les
-- suppressions ci-dessus ne sont pas encore visibles pour un NOT EXISTS.
-- (Le fichier reste dans le bucket : seule la référence part — un objet de
-- storage sans ligne n'est plus atteignable par l'application.)
del_pieces AS (
  DELETE FROM accounting_attachments a
   WHERE a.entity_type = 'cash_journal'
     AND (
          a.entity_id IN (SELECT id FROM orphelins_journal)
       OR NOT EXISTS (SELECT 1 FROM cash_journal j WHERE j.id = a.entity_id)
     )
  RETURNING a.id
),

del_registre AS (
  DELETE FROM cheques c
   USING orphelins_registre o
   WHERE c.id = o.id
  RETURNING c.mode, c.source_type, c.direction, c.amount
),

-- Soldes tels qu'ils seront APRÈS la purge : les lignes retirées sont exclues
-- ici plutôt que relues, pour la même raison de visibilité.
soldes AS (
  SELECT COALESCE(channel, 'caisse') AS registre,
         count(*) AS nb,
         sum(CASE WHEN type = 'entree' THEN amount ELSE -amount END) AS solde
    FROM cash_journal
   WHERE id NOT IN (SELECT id FROM orphelins_journal)
   GROUP BY 1
)

-- ------------------------------------------------------------
-- 3. Compte rendu
-- ------------------------------------------------------------
SELECT 'purge' AS bloc, COALESCE(channel, 'caisse') AS registre,
       source_type AS origine, type AS sens, count(*) AS nb, sum(amount) AS montant
  FROM del_journal
 GROUP BY 1, 2, 3, 4
UNION ALL
SELECT 'purge', 'pièces jointes', 'cash_journal', '—', count(*), NULL::numeric
  FROM del_pieces
HAVING count(*) > 0
UNION ALL
SELECT 'purge', 'registre — ' || mode, source_type, direction, count(*), sum(amount)
  FROM del_registre
 GROUP BY 1, 2, 3, 4
UNION ALL
SELECT 'solde après purge', registre, '—', 'entrées − sorties', nb, solde
  FROM soldes
 ORDER BY 1, 2, 3, 4;
