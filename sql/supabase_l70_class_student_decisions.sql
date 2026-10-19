-- ============================================================
-- L70 — Décision du jury (admission) par élève + jury de classe
-- ============================================================
-- Réplique la colonne "Proposition/Commentaires du jury" de la feuille
-- "Modalité de passage de 1ère TS" de l'Excel de référence. Le calcul
-- (MPCC1/MPEFCFT1/MPEFCFP1/MG1, cf. grades.py::compute_class_mg1_summary)
-- ne change pas : cette table stocke uniquement la décision ÉCRITE par le
-- jury quand elle diverge de — ou confirme — la suggestion automatique par
-- seuil de MG1 (cf. grades.py::compute_class_decisions). Sans ligne ici,
-- l'élève n'a qu'une suggestion, jamais une décision officielle.
--
-- status est contraint (valeurs fermées, cf. l'Excel) ; mention est du
-- texte libre écrit par le jury (ex. "Excellent", "Bien" — ou tout autre
-- commentaire), jamais contraint : les bandes de seuil ne sont qu'une
-- suggestion, le jury a le dernier mot.

CREATE TABLE IF NOT EXISTS class_student_decisions (
  id          uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  class_id    uuid        NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
  student_id  uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  status      text        NOT NULL CHECK (status IN (
                'admis', 'admis_avec_rachat', 'non_admis_redouble',
                'redouble_exceptionnel', 'reoriente', 'exclu'
              )),
  mention     text,
  decided_by  uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  decided_at  timestamptz DEFAULT now(),
  updated_at  timestamptz DEFAULT now(),
  UNIQUE (class_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_class_student_decisions_class ON class_student_decisions(class_id);

ALTER TABLE class_student_decisions ENABLE ROW LEVEL SECURITY;
-- Pas de policy : accès exclusivement via le backend service-role.

DROP TRIGGER IF EXISTS trg_class_student_decisions_updated_at ON class_student_decisions;
CREATE TRIGGER trg_class_student_decisions_updated_at BEFORE UPDATE ON class_student_decisions
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ============================================================
-- Jury de la décision finale (par classe) — 4 rôles, PAS le jury d'Examen
-- ============================================================
-- Un jury de classe est distinct du jury d'un Examen donné (continuous_
-- assessments.jury, L66) : il signe la décision finale de passage pour
-- TOUTE la cohorte, pas une épreuve. Même forme que class_grade_weights
-- (clé = class_id, une seule ligne par classe) plutôt qu'une table à
-- part avec FK — pas de relation à modéliser, juste une petite liste
-- (4 rôles fixes côté Excel : Président·e / Membre professionnel / Membre
-- formateur 1 / Membre formateur 2, mais stockée en JSONB libre comme
-- continuous_assessments.jury pour rester de simples champs texte libres
-- côté frontend, pas une 5ᵉ table).

CREATE TABLE IF NOT EXISTS class_jury (
  class_id    uuid        PRIMARY KEY REFERENCES classes(id) ON DELETE CASCADE,
  -- [{ "name": "...", "role": "..." }, ...] — jusqu'à 4 entrées.
  members     jsonb       NOT NULL DEFAULT '[]'::jsonb,
  updated_by  uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  updated_at  timestamptz DEFAULT now()
);

ALTER TABLE class_jury ENABLE ROW LEVEL SECURITY;
-- Pas de policy : accès exclusivement via le backend service-role.

DROP TRIGGER IF EXISTS trg_class_jury_updated_at ON class_jury;
CREATE TRIGGER trg_class_jury_updated_at BEFORE UPDATE ON class_jury
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
