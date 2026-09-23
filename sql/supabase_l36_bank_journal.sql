-- ============================================================
-- IPISB Connect — Séparation Journal de caisse / JOURNAL DES COMPTES (banque)
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
-- Dépend de : cash_journal (l21/l22/l33).
-- ============================================================
--
-- Objectif :
--   Le journal de caisse mélangeait jusqu'ici les mouvements ESPÈCES et les
--   mouvements BANCAIRES (virements, ordres de virement, chèques). On sépare les
--   deux registres sur une même table (mêmes colonnes, mêmes règles) via un axe
--   `channel` :
--       - 'caisse' : espèces (caisse physique)     → « Journal de caisse »
--       - 'banque' : virement / OV / chèque / carte → « Journal des comptes »
--   Chaque journal calcule son propre solde cumulé (Solde Caisse / Solde Compte).
--
--   Nouveaux champs :
--       - channel      : registre d'appartenance de la ligne
--       - payment_mode : mode de règlement normalisé (virement, ov_permanent,
--                        ov_ponctuel, cheque, prelevement, carte, versement,
--                        especes, caisse_sociale, autre)
--       - payment_ref  : n° de chèque / n° d'OV / référence de virement
--
--   Règle : une opération bancaire est déclarée par construction — toute ligne
--   'banque' porte nc = 'comptable' (la caisse sociale n'existe qu'en espèces).
--
--   Corrige aussi un oubli de l1(35) : source_type = 'mission_note' n'était pas
--   autorisé par la contrainte CHECK, ce qui empêchait silencieusement les notes
--   de frais de mission d'alimenter le journal.

BEGIN;

-- ------------------------------------------------------------
-- 1. Nouvelles colonnes
-- ------------------------------------------------------------
ALTER TABLE cash_journal
  ADD COLUMN IF NOT EXISTS channel      text NOT NULL DEFAULT 'caisse',
  ADD COLUMN IF NOT EXISTS payment_mode text,
  ADD COLUMN IF NOT EXISTS payment_ref  text;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cash_journal_channel_check') THEN
    ALTER TABLE cash_journal
      ADD CONSTRAINT cash_journal_channel_check CHECK (channel IN ('caisse', 'banque'));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS cash_journal_channel_date_idx ON cash_journal (channel, entry_date);

COMMENT ON COLUMN cash_journal.channel      IS 'caisse = espèces (Journal de caisse) | banque = virement/OV/chèque (Journal des comptes).';
COMMENT ON COLUMN cash_journal.payment_mode IS 'Mode normalisé : virement | versement | ov_permanent | ov_ponctuel | cheque | prelevement | carte | especes | caisse_sociale | autre.';
COMMENT ON COLUMN cash_journal.payment_ref  IS 'N° de chèque / n° d''OV / référence du virement.';

-- ------------------------------------------------------------
-- 2. Élargir source_type : ajout de 'mission_note'
-- ------------------------------------------------------------
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cash_journal_source_type_check') THEN
    ALTER TABLE cash_journal DROP CONSTRAINT cash_journal_source_type_check;
  END IF;
END $$;

ALTER TABLE cash_journal
  ADD CONSTRAINT cash_journal_source_type_check
  CHECK (source_type IN (
    'manual', 'purchase_request', 'revenue', 'expense',
    'purchase_payment', 'tuition_payment', 'cash_note', 'mission_note'
  ));

COMMENT ON COLUMN cash_journal.source_type IS
  'manual = saisie | purchase_request = émission de commande | revenue = recette | expense = dépense | purchase_payment = paiement d''achat | tuition_payment = scolarité | cash_note = note de caisse | mission_note = frais de mission.';

-- ------------------------------------------------------------
-- 3. Normalisation des modes de règlement (helpers SQL)
--    Les modes sont saisis tantôt en clés canoniques ('ov_permanent', 'cheque'),
--    tantôt en libellés libres français ('Virement', 'Chèque', 'Espèces'…).
--    Ces deux fonctions ramènent tout à une clé unique et à son registre.
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION journal_mode_key(raw text)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT CASE
    WHEN k IN ('virement', 'virement bancaire', 'transfert', 'transfert bancaire') THEN 'virement'
    WHEN k IN ('versement', 'versement bancaire')                                  THEN 'versement'
    WHEN k IN ('cheque', 'chq', 'cheque bancaire')                                 THEN 'cheque'
    WHEN k IN ('ov_permanent', 'ov permanent')                                     THEN 'ov_permanent'
    WHEN k IN ('ov_ponctuel', 'ov ponctuel', 'ov')                                 THEN 'ov_ponctuel'
    WHEN k IN ('prelevement', 'prelevement automatique')                           THEN 'prelevement'
    WHEN k IN ('carte', 'carte bancaire', 'cb')                                    THEN 'carte'
    WHEN k IN ('espece', 'especes', 'cash', 'liquide', 'numeraire')                THEN 'especes'
    WHEN k IN ('caisse_sociale', 'caisse sociale')                                 THEN 'caisse_sociale'
    WHEN k = 'autre'                                                               THEN 'autre'
    ELSE NULL
  END
  FROM (
    SELECT lower(btrim(translate(
      coalesce(raw, ''),
      'éèêëàâäçôöûüùïîÉÈÊËÀÂÄÇÔÖÛÜÙÏÎ',
      'eeeeaaacoouuuiiEEEEAAACOOUUUII'
    ))) AS k
  ) t
$$;

