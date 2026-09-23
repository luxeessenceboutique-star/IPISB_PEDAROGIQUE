-- L48 — Catégorie des évaluations « Note directe » (Contrôle continu / Examen)
-- À exécuter UNE fois dans le SQL Editor de Supabase. Idempotent.
--
-- Contexte : le raccourci de saisie directe (page Notes, professeur) ne se
-- limite plus à UNE note par module — le professeur peut créer plusieurs
-- évaluations (ex. « Devoir 1 », « Examen final »), chacune catégorisée
-- Contrôle continu ou Examen, qui contribuent à la moyenne pondérée du
-- module (devoir_avg / exam_avg) exactement comme un vrai devoir noté ou un
-- vrai examen QCM.

ALTER TABLE public.assignments
  ADD COLUMN IF NOT EXISTS quick_grade_category text
  CHECK (quick_grade_category IN ('devoir', 'exam'));

COMMENT ON COLUMN public.assignments.quick_grade_category IS
  'Uniquement pour is_quick_grade=true : catégorie de pondération de cette évaluation saisie directement — devoir (Contrôle continu) ou exam (Examen). Alimente devoir_avg / exam_avg dans compute_course_grade().';
