-- ============================================================
-- IPISB Platform — Rooms (Salles) Migration
-- Real, admin-managed room records (capacity, building/floor, équipement) —
-- until now `timetable_slots.room` was free text with no master record.
-- Matched to timetable occupancy by name (case/whitespace-insensitive) in
-- GET /api/timetables/rooms/usage.
-- ============================================================

CREATE TABLE IF NOT EXISTS rooms (
  id          uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  name        text        NOT NULL UNIQUE,
  capacity    integer,
  building    text,
  floor       text,
  equipment   text,
  notes       text,
  created_by  uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at  timestamptz DEFAULT now(),
  updated_at  timestamptz DEFAULT now()
);

ALTER TABLE rooms ENABLE ROW LEVEL SECURITY;
-- No policies: only the backend (service key) reads/writes — same pattern
-- as student_details/student_roster (admin-only via API-level checks).
