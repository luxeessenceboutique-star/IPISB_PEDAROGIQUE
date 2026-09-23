-- ============================================================
-- IPISB Platform — RH Phase 6 Migration: Leave/Absence Taxonomy
-- Run this ONCE in the Supabase SQL Editor.
--
-- Full taxonomy (6 requestable types, each with an official code):
--   recovery ............... R  — Récupération / Compensatoire   (untracked balance)
--   sick .................... M  — Maladie                        (sick_total/sick_used, 12 j/an par défaut)
--   unpaid ................... CS — Congé sans solde               (untracked balance)
--   permission ............... P  — Permission / Absence autorisée (personal_total/personal_used, 5 j/an — colonnes réutilisées)
--   other ..................... A  — Autre                         (annual_total/annual_used, accrual 1.5 j/mois — colonnes réutilisées)
--   unjustified_absence ...... AJ — Absence injustifiée            (untracked, ne bascule pas l'employé en 'on-leave')
--
-- Two more codes from the spec are NOT leave types, by design:
--   - "Travail" (T, vert) is a calendar-only "present at work" marker,
--     rendered client-side for days with no leave — nothing to store.
--   - "Congé annulé" (C, bleu) is a STATUS on an existing request
--     (see step 3), not a type — HR calling off a previously approved
--     leave, not a new kind of leave someone requests.
--
-- 'annual_total'/'annual_used' and 'personal_total'/'personal_used' keep
-- their existing physical column names (non-destructive) but are now the
-- "Autre" and "Permission" buckets respectively — relabeled in the UI.
-- ============================================================

-- 1. Migrate existing data BEFORE tightening the CHECK constraint.
--    Old 'annual'/'personal'/'maternity'/'paternity' all fold into 'other'.
--    Old 'unpaid' keeps its literal meaning — it's now a first-class type,
--    no migration needed. 'sick'/'recovery'/'unjustified_absence' already match.
UPDATE leave_requests SET type = 'other'
  WHERE type IN ('annual', 'personal', 'maternity', 'paternity');

-- 2. New type taxonomy.
ALTER TABLE leave_requests DROP CONSTRAINT IF EXISTS leave_requests_type_check;
ALTER TABLE leave_requests ADD CONSTRAINT leave_requests_type_check
  CHECK (type IN ('recovery', 'sick', 'unpaid', 'permission', 'other', 'unjustified_absence'));

-- 3. New status value: 'cancelled' — set when HR calls off a previously
--    approved leave (as opposed to 'rejected', which is for requests never approved).
ALTER TABLE leave_requests DROP CONSTRAINT IF EXISTS leave_requests_status_check;
ALTER TABLE leave_requests ADD CONSTRAINT leave_requests_status_check
  CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled'));

-- 4. Supporting document upload — required for every type above except
--    unjustified_absence (enforced in the UI, not the DB — HR may need to
--    attach it after the fact).
ALTER TABLE leave_requests ADD COLUMN IF NOT EXISTS document_path text;
ALTER TABLE leave_requests ADD COLUMN IF NOT EXISTS document_filename text;

-- 5. Fractional accrual (1.5 days × months worked) for the "Autre" bucket
--    (still the annual_total column under the hood).
ALTER TABLE leave_balances ALTER COLUMN annual_total TYPE numeric;
ALTER TABLE leave_balances ALTER COLUMN annual_total SET DEFAULT 0;

-- 6. Approval / cancellation trigger, rewritten for the new taxonomy.
--    Cancelling a previously-approved leave reverses whatever the approval
--    applied (balance usage + employee status), symmetric to the approval branch.
CREATE OR REPLACE FUNCTION public.handle_leave_approval()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.status = 'approved' AND OLD.status != 'approved' THEN
    INSERT INTO leave_balances (employee_id, year)
    VALUES (NEW.employee_id, EXTRACT(YEAR FROM NEW.start_date)::int)
    ON CONFLICT (employee_id, year) DO NOTHING;

    IF NEW.type = 'sick' THEN
      UPDATE leave_balances SET sick_used = sick_used + NEW.days
      WHERE employee_id = NEW.employee_id AND year = EXTRACT(YEAR FROM NEW.start_date)::int;
    ELSIF NEW.type = 'permission' THEN
      UPDATE leave_balances SET personal_used = personal_used + NEW.days
      WHERE employee_id = NEW.employee_id AND year = EXTRACT(YEAR FROM NEW.start_date)::int;
    ELSIF NEW.type = 'other' THEN
      UPDATE leave_balances SET annual_used = annual_used + NEW.days
      WHERE employee_id = NEW.employee_id AND year = EXTRACT(YEAR FROM NEW.start_date)::int;
    END IF;
    -- 'recovery', 'unpaid', 'unjustified_absence' aren't deducted from any balance.

    IF NEW.type != 'unjustified_absence' THEN
      UPDATE employees SET status = 'on-leave' WHERE id = NEW.employee_id;
    END IF;

  ELSIF NEW.status = 'cancelled' AND OLD.status = 'approved' THEN
    IF NEW.type = 'sick' THEN
      UPDATE leave_balances SET sick_used = GREATEST(0, sick_used - NEW.days)
      WHERE employee_id = NEW.employee_id AND year = EXTRACT(YEAR FROM NEW.start_date)::int;
    ELSIF NEW.type = 'permission' THEN
      UPDATE leave_balances SET personal_used = GREATEST(0, personal_used - NEW.days)
      WHERE employee_id = NEW.employee_id AND year = EXTRACT(YEAR FROM NEW.start_date)::int;
    ELSIF NEW.type = 'other' THEN
      UPDATE leave_balances SET annual_used = GREATEST(0, annual_used - NEW.days)
      WHERE employee_id = NEW.employee_id AND year = EXTRACT(YEAR FROM NEW.start_date)::int;
    END IF;

    IF NEW.type != 'unjustified_absence' THEN
      UPDATE employees SET status = 'active' WHERE id = NEW.employee_id AND status = 'on-leave';
    END IF;
  END IF;

  RETURN NEW;
END;
$$;
