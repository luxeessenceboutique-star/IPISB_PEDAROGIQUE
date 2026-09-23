-- ============================================================
-- IPISB Connect — L40 : date de remise (« déposé le ») au registre
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
-- Dépend de : l37 (table cheques), l38 (colonne mode).
-- ============================================================
--
-- Le registre datait l'établissement de la pièce (issue_date), son échéance
-- (due_date) et son encaissement (cashed_date) — mais pas sa REMISE. Or c'est
-- la date que la banque et le contrôle réclament : le jour où le chèque a été
-- déposé, où l'ordre de virement a été transmis. Entre « remis » et
-- « encaissé » il peut s'écouler des semaines, et le passage au statut 'remis'
-- ne laissait jusqu'ici aucune trace datée.
--
-- Le tableau d'export des règlements bancaires en fait une colonne à part
-- entière (« Déposé le »), à côté de « Encaissé le ».

ALTER TABLE cheques ADD COLUMN IF NOT EXISTS remitted_date date;

COMMENT ON COLUMN cheques.remitted_date IS
  'Date de remise à la banque (chèque) ou de transmission de l''ordre (virement, OV, versement).';

-- Rattrapage : les pièces actuellement au statut 'remis' ont été remises le jour
-- de leur dernier changement de statut — c'est précisément ce que updated_at
-- enregistre pour elles. Les pièces déjà encaissées ne sont PAS rattrapées :
-- leur updated_at porte la date d'encaissement, pas celle du dépôt ; inventer
-- une date de remise serait pire que la laisser vide.
UPDATE cheques
   SET remitted_date = COALESCE(updated_at::date, issue_date)
 WHERE remitted_date IS NULL
   AND status = 'remis';

CREATE INDEX IF NOT EXISTS idx_cheques_remitted ON cheques(remitted_date);

-- Contrôle : répartition des pièces selon ce qui est daté.
SELECT status,
       count(*)                                        AS nb,
       count(*) FILTER (WHERE remitted_date IS NOT NULL) AS avec_date_de_remise,
       count(*) FILTER (WHERE cashed_date   IS NOT NULL) AS avec_date_encaissement
  FROM cheques
 GROUP BY status
 ORDER BY status;
