-- ============================================================
-- IPISB Platform — Submissions Storage Bucket
-- Run this ONCE in the Supabase SQL Editor
-- ============================================================

-- 1. Create the submissions storage bucket (public read so file URLs work)
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'submissions',
  'submissions',
  true,
  26214400,  -- 25 MB limit
  ARRAY[
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'image/jpeg',
    'image/png',
    'image/gif',
    'image/webp',
    'text/plain',
    'application/zip',
    'application/x-rar-compressed'
  ]
)
ON CONFLICT (id) DO NOTHING;

-- 2. RLS policies for the bucket

-- Authenticated users can upload to their own folder (path starts with their user ID)
CREATE POLICY "submissions_insert_own"
  ON storage.objects FOR INSERT
  WITH CHECK (
    bucket_id = 'submissions' AND
    auth.uid()::text = (storage.foldername(name))[1]
  );

-- Authenticated users can update their own files
CREATE POLICY "submissions_update_own"
  ON storage.objects FOR UPDATE
  USING (
    bucket_id = 'submissions' AND
    auth.uid()::text = (storage.foldername(name))[1]
  );

-- Public read (bucket is public, so Supabase handles this automatically)
-- But explicit SELECT policy for authenticated users too:
CREATE POLICY "submissions_select_authenticated"
  ON storage.objects FOR SELECT
  USING (
    bucket_id = 'submissions' AND
    auth.role() = 'authenticated'
  );

-- Students can delete their own files
CREATE POLICY "submissions_delete_own"
  ON storage.objects FOR DELETE
  USING (
    bucket_id = 'submissions' AND
    auth.uid()::text = (storage.foldername(name))[1]
  );
