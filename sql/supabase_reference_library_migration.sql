-- ============================================================
-- IPISB Platform — Reference Document Library
-- Run this ONCE in the Supabase SQL Editor
--
-- A staff-facing storage bucket for official reference documents
-- (CDC, fiches descriptives, programmes de formation, règlements…) so
-- admins/professors can consult them from the platform instead of a
-- shared drive. Mirrors the existing "course-materials" bucket pattern
-- (public bucket, files organized by folder prefix, no DB table needed —
-- see backend/routers/resources.py for the same approach per-course).
-- ============================================================

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'reference-library',
  'reference-library',
  true,
  52428800,  -- 50 MB limit (some CDC/programme PDFs are large)
  ARRAY[
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'image/jpeg',
    'image/png'
  ]
)
ON CONFLICT (id) DO NOTHING;

-- Service role (backend) has full access
CREATE POLICY "reference_library_service_role_all"
  ON storage.objects FOR ALL TO service_role
  USING (bucket_id = 'reference-library') WITH CHECK (bucket_id = 'reference-library');

-- Authenticated users can read (bucket is also public, this just covers
-- the authenticated-client read path the same way course-materials does)
CREATE POLICY "reference_library_select_authenticated"
  ON storage.objects FOR SELECT TO authenticated
  USING (bucket_id = 'reference-library');
