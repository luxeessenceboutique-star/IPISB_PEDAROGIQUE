-- ============================================================
-- IPISB Platform — RH Phase 2 Migration
-- Run this ONCE in the Supabase SQL Editor, AFTER supabase_rh_migration.sql
--
-- Departments, contract types, assets, onboarding, recruitment,
-- org chart, training/skills, talent management.
--
-- Reuses public.set_updated_at() defined in supabase_rh_migration.sql.
-- RLS enabled with no policies everywhere — backend-service-key only,
-- same convention as every other IPISB migration.
-- ============================================================

-- ============================================================
-- 1. Departments & contract types (lookup tables)
-- ============================================================
CREATE TABLE IF NOT EXISTS departments (
  id          uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  name        text        NOT NULL UNIQUE,
  description text,
  created_at  timestamptz DEFAULT now()
);

ALTER TABLE departments ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS contract_types (
  id          uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  name        text        NOT NULL UNIQUE,
  description text,
  is_active   boolean     NOT NULL DEFAULT true,
  created_at  timestamptz DEFAULT now()
);

ALTER TABLE contract_types ENABLE ROW LEVEL SECURITY;

INSERT INTO contract_types (name, description) VALUES
  ('CDI', 'Contrat à Durée Indéterminée'),
  ('CDD', 'Contrat à Durée Déterminée'),
  ('Stage', 'Convention de stage'),
  ('Freelance', 'Contrat de prestation')
ON CONFLICT (name) DO NOTHING;

-- Widen the employees.status enum (phase 1) so recruitment candidates
-- can live in the same table.
ALTER TABLE employees DROP CONSTRAINT IF EXISTS employees_status_check;
ALTER TABLE employees ADD CONSTRAINT employees_status_check
  CHECK (status IN ('active', 'on-leave', 'inactive', 'candidate'));

