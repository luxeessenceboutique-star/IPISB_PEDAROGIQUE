-- ============================================================
-- IPISB Platform — Document Templates Migration
-- Run this ONCE in the Supabase SQL Editor
-- ============================================================

-- Admin-uploaded example documents (docx/pdf/image). On upload, the backend
-- runs an LLM pass once to detect which spans are student-specific ("fields")
-- and stores that map here. Every later generation reuses the stored field
-- map — no LLM call needed after the first upload.
CREATE TABLE IF NOT EXISTS document_templates (
  id          uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  name        text        NOT NULL,
  file_path   text        NOT NULL,           -- path within the "document-templates" bucket
  file_kind   text        NOT NULL,           -- 'docx' | 'pdf' | 'image'
  content_type text       NOT NULL,           -- original MIME type, needed to re-open the source file
  fields      jsonb       NOT NULL DEFAULT '[]', -- detected field map, see backend/utils/templates.py
  created_by  uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at  timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_document_templates_created ON document_templates(created_at DESC);

ALTER TABLE document_templates ENABLE ROW LEVEL SECURITY;
-- No SELECT policy: only the backend (service key) reads/writes, same as audit_log.

INSERT INTO storage.buckets (id, name, public)
VALUES ('document-templates', 'document-templates', false)
ON CONFLICT (id) DO NOTHING;

-- Link generated documents back to the template that produced them.
ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS template_id uuid REFERENCES document_templates(id) ON DELETE SET NULL;

-- ============================================================
-- Backend runs on the service key and bypasses RLS everywhere above;
-- these policies only lock down direct anon/authenticated client access.
-- ============================================================
