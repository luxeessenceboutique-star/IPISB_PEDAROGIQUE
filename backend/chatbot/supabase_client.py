"""
Supabase client for chat session persistence and document storage.

Required Supabase table (run once in the SQL editor):

    CREATE TABLE chat_sessions (
      id TEXT PRIMARY KEY,
      phone TEXT,
      stage TEXT DEFAULT 'chat',
      slots JSONB DEFAULT '{}',
      docs JSONB DEFAULT '{}',
      messages JSONB DEFAULT '[]',
      airtable_record_id TEXT,
      created_at TIMESTAMPTZ DEFAULT now(),
      updated_at TIMESTAMPTZ DEFAULT now()
    );

    -- Index for fast phone lookups
    CREATE INDEX idx_chat_sessions_phone ON chat_sessions (phone);

    -- Auto-update updated_at on every row change
    CREATE OR REPLACE FUNCTION update_updated_at_column()
    RETURNS TRIGGER AS $$
    BEGIN NEW.updated_at = now(); RETURN NEW; END;
    $$ LANGUAGE plpgsql;

    CREATE TRIGGER set_updated_at
    BEFORE UPDATE ON chat_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

Required Supabase Storage:
    Create a public bucket named "registration-docs"
    (Dashboard → Storage → New Bucket → name: registration-docs → Public: ON)
"""

import os
import logging
from typing import Any

log = logging.getLogger(__name__)

SUPABASE_URL         = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
BUCKET_NAME          = "registration-docs"


def _client():
    """Return a Supabase client instance (lazy, one per call is fine for serverless)."""
    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def save_session(
    session_id: str,
    phone: str,
    messages: list[dict],
    slots: dict,
    stage: str,
    docs: dict | None = None,
    airtable_record_id: str | None = None,
) -> bool:
    """
    Upsert a chat session row.  Returns True on success, False on error.

    docs format: { "cin": {"url": "...", "filename": "..."}, ... }
    """
    try:
        client = _client()
        payload: dict[str, Any] = {
            "id":       session_id,
            "phone":    phone or "",
            "stage":    stage,
            "slots":    slots,
            "messages": messages,
        }
        if docs is not None:
            payload["docs"] = docs
        if airtable_record_id is not None:
            payload["airtable_record_id"] = airtable_record_id

        client.table("chat_sessions").upsert(payload).execute()
        log.info("Session saved: %s (stage=%s)", session_id, stage)
        return True
    except Exception as e:
        log.warning("save_session failed: %s", e)
        return False


def get_session(session_id: str) -> dict | None:
    """
    Retrieve a session by its ID.
    Returns the row dict or None if not found.
    """
    try:
        client = _client()
        result = (
            client.table("chat_sessions")
            .select("*")
            .eq("id", session_id)
            .single()
            .execute()
        )
        return result.data
    except Exception as e:
        log.warning("get_session(%s) failed: %s", session_id, e)
        return None


def get_session_by_phone(phone: str) -> dict | None:
    """
    Find the most recent session for a given phone number.
    Returns the row dict or None.
    """
    try:
        client = _client()
        result = (
            client.table("chat_sessions")
            .select("*")
            .eq("phone", phone)
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = result.data
        return rows[0] if rows else None
    except Exception as e:
        log.warning("get_session_by_phone(%s) failed: %s", phone, e)
        return None


def upload_document(
    file_bytes: bytes,
    filename: str,
    session_id: str,
) -> str:
    """
    Upload a file to Supabase Storage bucket 'registration-docs'.

    The object path is: <session_id>/<filename>
    Returns the public URL of the uploaded file.
    Raises RuntimeError on failure.
    """
    try:
        client = _client()
        storage_path = f"{session_id}/{filename}"

        # Infer content-type from extension
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        _mime_map = {
            "pdf":  "application/pdf",
            "jpg":  "image/jpeg",
            "jpeg": "image/jpeg",
            "png":  "image/png",
            "gif":  "image/gif",
            "webp": "image/webp",
            "doc":  "application/msword",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        content_type = _mime_map.get(ext, "application/octet-stream")

        # Remove any existing file at that path before uploading
        try:
            client.storage.from_(BUCKET_NAME).remove([storage_path])
        except Exception:
            pass  # File may not exist yet — that's fine

        client.storage.from_(BUCKET_NAME).upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": content_type},
        )

        public_url: str = client.storage.from_(BUCKET_NAME).get_public_url(storage_path)
        log.info("Uploaded %s to Supabase Storage: %s", filename, public_url)
        return public_url

    except Exception as e:
        log.error("upload_document failed for %s: %s", filename, e)
        raise RuntimeError(f"Storage upload failed: {e}") from e