-- ============================================================
-- 2. Assets
-- ============================================================
CREATE TABLE IF NOT EXISTS assets (
  id              uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  name            text        NOT NULL,
  category        text,
  serial_number   text        UNIQUE,
  employee_id     uuid        REFERENCES employees(id) ON DELETE SET NULL,
  status          text        NOT NULL DEFAULT 'available' CHECK (status IN ('available', 'assigned', 'maintenance', 'retired')),
  assigned_at     timestamptz,
  notes           text,
  created_at      timestamptz DEFAULT now(),
  updated_at      timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_assets_employee ON assets(employee_id);

ALTER TABLE assets ENABLE ROW LEVEL SECURITY;

DROP TRIGGER IF EXISTS trg_assets_updated_at ON assets;
CREATE TRIGGER trg_assets_updated_at
  BEFORE UPDATE ON assets
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ============================================================
-- 3. Onboarding (30/60/90-day plans, buddy, contract sign, pulse surveys)
-- ============================================================
CREATE TABLE IF NOT EXISTS employee_onboarding (
  id                  uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  employee_id         uuid        NOT NULL UNIQUE REFERENCES employees(id) ON DELETE CASCADE,
  phase               text        NOT NULL DEFAULT 'day30' CHECK (phase IN ('day30', 'day60', 'day90', 'completed')),
  buddy_name          text,
  buddy_email         text,
  contract_signed     boolean     NOT NULL DEFAULT false,
  contract_signed_at  timestamptz,
  plan_30             jsonb       DEFAULT '[]',
  plan_60             jsonb       DEFAULT '[]',
  plan_90             jsonb       DEFAULT '[]',
  created_at          timestamptz DEFAULT now(),
  updated_at          timestamptz DEFAULT now()
);

ALTER TABLE employee_onboarding ENABLE ROW LEVEL SECURITY;

DROP TRIGGER IF EXISTS trg_employee_onboarding_updated_at ON employee_onboarding;
CREATE TRIGGER trg_employee_onboarding_updated_at
  BEFORE UPDATE ON employee_onboarding
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TABLE IF NOT EXISTS pulse_surveys (
  id                  uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  employee_id         uuid        NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  week_number         integer,
  satisfaction_score  integer     CHECK (satisfaction_score BETWEEN 1 AND 5),
  integration_score   integer     CHECK (integration_score BETWEEN 1 AND 5),
  clarity_score       integer     CHECK (clarity_score BETWEEN 1 AND 5),
  comment             text,
  created_at          timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pulse_surveys_employee ON pulse_surveys(employee_id);

ALTER TABLE pulse_surveys ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- 4. Recruitment — ads, interviews, slots (candidates = employees
--    rows with status='candidate', no dedicated table needed)
-- ============================================================
CREATE TABLE IF NOT EXISTS recruitment_ads (
  id           uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  poste        text        NOT NULL,
  description  text,
  competences  text,
  experience   text,
  contenu      text        NOT NULL,
  image_url    text,
  is_active    boolean     NOT NULL DEFAULT true,
  created_by   uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at   timestamptz DEFAULT now(),
  updated_at   timestamptz DEFAULT now()
);

ALTER TABLE recruitment_ads ENABLE ROW LEVEL SECURITY;

DROP TRIGGER IF EXISTS trg_recruitment_ads_updated_at ON recruitment_ads;
CREATE TRIGGER trg_recruitment_ads_updated_at
  BEFORE UPDATE ON recruitment_ads
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TABLE IF NOT EXISTS interviews (
  id            uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  candidate_id  uuid        NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  recruiter_id  uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  date          date        NOT NULL,
  start_time    time        NOT NULL,
  end_time      time        NOT NULL,
  type          text        NOT NULL CHECK (type IN ('rh', 'technical', 'final')),
  status        text        NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'completed', 'cancelled')),
  meet_link     text,
  notes         text,
  created_by    uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at    timestamptz DEFAULT now(),
  updated_at    timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_interviews_candidate ON interviews(candidate_id);

ALTER TABLE interviews ENABLE ROW LEVEL SECURITY;

DROP TRIGGER IF EXISTS trg_interviews_updated_at ON interviews;
CREATE TRIGGER trg_interviews_updated_at
  BEFORE UPDATE ON interviews
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TABLE IF NOT EXISTS hr_slots (
  id            uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  date          date        NOT NULL,
  start_time    time        NOT NULL,
  end_time      time        NOT NULL,
  status        text        NOT NULL DEFAULT 'free' CHECK (status IN ('free', 'reserved')),
  ad_id         uuid        REFERENCES recruitment_ads(id) ON DELETE SET NULL,
  interview_id  uuid        REFERENCES interviews(id) ON DELETE SET NULL,
  created_at    timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_hr_slots_date ON hr_slots(date);

ALTER TABLE hr_slots ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- 5. Org chart — projects, members, canvas node positions
-- ============================================================
CREATE TABLE IF NOT EXISTS orgchart_projects (
  id          uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  name        text        NOT NULL,
  description text,
  color       text        NOT NULL DEFAULT '#0891b2',
  created_at  timestamptz DEFAULT now()
);

ALTER TABLE orgchart_projects ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS orgchart_team_members (
  id            uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  project_id    uuid        NOT NULL REFERENCES orgchart_projects(id) ON DELETE CASCADE,
  employee_id   uuid        NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  role_in_team  text,
  created_at    timestamptz DEFAULT now(),
  UNIQUE (project_id, employee_id)
);

CREATE INDEX IF NOT EXISTS idx_orgchart_members_employee ON orgchart_team_members(employee_id);

ALTER TABLE orgchart_team_members ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS orgchart_node_positions (
  employee_id  uuid   PRIMARY KEY REFERENCES employees(id) ON DELETE CASCADE,
  x            float8 NOT NULL DEFAULT 0,
  y            float8 NOT NULL DEFAULT 0
);

ALTER TABLE orgchart_node_positions ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- 6. Training catalog, assignments, skills matrix
-- ============================================================
CREATE TABLE IF NOT EXISTS training_catalog (
  id              uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  title           text        NOT NULL,
  category        text        NOT NULL DEFAULT 'technique',
  provider        text,
  duration_hours  integer     DEFAULT 0,
  cost_dh         numeric(10,2) DEFAULT 0,
  description     text,
  is_active       boolean     NOT NULL DEFAULT true,
  created_at      timestamptz DEFAULT now()
);

ALTER TABLE training_catalog ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS employee_trainings (
  id            uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  employee_id   uuid        NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  training_id   uuid        NOT NULL REFERENCES training_catalog(id) ON DELETE CASCADE,
  status        text        NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'in_progress', 'completed', 'cancelled')),
  assigned_at   timestamptz DEFAULT now(),
  completed_at  timestamptz,
  score         integer,
  notes         text
);

