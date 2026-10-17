-- ============================================================
-- L65 — Contrôle continu : génération IA multi-cours + édition
-- ============================================================
-- Une évaluation "Contrôle continu" peut s'appuyer sur PLUSIEURS cours à la
-- fois (course_ids) — contrairement à un Examen (exams.course_id unique).
-- Le contenu (questions + corrigé type) est une liste de sections notées,
-- stockée en JSONB plutôt qu'en lignes séparées : la structure (consigne,
-- barème, corrigé) est fixe et fermée (format du modèle papier de
-- l'établissement), et chaque section est éditée comme un bloc de texte
-- riche (HTML Tiptap), pas comme un ensemble de champs normalisés.

CREATE TABLE IF NOT EXISTS continuous_assessments (
  id              uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  title           text        NOT NULL,
  course_ids      uuid[]      NOT NULL DEFAULT '{}',
  filiere         text,
  niveau          text,
  formateur       text,
  date_evaluation date,
  duree_epreuve   text,
  total_points    numeric     NOT NULL DEFAULT 20,
  -- [{ "id": "s1", "consigne": "<p>...</p>", "bareme": 6, "corrige": "<p>...</p>" }, ...]
  sections        jsonb       NOT NULL DEFAULT '[]'::jsonb,
  status          text        NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published')),
  created_by      uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at      timestamptz DEFAULT now(),
  updated_at      timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_continuous_assessments_created_by ON continuous_assessments(created_by);
CREATE INDEX IF NOT EXISTS idx_continuous_assessments_course_ids ON continuous_assessments USING gin(course_ids);

ALTER TABLE continuous_assessments ENABLE ROW LEVEL SECURITY;
-- Pas de policy : accès exclusivement via le backend service-role, comme le
-- reste du schéma (cf. sql/supabase_rh_migration.sql).

DROP TRIGGER IF EXISTS trg_continuous_assessments_updated_at ON continuous_assessments;
CREATE TRIGGER trg_continuous_assessments_updated_at BEFORE UPDATE ON continuous_assessments
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
