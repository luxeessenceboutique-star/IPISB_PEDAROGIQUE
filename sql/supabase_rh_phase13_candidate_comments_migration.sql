-- ============================================================
-- IPISB Platform — RH Phase 13 Migration: Candidate Comments
-- Run this ONCE in the Supabase SQL Editor.
--
-- Running comment log on candidate profiles (Recrutement → Candidats) —
-- lets HR/admins leave timestamped feedback (interview impressions, team
-- notes) distinct from the existing single "notes" field.
-- ============================================================

CREATE TABLE IF NOT EXISTS candidate_comments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  candidate_id uuid NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  author_id uuid NOT NULL REFERENCES auth.users(id),
  text text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_candidate_comments_candidate ON candidate_comments(candidate_id);

ALTER TABLE candidate_comments ENABLE ROW LEVEL SECURITY;
-- No policies added on purpose — this table is only ever touched by the
-- backend via the service-role key (which bypasses RLS), same as the rest
-- of the RH module.