CREATE INDEX IF NOT EXISTS idx_employee_trainings_employee ON employee_trainings(employee_id);

ALTER TABLE employee_trainings ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS skills (
  id          uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  name        text        NOT NULL,
  category    text        NOT NULL DEFAULT 'technique',
  description text,
  is_active   boolean     NOT NULL DEFAULT true,
  created_at  timestamptz DEFAULT now()
);

ALTER TABLE skills ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS employee_skills (
  id            uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  employee_id   uuid        NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  skill_id      uuid        NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
  level         text        NOT NULL DEFAULT 'beginner' CHECK (level IN ('beginner', 'intermediate', 'advanced', 'expert')),
  assessed_at   timestamptz DEFAULT now(),
  UNIQUE (employee_id, skill_id)
);

ALTER TABLE employee_skills ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- 7. Talent management — 9-box profiles, OKRs, PDI
-- ============================================================
CREATE TABLE IF NOT EXISTS talent_profiles (
  id                     uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  employee_id            uuid        NOT NULL UNIQUE REFERENCES employees(id) ON DELETE CASCADE,
  performance_score      integer     NOT NULL DEFAULT 3 CHECK (performance_score BETWEEN 1 AND 5),
  potential_score        integer     NOT NULL DEFAULT 3 CHECK (potential_score BETWEEN 1 AND 5),
  talent_category        text        NOT NULL DEFAULT 'key_player',
  flight_risk            text        NOT NULL DEFAULT 'low' CHECK (flight_risk IN ('low', 'medium', 'high')),
  is_critical_position    boolean     NOT NULL DEFAULT false,
  successor_names        jsonb       DEFAULT '[]',
  career_path            text,
  next_role               text,
  notes                  text,
  created_at             timestamptz DEFAULT now(),
  updated_at             timestamptz DEFAULT now()
);

ALTER TABLE talent_profiles ENABLE ROW LEVEL SECURITY;

DROP TRIGGER IF EXISTS trg_talent_profiles_updated_at ON talent_profiles;
CREATE TRIGGER trg_talent_profiles_updated_at
  BEFORE UPDATE ON talent_profiles
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TABLE IF NOT EXISTS employee_okrs (
  id           uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  employee_id  uuid        NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  title        text        NOT NULL,
  description  text,
  quarter      text,
  progress     integer     NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
  status       text        NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'cancelled')),
  created_at   timestamptz DEFAULT now(),
  updated_at   timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_employee_okrs_employee ON employee_okrs(employee_id);

ALTER TABLE employee_okrs ENABLE ROW LEVEL SECURITY;

DROP TRIGGER IF EXISTS trg_employee_okrs_updated_at ON employee_okrs;
CREATE TRIGGER trg_employee_okrs_updated_at
  BEFORE UPDATE ON employee_okrs
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TABLE IF NOT EXISTS pdi_items (
  id            uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  employee_id   uuid        NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  title         text        NOT NULL,
  action_type   text        NOT NULL DEFAULT 'formation',
  target_date   date,
  status        text        NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed')),
  notes         text,
  created_at    timestamptz DEFAULT now(),
  updated_at    timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pdi_items_employee ON pdi_items(employee_id);

ALTER TABLE pdi_items ENABLE ROW LEVEL SECURITY;

DROP TRIGGER IF EXISTS trg_pdi_items_updated_at ON pdi_items;
CREATE TRIGGER trg_pdi_items_updated_at
  BEFORE UPDATE ON pdi_items
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
