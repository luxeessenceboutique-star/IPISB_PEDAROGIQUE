-- ============================================================
-- IPISB Platform — RH (Ressources Humaines) Migration
-- Run this ONCE in the Supabase SQL Editor
--
-- Core HR: employee directory, leave/absence requests + balances,
-- payroll (Moroccan CNSS/IR), performance reviews + goals, holidays.
-- Ported from a sister HR platform, trimmed to the fields these tables
-- actually need (no CV/AI-analysis columns, no file attachments, no
-- onboarding/talent/training/recruitment — those aren't in scope here).
--
-- Audit trail reuses the existing `audit_log` table (utils/audit.py),
-- same as the L4 accounting migration. All access goes through the
-- FastAPI service-role backend, so RLS is enabled with no policies.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

-- ============================================================
-- 1. Employees
-- ============================================================
CREATE TABLE IF NOT EXISTS employees (
  id              uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  full_name       text        NOT NULL,
  cin             text,
  matricule       text,
  email           text,
  phone           text,
  position        text,
  department      text,
  status          text        NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'on-leave', 'inactive')),
  hire_date       date,
  contract_type   text,
  contract_start  date,
  contract_end    date,
  salary          numeric,
  birth_date      date,
  address         text,
  city            text,
  nationality     text,
  manager         text,
  cnss_number     text,
  bank_account    text,
  notes           text,
  created_by      uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at      timestamptz DEFAULT now(),
  updated_at      timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_employees_status ON employees(status);
CREATE INDEX IF NOT EXISTS idx_employees_department ON employees(department);
CREATE INDEX IF NOT EXISTS idx_employees_full_name_trgm ON employees USING gin (full_name gin_trgm_ops);

ALTER TABLE employees ENABLE ROW LEVEL SECURITY;
-- No SELECT policy: HR data (salaries, personal info) is backend-service-key only.

DROP TRIGGER IF EXISTS trg_employees_updated_at ON employees;
CREATE TRIGGER trg_employees_updated_at
  BEFORE UPDATE ON employees
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ============================================================
-- 2. Leave requests + balances
-- ============================================================
CREATE TABLE IF NOT EXISTS leave_requests (
  id           uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  employee_id  uuid        REFERENCES employees(id) ON DELETE CASCADE,
  type         text        NOT NULL DEFAULT 'annual' CHECK (type IN ('annual', 'sick', 'personal', 'maternity', 'paternity', 'unpaid')),
  start_date   date        NOT NULL,
  end_date     date        NOT NULL,
  days         integer     NOT NULL DEFAULT 0,
  status       text        NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
  reason       text,
  reviewed_by  uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  reviewed_at  timestamptz,
  comment      text,
  created_by   uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at   timestamptz DEFAULT now(),
  updated_at   timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_leave_requests_employee ON leave_requests(employee_id);
CREATE INDEX IF NOT EXISTS idx_leave_requests_status   ON leave_requests(status);

ALTER TABLE leave_requests ENABLE ROW LEVEL SECURITY;

DROP TRIGGER IF EXISTS trg_leave_requests_updated_at ON leave_requests;
CREATE TRIGGER trg_leave_requests_updated_at
  BEFORE UPDATE ON leave_requests
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TABLE IF NOT EXISTS leave_balances (
  id              uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  employee_id     uuid        NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  year            integer     NOT NULL DEFAULT EXTRACT(YEAR FROM now())::int,
  annual_total    integer     NOT NULL DEFAULT 21,
  annual_used     integer     NOT NULL DEFAULT 0,
  sick_total      integer     NOT NULL DEFAULT 12,
  sick_used       integer     NOT NULL DEFAULT 0,
  personal_total  integer     NOT NULL DEFAULT 5,
  personal_used   integer     NOT NULL DEFAULT 0,
  updated_at      timestamptz DEFAULT now(),
  UNIQUE (employee_id, year)
);

ALTER TABLE leave_balances ENABLE ROW LEVEL SECURITY;

DROP TRIGGER IF EXISTS trg_leave_balances_updated_at ON leave_balances;
CREATE TRIGGER trg_leave_balances_updated_at
  BEFORE UPDATE ON leave_balances
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- Auto-update leave_balances + employee status when a leave request is approved
CREATE OR REPLACE FUNCTION public.handle_leave_approval()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.status = 'approved' AND OLD.status != 'approved' THEN
    INSERT INTO leave_balances (employee_id, year)
    VALUES (NEW.employee_id, EXTRACT(YEAR FROM NEW.start_date)::int)
    ON CONFLICT (employee_id, year) DO NOTHING;

    IF NEW.type = 'annual' THEN
      UPDATE leave_balances
        SET annual_used = annual_used + NEW.days
      WHERE employee_id = NEW.employee_id
        AND year = EXTRACT(YEAR FROM NEW.start_date)::int;
    ELSIF NEW.type = 'sick' THEN
      UPDATE leave_balances
        SET sick_used = sick_used + NEW.days
      WHERE employee_id = NEW.employee_id
        AND year = EXTRACT(YEAR FROM NEW.start_date)::int;
    ELSIF NEW.type = 'personal' THEN
      UPDATE leave_balances
        SET personal_used = personal_used + NEW.days
      WHERE employee_id = NEW.employee_id
        AND year = EXTRACT(YEAR FROM NEW.start_date)::int;
    END IF;

    UPDATE employees SET status = 'on-leave' WHERE id = NEW.employee_id;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_leave_approval ON leave_requests;
CREATE TRIGGER trg_leave_approval
  AFTER UPDATE ON leave_requests
  FOR EACH ROW EXECUTE FUNCTION public.handle_leave_approval();

-- ============================================================
-- 3. Public holidays (Maroc)
-- ============================================================
CREATE TABLE IF NOT EXISTS holidays (
  id            uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  name          text        NOT NULL,
  date          date        NOT NULL UNIQUE,
  is_recurring  boolean     DEFAULT true,
  created_at    timestamptz DEFAULT now()
);

ALTER TABLE holidays ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- 4. Payroll records — Moroccan CNSS/IR payslips
-- ============================================================
CREATE TABLE IF NOT EXISTS payroll_records (
  id              uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  employee_id     uuid        REFERENCES employees(id) ON DELETE CASCADE,
  month           integer     NOT NULL CHECK (month BETWEEN 1 AND 12),
  year            integer     NOT NULL,
  base_salary     numeric     NOT NULL DEFAULT 0,
  bonuses         numeric     DEFAULT 0,
  deductions      numeric     DEFAULT 0,
  cnss            numeric     DEFAULT 0,
  ir              numeric     DEFAULT 0,
  net_salary      numeric     DEFAULT 0,
  gross_salary    numeric     DEFAULT 0,
  status          text        NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'validated', 'paid')),
  paid_at         timestamptz,
  notes           text,
  created_by      uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at      timestamptz DEFAULT now(),
  updated_at      timestamptz DEFAULT now(),
  UNIQUE (employee_id, month, year)
);

