-- ============================================================
-- IPISB Connect — L38 : validation N+1 de TOUT décaissement bancaire
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
-- Dépend de : l14 (next_reference), l19/l20 (pending_operations),
--             l21/l36 (cash_journal, journal_mode_key), l37 (registre cheques).
-- ============================================================
--
-- l37 soumettait à validation N+1 les seuls chèques émis. La règle est étendue :
-- TOUT règlement qui fait sortir de l'argent du compte bancaire passe par une
-- approbation avant d'atteindre la table métier ET le journal :
--
--     cheque · versement · virement · ov_permanent · ov_ponctuel
--
-- Non concernés (inchangés) :
--   • les ENCAISSEMENTS (scolarité, recettes) — recevoir n'est pas une décision.
--     Seuls les chèques REÇUS restent inscrits au registre, pour le suivi de
--     leur encaissement ;
--   • les espèces / la caisse sociale — hors circuit bancaire, elles relèvent
--     de la file 'cash_journal_*' du journal de caisse ;
--   • le décaissement émis à la validation d'une DA : l'admin l'a déjà validé
--     à ce moment-là (validation unique, cf. l23).
--
-- Le registre `cheques` devient le registre de TOUTES ces pièces (colonne
-- `mode`), chacune suivie une par une dans son cycle de vie :
--
--   chèque    : en_attente → a_remettre → remis    → encaisse | impaye
--   virement  : en_attente → a_remettre → remis    → encaisse | impaye
--   (lecture) : validation → à exécuter → transmis → exécuté  | rejeté banque
--
-- Les références sont préfixées par nature : CHQ- (chèque), VRS- (versement),
-- VIR- (virement et ordres de virement).

BEGIN;

-- ------------------------------------------------------------
-- 1. Nature de la pièce : colonne `mode`
-- ------------------------------------------------------------
ALTER TABLE cheques ADD COLUMN IF NOT EXISTS mode text NOT NULL DEFAULT 'cheque';

ALTER TABLE cheques DROP CONSTRAINT IF EXISTS cheques_mode_check;
ALTER TABLE cheques
  ADD CONSTRAINT cheques_mode_check
  CHECK (mode IN ('cheque', 'versement', 'virement', 'ov_permanent', 'ov_ponctuel'));

CREATE INDEX IF NOT EXISTS cheques_mode_idx ON cheques (mode, status);

COMMENT ON TABLE  cheques      IS 'Registre des règlements bancaires : un règlement = une ligne, suivie de l''émission à l''encaissement (chèques, versements, virements, OV).';
COMMENT ON COLUMN cheques.mode IS 'Nature de la pièce : cheque | versement | virement | ov_permanent | ov_ponctuel.';
COMMENT ON COLUMN cheques.cheque_number IS 'N° du chèque, ou référence du bordereau de versement / de l''ordre de virement.';

-- ------------------------------------------------------------
-- 2. Référence préfixée selon la nature (CHQ / VRS / VIR)
--    Le DEFAULT de colonne ne peut pas dépendre de `mode` : on le remplace par
--    un trigger BEFORE INSERT, qui ne numérote que si aucune référence n'est
--    fournie.
-- ------------------------------------------------------------
ALTER TABLE cheques ALTER COLUMN reference DROP DEFAULT;

CREATE OR REPLACE FUNCTION cheque_reference_prefix(p_mode text) RETURNS text AS $$
  SELECT CASE p_mode
           WHEN 'versement' THEN 'VRS'
           WHEN 'virement'  THEN 'VIR'
           WHEN 'ov_permanent' THEN 'VIR'
           WHEN 'ov_ponctuel'  THEN 'VIR'
           ELSE 'CHQ'
         END;
$$ LANGUAGE sql IMMUTABLE;

CREATE OR REPLACE FUNCTION cheques_set_reference() RETURNS trigger AS $$
BEGIN
  IF NEW.reference IS NULL THEN
    NEW.reference := next_reference(cheque_reference_prefix(NEW.mode));
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS cheques_set_reference_trg ON cheques;
CREATE TRIGGER cheques_set_reference_trg
  BEFORE INSERT ON cheques
  FOR EACH ROW EXECUTE FUNCTION cheques_set_reference();

