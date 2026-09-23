-- ============================================================
-- L55 — Référentiel des locaux du bâtiment (pièce par pièce, étage par étage)
-- ============================================================
-- Contexte
--   Le champ « Localisation » de l'inventaire et la ventilation « affectation
--   par local » (L54) se tapaient à la main → « tp », « Salle A », « salle 3 »…
--   Impossible d'avoir une vue fiable « quel matériel dans quelle salle ».
--
--   On crée un référentiel `locaux` : une ligne par pièce, rattachée à un
--   étage. Les formulaires d'inventaire choisiront désormais dans cette liste
--   (avec ajout rapide d'un local à la volée).
--
--   Étages retenus : 3e, 4e, terrasse (extensible : rdc, 1er, 2e).
--   Seul le 3e est pré-rempli ici (plan d'évacuation fourni) ; le 4e et la
--   terrasse seront saisis depuis la page « Locaux ».
--
-- À exécuter dans : Supabase → SQL Editor
-- Dépend de       : rien (table autonome)
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS locaux (
  id         uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  name       text        NOT NULL,
  floor      text        NOT NULL DEFAULT '3e',
  code       text,
  capacity   integer     CHECK (capacity IS NULL OR capacity >= 0),
  note       text,
  sort_order integer     NOT NULL DEFAULT 0,
  active     boolean     NOT NULL DEFAULT true,
  created_by uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  UNIQUE (name, floor)
);

CREATE INDEX IF NOT EXISTS idx_locaux_floor ON locaux(floor);

ALTER TABLE locaux ENABLE ROW LEVEL SECURITY;
-- Comme le reste de la compta : pas de policy → accès backend (service key) seul.

-- ── Amorçage : 3e étage (plan d'évacuation) ─────────────────────────────────
INSERT INTO locaux (name, floor, sort_order) VALUES
  ('Salle 01',        '3e', 1),
  ('Salle 02',        '3e', 2),
  ('Salle 03',        '3e', 3),
  ('Salle 04',        '3e', 4),
  ('Bureau B2',       '3e', 5),
  ('Bloc sanitaire',  '3e', 6),
  ('Accueil',         '3e', 7),
  ('Espace d''attente','3e', 8)
ON CONFLICT (name, floor) DO NOTHING;

COMMIT;
