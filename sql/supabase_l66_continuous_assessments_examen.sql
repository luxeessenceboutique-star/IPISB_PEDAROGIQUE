-- ============================================================
-- L66 — Contrôle continu devient aussi « Examen » (2e gabarit Word)
-- ============================================================
-- doc_type distingue les deux gabarits Word exportables depuis la même
-- table/éditeur : 'controle_continu' (Question + Corrigé type, voir L65) et
-- 'examen' (épreuve théorique + jury + épreuve pratique optionnelle, sur le
-- gabarit officiel « ETEIQUE IP1 QUES.docx »). jury et pratique_sections ne
-- sont utilisés que par doc_type='examen' — saisis à la main (le jury
-- change à chaque examen, la partie pratique n'est pas générée par l'IA).

ALTER TABLE continuous_assessments
  ADD COLUMN IF NOT EXISTS doc_type text NOT NULL DEFAULT 'controle_continu'
    CHECK (doc_type IN ('controle_continu', 'examen')),
  -- [{ "name": "Mme DIRANE BOUCHRA", "role": "Président du jury d'examens" }, ...]
  ADD COLUMN IF NOT EXISTS jury jsonb NOT NULL DEFAULT '[]'::jsonb,
  -- même forme que `sections` (consigne/bareme/corrige) — épreuve pratique,
  -- saisie manuelle, optionnelle.
  ADD COLUMN IF NOT EXISTS pratique_sections jsonb NOT NULL DEFAULT '[]'::jsonb;
