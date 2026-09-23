-- ============================================================
-- IPISB Connect — REGISTRE DES CHÈQUES + validation N+1 des chèques émis
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
-- Dépend de : l14 (next_reference), l19/l20 (pending_operations), l21/l36 (cash_journal).
-- ============================================================
--
-- Objectif :
--   1. Un registre dédié `cheques` — un chèque = une ligne, suivie de bout en
--      bout (émission → remise → encaissement / impayé), quelle que soit
--      l'opération qui l'a produit (paiement d'achat, note de caisse, frais de
--      mission, dépense, scolarité, recette, saisie manuelle au journal).
--   2. Tout chèque ÉMIS passe par une validation N+1 : l'opération est mise en
--      attente dans `pending_operations` (op_type = 'cheque_payment') et
--      n'atteint NI la table métier NI le journal avant approbation admin.
--      Les chèques REÇUS (scolarité, recettes) sont seulement inscrits au
--      registre : un encaissement n'est pas une décision à valider.
--
-- Cycle de vie (colonne `status`) :
--     en_attente   → chèque émis en attente de validation N+1
--     rejete       → validation refusée (l'opération n'a pas eu lieu)
--     a_remettre   → validé, chèque à signer / remettre au bénéficiaire
--     remis        → remis au bénéficiaire (émis) / déposé en banque (reçu)
--     encaisse     → débité / crédité en banque  ← état terminal normal
--     impaye       → rejeté par la banque (provision, opposition…)
--     annule       → chèque annulé (erreur d'établissement, perte)
--
--   Les chèques reçus naissent directement en 'remis' (on détient le chèque) ;
--   les chèques émis naissent en 'en_attente'.

BEGIN;

-- ------------------------------------------------------------
-- 1. Registre des chèques
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cheques (
  id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  reference        text        DEFAULT next_reference('CHQ'),   -- CHQ-AAAA-NNNN (auto)

  direction        text        NOT NULL
                                 CHECK (direction IN ('emis', 'recu')),
  status           text        NOT NULL DEFAULT 'en_attente'
                                 CHECK (status IN ('en_attente', 'rejete', 'a_remettre',
                                                   'remis', 'encaisse', 'impaye', 'annule')),

  cheque_number    text,                        -- n° figurant sur le chèque
  bank             text,                        -- banque tirée / banque du tireur
  amount           numeric     NOT NULL DEFAULT 0,
  counterparty     text,                        -- bénéficiaire (émis) | tireur (reçu)
  label            text,                        -- objet du chèque (motif)

  issue_date       date        NOT NULL DEFAULT CURRENT_DATE,   -- date d'établissement
  due_date         date,                        -- échéance / date de remise convenue
  cashed_date      date,                        -- date d'encaissement (ou d'impayé)

  -- Opération d'origine : le chèque reste rattaché à ce qui l'a produit.
  source_type      text        NOT NULL DEFAULT 'manual'
                                 CHECK (source_type IN ('manual', 'purchase_payment', 'cash_note',
                                                        'mission_note', 'expense', 'tuition_payment',
                                                        'revenue', 'cash_journal')),
  source_id        uuid,                        -- id de la ligne métier (après validation)
  pending_op_id    uuid        REFERENCES pending_operations(id) ON DELETE SET NULL,
  journal_entry_id uuid        REFERENCES cash_journal(id) ON DELETE SET NULL,

  -- Validation N+1 (chèques émis)
  approved_by      uuid,
  approved_at      timestamptz,
  review_comment   text,                        -- motif du rejet / observation

  comment          text,
  created_by       uuid,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz
);

