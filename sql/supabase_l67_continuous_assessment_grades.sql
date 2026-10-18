-- ============================================================
-- L67 — Notes d'Examen (EFCF Théorique / Pratique) par élève
-- ============================================================
-- Une fois qu'un Examen (continuous_assessments, doc_type='examen') a été
-- généré/imprimé/administré, le formateur/admin saisit ici la note de
-- chaque élève concerné : Théorique (sur `sections`) et, si l'épreuve en
-- comporte, Pratique (sur `pratique_sections`). Une ligne par élève par
-- Examen. Les scores sont stockés BRUTS (sur le barème propre à cet
-- Examen), pas déjà normalisés sur 20 — la normalisation /20 se fait au
-- calcul (cf. grades.py::_category_average), comme pour
-- assignments.max_grade / exam_responses.total.
-- Alimente MPEFCFT1 / MPEFCFP1 (cf. backend/routers/grades.py).

CREATE TABLE IF NOT EXISTS continuous_assessment_grades (
  id              uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  assessment_id   uuid        NOT NULL REFERENCES continuous_assessments(id) ON DELETE CASCADE,
  student_id      uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  theorique_score numeric     CHECK (theorique_score IS NULL OR theorique_score >= 0),
  pratique_score  numeric     CHECK (pratique_score IS NULL OR pratique_score >= 0),
  graded_by       uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  graded_at       timestamptz DEFAULT now(),
  updated_at      timestamptz DEFAULT now(),
  UNIQUE (assessment_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_cag_assessment ON continuous_assessment_grades(assessment_id);
CREATE INDEX IF NOT EXISTS idx_cag_student ON continuous_assessment_grades(student_id);

ALTER TABLE continuous_assessment_grades ENABLE ROW LEVEL SECURITY;
-- Pas de policy : accès exclusivement via le backend service-role, comme
-- continuous_assessments (cf. L65).

DROP TRIGGER IF EXISTS trg_cag_updated_at ON continuous_assessment_grades;
CREATE TRIGGER trg_cag_updated_at BEFORE UPDATE ON continuous_assessment_grades
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
