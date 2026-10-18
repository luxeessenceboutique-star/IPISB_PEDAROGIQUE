-- ============================================================
-- L69 — Pondération de la Moyenne générale (MG1) par classe
-- ============================================================
-- Mirroring course_grade_weights (academic_extensions migration), mais SANS
-- forcer la somme à 100 : l'Excel de référence pondère
-- MPCC1/MPEFCFT1/MPEFCFP1 par 3/2/3 (somme = 8), puis divise par 8 — pas
-- par 100. Le calcul (grades.py) divise toujours par la somme réelle des
-- poids présents.

CREATE TABLE IF NOT EXISTS class_grade_weights (
  class_id        uuid        PRIMARY KEY REFERENCES classes(id) ON DELETE CASCADE,
  cc_weight       numeric     NOT NULL DEFAULT 3 CHECK (cc_weight > 0),
  efcf_th_weight  numeric     NOT NULL DEFAULT 2 CHECK (efcf_th_weight > 0),
  efcf_pr_weight  numeric     NOT NULL DEFAULT 3 CHECK (efcf_pr_weight > 0),
  updated_by      uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  updated_at      timestamptz DEFAULT now()
);

ALTER TABLE class_grade_weights ENABLE ROW LEVEL SECURITY;
-- Pas de policy : accès exclusivement via le backend service-role.

DROP TRIGGER IF EXISTS trg_class_grade_weights_updated_at ON class_grade_weights;
CREATE TRIGGER trg_class_grade_weights_updated_at BEFORE UPDATE ON class_grade_weights
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
