-- ============================================================
-- IPISB Platform — Login Approval Gate Migration
-- Run this ONCE in the Supabase SQL Editor.
--
-- Admin/professor accounts must be approved by email (one-click link)
-- before they can access the platform: on first login, and again after
-- 30 days of inactivity. Existing admin/professor accounts are
-- pre-approved below so nobody is locked out the moment this ships.
-- ============================================================

ALTER TABLE profiles
  ADD COLUMN IF NOT EXISTS login_approved_at timestamptz,
  ADD COLUMN IF NOT EXISTS last_login_at timestamptz;

CREATE TABLE IF NOT EXISTS login_approval_requests (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  token text NOT NULL UNIQUE,
  reason text NOT NULL DEFAULT 'first_login', -- 'first_login' | 'inactivity'
  status text NOT NULL DEFAULT 'pending',     -- 'pending' | 'approved' | 'expired'
  created_at timestamptz NOT NULL DEFAULT now(),
  approved_at timestamptz,
  expires_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_login_approval_requests_user ON login_approval_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_login_approval_requests_token ON login_approval_requests(token);

ALTER TABLE login_approval_requests ENABLE ROW LEVEL SECURITY;
-- No policies added on purpose — this table is only ever touched by the
-- backend via the service-role key (which bypasses RLS). Default-deny
-- keeps it unreachable from the anon/authenticated Supabase clients.

-- Some admin/professor auth accounts predate the profiles row being created
-- at signup time (found one in production: admin@ipisb.ma). Backfill a
-- minimal profiles row for those first, so the pre-approval UPDATE below
-- doesn't silently skip them and leave them gated on their next login.
INSERT INTO profiles (id, email, full_name, created_at)
SELECT u.id, u.email, COALESCE(u.raw_user_meta_data->>'full_name', u.email), now()
FROM auth.users u
JOIN user_roles ur ON ur.user_id = u.id
WHERE ur.role IN ('admin', 'professor')
ON CONFLICT (id) DO NOTHING;

-- Pre-approve every existing admin/professor account so they keep working
-- immediately; only new accounts (or 30+ days inactive ones going forward)
-- will hit the approval gate.
UPDATE profiles
SET login_approved_at = now(), last_login_at = now()
WHERE id IN (
  SELECT user_id FROM user_roles WHERE role IN ('admin', 'professor')
);
