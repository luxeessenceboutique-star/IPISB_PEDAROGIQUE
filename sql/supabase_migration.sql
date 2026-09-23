-- ============================================================
-- IPISB Platform — Hierarchical Accounts Migration
-- Run this ONCE in the Supabase SQL Editor
-- ============================================================

-- 1. Add created_by column to profiles (tracks which admin/professor created this account)
ALTER TABLE profiles
  ADD COLUMN IF NOT EXISTS created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL;

-- 2. Index for fast professor→student lookups
CREATE INDEX IF NOT EXISTS idx_profiles_created_by ON profiles(created_by);

-- 3. Ensure user_roles has a unique constraint to allow safe upsert
ALTER TABLE user_roles
  DROP CONSTRAINT IF EXISTS user_roles_user_id_role_key;
ALTER TABLE user_roles
  ADD CONSTRAINT user_roles_user_id_role_key UNIQUE (user_id, role);

-- 4. RLS policies — only allow the backend service key to insert/update/delete
--    (The backend already uses the service key which bypasses RLS,
--     but lock down anon/authenticated direct access for safety)

-- profiles: authenticated users can read their own profile only
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "profiles_select_own" ON profiles;
CREATE POLICY "profiles_select_own"
  ON profiles FOR SELECT
  USING (auth.uid() = id);

-- user_roles: authenticated users can read their own roles only
ALTER TABLE user_roles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "user_roles_select_own" ON user_roles;
CREATE POLICY "user_roles_select_own"
  ON user_roles FOR SELECT
  USING (auth.uid() = user_id);

-- ============================================================
-- After running this migration, run from the backend directory:
--   python seed_admins.py
-- to create the two IPISB administrator accounts.
-- ============================================================