-- Références manquantes (table préexistante d'une exécution partielle).
UPDATE cheques SET reference = next_reference('CHQ', EXTRACT(year FROM created_at)::int)
 WHERE reference IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS cheques_reference_uniq   ON cheques (reference);
CREATE        INDEX IF NOT EXISTS cheques_status_idx       ON cheques (status);
CREATE        INDEX IF NOT EXISTS cheques_direction_due_idx ON cheques (direction, due_date);
CREATE        INDEX IF NOT EXISTS cheques_source_idx       ON cheques (source_type, source_id);
CREATE        INDEX IF NOT EXISTS cheques_number_idx       ON cheques (cheque_number);

-- Garde-fou métier : un même n° de chèque ÉMIS ne peut pas servir deux fois.
-- Les chèques annulés / rejetés libèrent le numéro ; les chèques sans numéro
-- saisi (NULL) ne sont pas contraints.
CREATE UNIQUE INDEX IF NOT EXISTS cheques_emis_number_uniq
  ON cheques (cheque_number)
  WHERE direction = 'emis' AND cheque_number IS NOT NULL
    AND status NOT IN ('annule', 'rejete');

ALTER TABLE cheques ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS cheques_service_all ON cheques;
CREATE POLICY cheques_service_all
  ON cheques FOR ALL
  TO service_role
  USING (true) WITH CHECK (true);

COMMENT ON TABLE  cheques                  IS 'Registre des chèques : un chèque = une ligne, suivie de l''émission à l''encaissement.';
COMMENT ON COLUMN cheques.direction        IS 'emis = chèque établi par l''école (sortie) | recu = chèque encaissé par l''école (entrée).';
COMMENT ON COLUMN cheques.status           IS 'en_attente (validation N+1) | rejete | a_remettre | remis | encaisse | impaye | annule.';
COMMENT ON COLUMN cheques.counterparty     IS 'Bénéficiaire du chèque (émis) ou tireur / émetteur (reçu).';
COMMENT ON COLUMN cheques.due_date         IS 'Échéance convenue : date de remise/présentation attendue. Sert au tableau des chèques en retard.';
COMMENT ON COLUMN cheques.source_type      IS 'Opération d''origine : manual | purchase_payment | cash_note | mission_note | expense | tuition_payment | revenue | cash_journal.';
COMMENT ON COLUMN cheques.pending_op_id    IS 'Opération en attente (pending_operations) qui sera exécutée à la validation du chèque.';
COMMENT ON COLUMN cheques.journal_entry_id IS 'Ligne du Journal des comptes créée à la validation (cash_journal).';

-- ------------------------------------------------------------
-- 2. Nouveau type d'opération en validation N+1 : 'cheque_payment'
--    Le payload porte l'opération complète à rejouer après approbation
--    ({"kind": "...", "data": {...}, "cheque_id": "..."}).
-- ------------------------------------------------------------
ALTER TABLE pending_operations DROP CONSTRAINT IF EXISTS pending_operations_op_type_check;

ALTER TABLE pending_operations
  ADD CONSTRAINT pending_operations_op_type_check
  CHECK (op_type IN (
    'tuition_payment', 'student_enrollment', 'class_create', 'student_transfer',
    'cash_journal_create', 'cash_journal_edit', 'cash_journal_delete',
    'cheque_payment'
  ));

COMMENT ON COLUMN pending_operations.op_type IS
  'tuition_payment | student_enrollment | class_create | student_transfer | cash_journal_create | cash_journal_edit | cash_journal_delete | cheque_payment';

COMMIT;

-- ------------------------------------------------------------
-- 3. Reprise de l'historique : inscrire au registre les chèques déjà passés
--    en base. Ils sont créés directement en 'encaisse' (opérations closes,
--    antérieures à la mise en place du circuit) pour ne pas polluer la file
--    de validation ni les alertes d'échéance.
--    Idempotent : NOT EXISTS sur (source_type, source_id).
-- ------------------------------------------------------------

-- 3.a Paiements d'achat réglés par chèque (chèques émis)
INSERT INTO cheques (direction, status, cheque_number, amount, counterparty, label,
                     issue_date, cashed_date, source_type, source_id, created_by, created_at)
SELECT 'emis', 'encaisse', p.reference, p.amount,
       COALESCE(s.company_name, 'Fournisseur'),
       'Paiement achat ' || COALESCE(pu.purchase_number, ''),
       p.payment_date, p.payment_date, 'purchase_payment', p.id, p.created_by, p.created_at
  FROM purchase_payments p
  LEFT JOIN purchases pu ON pu.id = p.purchase_id
  LEFT JOIN suppliers  s ON s.id  = pu.supplier_id
 WHERE journal_mode_key(p.payment_method) = 'cheque'
   AND NOT EXISTS (SELECT 1 FROM cheques c
                    WHERE c.source_type = 'purchase_payment' AND c.source_id = p.id);

-- 3.b Notes de caisse payées par chèque (chèques émis)
INSERT INTO cheques (direction, status, cheque_number, amount, counterparty, label,
                     issue_date, cashed_date, source_type, source_id, created_by, created_at)
SELECT 'emis', 'encaisse', n.payment_reference, n.total,
       COALESCE(n.beneficiary_name, 'Bénéficiaire'),
       'Note de caisse ' || COALESCE(n.reference, ''),
       COALESCE(n.payment_date, n.note_date), n.payment_date, 'cash_note', n.id, n.created_by, n.created_at
  FROM cash_notes n
 WHERE journal_mode_key(n.payment_method) = 'cheque'
   AND NOT EXISTS (SELECT 1 FROM cheques c
                    WHERE c.source_type = 'cash_note' AND c.source_id = n.id);

-- 3.c Notes de frais de mission payées par chèque (chèques émis)
INSERT INTO cheques (direction, status, cheque_number, amount, counterparty, label,
                     issue_date, cashed_date, source_type, source_id, created_by, created_at)
SELECT 'emis', 'encaisse', n.payment_reference, n.total,
       COALESCE(n.beneficiary_name, 'Bénéficiaire'),
       'Frais de mission ' || COALESCE(n.reference, ''),
       COALESCE(n.payment_date, n.note_date), n.payment_date, 'mission_note', n.id, n.created_by, n.created_at
  FROM mission_notes n
 WHERE journal_mode_key(n.payment_method) = 'cheque'
   AND NOT EXISTS (SELECT 1 FROM cheques c
                    WHERE c.source_type = 'mission_note' AND c.source_id = n.id);

-- 3.d Dépenses réglées par chèque (chèques émis)
INSERT INTO cheques (direction, status, amount, counterparty, label,
                     issue_date, cashed_date, source_type, source_id, created_by, created_at)
SELECT 'emis', 'encaisse', e.amount,
       COALESCE(s.company_name, 'Bénéficiaire'), 'Dépense — ' || e.title,
       e.expense_date, e.expense_date, 'expense', e.id, e.created_by, e.created_at
  FROM expenses e
  LEFT JOIN suppliers s ON s.id = e.supplier_id
 WHERE journal_mode_key(e.payment_method) = 'cheque'
   AND NOT EXISTS (SELECT 1 FROM cheques c
                    WHERE c.source_type = 'expense' AND c.source_id = e.id);

-- 3.e Scolarité encaissée par chèque (chèques reçus)
INSERT INTO cheques (direction, status, amount, counterparty, label,
                     issue_date, cashed_date, source_type, source_id, created_by, created_at)
-- NB : tuition_payments n'a pas de `payment_date` — la date effective est `paid_on`.
SELECT 'recu', 'encaisse', t.amount,
       COALESCE(pr.full_name, pr.email, 'Élève'),
       'Scolarité ' || COALESCE(t.reference, ''),
       COALESCE(t.paid_on, t.created_at::date), t.paid_on, 'tuition_payment', t.id, t.created_by, t.created_at
  FROM tuition_payments t
  LEFT JOIN profiles pr ON pr.id = t.student_id
 WHERE journal_mode_key(t.method) = 'cheque'
   AND NOT EXISTS (SELECT 1 FROM cheques c
                    WHERE c.source_type = 'tuition_payment' AND c.source_id = t.id);

-- 3.f Recettes encaissées par chèque (chèques reçus)
INSERT INTO cheques (direction, status, amount, counterparty, label,
                     issue_date, cashed_date, source_type, source_id, created_by, created_at)
SELECT 'recu', 'encaisse', r.total_incl_vat, COALESCE(r.title, 'Tiers'),
       'Recette ' || COALESCE(r.revenue_number, ''),
       r.revenue_date, r.revenue_date, 'revenue', r.id, r.created_by, r.created_at
  FROM revenues r
 WHERE journal_mode_key(r.payment_method) = 'cheque'
   AND NOT EXISTS (SELECT 1 FROM cheques c
                    WHERE c.source_type = 'revenue' AND c.source_id = r.id);

-- Rattacher chaque chèque repris à sa ligne du Journal des comptes.
UPDATE cheques c SET journal_entry_id = j.id
  FROM cash_journal j
 WHERE c.journal_entry_id IS NULL
   AND j.source_type = c.source_type AND j.source_id = c.source_id;

-- ------------------------------------------------------------
-- 4. Contrôle (à lire dans le résultat du SQL Editor)
-- ------------------------------------------------------------
SELECT direction, status, count(*) AS nb, sum(amount) AS montant
  FROM cheques
 GROUP BY direction, status
 ORDER BY direction, status;
