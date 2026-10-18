-- ============================================================
-- L68 — Note de Stage (par élève, par classe/cohorte)
-- ============================================================
-- Une seule note de Stage par élève par classe, non rattachée à une
-- UF/un cours — coefficient 3 dans l'Excel de référence (feuille
-- "P F C V"), compté avec les 20 UF pratiques dans MPEFCFP1. Saisie
-- directe (pas de workflow IA/docx), éditable depuis la page Notes.

CREATE TABLE IF NOT EXISTS class_stage_grades (
  id          uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  class_id    uuid        NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
  student_id  uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  grade       numeric     CHECK (grade IS NULL OR grade >= 0),
  coefficient numeric     NOT NULL DEFAULT 3 CHECK (coefficient > 0),
  graded_by   uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  graded_at   timestamptz DEFAULT now(),
  updated_at  timestamptz DEFAULT now(),
  UNIQUE (class_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_class_stage_grades_class ON class_stage_grades(class_id);

ALTER TABLE class_stage_grades ENABLE ROW LEVEL SECURITY;
-- Pas de policy : accès exclusivement via le backend service-role.

DROP TRIGGER IF EXISTS trg_class_stage_grades_updated_at ON class_stage_grades;
CREATE TRIGGER trg_class_stage_grades_updated_at BEFORE UPDATE ON class_stage_grades
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
