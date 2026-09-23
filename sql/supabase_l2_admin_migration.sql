-- ============================================================
-- IPISB Platform — L2 Gestion Administrative Migration
-- Run this ONCE in the Supabase SQL Editor
-- ============================================================

-- 1. Students registry extension (statut, photo — filière/promotion are
--    already modelled via `classes`, so we don't duplicate that concept)
ALTER TABLE profiles
  ADD COLUMN IF NOT EXISTS statut     text NOT NULL DEFAULT 'actif',
  ADD COLUMN IF NOT EXISTS photo_url  text;

-- Fast full-text search on name/email (<150ms target)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_profiles_full_name_trgm ON profiles USING gin (full_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_profiles_email_trgm     ON profiles USING gin (email gin_trgm_ops);

-- ============================================================
-- 2. Documents — attestations/certificats with QR verification
-- ============================================================
CREATE TABLE IF NOT EXISTS documents (
  id                uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  type              text        NOT NULL,               -- 'attestation_scolarite' | 'certificat' | 'convocation'
  student_id        uuid        REFERENCES auth.users(id) ON DELETE CASCADE,
  file_path         text        NOT NULL,                -- path within the "documents" storage bucket
  statut            text        NOT NULL DEFAULT 'valide', -- 'valide' | 'revoque'
  verification_code text        NOT NULL UNIQUE,
  generated_by      uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at        timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_documents_student ON documents(student_id);
CREATE INDEX IF NOT EXISTS idx_documents_code    ON documents(verification_code);

ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "documents_select_own" ON documents;
CREATE POLICY "documents_select_own"
  ON documents FOR SELECT
  USING (auth.uid() = student_id OR auth.uid() = generated_by);

-- Private bucket: the PDF itself is only ever served through backend-issued
-- signed URLs. The public /verify/{code} endpoint returns authenticity JSON,
-- never the file, so no public bucket policy is needed.
INSERT INTO storage.buckets (id, name, public)
VALUES ('documents', 'documents', false)
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 3. Schedules — weekly timetable with room/instructor conflict detection
-- ============================================================
CREATE TABLE IF NOT EXISTS schedules (
  id             uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  class_id       uuid        REFERENCES classes(id) ON DELETE CASCADE,
  professor_id   uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  room           text        NOT NULL,
  title          text,
  start_time     timestamptz NOT NULL,
  end_time       timestamptz NOT NULL,
  recurrence     text        NOT NULL DEFAULT 'once',   -- 'once' | 'weekly'
  created_by     uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at     timestamptz DEFAULT now(),
  CHECK (end_time > start_time)
);

CREATE INDEX IF NOT EXISTS idx_schedules_room ON schedules(room);
CREATE INDEX IF NOT EXISTS idx_schedules_professor ON schedules(professor_id);
CREATE INDEX IF NOT EXISTS idx_schedules_class ON schedules(class_id);

ALTER TABLE schedules ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "schedules_select_all_authenticated" ON schedules;
CREATE POLICY "schedules_select_all_authenticated"
  ON schedules FOR SELECT
  USING (auth.role() = 'authenticated');

-- ============================================================
-- 4. Internal announcements (role-targeted)
-- ============================================================
CREATE TABLE IF NOT EXISTS announcements_internal (
  id             uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  titre          text        NOT NULL,
  corps          text        NOT NULL,
  audience_roles text[]      NOT NULL DEFAULT '{}',
  created_by     uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at     timestamptz DEFAULT now()
);

ALTER TABLE announcements_internal ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "announcements_select_all_authenticated" ON announcements_internal;
CREATE POLICY "announcements_select_all_authenticated"
  ON announcements_internal FOR SELECT
  USING (auth.role() = 'authenticated');

-- ============================================================
-- 5. Audit log — transversal, reused by every admin-mutating action
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_log (
  id          uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id     uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  action      text        NOT NULL,       -- e.g. 'document.generate', 'schedule.create'
  entity_type text        NOT NULL,       -- e.g. 'document', 'schedule'
  entity_id   text,
  meta        jsonb,
  created_at  timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON audit_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at DESC);

ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
-- No SELECT policy: only the backend (service key) reads/writes audit_log.

-- ============================================================
-- Backend runs on the service key and bypasses RLS everywhere above;
-- these policies only lock down direct anon/authenticated client access.
-- ============================================================
