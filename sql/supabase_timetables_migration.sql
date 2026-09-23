-- ============================================================
-- IPISB Platform — Timetables Migration
-- Official weekly "Emploi du temps" per class (Filière), matching
-- the institute's signed template. Run this ONCE in the Supabase SQL Editor.
-- ============================================================

-- 1. Timetable header — one row per class per week
CREATE TABLE IF NOT EXISTS timetables (
  id            uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  class_id      uuid        NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
  academic_year text        NOT NULL,               -- e.g. "2025/2026"
  week_start    date        NOT NULL,               -- Monday
  week_end      date        NOT NULL,               -- Friday
  status        text        NOT NULL DEFAULT 'draft',  -- 'draft' | 'validated'
  validated_by  uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  validated_at  timestamptz,
  created_by    uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at    timestamptz DEFAULT now(),
  UNIQUE (class_id, week_start)
);

CREATE INDEX IF NOT EXISTS idx_timetables_class ON timetables(class_id);

ALTER TABLE timetables ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "timetables_select_all_authenticated" ON timetables;
CREATE POLICY "timetables_select_all_authenticated"
  ON timetables FOR SELECT
  USING (auth.role() = 'authenticated');

-- 2. Timetable slots — the day/hour grid cells
CREATE TABLE IF NOT EXISTS timetable_slots (
  id            uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  timetable_id  uuid        NOT NULL REFERENCES timetables(id) ON DELETE CASCADE,
  day_of_week   smallint    NOT NULL,               -- 0=Lundi .. 4=Vendredi
  start_time    time        NOT NULL,
  end_time      time        NOT NULL,
  subject       text,                               -- "Séquence (Matière)"; null = empty "-" cell
  slot_type     text        NOT NULL DEFAULT 'course',  -- 'course' | 'exam' (→ "Contrôle continue")
  professor_id  uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  room          text,
  created_at    timestamptz DEFAULT now(),
  CHECK (end_time > start_time),
  CHECK (day_of_week BETWEEN 0 AND 4)
);

CREATE INDEX IF NOT EXISTS idx_timetable_slots_timetable ON timetable_slots(timetable_id);
CREATE INDEX IF NOT EXISTS idx_timetable_slots_professor ON timetable_slots(professor_id);
CREATE INDEX IF NOT EXISTS idx_timetable_slots_room ON timetable_slots(room);

ALTER TABLE timetable_slots ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "timetable_slots_select_all_authenticated" ON timetable_slots;
CREATE POLICY "timetable_slots_select_all_authenticated"
  ON timetable_slots FOR SELECT
  USING (auth.role() = 'authenticated');