CREATE INDEX IF NOT EXISTS idx_payroll_records_period ON payroll_records(year, month);

ALTER TABLE payroll_records ENABLE ROW LEVEL SECURITY;

DROP TRIGGER IF EXISTS trg_payroll_records_updated_at ON payroll_records;
CREATE TRIGGER trg_payroll_records_updated_at
  BEFORE UPDATE ON payroll_records
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ============================================================
-- 5. Performance reviews + goals
-- ============================================================
CREATE TABLE IF NOT EXISTS performance_reviews (
  id            uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  employee_id   uuid        REFERENCES employees(id) ON DELETE CASCADE,
  reviewer_id   uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  period        text        NOT NULL,
  score         integer     CHECK (score BETWEEN 1 AND 5),
  feedback      text,
  objectives    text,
  achievements  text,
  improvements  text,
  status        text        NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'submitted', 'acknowledged')),
  created_at    timestamptz DEFAULT now(),
  updated_at    timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_performance_reviews_employee ON performance_reviews(employee_id);

ALTER TABLE performance_reviews ENABLE ROW LEVEL SECURITY;

DROP TRIGGER IF EXISTS trg_performance_reviews_updated_at ON performance_reviews;
CREATE TRIGGER trg_performance_reviews_updated_at
  BEFORE UPDATE ON performance_reviews
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TABLE IF NOT EXISTS performance_goals (
  id           uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  employee_id  uuid        REFERENCES employees(id) ON DELETE CASCADE,
  title        text        NOT NULL,
  description  text,
  status       text        NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'done')),
  progress     integer     NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
  due_date     date,
  created_at   timestamptz DEFAULT now(),
  updated_at   timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_performance_goals_employee ON performance_goals(employee_id);

ALTER TABLE performance_goals ENABLE ROW LEVEL SECURITY;

DROP TRIGGER IF EXISTS trg_performance_goals_updated_at ON performance_goals;
CREATE TRIGGER trg_performance_goals_updated_at
  BEFORE UPDATE ON performance_goals
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