CREATE OR REPLACE FUNCTION journal_mode_channel(raw text)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT CASE
    WHEN journal_mode_key(raw) IN ('virement', 'versement', 'cheque',
                                   'ov_permanent', 'ov_ponctuel',
                                   'prelevement', 'carte')
    THEN 'banque' ELSE 'caisse'
  END
$$;

COMMENT ON FUNCTION journal_mode_key(text)     IS 'Normalise un mode de règlement (clé canonique ou libellé FR) en clé unique ; NULL si inconnu.';
COMMENT ON FUNCTION journal_mode_channel(text) IS 'Registre déduit du mode : banque (virement/OV/chèque/carte) sinon caisse.';

-- ------------------------------------------------------------
-- 4. Reventilation des lignes existantes vers le bon journal
--    Chaque source porte son propre mode de règlement ; on le recopie sur la
--    ligne de journal et on bascule la ligne en 'banque' si le mode l'exige.
--    Les lignes sans mode identifiable restent en caisse (comportement actuel).
-- ------------------------------------------------------------

-- 4.a Paiements d'achat (purchase_payments.payment_method + n° chèque/virement)
UPDATE cash_journal j SET
  payment_mode = COALESCE(journal_mode_key(p.payment_method), j.payment_mode),
  payment_ref  = COALESCE(j.payment_ref, p.reference),
  channel      = journal_mode_channel(p.payment_method),
  nc           = CASE WHEN journal_mode_channel(p.payment_method) = 'banque' THEN 'comptable' ELSE j.nc END
FROM purchase_payments p
WHERE j.source_type = 'purchase_payment' AND j.source_id = p.id;

-- 4.b Notes de caisse payées (cash_notes.payment_method)
UPDATE cash_journal j SET
  payment_mode = COALESCE(journal_mode_key(n.payment_method), j.payment_mode),
  payment_ref  = COALESCE(j.payment_ref, n.payment_reference),
  channel      = journal_mode_channel(n.payment_method),
  nc           = CASE WHEN journal_mode_channel(n.payment_method) = 'banque' THEN 'comptable' ELSE j.nc END
FROM cash_notes n
WHERE j.source_type = 'cash_note' AND j.source_id = n.id;

-- 4.c Notes de frais de mission payées (mission_notes.payment_method)
UPDATE cash_journal j SET
  payment_mode = COALESCE(journal_mode_key(n.payment_method), j.payment_mode),
  payment_ref  = COALESCE(j.payment_ref, n.payment_reference),
  channel      = journal_mode_channel(n.payment_method),
  nc           = CASE WHEN journal_mode_channel(n.payment_method) = 'banque' THEN 'comptable' ELSE j.nc END
FROM mission_notes n
WHERE j.source_type = 'mission_note' AND j.source_id = n.id;

-- 4.d Recettes (revenues.payment_method — libellés libres FR)
UPDATE cash_journal j SET
  payment_mode = COALESCE(journal_mode_key(r.payment_method), j.payment_mode),
  channel      = journal_mode_channel(r.payment_method),
  nc           = CASE WHEN journal_mode_channel(r.payment_method) = 'banque' THEN 'comptable' ELSE j.nc END
FROM revenues r
WHERE j.source_type = 'revenue' AND j.source_id = r.id;

-- 4.e Dépenses (expenses.payment_method — libellés libres FR)
UPDATE cash_journal j SET
  payment_mode = COALESCE(journal_mode_key(e.payment_method), j.payment_mode),
  channel      = journal_mode_channel(e.payment_method),
  nc           = CASE WHEN journal_mode_channel(e.payment_method) = 'banque' THEN 'comptable' ELSE j.nc END
FROM expenses e
WHERE j.source_type = 'expense' AND j.source_id = e.id;

-- 4.f Scolarité (tuition_payments.method : espèce | chèque | virement | autre)
UPDATE cash_journal j SET
  payment_mode = COALESCE(journal_mode_key(t.method), j.payment_mode),
  channel      = journal_mode_channel(t.method),
  nc           = CASE WHEN journal_mode_channel(t.method) = 'banque' THEN 'comptable' ELSE j.nc END
FROM tuition_payments t
WHERE j.source_type = 'tuition_payment' AND j.source_id = t.id;

-- 4.g Émission de commande (purchase_requests.payment_mode), le cas échéant
UPDATE cash_journal j SET
  payment_mode = COALESCE(journal_mode_key(pr.payment_mode), j.payment_mode),
  channel      = journal_mode_channel(pr.payment_mode),
  nc           = CASE WHEN journal_mode_channel(pr.payment_mode) = 'banque' THEN 'comptable' ELSE j.nc END
FROM purchase_requests pr
WHERE j.source_type = 'purchase_request' AND j.source_id = pr.id;

-- 4.h Garde-fou : aucune ligne bancaire ne peut être « caisse sociale ».
UPDATE cash_journal SET nc = 'comptable' WHERE channel = 'banque' AND nc <> 'comptable';

COMMIT;

-- ------------------------------------------------------------
-- 5. Contrôle (à lire dans le résultat du SQL Editor)
-- ------------------------------------------------------------
SELECT channel,
       count(*)                                      AS lignes,
       sum(CASE WHEN type = 'entree' THEN amount ELSE 0 END) AS total_entrees,
       sum(CASE WHEN type = 'sortie' THEN amount ELSE 0 END) AS total_sorties
  FROM cash_journal
 GROUP BY channel
 ORDER BY channel;