-- ------------------------------------------------------------
-- 3. Unicité du numéro : garde-fou propre AUX CHÈQUES
--    Deux versements peuvent porter la même référence de bordereau (ou aucune) ;
--    un même n° de chèque émis, jamais.
-- ------------------------------------------------------------
DROP INDEX IF EXISTS cheques_emis_number_uniq;
CREATE UNIQUE INDEX IF NOT EXISTS cheques_emis_number_uniq
  ON cheques (cheque_number)
  WHERE direction = 'emis' AND mode = 'cheque' AND cheque_number IS NOT NULL
    AND status NOT IN ('annule', 'rejete');

-- ------------------------------------------------------------
-- 4. File de validation : 'cheque_payment' → 'bank_payment'
--    Le payload porte l'opération complète à rejouer après approbation
--    ({"kind": "...", "mode": "...", "data": {...}, "cheque_id": "..."}).
--    'cheque_payment' reste accepté (rows historiques / déploiement en cours).
-- ------------------------------------------------------------
ALTER TABLE pending_operations DROP CONSTRAINT IF EXISTS pending_operations_op_type_check;

ALTER TABLE pending_operations
  ADD CONSTRAINT pending_operations_op_type_check
  CHECK (op_type IN (
    'tuition_payment', 'student_enrollment', 'class_create', 'student_transfer',
    'cash_journal_create', 'cash_journal_edit', 'cash_journal_delete',
    'cheque_payment', 'bank_payment'
  ));

UPDATE pending_operations SET op_type = 'bank_payment' WHERE op_type = 'cheque_payment';

COMMENT ON COLUMN pending_operations.op_type IS
  'tuition_payment | student_enrollment | class_create | student_transfer | cash_journal_create | cash_journal_edit | cash_journal_delete | bank_payment (règlement bancaire : chèque, versement, virement, OV)';

COMMIT;

