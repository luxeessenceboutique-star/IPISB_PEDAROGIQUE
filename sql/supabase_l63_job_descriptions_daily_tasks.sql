-- L63 — Fiche de poste digitalisée, tâches quotidiennes, et volet
-- mensuel/semestriel/annuel de l'évaluation (avec décision de prime de
-- rendement liée à la paie).
-- --------------------------------------------------------------
-- Flux demandé :
--   Fiche de poste (grands titres + sous-titres, chacun pondéré par un
--   coefficient) --> tâches quotidiennes saisies par le salarié (délai +
--   commentaire), validées/notées/retournées par le responsable -->
--   agrégat mensuel (nombre de tâches + note pondérée /20) --> décision de
--   prime de rendement (suggestion automatique, modifiable, appliquée sur
--   la fiche de paie) --> évaluation semestrielle (projets, résultats
--   moyen/long terme) --> évaluation annuelle (objectifs annuels, note +
--   évolution vs année précédente).

-- 1. Fiche de poste : une par (département, poste) — les postes ne sont
--    pas normalisés ailleurs (employees.department/position sont du texte
--    libre), donc réutilisable par tous les salariés occupant ce poste.
CREATE TABLE IF NOT EXISTS job_descriptions (
  id           uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  department   text        NOT NULL,
  position     text        NOT NULL,
  mission      text,
  created_by   uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at   timestamptz DEFAULT now(),
  updated_at   timestamptz DEFAULT now(),
  UNIQUE (department, position)
);

DROP TRIGGER IF EXISTS trg_job_descriptions_updated_at ON job_descriptions;
CREATE TRIGGER trg_job_descriptions_updated_at
  BEFORE UPDATE ON job_descriptions
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- 2. Rubriques : grands titres (parent_id NULL) et sous-titres (parent_id =
--    un grand titre), chacun pondéré par un coefficient utilisé dans la
--    moyenne pondérée mensuelle.
CREATE TABLE IF NOT EXISTS job_description_headings (
  id                  uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  job_description_id  uuid        NOT NULL REFERENCES job_descriptions(id) ON DELETE CASCADE,
  parent_id           uuid        REFERENCES job_description_headings(id) ON DELETE CASCADE,
  label               text        NOT NULL,
  coefficient         numeric     NOT NULL DEFAULT 1 CHECK (coefficient > 0),
  sort_order          integer     NOT NULL DEFAULT 0,
  created_at          timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_jd_headings_jd ON job_description_headings(job_description_id);
CREATE INDEX IF NOT EXISTS idx_jd_headings_parent ON job_description_headings(parent_id);

-- 3. Tâches quotidiennes : rattachées à une rubrique de la fiche de poste
--    (heading_id) ou libres ("autres tâches", heading_id NULL). Le
--    coefficient est copié à la création pour ne pas rejouer l'historique
--    si la fiche de poste change ensuite. Cycle : submitted (salarié) -->
--    validated (note + commentaire responsable) ou returned (renvoyé avec
--    commentaire, le salarié peut corriger et re-soumettre).
CREATE TABLE IF NOT EXISTS daily_tasks (
  id                uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  employee_id       uuid        NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  heading_id        uuid        REFERENCES job_description_headings(id) ON DELETE SET NULL,
  label             text        NOT NULL,
  coefficient       numeric     NOT NULL DEFAULT 1 CHECK (coefficient > 0),
  task_date         date        NOT NULL DEFAULT current_date,
  due_date          date,
  employee_comment  text,
  status            text        NOT NULL DEFAULT 'submitted' CHECK (status IN ('submitted', 'validated', 'returned')),
  note              numeric     CHECK (note >= 0 AND note <= 20),
  manager_comment   text,
  validated_by      uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  validated_at      timestamptz,
  created_by        uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at        timestamptz DEFAULT now(),
  updated_at        timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_daily_tasks_employee ON daily_tasks(employee_id);
CREATE INDEX IF NOT EXISTS idx_daily_tasks_date ON daily_tasks(task_date);
CREATE INDEX IF NOT EXISTS idx_daily_tasks_status ON daily_tasks(status);

DROP TRIGGER IF EXISTS trg_daily_tasks_updated_at ON daily_tasks;
CREATE TRIGGER trg_daily_tasks_updated_at
  BEFORE UPDATE ON daily_tasks
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE job_descriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_description_headings ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_tasks ENABLE ROW LEVEL SECURITY;
-- Pas de policy SELECT : comme le reste RH, accès exclusivement via le
-- backend service-role (deps.can_access_rh()).

-- 4. performance_reviews : passage à un barème /20 (au lieu de /5) +
--    distinction mensuel/semestriel/annuel + décision de prime de
--    rendement (mensuel uniquement).
ALTER TABLE performance_reviews DROP CONSTRAINT IF EXISTS performance_reviews_score_check;
ALTER TABLE performance_reviews ALTER COLUMN score TYPE numeric;
ALTER TABLE performance_reviews ADD CONSTRAINT performance_reviews_score_check CHECK (score >= 0 AND score <= 20);

ALTER TABLE performance_reviews
  ADD COLUMN IF NOT EXISTS review_type text NOT NULL DEFAULT 'annual' CHECK (review_type IN ('monthly', 'semestrial', 'annual')),
  ADD COLUMN IF NOT EXISTS task_count integer,
  ADD COLUMN IF NOT EXISTS bonus_suggested numeric,
  ADD COLUMN IF NOT EXISTS bonus_decided numeric,
  ADD COLUMN IF NOT EXISTS payroll_record_id uuid REFERENCES payroll_records(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_performance_reviews_type ON performance_reviews(review_type);

-- 5. performance_goals = "objectifs annuels" existants — ajout d'une année
--    explicite pour les regrouper proprement en tableau par exercice.
ALTER TABLE performance_goals ADD COLUMN IF NOT EXISTS year integer;
CREATE INDEX IF NOT EXISTS idx_performance_goals_year ON performance_goals(year);
