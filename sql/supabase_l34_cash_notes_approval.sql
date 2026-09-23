-- ============================================================
-- IPISB Connect — Avance de note de caisse : approbation N+1 + exécution paiement
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
-- Dépend de : cash_notes (l32), nc (l33).
-- ============================================================
--
-- Objectif :
--   Transformer la note de caisse en une AVANCE soumise à un circuit :
--     1. Saisie        → status 'pending'   (en attente d'approbation N+1)
--     2. Approbation   → status 'approved'  (validée par l'admin / Direction)
--     3. Rejet         → status 'rejected'  (motif obligatoire)
--     4. Exécution     → status 'paid'      (décaissement réel dans l'onglet
--                                            Paiements → ligne 'sortie' au journal)
--
--   La ligne de journal de caisse (comptabilisation) N'EST PLUS créée à la
--   saisie : elle l'est UNIQUEMENT à l'exécution du paiement (voir backend).

-- ------------------------------------------------------------
-- 1. Colonnes de workflow sur la note de caisse
-- ------------------------------------------------------------
ALTER TABLE cash_notes
  ADD COLUMN IF NOT EXISTS status            text        NOT NULL DEFAULT 'pending',
  ADD COLUMN IF NOT EXISTS approved_by       uuid,
  ADD COLUMN IF NOT EXISTS approved_at       timestamptz,
  ADD COLUMN IF NOT EXISTS rejection_reason  text,
  ADD COLUMN IF NOT EXISTS paid_by           uuid,
  ADD COLUMN IF NOT EXISTS paid_at           timestamptz,
  ADD COLUMN IF NOT EXISTS payment_method    text,   -- ov_permanent | ov_ponctuel | cheque | caisse_sociale | autre
  ADD COLUMN IF NOT EXISTS payment_reference text,   -- n° chèque / virement saisi à l'exécution
  ADD COLUMN IF NOT EXISTS payment_date      date;   -- date effective du décaissement

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cash_notes_status_check') THEN
    ALTER TABLE cash_notes
      ADD CONSTRAINT cash_notes_status_check
      CHECK (status IN ('pending', 'approved', 'rejected', 'paid'));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS cash_notes_status_idx ON cash_notes (status);

-- ------------------------------------------------------------
-- 2. Backfill : les notes existantes ont déjà généré leur ligne de journal
--    sous l'ancien flux (décaissement immédiat). On les considère 'paid'
--    pour ne pas les re-soumettre au circuit ni dupliquer la comptabilisation.
-- ------------------------------------------------------------
UPDATE cash_notes
   SET status       = 'paid',
       paid_at      = COALESCE(paid_at, created_at),
       payment_date = COALESCE(payment_date, note_date)
 WHERE status = 'pending'
   AND EXISTS (
     SELECT 1 FROM cash_journal j
      WHERE j.source_type = 'cash_note' AND j.source_id = cash_notes.id
   );

COMMENT ON COLUMN cash_notes.status         IS 'Circuit : pending (attente N+1) | approved (validée) | rejected (refusée) | paid (payée/comptabilisée).';
COMMENT ON COLUMN cash_notes.approved_by    IS 'Admin ayant approuvé (N+1).';
COMMENT ON COLUMN cash_notes.rejection_reason IS 'Motif du rejet (obligatoire au rejet).';
COMMENT ON COLUMN cash_notes.paid_by        IS 'Admin ayant exécuté le paiement (décaissement).';
COMMENT ON COLUMN cash_notes.payment_method IS 'Mode de règlement à l''exécution : ov_permanent | ov_ponctuel | cheque | caisse_sociale | autre.';