-- ------------------------------------------------------------
-- 5. Reprise de l'historique : inscrire au registre les décaissements
--    bancaires NON-chèque déjà en base (les chèques l'ont été par l37), ainsi
--    que les sorties bancaires saisies au Journal des comptes — que l37 ne
--    reprenait pas. Créés directement en 'encaisse' : opérations closes,
--    antérieures au circuit, à écarter de la file de validation et des alertes.
--    Idempotent : NOT EXISTS sur (source_type, source_id).
-- ------------------------------------------------------------

-- 5.a Paiements d'achat (virement / versement / OV)
INSERT INTO cheques (mode, direction, status, cheque_number, amount, counterparty, label,
                     issue_date, cashed_date, source_type, source_id, created_by, created_at)
SELECT journal_mode_key(p.payment_method), 'emis', 'encaisse', p.reference, p.amount,
       COALESCE(s.company_name, 'Fournisseur'),
       'Paiement achat ' || COALESCE(pu.purchase_number, ''),
       p.payment_date, p.payment_date, 'purchase_payment', p.id, p.created_by, p.created_at
  FROM purchase_payments p
  LEFT JOIN purchases pu ON pu.id = p.purchase_id
  LEFT JOIN suppliers  s ON s.id  = pu.supplier_id
 WHERE journal_mode_key(p.payment_method) IN ('versement', 'virement', 'ov_permanent', 'ov_ponctuel')
   AND NOT EXISTS (SELECT 1 FROM cheques c
                    WHERE c.source_type = 'purchase_payment' AND c.source_id = p.id);

-- 5.b Notes de caisse
INSERT INTO cheques (mode, direction, status, cheque_number, amount, counterparty, label,
                     issue_date, cashed_date, source_type, source_id, created_by, created_at)
SELECT journal_mode_key(n.payment_method), 'emis', 'encaisse', n.payment_reference, n.total,
       COALESCE(n.beneficiary_name, 'Bénéficiaire'),
       'Note de caisse ' || COALESCE(n.reference, ''),
       COALESCE(n.payment_date, n.note_date), n.payment_date, 'cash_note', n.id, n.created_by, n.created_at
  FROM cash_notes n
 WHERE journal_mode_key(n.payment_method) IN ('versement', 'virement', 'ov_permanent', 'ov_ponctuel')
   AND NOT EXISTS (SELECT 1 FROM cheques c
                    WHERE c.source_type = 'cash_note' AND c.source_id = n.id);

-- 5.c Frais de mission
INSERT INTO cheques (mode, direction, status, cheque_number, amount, counterparty, label,
                     issue_date, cashed_date, source_type, source_id, created_by, created_at)
SELECT journal_mode_key(n.payment_method), 'emis', 'encaisse', n.payment_reference, n.total,
       COALESCE(n.beneficiary_name, 'Bénéficiaire'),
       'Frais de mission ' || COALESCE(n.reference, ''),
       COALESCE(n.payment_date, n.note_date), n.payment_date, 'mission_note', n.id, n.created_by, n.created_at
  FROM mission_notes n
 WHERE journal_mode_key(n.payment_method) IN ('versement', 'virement', 'ov_permanent', 'ov_ponctuel')
   AND NOT EXISTS (SELECT 1 FROM cheques c
                    WHERE c.source_type = 'mission_note' AND c.source_id = n.id);

-- 5.d Dépenses
INSERT INTO cheques (mode, direction, status, amount, counterparty, label,
                     issue_date, cashed_date, source_type, source_id, created_by, created_at)
SELECT journal_mode_key(e.payment_method), 'emis', 'encaisse', e.amount,
       COALESCE(s.company_name, 'Bénéficiaire'), 'Dépense — ' || e.title,
       e.expense_date, e.expense_date, 'expense', e.id, e.created_by, e.created_at
  FROM expenses e
  LEFT JOIN suppliers s ON s.id = e.supplier_id
 WHERE journal_mode_key(e.payment_method) IN ('versement', 'virement', 'ov_permanent', 'ov_ponctuel')
   AND NOT EXISTS (SELECT 1 FROM cheques c
                    WHERE c.source_type = 'expense' AND c.source_id = e.id);

-- 5.e Sorties saisies au Journal des comptes (tous modes bancaires, chèque inclus :
--     l37 ne reprenait pas cette source).
--     L'index d'unicité des n° de chèque émis s'applique aussi à ces lignes : si
--     l'historique porte deux fois le même numéro (saisie approximative), on
--     garde la ligne mais on laisse son numéro à NULL plutôt que de faire échouer
--     toute la reprise. Le montant, la date et l'objet, eux, sont conservés.
INSERT INTO cheques (mode, direction, status, cheque_number, amount, counterparty, label,
                     issue_date, cashed_date, source_type, source_id, journal_entry_id,
                     created_by, created_at)
SELECT j.payment_mode, 'emis', 'encaisse',
       CASE
         WHEN j.payment_mode = 'cheque' AND j.payment_ref IS NOT NULL
              AND (j.rn > 1
                   OR EXISTS (SELECT 1 FROM cheques c2
                               WHERE c2.direction = 'emis' AND c2.mode = 'cheque'
                                 AND c2.cheque_number = j.payment_ref
                                 AND c2.status NOT IN ('annule', 'rejete')))
           THEN NULL
         ELSE j.payment_ref
       END,
       j.amount, j.prestataire, j.action, j.entry_date, j.entry_date,
       'cash_journal', j.id, j.id, j.created_by, j.created_at
  FROM (
    SELECT j.*,
           row_number() OVER (
             PARTITION BY CASE WHEN j.payment_mode = 'cheque' THEN j.payment_ref END
             ORDER BY j.entry_date, j.created_at
           ) AS rn
      FROM cash_journal j
     WHERE j.type = 'sortie'
       AND j.payment_mode IN ('cheque', 'versement', 'virement', 'ov_permanent', 'ov_ponctuel')
       AND NOT EXISTS (SELECT 1 FROM cheques c
                        WHERE c.source_type = 'cash_journal' AND c.source_id = j.id)
  ) j;

-- Rattacher chaque pièce reprise à sa ligne du Journal des comptes.
UPDATE cheques c SET journal_entry_id = j.id
  FROM cash_journal j
 WHERE c.journal_entry_id IS NULL
   AND j.source_type = c.source_type AND j.source_id = c.source_id;

-- ------------------------------------------------------------
-- 6. Contrôle (à lire dans le résultat du SQL Editor)
-- ------------------------------------------------------------
SELECT mode, direction, status, count(*) AS nb, sum(amount) AS montant
  FROM cheques
 GROUP BY mode, direction, status
 ORDER BY mode, direction, status;
